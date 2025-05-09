# Neo-Panamax (NPX) lock model
# M. G. Castrellon | 9 May 2025

# Required libraries
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Local packages
from data_classes import *
from lock_elements import *
from custom_exceptions import *
import src.utilities.hydrodynamics as hd
import src.utilities.helper_functions as hf

# Get logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Setup console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter("{levelname}: {message}", style="{"))
logger.addHandler(console_handler)

# Setup file handler
file_handler = logging.FileHandler("app.log", mode="w", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("{levelname}: {message}", style="{"))
file_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)


# Define model class
class NeoPanamaxLock:

    def __init__(self, design_specs: LockDesignSpecifications):

        # Initialize lock chamber objects
        self.chambers = {}
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham] = LockChamber(
                length=design_specs.chamber_dimensions['L'],
                width=design_specs.chamber_dimensions['W'],
                z_bottom=design_specs.chamber_z_elevations[cham][0],
                z_top=design_specs.chamber_z_elevations[cham][1],
                H_min=design_specs.chamber_operating_limits[cham][0],
                H_max=design_specs.chamber_operating_limits[cham][1]
            )

        # Initialize water saving basin objects
        self.basins = {'LC': {}, 'MC': {}, 'UC': {}}
        for cham in self.basins.keys():
            for basin in ['Top', 'Int', 'Bot']:
                self.basins[cham][basin] = WaterSavingBasin(
                    length=design_specs.wsb_dimensions['L'],
                    width=design_specs.wsb_dimensions['W'],
                    z_bottom=design_specs.wsb_z_elevations[cham][0],
                    z_top=design_specs.wsb_z_elevations[cham][1],
                    H_min=design_specs.wsb_operating_limits[cham][0],
                    H_max=design_specs.wsb_operating_limits[cham][1]
                )

        # Create attributes for lock heads
        self.lock_heads = {'Z': design_specs.z_lock_head_sills}
        self.lock_heads['Chambers'] = {
            'LH1': ['UC'],
            'LH2': ['MC', 'UC'],
            'LH3': ['LC', 'MC'],
            'LH4': ['LC']
        }

        # Initialize data object to store operation outputs
        self.operation_outputs = OperationOutputs()


    def set_initial_conditions(self, H_lake, H_ocean, initial_salinity,
                               direction, ts_lock_operation_start,
                               water_temperature=28):

        initial_levels = self.calc_initial_levels(H_lake, H_ocean, direction)

        # Add initial conditions to the lock chambers and basins
        for cham in ['LC', 'MC', 'UC']:
            chamber_salinity = initial_salinity[cham]
            basin_salinity = initial_salinity[cham[0]+'B']

            self.chambers[cham].add_initial_conditions(
                H0=initial_levels[cham], S0=chamber_salinity)

            for basin in ['Top', 'Int', 'Bot']:
                self.basins[cham][basin].add_initial_conditions(
                H0=initial_levels[cham[0]+'B'+basin],
                S0=basin_salinity)

        # Pass the temperature to the class attribute
        self.T = water_temperature

        # Initialize time counter for minutes elapsed since start of the operation
        self.operation_start_dt = ts_lock_operation_start
        self.t_min = 0


    def calc_initial_levels(self, H_lake, H_ocean, direction):
        """
        For uplockage, the lower chamber is at the level of the ocean (low level)
        and the rest of the chambers are at their higher operational levels.
        For downlockage, the upper chamber is at the level of the lake (high level)
        and the rest of the chambers are at their lower operational levels.
        The WSBs start at the opposite level of the related chamber.
        """
        initial_levels = {}

        chamber_operational_levels = self.calc_chamber_operational_levels(H_lake, H_ocean)
        wsb_operational_levels = self.calc_wsb_operational_levels(chamber_operational_levels)

        levels_dict = {'up': {'LC': 0, 'MC': 1, 'UC': 1},
                       'down': {'LC': 0, 'MC': 0, 'UC': 1}}

        for cham, c_level in levels_dict[direction].items():
            initial_levels[cham] = chamber_operational_levels[cham][c_level]

            b_level = 1 - c_level  # Level of WSB is opposite of related chamber.

            for basin in ['Top', 'Int', 'Bot']:
                my_key = f'{cham[0]}B{basin}'
                initial_levels[my_key] = wsb_operational_levels[my_key][b_level]

        return initial_levels


    def calc_chamber_operational_levels(self, H_lake, H_ocean):
        """
        Calculates the operational levels of the lock chambers based on the current
        levels of the lake and the ocean.
        """

        Au = self.chambers['UC'].area
        Am = self.chambers['MC'].area
        Al = self.chambers['LC'].area

        denominator = ((Am + Al)*(Au + Am)/Am) - Am
        numerator = H_ocean*Al + (Am + Al)*H_lake*Au/Am

        uc_high = H_lake
        uc_low = numerator/denominator

        mc_high = uc_low
        mc_low = ((Au + Am)/Am)*mc_high - H_lake*Au/Am

        lc_high = mc_low
        lc_low = H_ocean

        chamber_operational_levels = {
            'UC': (uc_low, uc_high),
            'MC': (mc_low, mc_high),
            'LC': (lc_low, lc_high)
        }

        return chamber_operational_levels


    def calc_wsb_operational_levels(self, chamber_operational_levels):
        """
        Calculates the operational levels of the WSBs based on the operational
        levels of the lock chambers.
        """
        wsb_operational_levels = {}
        fractions = {'Top': (3, 4), 'Int': (2, 3), 'Bot': (1, 2)}

        for cham in self.basins.keys():
            c_low = chamber_operational_levels[cham][0]
            c_high = chamber_operational_levels[cham][1]

            for basin in ['Top', 'Int', 'Bot']:
                frac_low, frac_high = fractions[basin]
                b_low = c_low + (frac_low / 5) * (c_high - c_low)
                b_high = c_low + (frac_high / 5) * (c_high - c_low)

                wsb_operational_levels[f'{cham[0]}B{basin}'] = (b_low, b_high)

        return wsb_operational_levels


    def operate(self, operation_params_list, boundary_conditions):
        """
        Main method that performs the lock operation. This functions controls whether a transit is performed
        or if a turnaround is needed (in case two consecutive transits are in opposite directions).
        """
        for i in range(len(operation_params_list)):
            current_operation = OperationParameters(**operation_params_list[i])
            current_direction = current_operation.direction

            self.transit(operation_params=current_operation, boundary_conditions=boundary_conditions)

            if i != len(operation_params_list):
                next_operation = OperationParameters(**operation_params_list[i + 1])
                next_direction = next_operation.direction
                dt = next_operation.dt_lockage_starts

                if current_direction != next_direction:
                    if next_direction != 'dummy':
                        t_turnaround = 30 # Assumed time it takes to perform a turnaround (minutes)
                        t_elapsed = self.minutes_since_operation_started(dt_string=dt) - t_turnaround
                        self.turnaround(bcs=boundary_conditions, new_direction=next_direction, t_init=t_elapsed)


    def minutes_since_operation_started(self, dt_string, time_format='%Y-%m-%d %H:%M:%S'):
        """
        Calculate the elapsed time in minutes between the start of the lock operation and the
        start of an individual lockage. Both date time stamps must be in the same time format,
        which can be specified by the user.
        """
        date1 = datetime.strptime(self.operation_start_dt, time_format)
        date2 = datetime.strptime(dt_string, time_format)
        elapsed_seconds = (date2 - date1).total_seconds()
        elapsed_minutes = elapsed_seconds / 60
        return elapsed_minutes


    def minutes_to_datetime(self, t_min):
        """
        Converts elapsed minutes to a datetime object, assuming
        the elapsed time is in minutes since the start of the operation.
        """
        initial_dt_object = datetime.fromisoformat(self.operation_start_dt)
        new_dt_object = initial_dt_object + timedelta(seconds=t_min*60)
        return new_dt_object.strftime("%Y-%m-%d %H:%M:%S")


    def transit(self, operation_params, boundary_conditions):

        # Log start of transit
        logger.info(
            f'[{operation_params.dt_lockage_starts}] - LOCKAGE ({operation_params.lockage_id} '
            f'({operation_params.direction.upper()}) STARTS')

        logger.debug(f'{" "*24}Use of water saving basins: {operation_params.wsb_flag}')

        # Perform transit based on the direction
        if operation_params.direction == 'up':
            self.uplockage(inputs=operation_params, bcs=boundary_conditions)
        elif operation_params.direction == 'down':
            self.downlockage(inputs=operation_params, bcs=boundary_conditions)
        elif operation_params.direction == 'dummy':
            self.downlockage(inputs=operation_params, bcs=boundary_conditions)
        else:
            raise ValueError("Direction must be either 'up', 'down' or 'dummy'.")

        # Log end of transit
        logger.info(f'[{self.minutes_to_datetime(self.t_min)}] - '
                    f'LOCKAGE ({operation_params.lockage_id} FINISHES')


    def uplockage(self, inputs, bcs):

        # 1) Drain the lock chamber to the level of the ocean (LH4)
        H_ocean, S_ocean = hf.extract_boundary_conditions(
            df=bcs, time_stamp=inputs.dt_lockage_starts, location='ocean')

        if self.chambers['LC'].get_current_level() > H_ocean:
            drain_time = 12  # Assumed time it takes for the lower chamber to drain (minutes)
            equalization_start_time = self.t_min - drain_time
            self.chambers['LC'].record_current_status(t_min=equalization_start_time)
            logger.info(f'[{self.minutes_to_datetime(equalization_start_time)}] - LH4 Equalization Starts')

            if inputs.wsb_flag:
                self.drain_chamber_to_wsb(chamber='LC', ts=time0, teq=tdrain)

            self.chambers['LC'].drain_chamber(H_final=H_ocean, t_min=initial_time_stamp)
            logger.info(f'[{self.minutes_to_datetime(initial_time_stamp)}] - LH4 Equalization Finishes')

        else:
            logger.info(f'[{self.minutes_to_datetime(self.t_min)}] - LH4 Already Equalized')

        ## 2) Gates at LH4 open, salinity enters from the ocean and ship enters the lock
        t_transit = self.tGateOpen['LH4']  # minutes
        time_stamp = initial_time_stamp + t_transit  # minutes
        V_ex_ocean = self.exchange_with_boundary(S_ocean=S_ocean)
        self.chambers['LC'].ship_enters(V_lhs=V_ex_ocean, S_lhs=S_ocean, t_min=time_stamp)

        ## 3) Equalization and transit between LC and MC
        teq = self.eqTime['LC']  # minutes
        time_stamp = self.equalize_and_cross(
            lock_head='LH3', direction='up', wsb_use=wsb_use, init_time=time_stamp, teq=teq)

        ## 4) Equalization and transit between MC and UC
        teq = self.eqTime['MC']  # minutes
        time_stamp = self.equalize_and_cross(
            lock_head='LH2', direction='up', wsb_use=wsb_use, init_time=time_stamp, teq=teq)

        ## 5) Lift the ship to the level of the lake (LH1)
        if self.chambers['UC'].get_current_level() < H_lake:
            self.chambers['UC'].record_current_status(t_min=time_stamp)
            logger.info(f'[{self.minutes_to_datetime(time_stamp)}] - LH1 Equalization Starts')
            ## 5.1) Fill water from WSB (if needed)
            if sum(wsb_use['UC'].values()) > 0:
                self.fill_chamber_from_wsb(chamber='UC', ts=time_stamp, teq=self.eqTime['UC'])
            ## 5.2) Finish filling chamber to the level of the lake
            start_luc = self.chambers['UC'].get_current_level()
            wldiff = H_lake - start_luc  # Difference in water level in meters
            logger.debug(f'[{self.minutes_to_datetime(time_stamp)}] - Difference in water level: {wldiff:0.2f} m')
            time_stamp = time_stamp + self.eqTime['UC']  # minutes to fill chamber
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, t_min=time_stamp)
            logger.info(f'[{self.minutes_to_datetime(time_stamp)}] - LH1 Equalization Finishes')
            # super().record_freshwater_consumed(start_luc=start_luc, end_luc=H_lake, ts=time_stamp)
        else:
            # super().record_freshwater_consumed(start_luc=H_lake, end_luc=H_lake, ts=time_stamp)
            logger.info(f'[{self.minutes_to_datetime(time_stamp)}] - LH1 Already Equalized')

        ## 6) Gates at LH1 open, salt mass enters the lake and ship leaves the lock
        t_transit = self.tGateOpen['LH1']  # minutes
        time_stamp = time_stamp + t_transit  # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = super().exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_leaves(V_rhs=V_ex_lake, S_rhs=S_lake, t_min=time_stamp)
        # super().calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='up', ts=time_stamp)


    def downlockage(self, inputs, bcs):
        pass


    def turnaround(self, bcs, new_direction, t_init):
        pass
