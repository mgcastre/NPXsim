# NeoPanamaxLock class for Panama Canal's lock model
# M. G. Castrellon | 18 March 2025

# Required Libraries
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from classes.lock_elements import *
from classes.three_steps_lock import *
import utilities.hydrodynamics as hd

# Define class
class NeoPanamaxLock(ThreeStepsLock):

    def __init__(self, lock_bottom_elevs, lock_head_sills, 
                 wsb_dims, wsb_bottom_elevs):
        
        # Initialize parent class
        super().__init__(lock_length=430, lock_width=55, 
                         lock_bottom_elevs=lock_bottom_elevs, 
                         lock_head_sills=lock_head_sills)

        # Initialize water saving basin objects
        self.basins = {'LC': {}, 'MC': {}, 'UC': {}}
        for cham in self.basins.keys():
            for basin in ['Top', 'Int', 'Bot']:
                self.basins[cham][basin] = WaterSavingBasin(
                    length=wsb_dims['L'], width=wsb_dims['W'],
                    z_bottom=wsb_bottom_elevs[cham][basin],
                    S0=None, H0=None
                )
    
    @staticmethod
    def calc_wsb_operational_levels(chamber_levels):
        wsb_levels = {}
        fractions = {'Top': (3, 4), 'Int': (2, 3), 'Bot': (1, 2)}
        for chamber, (c_low, c_high) in chamber_levels.items():
            for basin, (n_low, n_high) in fractions.items():
                my_key = f'{chamber[0]}B{basin}'
                level_low = c_low + (n_low/5)*(c_high - c_low)
                level_high = c_low + (n_high/5)*(c_high - c_low)
                wsb_levels[my_key] = (level_low, level_high)
        return wsb_levels
    
    def calc_operational_levels(self, H_lake, H_ocean):
        cham_op_levels = super().calc_operational_levels(H_lake, H_ocean)
        wsb_op_levels = self.calc_wsb_operational_levels(cham_op_levels)
        return {**cham_op_levels, **wsb_op_levels}
    
    @staticmethod
    def calc_initial_levels(operational_levels, direction):
        cham_init_levels = {}
        wsb_init_levels = {}
        # For uplockage, the lower chamber is at the level of the ocean (low level)
        # and the rest of the chambers are at their higher operational levels.
        # For downlockage, the upper chamber is at the level of the lake (high level)
        # and the rest of the chambers are at their lower operational levels.
        levels_dict = {'up': {'LC': 0, 'MC': 1, 'UC': 1}, 
                       'down': {'LC': 0, 'MC': 0, 'UC': 1}}
        for cham, c_level in levels_dict[direction].items():
            cham_init_levels[cham] = operational_levels[cham][c_level]
            b_level = 1 - c_level # Level of WSB is opposite of related chamber.
            for basin in ['Top', 'Int', 'Bot']:
                my_key = f'{cham[0]}B{basin}'
                wsb_init_levels[my_key] = operational_levels[my_key][b_level]
        return {**cham_init_levels, **wsb_init_levels}
    
    def set_initial_conditions(self, boundary_conditions, salinities, 
                               direction, operation_start_dt, 
                               water_temperature=28):
        # Calculate initial operational water levels
        H_lake = boundary_conditions['H_lake']
        H_ocean = boundary_conditions['H_ocean']
        op_levels = self.calc_operational_levels(H_lake, H_ocean)
        initial_levels = self.calc_initial_levels(op_levels, direction)
        # Add initial conditions to the lock chambers
        for cham in ['LC', 'MC', 'UC']:
            chamber_salinity = salinities[cham]
            basins_salinity = salinities[cham[0]+'B']
            self.chambers[cham].add_initial_conditions(
                H0=initial_levels[cham], S0=chamber_salinity
            )
            for basin in ['Top', 'Int', 'Bot']:
                self.basins[cham][basin].add_initial_conditions(
                H0=initial_levels[cham[0]+'B'+basin],
                S0=basins_salinity
            )
        # Pass the temperature to the class attribute
        self.T = water_temperature
        # Add master initial operation start time
        self.operation_start_dt = operation_start_dt
    
    @staticmethod
    def equalization_params(reservoir_high, reservoir_low):
        A1 = reservoir_high.area
        A2 = reservoir_low.area
        H1 = reservoir_high.get_current_level()
        H2 = reservoir_low.get_current_level()
        Hf = hd.calc_equalization_level(A1, A2, H1, H2)
        return Hf
    
    def drain_chamber_to_wsb(self, chamber, ts, teq):
        for basin in ['Top', 'Int', 'Bot']:
            reservoir_high = self.chambers[chamber]
            reservoir_low = self.basins[chamber][basin]
            reservoir_low.record_current_status(ts=ts)
            Hf = self.equalization_params(reservoir_high, reservoir_low)
            ts = ts + teq/4 # Updating time stamp with 1/4 of equalization time
            S_lift = self.chambers[chamber].get_current_salinity()
            self.chambers[chamber].drain_chamber(H_final=Hf, ts=ts)
            self.basins[chamber][basin].fill_basin(H_final=Hf, S_lift=S_lift, ts=ts)
            print(f'\t{self.ts_to_datetime(ts)}: {chamber} finished draining to {basin} basin.')
    
    def fill_chamber_from_wsb(self, chamber, ts, teq):
        for basin in ['Bot', 'Int', 'Top']:
            reservoir_low = self.chambers[chamber]
            reservoir_high = self.basins[chamber][basin]
            reservoir_high.record_current_status(ts=ts)
            Hf = self.equalization_params(reservoir_high, reservoir_low)
            ts = ts + teq/4 # Updating time stamp with 1/4 of equalization time
            S_lift = self.basins[chamber][basin].get_current_salinity()
            self.basins[chamber][basin].drain_basin(H_final=Hf, ts=ts)
            self.chambers[chamber].fill_chamber(H_final=Hf, ts=ts, S_lift=S_lift)
            print(f'\t{self.ts_to_datetime(ts)}: {chamber} finished filling from {basin} basin.')
    
    def equalize_and_cross(self, lock_head, direction, wsb_use, init_time, teq):
        lower_cham, upper_cham = self.lock_heads['Chambers'][lock_head]
        self.chambers[lower_cham].record_current_status(ts=init_time)
        self.chambers[upper_cham].record_current_status(ts=init_time)
        print(f'{self.ts_to_datetime(init_time)}: {lock_head} Equalization Started')
        # 1. Drain and fill chambers with water saving basins
        if wsb_use[upper_cham]:
            self.drain_chamber_to_wsb(upper_cham, ts=init_time, teq=teq)
        if wsb_use[lower_cham]:
            self.fill_chamber_from_wsb(lower_cham, ts=init_time, teq=teq)
        # 2. Finish chamber equalization (if needed) and cross between chambers
        time_stamp = super().equalize_and_cross(lock_head, direction, init_time)
        time_eq_finished = time_stamp - teq # Time when equalization finished in minutes
        print(f'{self.ts_to_datetime(time_eq_finished)}: {lock_head} Equalization Finished')
        return time_stamp
    
    def ts_to_datetime(self, ts_minutes):
        # Convert elapsed minutes to a datetime object,
        # assuming the elapsed time is in minutes since the start of the operation
        initial_dt_object = datetime.fromisoformat(self.operation_start_dt)
        new_dt_object = initial_dt_object + timedelta(seconds=ts_minutes*60)
        return new_dt_object.strftime("%Y-%m-%d %H:%M:%S")
    
    def operate(self, operation_params, boundary_conditions):
        print(f'Starting lock operations at {self.operation_start_dt}')
        for i in range(len(operation_params)):
            this_transit = operation_params[i]
            self.transit(this_transit, boundary_conditions[i])
            try:
                next_transit = operation_params[i+1]
            except IndexError:
                break
            if this_transit['Direction'] != next_transit['Direction']:
                ts = self.calc_elapsed_minutes(next_transit['TS_LocksReady']) - 30
                print(f'\n{self.ts_to_datetime(ts)}: TURNAROUND')
                self.turnaround(boundary_conditions[i+1], next_transit['Direction'], tinit=ts)
    
    def transit(self, operation_params, boundary_conditions):
        # Extract lockage number
        self.lockage_number = operation_params['Num']
        # Extract volume of the ship transiting the lock
        self.V_ship = operation_params['V_ship']
        # Extract boundary conditions
        S_ocean = boundary_conditions['S_ocean']
        H_ocean = boundary_conditions['H_ocean']
        S_lake = boundary_conditions['S_lake']
        H_lake = boundary_conditions['H_lake']
        # Add chamber's length and ship's volume to lock chamber
        for cham in ['LC', 'MC', 'UC']:
            L = operation_params['Chamber_Length']
            self.chambers[cham].add_ship(self.V_ship)
            self.chambers[cham].change_length(L)
        # Extract lock operation parameters
        self.tGateOpen = operation_params['tGateOpen']
        self.eqTime = operation_params['eqTime']
        # Extract lockage direction and wsb use
        direction = operation_params['Direction']
        wsb_use = operation_params['WSBUse_Simple']
        # Calculate initial lockage time stamp in minutes
        lockage_start_dt = operation_params['TS_LockageStarts']
        initial_time = self.calc_elapsed_minutes(lockage_start_dt)
        # Perform transit based on the direction
        print(f'\nLockage {self.lockage_number} started at {lockage_start_dt}')
        print(f'Direction: {direction.title()}lockage')
        if direction == 'up':
            self.uplockage(initial_time, wsb_use, S_ocean, H_ocean, S_lake, H_lake)
        elif direction == 'down':
            self.downlockage(initial_time, wsb_use, S_ocean, H_ocean, S_lake, H_lake)
        else:
            raise ValueError("Direction must be either 'up' or 'down'.")
    
    def uplockage(self, initial_time_stamp, wsb_use, S_ocean, H_ocean, S_lake, H_lake):
        ## 1) Drain the lock chamber to the level of the ocean (LH4)
        if self.chambers['LC'].get_current_level() > H_ocean:
            tdrain = 12 # Minutes to drain chamber (assumed)
            self.chambers['LC'].record_current_status(ts=initial_time_stamp-tdrain)
            print(f'{self.ts_to_datetime(initial_time_stamp-tdrain)}: LH4 Equalization Started')
            if wsb_use['LC']:
                time0 = initial_time_stamp - tdrain # minutes
                self.drain_chamber_to_wsb(chamber='LC', ts=time0, teq=tdrain)
            self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=initial_time_stamp)
            print(f'{self.ts_to_datetime(initial_time_stamp)}: LC finished draining to ocean level')
        else:
            print(f'{self.ts_to_datetime(initial_time_stamp)}: LH4 Already Equalized')
        ## 2) Gates at LH4 open, salinity enters from the ocean and ship enters the lock
        t_transit = self.tGateOpen['LH4'] # minutes
        time_stamp = initial_time_stamp + t_transit # minutes
        V_ex_ocean = self.exchange_with_boundary(S_ocean=S_ocean)
        self.chambers['LC'].ship_enters(V_lhs=V_ex_ocean, S_lhs=S_ocean, ts=time_stamp)
        ## 3) Equalization and transit between LC and MC
        teq = self.eqTime['LC'] # minutes
        time_stamp = self.equalize_and_cross(
            lock_head='LH3', direction='up', wsb_use=wsb_use, init_time=time_stamp, teq=teq)
        ## 4) Equalization and transit between MC and UC
        teq = self.eqTime['MC'] # minutes
        time_stamp = self.equalize_and_cross(
            lock_head='LH2', direction='up', wsb_use=wsb_use, init_time=time_stamp, teq=teq)
        ## 5) Lift the ship to the level of the lake (LH1)
        if self.chambers['UC'].get_current_level() < H_lake:
            self.chambers['UC'].record_current_status(ts=time_stamp)
            print(f'{self.ts_to_datetime(time_stamp)}: LH1 Equalization Started')
            ## 5.1) Fill water from WSB (if needed)
            if wsb_use['UC']:
                self.fill_chamber_from_wsb(chamber='UC', ts=time_stamp, teq=self.eqTime['UC'])
            ## 5.2) Finish filling chamber to the level of the lake
            time_stamp = time_stamp + self.eqTime['UC'] # minutes to fill chamber
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=time_stamp)
            print(f'{self.ts_to_datetime(time_stamp)}: UC finished filling to lake level')
            super().record_freshwater_consumed(end_luc=H_lake, ts=time_stamp)
        else:
            print(f'{self.ts_to_datetime(time_stamp)}: LH1 Already Equalized')
        ## 6) Gates at LH1 open, salt mass enters the lake and ship leaves the lock
        t_transit = self.tGateOpen['LH1'] # minutes
        time_stamp = time_stamp + t_transit # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = self.exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_leaves(V_rhs=V_ex_lake, S_rhs=S_lake, ts=time_stamp)
        self.calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='up', ts=time_stamp)

    def downlockage(self, initial_time_stamp, wsb_use, S_ocean, H_ocean, S_lake, H_lake):
        ## 1) Lift upper chamber to level of the lake (LH1)
        if self.chambers['UC'].get_current_level() < H_lake:
            tfill = 12 # Minutes to fill chamber (assumed)
            self.chambers['UC'].record_current_status(ts=initial_time_stamp-tfill)
            print(f'{self.ts_to_datetime(initial_time_stamp-tfill)}: LH1 Equalization Started')
            if wsb_use['UC']:
                time0 = initial_time_stamp - tfill # minutes
                self.fill_chamber_from_wsb(chamber='UC', ts=time0, teq=tfill)
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=initial_time_stamp)
            print(f'{self.ts_to_datetime(initial_time_stamp)}: UC finished filling to lake level')
            super().record_freshwater_consumed(end_luc=H_lake, ts=initial_time_stamp)
        else:
            print(f'{self.ts_to_datetime(initial_time_stamp)}: LH1 Already Equalized')
        ## 2) Gates at LH1 open, salt mass enters the lake and ship enters the lock
        t_transit = self.tGateOpen['LH1'] # minutes
        time_stamp = initial_time_stamp + t_transit # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = super().exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_enters(V_lhs=V_ex_lake, S_lhs=S_lake, ts=time_stamp)
        super().calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='down', ts=time_stamp)
        ## 3) Equalization and transit between UC and MC
        teq = self.eqTime['UC'] # minutes
        time_stamp = self.equalize_and_cross(
            lock_head='LH2', direction='down', wsb_use=wsb_use, init_time=time_stamp, teq=teq)
        ## 4) Equalization and transit between MC and LC
        teq = self.eqTime['MC'] # minutes
        time_stamp = self.equalize_and_cross(
            lock_head='LH3', direction='down', wsb_use=wsb_use, init_time=time_stamp, teq=teq)
        ## 5) Drain to the level of the ocean (LH4)
        if self.chambers['LC'].get_current_level() > H_ocean:
            self.chambers['LC'].record_current_status(ts=time_stamp)
            print(f'{self.ts_to_datetime(time_stamp)}: LH4 Equalization Started')
            ## 5.1) Drain water from chamber to WSB (if needed)
            if wsb_use['LC']:
                self.drain_chamber_to_wsb(chamber='LC', ts=time_stamp, teq=self.eqTime['LC'])
            ## 5.2) Finish draining chamber to the level of the ocean
            time_stamp = time_stamp + self.eqTime['LC'] # total minutes to drain chamber
            self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=time_stamp)
            print(f'{self.ts_to_datetime(time_stamp)}: LC finished draining')
        ## 6) Gates at LH4 open, salinity enters from the ocean and ship leaves the lock
        t_transit = self.tGateOpen['LH4'] # minutes
        time_stamp = time_stamp + t_transit # minutes
        V_ex_ocean = super().exchange_with_boundary(S_ocean=S_ocean) 
        self.chambers['LC'].ship_leaves(V_rhs=V_ex_ocean, S_rhs=S_ocean, ts=time_stamp)
        print(f'{self.ts_to_datetime(time_stamp)}: Lockage {self.lockage_number} finished')

    def get_results_df(self, variable, pivot=True, interpolate=True):
        list_of_dfs = []
        for cham in ['LC', 'MC', 'UC']:
            results = self.chambers[cham].get_results_dictionary()
            df = pd.DataFrame(results).loc[:, ['Time', variable]]
            df['Location'] = cham
            list_of_dfs.append(df)
            for basin in ['Top', 'Int', 'Bot']:
                results = self.basins[cham][basin].get_results_dictionary()
                df = pd.DataFrame(results).loc[:, ['Time', variable]]
                df['Location'] = f'{cham[0]}B{basin}'
                list_of_dfs.append(df)
        # Concatenate all dataframes
        df = pd.concat(list_of_dfs).reset_index(drop=True)
        # Calculate Date_Time timestamp column and set as index
        df['TimeTrans'] = pd.to_timedelta(df['Time'], unit='min')
        df['Date_Time'] = pd.to_datetime(self.operation_start_dt) + df['TimeTrans']
        df = df.drop(columns='TimeTrans')
        df = df.set_index('Date_Time')
        if pivot:
            df = df.drop_duplicates()
            df = df.pivot(columns='Location', values=variable)
        if interpolate:
            df = df.resample('1min').mean()
            df = df.reindex(pd.date_range(df.index[0], df.index[-1], freq='1min'))
            df = df.interpolate(method='linear', limit_area='inside')
            df = df.ffill()
        return df

    def get_water_levels(self, pivot=True, interpolate=True):
        df = self.get_results_df('Level', pivot=pivot, interpolate=interpolate)
        return df
    
    def get_salinities(self, pivot=True, interpolate=True):
        df = self.get_results_df('Salinity', pivot=pivot, interpolate=interpolate)
        return df

    
    def turnaround(self, boundary_conditions, new_direction, tinit):
        # Record current conditions before initiating turnaround
        self.chambers['MC'].record_current_status(ts=tinit)
        if new_direction == 'up':
            self.chambers['UC'].record_current_status(ts=tinit)
        elif new_direction == 'down':
            self.chambers['LC'].record_current_status(ts=tinit)
        # Perform turnaround operation
        super().turnaround(boundary_conditions, new_direction, tinit)
