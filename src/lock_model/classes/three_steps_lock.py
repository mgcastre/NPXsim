# ThreeStepsLock class for Panama Canal's lock model
# M. G. Castrellon | 18 March 2025

# Import Libraries
import numpy as np
import pandas as pd
from datetime import datetime
from classes.lock_elements import *
from classes.custom_exceptions import *
import utilities.hydrodynamics as hd

# Define class
class ThreeStepsLock:

    def __init__(self, lock_length, lock_width, cham_bottom_elevs, 
                 lock_head_sills, operating_limits):
        # Initialize lock chamber objects
        self.chambers = {}
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham] = LockChamber(
                length=lock_length, width=lock_width,
                z_bottom=cham_bottom_elevs[cham],
                H_min=operating_limits[cham][0],
                H_max=operating_limits[cham][1],
                S0=None, H0=None
            )
        # Create attributes for lock heads
        self.lock_heads = {'Z': lock_head_sills}
        self.lock_heads['Chambers'] = {
            'LH1': ['UC'], 
            'LH2': ['MC', 'UC'],
            'LH3': ['LC', 'MC'], 
            'LH4': ['LC']
        }
        # Initialize dict to store salt mass load to the lake
        self.salt_mass_load = {'TS': [], 'DC': [], 'VD': []}
        # Initialize dict to store freshwater consumed per lockage
        self.freshwater_consumed = {'TS': [], 'ConsMMC': []}
    
    def calc_cham_operational_levels(self, H_lake, H_ocean):
        # Extract chamber areas
        Au = self.chambers['UC'].area
        Am = self.chambers['MC'].area
        Al = self.chambers['LC'].area
        # Calculate operational levels
        denominator = ((Am + Al)*(Au + Am)/Am) - Am
        numerator = H_ocean*Al + (Am + Al)*H_lake*Au/Am
        uc_high = H_lake
        uc_low = numerator/denominator
        mc_high = uc_low
        mc_low = ((Au + Am)/Am)*mc_high - H_lake*Au/Am
        lc_high = mc_low
        lc_low = H_ocean
        # Store operational levels in a dictionary
        cham_op_levels = {}
        cham_op_levels['UC'] = (uc_low, uc_high)
        cham_op_levels['MC'] = (mc_low, mc_high)
        cham_op_levels['LC'] = (lc_low, lc_high)
        # Return operational levels
        return cham_op_levels
    
    def calc_initial_levels(self, H_lake, H_ocean, direction):
        op_levels = self.calc_cham_operational_levels(H_lake, H_ocean)
        # During both uplockages and downlocakges, the UC initial level
        # is the lake level (higher level). Similarly, the LC initial level
        # is the level of the ocean (lower level) for both lockage directions.
        init_levels = {'LC': op_levels['LC'][0], 'UC': op_levels['UC'][1]}
        # During uplockages, the MC starts at its high level.
        if direction == 'up':
            init_levels['MC'] = op_levels['MC'][1]
        # During downlockages, the MC starts at its low level.
        if direction == 'down':
            init_levels['MC'] = op_levels['MC'][0]
        return init_levels
    
    def set_initial_conditions(self, boundary_conditions, salinities, 
                               direction, operation_start_dt, 
                               water_temperature=28):
        # Calculate initial operational water levels
        H_lake = boundary_conditions['H_lake']
        H_ocean = boundary_conditions['H_ocean']
        init_levels = self.calc_initial_levels(H_lake, H_ocean, direction)
        # Add initial conditions to the lock chambers
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham].add_initial_conditions(
                H0=init_levels[cham], S0=salinities[cham]
            )
        # Pass the temperature to the class attribute
        self.T = water_temperature
        # Add master initial operation start time
        self.operation_start_dt = operation_start_dt
    
    def extract_properties(self, cham):
        W = self.chambers[cham].width
        L = self.chambers[cham].length
        H = self.chambers[cham].get_current_level()
        return W, L, H
    
    def lock_exchange_factor(self, lock_head, S_boundary=None):
        # Extract salinity and water levels
        if lock_head == 'LH1':
            _, L, H = self.extract_properties('UC')
            S_lhs = self.chambers['UC'].get_current_salinity()
            S_rhs = S_boundary
        elif lock_head == 'LH2':
            _, L, H = self.extract_properties('MC')
            S_lhs = self.chambers['MC'].get_current_salinity()
            S_rhs = self.chambers['UC'].get_current_salinity()
        elif lock_head == 'LH3':
            _, L, H = self.extract_properties('LC')
            S_lhs = self.chambers['LC'].get_current_salinity()
            S_rhs = self.chambers['MC'].get_current_salinity()
        elif lock_head == 'LH4':
            _, L, H = self.extract_properties('LC')
            S_rhs = self.chambers['LC'].get_current_salinity()
            S_lhs = S_boundary
        # Calculate density of water in the lock chambers
        rho_lhs = hd.Rho_from_PSU(Salt=S_lhs, Temp=self.T)
        rho_rhs = hd.Rho_from_PSU(Salt=S_rhs, Temp=self.T)
        # Sort densities
        rho1, rho2 = (rho_rhs, rho_lhs) \
            if rho_lhs > rho_rhs else (rho_lhs, rho_rhs)
        # Calculate the exchange coefficient
        tOpen = self.tGateOpen[lock_head]*60 # seconds
        head = H - self.lock_heads['Z'][lock_head]
        Eff = hd.exchange_coefficient(
            rho1=rho1, rho2=rho2, H=head, 
            L=L, tOpen=tOpen, eta=0.8)
        # Return the exchange coefficient
        return Eff
    
    def equalize_chambers(self, upper_cham, lower_cham, ts):
        # 1. Calculate final equalization level
        W1, L1, H1 = self.extract_properties(upper_cham)
        W2, L2, H2 = self.extract_properties(lower_cham)
        Hf = hd.calc_equalization_level(A1=W1*L1, A2=W2*L2, H1=H1, H2=H2)
        # 2. Drain upper chamber to equalization level
        self.chambers[upper_cham].drain_chamber(H_final=Hf, ts=ts)
        # 3. Fill lower chamber to equalization level
        S_next_cham = self.chambers[upper_cham].get_current_salinity()
        self.chambers[lower_cham].fill_chamber(H_final=Hf, S_lift=S_next_cham, ts=ts)
        return Hf
    
    def move_ship(self, cham1, cham2, V_ex, ts):
        S_cham1 = self.chambers[cham1].get_current_salinity()
        S_cham2 = self.chambers[cham2].get_current_salinity()
        self.chambers[cham1].ship_leaves(V_rhs=V_ex, S_rhs=S_cham2, ts=ts)
        self.chambers[cham2].ship_enters(V_lhs=V_ex, S_lhs=S_cham1, ts=ts)
    
    def equalize_and_cross(self, lock_head, direction, init_time):
        # 1. Extract chambers involved in the lock head and assign order
        lower_cham, upper_cham = self.lock_heads['Chambers'][lock_head]
        cham1, cham2 = (lower_cham, upper_cham) \
            if direction == 'up' else (upper_cham, lower_cham)
        # 2. Equalize upper and lower chambers
        ts = init_time + self.eqTime[cham1] # minutes
        # print(f"Initial {upper_cham} level: "
        #       f"{self.chambers[upper_cham].get_current_level()} m")
        # print(f"Initial {lower_cham} level: "
        #       f"{self.chambers[lower_cham].get_current_level()} m")
        Hf = self.equalize_chambers(upper_cham, lower_cham, ts)
        # 3. Check if equalization level is within operational limits
        for cham in [upper_cham, lower_cham]:
            H_min, H_max = self.chambers[cham].get_operating_limits()
            if (H_min > Hf) or (Hf > H_max):
                raise WaterLevelError(Hf, H_min, H_max, res_name=cham)
        # 3. Open lock gates and move ship between chambers
        ## 3.1. Calculate volume of water to be exchanged
        Eff = self.lock_exchange_factor(lock_head)
        V_ex = self.calc_volume_exchanged(Eff=Eff, cham=upper_cham)
        ## 3.2 Calculate time stamp after crossing lock head (in minutes)
        ts = ts + self.tGateOpen[lock_head]
        ## 3.3 Move ship from first to second chamber
        self.move_ship(cham1, cham2, V_ex, ts)
        return ts

    def calc_volume_exchanged(self, Eff, cham):
        Hf = self.chambers[cham].get_current_level()
        if cham == 'UC':
            h = Hf - self.lock_heads['Z']['LH1']
        else:
            h = Hf - self.chambers[cham].z_bottom
        A = self.chambers[cham].area
        V_ex = Eff*(A*h - self.V_ship)
        return V_ex
    
    def calc_salt_mass_load(self, S_lake, V_ex_lake, S_chamber, direction, ts):
        c1 = hd.convert_salt_concentration(S_lake, self.T)
        c2 = hd.convert_salt_concentration(S_chamber, self.T)
        m_dc = V_ex_lake*(c2 - c1)
        if direction == 'up':
            m_vd = -1*self.V_ship*c1
        elif direction == 'down':
            m_vd = self.V_ship*c2
        # Recording salt mass load in UK Tonnes
        self.salt_mass_load['TS'].append(ts)
        self.salt_mass_load['DC'].append(m_dc/1000)
        self.salt_mass_load['VD'].append(m_vd/1000)
    
    def record_freshwater_consumed(self, start_luc, end_luc, ts):
        # Recording amount of freshwater used in million cubic meters
        vol = (end_luc - start_luc)*self.chambers['UC'].area
        self.freshwater_consumed['ConsMMC'].append(vol/1e6)
        self.freshwater_consumed['TS'].append(ts)
    
    def exchange_with_boundary(self, S_lake=None, S_ocean=None):
        if S_lake is not None:
            Eff = self.lock_exchange_factor(lock_head='LH1', S_boundary=S_lake)
            V_ex = self.calc_volume_exchanged(Eff=Eff, cham='UC')
        elif S_ocean is not None:
            Eff = self.lock_exchange_factor(lock_head='LH4', S_boundary=S_ocean)
            V_ex = self.calc_volume_exchanged(Eff=Eff, cham='LC')
        return V_ex
    
    def calc_elapsed_minutes(self, dt_string2, time_format='%Y-%m-%d %H:%M:%S'):
        """
        Calculate the elapsed time in minutes between the start of the lock operation and the
        start of an individual lockage. Both date time stamps must be in the same time format,
        which can be specified by the user.
        """	
        dt_string1 = self.operation_start_dt
        date1 = datetime.strptime(dt_string1, time_format)
        date2 = datetime.strptime(dt_string2, time_format)
        elapsed_minutes = (date2 - date1).total_seconds()/60
        return elapsed_minutes
    
    def operate(self, operation_params, boundary_conditions):
        for i in range(len(operation_params)):
            this_transit = operation_params[i]
            self.transit(this_transit, boundary_conditions[i])
            try:
                next_transit = operation_params[i+1]
            except IndexError:
                break
            if this_transit['Direction'] != next_transit['Direction']:
                ts = self.calc_elapsed_minutes(next_transit['TS_LocksReady']) - 30
                self.turnaround(boundary_conditions[i+1], next_transit['Direction'], tinit=ts)
    
    def transit(self, operation_params, boundary_conditions):
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
        # Extract lockage direction
        direction = operation_params['Direction']
        # Calculate initial lockage time stamp in minutes
        lockage_start_dt = operation_params['TS_LockageStarts']
        initial_time = self.calc_elapsed_minutes(lockage_start_dt)
        # Perform transit based on the direction
        if direction == 'up':
            self.uplockage(initial_time, S_ocean, H_ocean, S_lake, H_lake)
        elif direction == 'down':
            self.downlockage(initial_time, S_ocean, H_ocean, S_lake, H_lake)
        else:
            raise ValueError("Direction must be either 'up' or 'down'.")
    
    def uplockage(self, initial_time_stamp, S_ocean, H_ocean, S_lake, H_lake):
        ## 1) Drain the lock chamber to the level of the ocean (LH4)
        if self.chambers['LC'].get_current_level() > H_ocean:
            self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=initial_time_stamp)
        ## 2) Gates at LH4 open, salinity enters from the ocean and ship enters the lock
        t_transit = self.tGateOpen['LH4'] # minutes
        time_stamp = initial_time_stamp + t_transit # minutes
        V_ex_ocean = self.exchange_with_boundary(S_ocean=S_ocean)
        self.chambers['LC'].ship_enters(V_lhs=V_ex_ocean, S_lhs=S_ocean, ts=time_stamp)
        ## 3) Equalization and transit between LC and MC
        time_stamp = self.equalize_and_cross(lock_head='LH3', direction='up', init_time=time_stamp)
        ## 4) Equalization and transit between MC and UC
        time_stamp = self.equalize_and_cross(lock_head='LH2', direction='up', init_time=time_stamp)
        ## 5) Lift the ship to the level of the lake (LH1)
        start_luc = self.chambers['UC'].get_current_level()
        time_stamp = time_stamp + self.eqTime['UC'] # minutes to fill chamber
        self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=time_stamp)
        self.record_freshwater_consumed(start_luc=start_luc, end_luc=H_lake, ts=time_stamp)
        ## 6) Gates at LH1 open, salt mass enters the lake and ship leaves the lock
        t_transit = self.tGateOpen['LH1'] # minutes
        time_stamp = time_stamp + t_transit # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = self.exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_leaves(V_rhs=V_ex_lake, S_rhs=S_lake, ts=time_stamp)
        self.calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='up', ts=time_stamp)

    def downlockage(self, initial_time_stamp, S_ocean, H_ocean, S_lake, H_lake):
        ## 1) Lift upper chamber to level of the lake (LH1)
        if self.chambers['UC'].get_current_level() < H_lake:
            start_luc = self.chambers['UC'].get_current_level()
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=initial_time_stamp)
            self.record_freshwater_consumed(start_luc=start_luc, end_luc=H_lake, ts=initial_time_stamp)
        ## 2) Gates at LH1 open, salt mass enters the lake and ship enters the lock
        t_transit = self.tGateOpen['LH1'] # minutes
        time_stamp = initial_time_stamp + t_transit # minutes
        S_chamber = self.chambers['UC'].salinity[-1]
        V_ex_lake = self.exchange_with_boundary(S_lake=S_lake)
        self.chambers['UC'].ship_enters(V_lhs=V_ex_lake, S_lhs=S_lake, ts=time_stamp)
        self.calc_salt_mass_load(S_lake, V_ex_lake, S_chamber, direction='down', ts=time_stamp)
        ## 3) Equalization and transit between UC and MC
        time_stamp = self.equalize_and_cross(lock_head='LH2', direction='down', init_time=time_stamp)
        ## 4) Equalization and transit between MC and LC
        time_stamp = self.equalize_and_cross(lock_head='LH3', direction='down', init_time=time_stamp)
        ## 5) Drain to the level of the ocean (LH4)
        time_stamp = time_stamp + self.eqTime['LC'] # minutes to drain chamber
        self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=time_stamp)
        ## 6) Gates at LH4 open, salinity enters from the ocean and ship leaves the lock
        t_transit = self.tGateOpen['LH4'] # minutes
        time_stamp = time_stamp + t_transit # minutes
        V_ex_ocean = self.exchange_with_boundary(S_ocean=S_ocean) 
        self.chambers['LC'].ship_leaves(V_rhs=V_ex_ocean, S_rhs=S_ocean, ts=time_stamp)
    
    def turnaround(self, boundary_conditions, new_direction, tinit):
        # Extract boundary conditions
        H_ocean = boundary_conditions['H_ocean']
        S_lake = boundary_conditions['S_lake']
        H_lake = boundary_conditions['H_lake']
        # Calculate lock operational levels
        op_levels = self.calc_cham_operational_levels(H_lake, H_ocean)
        # A) From downlockage to uplockage:
        if new_direction == 'up':
            ## 1. Fill UC to the level of the Lake
            ts = tinit + 10 # minutes
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=ts)
            ## 2. Drain UC and fill MC to the top operating level of MC
            ts = ts + 10 # minutes
            Hf_mc = op_levels['MC'][1]
            S_uc = self.chambers['UC'].get_current_salinity()
            self.chambers['UC'].drain_chamber(H_final=Hf_mc, ts=ts)
            self.chambers['MC'].fill_chamber(H_final=Hf_mc, S_lift=S_uc, ts=ts)
            ## 3. Fill UC again to the level of the ocean
            ts = ts + 10 # minutes
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=ts)
            ## 4. Drain LC to the level of the ocean
            if self.chambers['LC'].get_current_level() > H_ocean:
                self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=ts)
        # B) From uplockage to downlockage:
        if new_direction == 'down':
            ## 1. Drain LC to the level of the ocean
            ts = tinit + 10 # minutes
            self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=ts)
            ## 2. Drain MC and fill LC to the lowest operational level of MC
            ts = ts + 10 # minutes
            Hf_mc = op_levels['MC'][0]
            S_mc = self.chambers['MC'].get_current_salinity()
            self.chambers['MC'].drain_chamber(H_final=Hf_mc, ts=ts)
            self.chambers['LC'].fill_chamber(H_final=Hf_mc, S_lift=S_mc, ts=ts)
            ## 3. Drain LC again to the level of the ocean
            ts = ts + 10 # minutes
            self.chambers['LC'].drain_chamber(H_final=H_ocean, ts=ts)
            ## 4. Fill UC to the level of the lake
            if self.chambers['UC'].get_current_level() < H_lake:
                self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=ts)
    
    def get_salt_load(self, Units='ton', Dictionary=True):
        """
        Returns the salt mass load etering the lake from the upper chamber.
        By default it returns a dictionary with the keys 'DC', 'VD', and 'Total'.
        If Dictionary is set to False, it returns the values in a tuple.
        By default, it returns the mass in tonnes, but it can also be returned in 
        kilogram by setting Units to 'kg'.
        """	
        sm_dc = np.array(self.salt_mass_load['DC'])
        sm_vd = np.array(self.salt_mass_load['VD'])
        if Units == 'ton':
            sm_dc = sm_dc/1000
            sm_vd = sm_vd/1000
        m_total = sm_dc + sm_vd
        if Dictionary:
            return {'DC': sm_dc, 'VD': sm_vd, 'Total': m_total}
        else:
            return sm_dc, sm_vd, m_total
    
    def make_results_df(self):
        """Returns a dataframe with the raw results of the lock model."""
        # Create a dataframe for each chamber and append it to a list
        list_of_results = []
        for ch in ['LC', 'MC', 'UC']:
            df = pd.DataFrame(
                {'Time': self.chambers[ch].time, 
                 'Salinity': self.chambers[ch].salinity,
                 'Water_Level': self.chambers[ch].water_level,
                 'Chamber': ch}
                )
            list_of_results.append(df)
        # Concatenate the list of dataframes and return the results
        results = pd.concat(list_of_results)
        return results

    def get_results(self, variable, dt_index, ffill):
        """
        Returns a dataframe with the results of a specific variable of 
        the lock model at different time steps sepecified by the user.
        """
        # Extract the results dataframe
        results = self.make_results_df()
        # Isolate the variable of interest
        df = results.loc[:, ['Time', variable, 'Chamber']]
        # Pivot the dataframe to have the chambers as columns
        df = df.pivot(index='Time', columns='Chamber', values=variable)
        # Add a datetime column as index
        df.reset_index(inplace=True)
        initial_time = self.operation_start_dt
        df['Time'] = pd.to_timedelta(df['Time'], unit='min')
        df['Date_Time'] = pd.to_datetime(initial_time) + df['Time']
        if dt_index:
            df.set_index('Date_Time', inplace=True)
            df.drop(columns='Time', inplace=True)
        if ffill:
            for col in ['LC', 'MC', 'UC']:
                df[col] = df[col].ffill()
        # Return the results dataframe
        return df
    
    def get_salinities(self, dt_index=True, ffill=True):
        """
        Returns a dataframe of the salinity of each chamber in the lock model.
        """
        df = self.get_results(variable='Salinity', 
                              dt_index=dt_index, ffill=ffill)
        return df

    
    def get_water_levels(self, dt_index=True, ffill=True):
        """
        Returns a dtaframe of the water level of each chamber in the lock model.
        """
        df = self.get_results(variable='Water_Level', 
                              dt_index=dt_index, ffill=ffill)
        return df

