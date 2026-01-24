"""
Example for initializing and running NPXsim simulations
M. G. Castrellon | 23 January 2026
"""

# Load libraries
import time
import json
import pandas as pd

# Load npxsim model
import npxsim.utilities.helper_functions as hf
from npxsim.model.neo_panamax_lock import NeoPanamaxLock

# Load data
data_dir = "./input_data"

## Load initial conditions
initial_salinities = json.load(open(f"{data_dir}/average_salinities.json", 'r'))

## Load lock design specifications
lock_design_specs = pd.read_csv(f"{data_dir}/design_specifications_acll.csv", sep=',')

## Load operation parameters and bcs
df_operations = pd.read_csv(f"{data_dir}/operation_params_template.csv", sep=",")

## Change date format in operations template
for col in ['TS_LocksReady', 'TS_LockageStarts']:
    df_operations[col] = pd.to_datetime(df_operations[col])

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

# Run example simulation

## Parse operation parameters and boundary conditions
operation_params = hf.prepare_operation_parameters(df_operations)
boundary_conditions = hf.prepare_boundary_conditions(df_operations)

## Add initial conditions
AguaClara.set_initial_conditions(
    direction=operation_params[0]['Direction'],
    boundary_conditions=boundary_conditions[0],
    operation_start_dt=operation_params[0]['TS_LocksReady'],
    salinities=initial_salinities["ACLL"],
)

## Operate the locks
start_time = time.time()
AguaClara.operate(operation_params, boundary_conditions)
end_time = time.time()

## Print simulation time
total_time = end_time - start_time
print(f"\nTotal simulation time: {total_time:.2f} seconds")

# Post-processing of model results

## Extract model results
operation_outputs = AguaClara.get_operation_outputs()
sim_salinities = AguaClara.get_salinities(pivot=False, interpolate=False)
sim_levels = AguaClara.get_water_levels(pivot=False, interpolate=False)

## Add some operation info to results
my_columns = ['Num', 'Direction', 'TS_LockageStarts', 'WSBasins']
op_info = df_operations[my_columns].copy()

operation_outputs = pd.merge(
    op_info,
    operation_outputs,
    on='Num',
    how='right'
)

## Calculate average salt mass load per lockage per direction
df_results = operation_outputs.loc[operation_outputs['Num'] > 24, :].copy()

my_columns = ['DC_Salt_Load', 'VD_Salt_Load', 'Total_Salt_Load']
summary_statistics = df_results.groupby('Direction')[my_columns].mean()

print("\nAverage salt mass load per lockage (in UK tonnes):")
print(summary_statistics.round(0))
