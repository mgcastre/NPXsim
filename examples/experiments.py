"""
Experiment: Impact of vessel sizes
M. G. Castrellon | 25 January 2026
"""

# Load libraries
import os
import json
import time
import pandas as pd

# Load npxsim model
import npxsim.utilities.helper_functions as hf
from npxsim.model.neo_panamax_lock import NeoPanamaxLock

# Define current working directory
os.chdir("/home/gaby/Code/NPXsim/")

# Define dinput and output directories
data_dir = "./examples/input_data"
results_dir = "./results"

# Define vessel sizes to test 
vessel_sizes = [0, 25, 50, 75, 85, 100, 125, 150, 175]

# Load data

## Load initial conditions
initial_salinities = json.load(open(f"{data_dir}/average_salinities.json", 'r'))

## Load lock design specifications
lock_design_specs = pd.read_csv(f"{data_dir}/design_specifications_acll.csv", sep=',')

## Load operation parameters and bcs
operations_template = pd.read_csv(f"{data_dir}/operation_params_template.csv", sep=",")

## Change date format in operations template
for col in ['TS_LocksReady', 'TS_LockageStarts']:
    operations_template[col] = pd.to_datetime(operations_template[col])

# Initialize lock object for simulation

## Parse design specifications of the locks
lhs, cham_params, wsb_params = hf.parse_design_specifications(df=lock_design_specs)

## Define dimensions of the WSBs
assumed_wsb_dims = {'L': 468, 'W': 60}

## Create an instance of an NPX lock
AguaClara = NeoPanamaxLock(
    wsb_dims=assumed_wsb_dims, lock_head_sills=lhs,
    cham_elevs=cham_params['Z'], wsb_elevs=wsb_params['Z'],
    chamber_operating_limits=cham_params['H'],
    wsb_operating_limits=wsb_params['H'],
)

# Define a function to initialize and run simulation
def run_simulation(df_operations: pd.DataFrame,
                   experiment_name: str, path_out: str,
                   initial_salinities: dict = initial_salinities['ACLL'],
                   lock_object: NeoPanamaxLock = AguaClara):
    
    ## Parse operation parameters and boundary conditions
    operation_params = hf.prepare_operation_parameters(df_operations)
    boundary_conditions = hf.prepare_boundary_conditions(df_operations)

    ## Add initial conditions
    lock_object.set_initial_conditions(
        direction=operation_params[0]['Direction'],
        boundary_conditions=boundary_conditions[0],
        operation_start_dt=operation_params[0]['TS_LocksReady'],
        salinities=initial_salinities,
    )

    ## Operate the locks
    lock_object.operate(operation_params, boundary_conditions)

    ## Extract model results and save
    if not os.path.exists(path_out):
        os.makedirs(path_out)

    operation_outputs = lock_object.get_operation_outputs()

    my_columns = ['Num', 'TS_LockageStarts', 'Direction', 'Ship_Vol_Disp']
    op_info = df_operations[my_columns].copy()
    
    operation_outputs = pd.merge(
        op_info,
        operation_outputs,
        on='Num',
        how='right'
    )

    fname = f"{path_out}/{experiment_name}_operation_outputs.csv"
    operation_outputs['Experiment_Name'] = experiment_name
    operation_outputs.to_csv(fname)

    for var in ['Level', 'Salinity']:
        df = lock_object.get_results(variable=var, pivot=True, interpolate=False)
        fname = f"{path_out}/{experiment_name}_sim_{var.lower()}.csv"
        df['Experiment_Name'] = experiment_name
        df.to_csv(fname)


# Run experiments (1) - Steady-State
print("Running experiments (1) - steady state")
start_time = time.time()

## Define output folder
path_out = f"{results_dir}/1_steady_state"

## Modify template
ops_new = operations_template.loc[operations_template['Num'] <= 50, :].copy(deep=True)

## Edit the time column (every TS_LockageStarts 90 minutes after the previous one)
ops_new['TS_LockageStarts'] =  \
    ops_new['TS_LockageStarts'].iloc[0] + pd.Timedelta(minutes=90)*ops_new.index

ops_new['TS_LocksReady'] = ops_new['TS_LockageStarts']

## Loop throgh directions and vessel sizes
for direction in ['Uplockage', 'Downlockage']:
    ops_new['Direction'] = direction

    for volume in vessel_sizes:
        ops_new['Ship_Vol_Disp'] = volume*1000

        experiment_name = f'ss_{direction.lower()}_{volume}'
        
        run_simulation(
            experiment_name=experiment_name,
            df_operations=ops_new,
            path_out=path_out
            )

end_time = time.time()
total_time = end_time - start_time
print(f"\tElapsed time: {total_time:.2f} seconds")


# Run experiments (2) - cycles of daily lockages
print("Running experiments (2) - daily lockages")
start_time = time.time()

## Define output folder
path_out = f"{results_dir}/2_daily_lockages"

## Copy and modify operations template
df_operations = operations_template.copy(deep=True)

## Define traffic order directory
traffic_order = {
    "original": ['Uplockage']*6 + ['Downlockage']*6,
    "reverse": ['Downlockage']*6 + ['Uplockage']*6
}

## Loop trough traffic order
for order, direction_list in traffic_order.items():
    df_operations['Direction'] = direction_list*5 # cycle of 5 days

    for volume in vessel_sizes:
        df_operations['Ship_Vol_Disp'] = volume*1000

        experiment_name = f'daily_{order}_{volume}'
        
        run_simulation(
            experiment_name=experiment_name,
            df_operations=df_operations,
            path_out=path_out
            )

end_time = time.time()
total_time = end_time - start_time
print(f"\tElapsed time: {total_time:.2f} seconds")
        