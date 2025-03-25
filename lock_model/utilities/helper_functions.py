# Helper functions for Panama Canal's lock model
# M. G. Castrellon | 11 February 2024

# Load Libraries
import pandas as pd

# Define functions

def filter_date_range(df, start_date, end_date, date_col='Date_Time'):
    """
    Filters a dataframe by a date range. The function accepts a dataframe and
    two strings with the start and end dates in the format 'YYYY-MM-DD HH:MM:SS'.
    """
    df[date_col] = pd.to_datetime(df[date_col])
    cond01 = df[date_col] >= pd.to_datetime(start_date)
    cond02 = df[date_col] <= pd.to_datetime(end_date)
    df_filtered = df.loc[cond01 & cond02, :]
    return df_filtered

def prepare_obs_salinities(df, start_date, end_date):
    """
    Prepares the observed salinities of the lock chambers. The function accepts
    a dataframe that must contain the columns 'Date_Time', 'LC', 'MC', and 'UC'.
    Additionally, the function accepts the start and end dates to filter the data.
    """
    ## Filter data by date range
    df_filtered = filter_date_range(df, start_date, end_date, date_col='Date_Time')
    df_filtered = df_filtered.loc[:, ['Date_Time', 'LC', 'MC', 'UC', 'LB', 'MB', 'UB']]
    df_filtered.set_index('Date_Time', inplace=True)
    ## Return filtered dataframe
    return df_filtered

def prepare_boundary_conditions(lock_operations_df):
    """
    Creates a list of dictionaries containing the boundary conditions to run
    the lock model (run transits). The function acceps a dataframe that
    must contain the following columns:
    - Ocean_Salinity: Salinity of the ocean
    - Ocean_Level: Level of the ocean
    - Lake_Salinity: Salinity of the lake
    - Lake_Level: Level of the lake
    """
    ## Define a dictionary to rename columns
    names_dict = {'Ocean_Salinity': 'S_ocean', 'Ocean_Level': 'H_ocean',
                  'Lake_Salinity': 'S_lake', 'Lake_Level': 'H_lake'}
    ## Create dictionary for boundary conditions
    boundary_conditions = lock_operations_df.rename(columns=names_dict) \
        .loc[:, ['S_ocean', 'H_ocean', 'S_lake', 'H_lake']] \
            .to_dict('records')
    ## Return dictionary
    return boundary_conditions

def prepare_operation_parameters(lock_operations_df):
    """
    Creates a list of dictionaries containing the operation parameters to run     
    the lock model (run transits). The function acceps a dataframe that
    must contain the following columns:
    - Num: Operation number
    - Direction: Lockage direction (Uplockage or Downlockage)
    - transitTimeLH1: Transit time for lock head 1
    - transitTimeLH2: Transit time for lock head 2
    - transitTimeLH3: Transit time for lock head 3
    - transitTimeLH4: Transit time for lock head 4
    - equalzTimeUC: Equalization time for upper chamber
    - equalzTimeMC: Equalization time for middle chamber
    - equalzTimeLC: Equalization time for lower chamber
    - TS_LocksReady: Time stamp for when locks are ready for the lockage
    - TS_LockageStarts: Lockage start time
    - Ship_Vol_Disp: Ship volume displacement
    - Chamber_Length: Lock chamber length
    """
    ## Define columns of interest for lock operations
    transit_time_cols = [f'transitTimeLH{i}' for i in range(1, 5)]
    eq_time_cols = [f'equalzTime{x}' for x in ['UC', 'MC', 'LC']]
    other_cols = ['TS_LocksReady', 'TS_LockageStarts', 'Direction', 
                  'Ship_Vol_Disp', 'Chamber_Length']
    wsb_use_cols = ['WSBasins'] + [f'{x}CWSBs' for x in ['U', 'M', 'L']] \
        + [f'{x}WSB{y}' for x in ['U', 'M', 'L'] for y in ['Top', 'Int', 'Bot']]
    ## Extract operation parameters for lock operations
    list_of_cols = transit_time_cols + eq_time_cols + other_cols + wsb_use_cols
    operation_params_df = lock_operations_df.loc[:, ['Num'] + list_of_cols]
    ## Add all of the transit and equalization times
    operation_params_df['Total_Lockage_Time'] = \
        operation_params_df[transit_time_cols + eq_time_cols].sum(axis=1)
    ## Rename vessel direction in lock operations
    operation_params_df['Direction'] = operation_params_df['Direction'] \
        .replace({'Downlockage': 'down', 'Uplockage': 'up'})
    ## Convert operation parameters to dictionary
    operation_params_raw = operation_params_df.to_dict('records')
    ## Transform dictionary into correct format
    operation_params = []
    for item in operation_params_raw:
        transformed_item = {
            'Num': item['Num'],
            'TS_LocksReady': str(item['TS_LocksReady']),
            'TS_LockageStarts': str(item['TS_LockageStarts']),
            'Chamber_Length': item['Chamber_Length'],
            'Direction': item['Direction'],
            'V_ship': item['Ship_Vol_Disp'],
            'eqTime': {
                'UC': item['equalzTimeUC'],
                'MC': item['equalzTimeMC'],
                'LC': item['equalzTimeLC']
            },
            'tGateOpen': {
                'LH1': item['transitTimeLH1'],
                'LH2': item['transitTimeLH2'],
                'LH3': item['transitTimeLH3'],
                'LH4': item['transitTimeLH4']
            },
            'WSB_Simple': {
                'UC': item['UCWSBs'],
                'MC': item['MCWSBs'],
                'LC': item['LCWSBs']
            },
            'WSB_Detailed': {
                'UC': {
                    'Top': item['UWSBTop'],
                    'Int': item['UWSBInt'],
                    'Bot': item['UWSBBot']},	
                'MC': {
                    'Top': item['MWSBTop'],
                    'Int': item['MWSBInt'],
                    'Bot': item['MWSBBot']},
                'LC': {
                    'Top': item['LWSBTop'],
                    'Int': item['LWSBInt'],
                    'Bot': item['LWSBBot']}
            }
        }
        operation_params.append(transformed_item)
    ## Return dictionary
    return operation_params

def extract_obs_water_levels(lock_operations_df, filling_time=10):
    """
    Extracts the observed water levels for the upper lock chamber. The function
    accepts a dataframe that must contain the following columns:
    - TS_LakeGateOpens: Time when the lake gate opens
    - Start_LUC: Water level at the start of filling the upper chamber (sometime before lake gate opens)
    - End_LUC: Water level at the end of filling the upper chamber (right before lake gate opens)
    Additionally, the function accepts a filling time (in minutes) to calculate the timestamp
    for the initial water level in the lock chamber (Start_LUC).
    """
    ## Extract observed water levels for upper chamber
    end_luc = lock_operations_df.loc[:, ['TS_LakeGateOpens', 'End_LUC']]
    start_luc = lock_operations_df.loc[:, ['TS_LakeGateOpens', 'Start_LUC']]
    ## Calculate time at the start of filling the upper chamber
    end_luc['Date_Time'] = pd.to_datetime(end_luc['TS_LakeGateOpens'])
    start_luc['Date_Time'] = pd.to_datetime(start_luc['TS_LakeGateOpens']) \
                             - pd.to_timedelta(filling_time, unit='min')
    ## Rename and drop columns
    start_luc.rename(columns={'Start_LUC': 'UC'}, inplace=True)
    start_luc.drop(columns='TS_LakeGateOpens', inplace=True)
    end_luc.rename(columns={'End_LUC': 'UC'}, inplace=True)
    end_luc.drop(columns='TS_LakeGateOpens', inplace=True)
    # Concate start and end level of upper chamber
    obs_water_levels = pd.concat([start_luc, end_luc])
    # Assign index and sort
    obs_water_levels.set_index('Date_Time', inplace=True)
    obs_water_levels.sort_index(inplace=True)
    # Return results
    return obs_water_levels

def extract_initial_salinities(salinity_df, initial_time):
    """
    Extracts the initial salinities for the lock chambers. The function accepts
    a dataframe that must contain the columns 'Date_Time', 'LC', 'MC', and 'UC'.
    Additionally, the function accepts the initial time to extract the salinities.
    """
    initial_salinities = salinity_df \
        .loc[salinity_df.index == initial_time] \
            .squeeze().to_dict()
    return initial_salinities

