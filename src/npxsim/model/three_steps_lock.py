# ThreeStepsLock class for Panama Canal's lock model
# M. G. Castrellon | 18 March 2025

# Import Libraries
import pandas as pd
from datetime import datetime
from npxsim.model.lock_elements import *
from npxsim.model.custom_exceptions import *
import npxsim.utilities.hydrodynamics as hd

# Define class
class ThreeStepsLock:

    def __init__(self, lock_length, lock_width, cham_elevs, 
                 lock_head_sills, operating_limits):
        # Initialize lock chamber objects
        self.chambers = {}
        for cham in ['LC', 'MC', 'UC']:
            self.chambers[cham] = LockChamber(
                length=lock_length, width=lock_width,
                z_bottom=cham_elevs[cham][0],
                z_top=cham_elevs[cham][1],
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
        # Initialize dicts to store freshwater consumption and salt mass load
        self.salt_mass_load = {'Num': [], 'TS': [], 'DC': [], 'VD': []}
        self.freshwater_use = {'Num': [], 'TS': [], 'ConsMMC': [], 
                               'OP_Type': [], 'Start_LUC': [], 'End_LUC': []}
    
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
        # Recording salt mass load in kilograms
        self.salt_mass_load['TS'].append(ts)
        self.salt_mass_load['DC'].append(m_dc)
        self.salt_mass_load['VD'].append(m_vd)
        self.salt_mass_load['Num'].append(self.Num)
    
    def record_freshwater_use(self, start_luc, end_luc, ts, op_type):
        # Calculate amount of freshwater used in million cubic meters
        vol = (end_luc - start_luc)*self.chambers['UC'].area
        
        # Record the freshwater consumption
        self.freshwater_use['Start_LUC'].append(start_luc)
        self.freshwater_use['End_LUC'].append(end_luc)
        self.freshwater_use['ConsMMC'].append(vol)
        self.freshwater_use['OP_Type'].append(op_type)
        self.freshwater_use['TS'].append(ts)
        
        if op_type == 'TA':
            lockage_id = self.Num + 1
        else:
            lockage_id = self.Num
        
        self.freshwater_use['Num'].append(lockage_id)
    
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
                ts = self.calc_elapsed_minutes(next_transit['TS_LockageStarts']) - 30
                self.turnaround(boundary_conditions[i+1], next_transit['Direction'], tinit=ts)
    
    def transit(self, operation_params, boundary_conditions):
        # Extract transit parameters
        self.Num = operation_params['Num']
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
        self.record_freshwater_use(start_luc=start_luc, end_luc=H_lake, ts=time_stamp, op_type='TR')
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
            self.record_freshwater_use(start_luc=start_luc, end_luc=H_lake, ts=initial_time_stamp, op_type='TR')
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
        # Record current conditions before initiating turnaround
        self.chambers['MC'].record_current_status(ts=tinit)
        if new_direction == 'up':
            self.chambers['UC'].record_current_status(ts=tinit)
        elif new_direction == 'down':
            self.chambers['LC'].record_current_status(ts=tinit)
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
            H_uc_current = self.chambers['UC'].get_current_level()
            self.record_freshwater_use(start_luc=H_uc_current, end_luc=H_lake, ts=ts, op_type='TA')
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=ts)
            ## 2. Drain UC and fill MC to the top operating level of MC
            ts = ts + 10 # minutes
            Hf_mc = op_levels['MC'][1]
            S_uc = self.chambers['UC'].get_current_salinity()
            self.chambers['UC'].drain_chamber(H_final=Hf_mc, ts=ts)
            self.chambers['MC'].fill_chamber(H_final=Hf_mc, S_lift=S_uc, ts=ts)
            ## 3. Fill UC again to the level of the ocean
            ts = ts + 10 # minutes
            H_uc_current = self.chambers['UC'].get_current_level()
            self.record_freshwater_use(start_luc=H_uc_current, end_luc=H_lake, ts=ts, op_type='TA')
            self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=ts)
            ## 4. Drain LC to the level of the ocean (if needed)
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
            ## 4. Fill UC to the level of the lake (if needed)
            if self.chambers['UC'].get_current_level() < H_lake:
                H_uc_current = self.chambers['UC'].get_current_level()
                self.record_freshwater_use(start_luc=H_uc_current, end_luc=H_lake, ts=ts, op_type='TA')
                self.chambers['UC'].fill_chamber(H_final=H_lake, S_lift=S_lake, ts=ts)
    
    def get_salt_load(self, units='ton'):
        """
        Calculate and return the salt mass load entering the lake from the upper chamber.
        Parameters
        ----------
        Units : str, optional
            Unit of mass for the output values. Accepts 'ton' for tonnes (default) or 'kg' for kilograms.
        Returns
        -------
        pandas.DataFrame
            DataFrame containing the salt mass load with columns:
                - 'TS': Timestamp or time step identifier.
                - 'DC': Salt load from the DC source (in specified units).
                - 'VD': Salt load from the VD source (in specified units).
                - 'Total_Salt_Load': Combined salt load from DC and VD (in specified units).
        Notes
        -----
        If `Units` is set to 'ton', the values for 'DC' and 'VD' are converted from kilograms to tonnes.
        The 'Total_Salt_Load' column is computed as the sum of 'DC' and 'VD' for each row.
        """
        df = pd.DataFrame(self.salt_mass_load)
        df = df.sort_values(by='TS', ascending=True)
        
        if units == 'ton':
            for col in ['DC', 'VD']:
                df[col] = df[col]/1000
        
        df['Total_Salt_Load'] = df['DC'] + df['VD']

        return df
    
    def get_freshwater_use(self, units='hm3'):
        """
        Returns the amount of freshwater use in the simulation.
        Parameters
        ----------
        Units : str, optional
            The units for the returned freshwater consumption values.
            Supported values:
                - 'hm3': Returns consumption in hectometers cubed (default).
                - Any other value: Returns consumption in the original units (cubic meters).
        Returns
        -------
        pandas.DataFrame
            DataFrame containing freshwater consumption data. If Units is 'hm3',
            the 'ConsMMC' column is converted from cubic meters to hectometers cubed.
        """
        df = pd.DataFrame(self.freshwater_use)
        df = df.sort_values(by='TS', ascending=True)
        df['Delta_LUC'] = df['End_LUC'] - df['Start_LUC']

        if units == 'hm3':
            df['ConsMMC'] = df['ConsMMC']/1e6
        
        return df
    
    def get_operation_outputs(self):
        """
        Generates a DataFrame summarizing the operational outputs for the lake system.
        This method computes and merges the freshwater use and the salt mass load 
        (in tons) entering the lake from the upper chamber. The resulting DataFrame is 
        indexed by the lockage number or ID, with columns for both freshwater use 
        and salt load.
        Returns:
            pd.DataFrame: A DataFrame containing columns for freshwater use and 
            salt mass load, aligned by lockage number/ID.
        """
        water_use_raw = self.get_freshwater_use(units='hm3')
        salt_load_raw = self.get_salt_load(units='ton')
        
        ## Pivot the water use DataFrame
        water_use = pd.pivot_table(
            water_use_raw, values='ConsMMC', index='Num', 
            columns='OP_Type', aggfunc='sum')

        ## Format water use DataFrame
        if 'TA' in water_use.columns:
            water_use['TA'] = water_use['TA'].fillna(0)
            water_use.columns = ['TA_Water_Use', 'TR_Water_Use']
        else:
            water_use['TA_Water_Use'] = 0
            water_use.rename(columns={'TR': 'TR_Water_Use'}, inplace=True)
        
        water_use['Total_Water_Use'] = water_use.sum(axis=1)
        water_use.reset_index(inplace=True)
        water_use.columns.name = None

        ## Format salt load DataFrame
        salt_load = salt_load_raw.copy()
        salt_load.drop(columns='TS', inplace=True)
        salt_load.rename(columns={'DC': 'DC_Salt_Load', 'VD': 'VD_Salt_Load'}, inplace=True)

        ## Merge DataFrame on Num column
        df = pd.merge(water_use, salt_load, on='Num', how='outer')

        return df
    
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
    
    def convert_col_to_datetime(self, df, col):
        initial_time = self.operation_start_dt
        df[col] = pd.to_timedelta(df[col], unit='min')
        df['Date_Time'] = pd.to_datetime(initial_time) + df[col]
        return df

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
        df = self.convert_col_to_datetime(df=df, col='Time')
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

