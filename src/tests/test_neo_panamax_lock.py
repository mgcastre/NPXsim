# Testing lock model (5)
# M. G. Castrellon 
# 18 March 2025

# %%

# Load libraries
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set the working directory
os.chdir("D:/SURFdrive/Projects/Lock_Model")

# Load custom modules
sys.path.append("./src/lock_model")
import utilities.helper_functions as hf
import utilities.plotting_functions as pf
from classes.neo_panamax_lock import NeoPanamaxLock

# Define input and output dir
output_dir = "./outputs/"
input_dir = "./data/processed/"

# %%

# Prepare model input data and observations

## Define time period to test WSBs (downlockages)
# start = '2023-10-23 10:00:00'
# end = '2023-10-23 22:00:00'

## Define time period to test WSBs (uplockage)
# start = '2023-10-18 23:00:00'
# end = '2023-10-19 10:00:00'

## Define time period to test turnaround time (1)
# start = '2023-10-19 06:00:00'
# end = '2023-10-19 12:00:00'

## Define time period to test turnaround time (2)
start = '2023-10-19 18:00:00'
end = '2023-10-20 06:00:00'

## Define time period to test long sequence of lockages (1)
# start = '2023-10-31 00:00:00'
# end = '2023-11-01 20:00:00'

## Define time period to test long sequence of lockages (2)
# start = '2023-10-18 23:00:00'
# end = '2023-10-19 21:00:00'

## Load model input data and observations
obs_salinities_avg = pd.read_feather(input_dir+"salinity_avg_1min.ftr")
obs_salinities_btm = pd.read_feather(input_dir+"salinity_btm_1min.ftr")
lock_operations_all = pd.read_csv(input_dir+"op_params_and_bcs.csv")

## Filter lock operations and calculate inital time
lock_operations = hf.filter_date_range(lock_operations_all, start, end, date_col='TS_LockageStarts')
initial_time = str(lock_operations['TS_LockageStarts'].iloc[0])

## Prepare observed salinities and extract initial salinities
obs_salinities_avg = hf.prepare_obs_salinities(obs_salinities_avg, start, end)
obs_salinities_btm = hf.prepare_obs_salinities(obs_salinities_btm, start, end)
initial_salinities = hf.extract_initial_salinities(obs_salinities_avg, initial_time)

## Prepare boundary conditions and operation parameters
boundary_conditions = hf.prepare_boundary_conditions(lock_operations)
operation_params = hf.prepare_operation_parameters(lock_operations)

## Extract observed water levels
obs_water_levels = hf.extract_obs_water_levels(lock_operations, filling_time=10)

# %%

# Create Agua Clara lock object

## Read design specifications and parse them
ds_acll = pd.read_csv("./data/external/acll_design_specifications.csv", sep=';')
lhs, cham_params, wsb_params = hf.parse_design_specifications(ds_acll)

## Create NPX lock object
AguaClara = NeoPanamaxLock(
    wsb_dims = {'L': 435, 'W': 65}, lock_head_sills = lhs, 
    cham_elevs = cham_params['Z'], wsb_elevs = wsb_params['Z'],
    chamber_operating_limits = cham_params['H'], 
    wsb_operating_limits = wsb_params['H'],
)

# %%

# Operate locks

## Add initial conditions
AguaClara.set_initial_conditions(
    direction=operation_params[0]['Direction'],
    boundary_conditions=boundary_conditions[0],
    operation_start_dt=initial_time,
    salinities=initial_salinities, 
)

## Operate a series of lockages
AguaClara.operate(operation_params, boundary_conditions)

# %%

# Plot simulated and observed water levels

## Extract simulated water level in each chamber and basin
sim_levels = AguaClara.get_water_levels()
sim_levels = sim_levels[sorted(sim_levels.columns, reverse=True)]

## Extract lock operations times
lock_times = lock_operations['TS_LockageStarts'].tolist()

## Define colors, linestyles and markers
my_colors = ['darkorange', 'green', 'royalblue']

## Make plot
end = sim_levels.index[-1]
pf.plot_water_levels(sim_levels, lock_times, start, end, figsize=(11, 5),
                     colors=my_colors, linestyles=['-', '--', '-.', ':'],
                     return_fig=False)

## Saving figure
# fig_name = 'sim_vs_obs_water_levels.png'
# fig.savefig(output_dir+fig_name, bbox_inches='tight', dpi=300)

# %%

# Plot simulated and observed salinities

## Extract simulated water level in each chamber and basin
sim_salinities = AguaClara.get_salinities()
sim_salinities = sim_salinities[sorted(sim_salinities.columns, reverse=True)]

## Calculate mean observed salinities every 15 minutes
obs_salinities_5min = obs_salinities_avg.resample('5min').mean()

## Rename columns to match simulated salinities
for x in ['U', 'M', 'L']:
    obs_salinities_5min.rename(columns={f'{x}B': f'{x}BInt'}, inplace=True)

## Plot salinities in chambers and intermediate basins
for res in ['Chambers', 'Basins']:
    pf.plot_salinities(obs=obs_salinities_5min, sim=sim_salinities, lock_times=lock_times,
                       xlims=[start, end], ylims=[0, 30], reservoirs=res, colors=my_colors, 
                       styles={'Sim': '-', 'Obs': 'o'}, figsize=(11, 5), return_fig=False)

## Saving figure
# fig_name = 'sim_vs_obs_chamber_salinity.png'
# fig.savefig(output_dir+fig_name, bbox_inches='tight', dpi=300)
# %%

# Save simulation results (not interpolated)
AguaClara.get_water_levels(pivot=True).to_csv("./outputs/simulated_water_levels.csv")
AguaClara.get_salinities(pivot=True).to_csv("./outputs/simulated_salinities.csv")