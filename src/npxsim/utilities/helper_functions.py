# Helper functions for Panama Canal's lock model
# M. G. Castrellon | 11 February 2024

# Load Libraries
import pandas as pd

# Define functions

def filter_date_range(df, start_date, end_date, date_col='Date_Time',
                      date_format='%Y-%m-%d %H:%M:%S'):
    """
    Filters a dataframe by a date range. The function accepts a dataframe and
    two strings with the start and end dates in the format 'YYYY-MM-DD HH:MM:SS'.
    """
    df[date_col] = pd.to_datetime(df[date_col], format=date_format)
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
    - Chamber_Length: Lock chamber lengt
    - WSBasins: Flag to indicate if WSBasins are used during lockage
    - UCWSBs: Flag to indicate if WSBs are used in the upper chamber
    - MCWSBs: Flag to indicate if WSBs are used in the middle chamber
    - LCWSBs: Flag to indicate if WSBs are used in the lower chamber
    """
    ## Define columns of interest for lock operations
    transit_time_cols = [f'transitTimeLH{i}' for i in range(1, 5)]
    eq_time_cols = [f'equalzTime{x}' for x in ['UC', 'MC', 'LC']]
    other_cols = ['TS_LocksReady', 'TS_LockageStarts', 'Direction', 
                  'Ship_Vol_Disp', 'Chamber_Length']
    wsb_use_cols = [f'{x}CWSBs' for x in ['U', 'M', 'L']]
    ## Extract operation parameters for lock operations
    list_of_cols = transit_time_cols + eq_time_cols + other_cols + wsb_use_cols
    operation_params_df = lock_operations_df.loc[:, ['Num', 'WSBasins'] + list_of_cols]
    ## Add all of the transit and equalization times
    operation_params_df['Total_Lockage_Time'] = \
        operation_params_df[transit_time_cols + eq_time_cols].sum(axis=1)
    ## Rename vessel direction in lock operations
    operation_params_df['Direction'] = operation_params_df['Direction'] \
        .replace({'Downlockage': 'down', 'Uplockage': 'up'})
    ### Add a flag if all WSBasins are used during lockage
    operation_params_df['WSB_All_Flag'] = 0
    operation_params_df['WSB_Num'] = operation_params_df[wsb_use_cols].sum(axis=1)
    operation_params_df.loc[operation_params_df['WSB_Num'] == 3, 'WSB_All_Flag'] = 1
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
            'WSB_Use_Flag': item['WSBasins'],
            'WSB_All_Flag': item['WSB_All_Flag'],
            'WSBUse_Simple': {
                'UC': item['UCWSBs'],
                'MC': item['MCWSBs'],
                'LC': item['LCWSBs']
            }
        }
        operation_params.append(transformed_item)
    ## Return dictionary
    return operation_params

def extract_obs_water_levels(df, filling_time=10):
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
    end_luc = df.loc[:, ['TS_LakeGateOpens', 'End_LUC']]
    start_luc = df.loc[:, ['TS_LakeGateOpens', 'Start_LUC']]
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

def parse_design_specifications(df, wsb_output=True):
    """
    Parses the design specifications for the locks and water saving basins.
    The function accepts a dataframe that must contain the following columns:
    - Location: Name of the lock chamber, basin or lock head
    - Z_bottom: Bottom elevation of the lock chamber, basin or lock head
    - Z_top: Top elevation of the lock chamber or basin
    - H_min: Minimum operating level of the lock chamber or basin
    - H_max: Maximum operating level of the lock chamber or basin
    The function returns the following dictionaries:
    - lock_head_sills: Dictionary with the lock head sill elevations
    - chamber_parameters: Dictionary with the elevations (Z) and water level (H)
                          operating limits for the lock chambers.
    - wsb_parameters: Dictionary with the elevations (Z) and water level (H)
                          operating limits for the water saving basins.
    """
    ## Reshape design specifications
    df = df.set_index('Location')
    ds_dict = df.to_dict(orient='index')
    ## Get lock_head_sills
    lock_heads = ['LH1', 'LH2', 'LH3', 'LH4']
    lock_head_sills = {lh: ds_dict[lh]['Z_bottom'] for lh in lock_heads}
    ## Get operating limits and elevations for locks and basins
    cham_op_limits, cham_elevs = {}, {}
    for cham in ['LC', 'MC', 'UC']:
        cham_op_limits[cham] = (ds_dict[cham]['H_min'], ds_dict[cham]['H_max'])
        cham_elevs[cham] = (ds_dict[cham]['Z_bottom'], ds_dict[cham]['Z_top'])
    ## Get operating limits and elevations for water saving basins
    wsb_op_limits, wsb_elevs = {}, {}
    basins = ['Top', 'Int', 'Bot']
    for cham in ['L', 'M', 'U']:
        wsb_op_limits[cham+'C'] = {
            x: (ds_dict[f'{cham}B_{x}']['H_min'], ds_dict[f'{cham}B_{x}']['H_max']) for x in basins
        }
        wsb_elevs[cham+'C'] = {
            x: (ds_dict[f'{cham}B_{x}']['Z_bottom'], ds_dict[f'{cham}B_{x}']['Z_top']) for x in basins
        }
    ## Combine parameters into dictionaries
    chamber_parameters = {'Z': cham_elevs, 'H': cham_op_limits}
    wsb_parameters = {'Z': wsb_elevs, 'H': wsb_op_limits}
    ## Return results
    if wsb_output:
        return lock_head_sills, chamber_parameters, wsb_parameters
    else:
        return lock_head_sills, chamber_parameters

def format_operation_summary(operation_params, df_outputs):
    """
    Formats the operation summary DataFrame by merging salt load, freshwater consumption,
    and operation parameters.
    """
    
    # Select relevant columns for operation summary
    op_columns = ['Num', 'TS_LockageStarts', 'Direction', 'WSBasins', 'Ship_Vol_Disp']
    operation_summary = operation_params.loc[:, op_columns].copy()
    
    # Merge salt load and freshwater consumption with operation parameters
    operation_summary = operation_summary.merge(df_outputs, on='Num', how='outer')
        
    return operation_summary