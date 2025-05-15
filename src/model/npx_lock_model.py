# Neo-Panamax (NPX) lock model
# M. G. Castrellon | 9 May 2025

# Required libraries
import logging
import numpy as np
import pandas as pd
from collections import namedtuple
from datetime import datetime, timedelta

# Local packages
from io_data_classes import *
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

        # Initialize lock head data class
        self.lock_heads = {}
        for lh in [f'LH{x}' for x in range(1, 5)]:
                self.lock_heads[lh] = LockHead(**design_specs.lock_head_params[lh])

        # Initialize data object to store operation outputs
        self.freshwater_consumed = FreshwaterConsumed()
        self.salt_mass_load = SaltMassLoad()


    def set_initial_conditions(self, H_lake, H_ocean, salinity,
                               direction, water_temperature):

        # Calculate initial levels based on boundary conditions
        initial_levels = self.calc_initial_levels(H_lake, H_ocean, direction)

        # Add initial conditions to the lock chambers and basins
        for cham in ['LC', 'MC', 'UC']:
            chamber_salinity = salinity[cham].chamber
            basin_salinity = salinity[cham].basins

            self.chambers[cham].add_initial_conditions(
                H0=initial_levels[cham], S0=chamber_salinity)

            for basin in ['Top', 'Int', 'Bot']:
                self.basins[cham][basin].add_initial_conditions(
                H0=initial_levels[cham[0]+'B'+basin],
                S0=basin_salinity)

        # Pass the temperature to the class attribute
        self.T = water_temperature


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
        start_dt = operation_params_list[0].dt_lockage_starts
        self.operation_start_dt = start_dt
        self.time = 0

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


    def transit(self, operation_params: OperationParameters,
                boundary_conditions: List) -> None:

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
        logger.info(f'[{self.minutes_to_datetime(self.time)}] - '
                    f'LOCKAGE ({operation_params.lockage_id} FINISHES')


    def uplockage(self, inputs: OperationParameters, bcs: List[namedtuple]) -> None:

        # 1) Drain the lock chamber to the level of the ocean (LH4)
        H_ocean, S_ocean = hf.extract_boundary_conditions(
            df=bcs, time_stamp=inputs.dt_lockage_starts, location='ocean')

        if self.chambers['LC'].get_current_level() > H_ocean:
            drain_time = 12  # Assumed time it takes for the lower chamber to drain (minutes)
            equalization_start_time = self.time - drain_time
            self.chambers['LC'].record_current_status(time=equalization_start_time)
            logger.info(f'[{self.minutes_to_datetime(equalization_start_time)}] - LH4 Equalization Starts')

            if inputs.wsb_flag.lock_head_4:
                self.drain_chamber_to_wsb(
                    chamber='LC', time=equalization_start_time, eq_time=drain_time)

            self.chambers['LC'].drain_chamber(H_final=H_ocean, time=self.time)
            logger.info(f'[{self.minutes_to_datetime(self.time)}] - LH4 Equalization Finishes')

        else:
            logger.info(f'[{self.minutes_to_datetime(self.time)}] - LH4 Already Equalized')

        ## 2) Gates at LH4 open, salinity enters from the ocean and ship enters the lock
        t_transit = inputs.transit_time.lock_head_4  # minutes
        self.time += t_transit  # Update time after transit
        V_ex_ocean = self.exchange_with_boundary(S_ocean=S_ocean, t_open=t_transit)
        self.chambers['LC'].ship_enters(V_lhs=V_ex_ocean, S_lhs=S_ocean, time=self.time)

        ## 3) Equalization and transit between LC and MC


        ## 4) Equalization and transit between MC and UC


        ## 5) Lift the ship to the level of the lake (LH1)
        time_stamp = self.minutes_to_datetime(self.time)
        H_lake, S_lake = hf.extract_boundary_conditions(df=bcs, time_stamp=time_stamp, location='lake')

        if self.chambers['UC'].get_current_level() < H_lake:
            logger.info(f'[{time_stamp}] - LH1 Equalization Starts')

            self.chambers['UC'].record_current_status(t_min=self.time)
            eq_time = inputs.equalization_time.upper_chamber

            if inputs.wsb_flag.lock_head_1:
                self.fill_chamber_from_wsb(chamber='UC', time=self.time, eq_time=eq_time)

            ## Water level difference between lake and upper chamber after using the basins
            dh = H_lake - self.chambers['UC'].get_current_level()
            logger.debug(f'{" "*24} - Water level difference with lake: {dh:0.2f} m')

            self.time += eq_time  # Update time after filling the chamber
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, t_min=time_stamp)
            logger.info(f'[{self.minutes_to_datetime(self.time)}] - LH1 Equalization Finishes')
            self.record_freshwater_consumed(level_difference=dh, time=self.time)

        else:
            logger.info(f'[{time_stamp}] - LH1 Already Equalized')
            self.record_freshwater_consumed(level_difference=0, time=self.time)

        ## 6) Gates at LH1 open, salt mass enters the lake and ship leaves the lock
        t_transit = inputs.transit_time.lock_head_1
        self.time = self.time + t_transit  # minutes
        V_ex_lake = super().exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_leaves(V_rhs=V_ex_lake, S_rhs=S_lake, t_min=time_stamp)

        # S_chamber = self.chambers['UC'].salinity[-1]
        # super().calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='up', ts=time_stamp)

        self.record_operation_outputs

    def downlockage(self, inputs: OperationParameters, bcs: pd.DataFrame) -> None:
        pass


    def drain_chamber_to_wsb(self, chamber: str, time: int, eq_time: int) -> None:
        for basin in ['Top', 'Int', 'Bot']:
            logger.debug(f'[{self.minutes_to_datetime(time)}] - {chamber} started draining to {basin} basin')

            self.basins[chamber][basin].record_current_status(time=time)
            time = time + eq_time / 4  # Assumed time for equalization

            Hf = self.basin_chamber_final_level(basin=basin, chamber=chamber)

            S_lift = self.chambers[chamber].get_current_salinity()
            self.chambers[chamber].drain_chamber(H_final=Hf, time=time)
            self.basins[chamber][basin].fill_basin(H_final=Hf, S_lift=S_lift, time=time)

            logger.debug(f'[{self.minutes_to_datetime(time)}] - {chamber} finished draining to {basin} basin')

            # try:
            #     self.check_reservoir_limits(Hf, chamber, ts, basin)
            # except ReservoirOverflowError:
            #     continue


    def fill_chamber_from_wsb(self, chamber: str, time: int, eq_time: int) -> None:
        for basin in ['Bot', 'Int', 'Top']:
            logger.debug(f'[{self.minutes_to_datetime(time)}] - {chamber} started filling from {basin} basin')

            self.basins[chamber][basin].record_current_status(time=time)
            time = time + eq_time / 4  # Assumed time for equalization

            Hf = self.basin_chamber_final_level(basin=basin, chamber=chamber)

            S_lift = self.basins[chamber][basin].get_current_salinity()
            self.basins[chamber][basin].drain_basin(H_final=Hf, time=time)
            self.chambers[chamber].fill_chamber(H_final=Hf, S_lift=S_lift, time=time)

            logger.debug(f'[{self.minutes_to_datetime(time)}] - {chamber} finished filling from {basin} basin')

            # try:
            #     self.check_reservoir_limits(Hf, chamber, ts, basin)
            # except ReservoirOverflowError:
            #     continue


    def basin_chamber_final_level(self, basin: str, chamber: str) -> float:
        A1 = self.chambers[chamber].area
        H1 = self.chambers[chamber].get_current_level()

        A2 = self.basins[chamber][basin].area
        H2 = self.basins[chamber][basin].get_current_level()

        Hf = hd.calc_equalization_level(A1, A2, H1, H2)

        logger.debug(f'{" " * 24}{chamber} initial level = {H1:.2f} m')
        logger.debug(f'{" " * 24}{chamber[0]}B{basin} initial level = {H2:.2f} m')

        return Hf


    def calc_lock_exchange_coefficient(self, H, S_lhs, S_rhs, z_sill, t_open, eta=1.0) -> float:

        # Calculate density of water in left and right of lock gate
        rho_lhs = hd.Rho_from_PSU(Salt=S_lhs, Temp=self.T)
        rho_rhs = hd.Rho_from_PSU(Salt=S_rhs, Temp=self.T)

        # Sort densities
        rho1, rho2 = (rho_rhs, rho_lhs) \
            if rho_lhs > rho_rhs else (rho_lhs, rho_rhs)

        # Calculate the exchange coefficient
        Eff = hd.exchange_coefficient(
            rho1=rho1, rho2=rho2, H=(H - z_sill),
            L=self.chambers['MC'].length,
            tOpen=t_open, eta=eta
        )

        return Eff


    def record_freshwater_consumed(self, level_difference: float, time: int):
        # Recording amount of freshwater used in million cubic meters (hm3)
        volume = level_difference * self.chambers['UC'].area
        self.operation_outputs.date_time = self.minutes_to_datetime(time)


    def turnaround(self, bcs, new_direction, t_init):
        pass
