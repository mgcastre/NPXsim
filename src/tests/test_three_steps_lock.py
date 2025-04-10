# Testing lock model (4)
# M. G. Castrellon 
# 25 January 2025

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
from classes.three_steps_lock import ThreeStepsLock

# Define output figure directory
output_dir = "./outputs/figures/lock_model/"

# %%

# Prepare model input data and observations

## Define time period for simulation (downlockages)
# start = '2023-10-11 10:00:00'
# end = '2023-10-11 20:00:00'

## Define time period for simulation (uplockages)
# start = '2023-11-03 23:00:00'
# end = '2023-11-04 10:00:00'
                          
## Define time period to test turnaround time (1)
# start = '2023-10-31 08:00:00'
# end = '2023-10-31 14:00:00'

## Define time period to test turnaround time (2)
# start = '2023-10-19 06:00:00'
# end = '2023-10-19 12:00:00'

## Define time period to test turnaround time (3)
start = '2023-10-19 18:00:00'
end = '2023-10-20 06:00:00'

## Define time period to test long sequence of lockages
# start = '2023-10-31 00:00:00'
# end = '2023-11-01 20:00:00'

## Load model input data and observations
obs_salinities_avg = pd.read_feather("./data/mean_salinity_1min.ftr")
obs_salinities_btm = pd.read_feather("./data/bottom_salinity_1min.ftr")
lock_operations = pd.read_csv("./data/op_params_and_bcs.csv")

## Filter lock operations and calculate inital time
lock_operations = hf.filter_date_range(lock_operations, start, end, date_col='TS_LockageStarts')
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

## Define lock sills and bottom elevations
lock_head_sills_ac = {'LH1': 6.40, 'LH2': -1.99, 'LH3': -10.35, 'LH4': -18.69}
cham_bottom_ac = {'LC': -18.69, 'MC': -10.35, 'UC': -1.99}

## Define lock operating limits
cham_op_limits = {'LC': (-0.39, 9.38), 'MC': (7.95, 18.28), 'UC': (16.31, 27.13)}

## Create NPX lock object
AguaClara = ThreeStepsLock(
    lock_length = 430, # m
    lock_width = 55, # m
    cham_bottom_elevs = cham_bottom_ac,
    lock_head_sills = lock_head_sills_ac,
    operating_limits = cham_op_limits,
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

# Plot simulated and observed salinity in lock chambers

## Pick colors
colors = ['royalblue', 'green', 'darkorange']

## Extract simulated results
sim_salinities = AguaClara.get_salinities()

## Calculate mean observed salinities every 15 minutes
obs_salinities_5min = obs_salinities_btm.resample('5min').mean()

## Plot simulated and observed salinities in lock chambers
my_colors = ['darkorange', 'green', 'royalblue']
lock_times = lock_operations['TS_LockageStarts'].tolist()
pf.plot_salinities(obs=obs_salinities_5min, sim=sim_salinities, lock_times=lock_times,
                    xlims=[start, end], ylims=[0, 30], reservoirs='Chambers', colors=my_colors, 
                    styles={'Sim': '-', 'Obs': 'o'}, figsize=(11, 5), return_fig=False)

## Saving figure
# fig_name = 'sim_vs_obs_chamber_salinity.png'
# fig.savefig(output_dir+fig_name, bbox_inches='tight', dpi=300)

# %%

# Plot simulated and observed water levels in lock chambers

## Extract simulated water levels for upper chamber
sim_water_levels = AguaClara.get_water_levels()
sim_water_levels.ffill(inplace=True)

## Pick colors
colors = ['royalblue', 'green', 'darkorange']

## Define water level operating limits
H_max = [9.38, 18.28, 27.13]
H_min = [-0.39, 7.95, 16.31]

## Initializa plot
fig, ax = plt.subplots(figsize=(10, 5))
ax.set_title('Simulated and observed water level in lock chambers')
## Plotting obs water levels
obs_water_levels.plot(
    ax=ax, color='darkorange', marker='o', 
    linestyle='', alpha=1.0)
## Plotting sim water levels
sim_water_levels.plot(
    ax=ax, color=colors, marker='', 
    linestyle='-', alpha=0.8)
## Plotting operational water levels
for i, chamber in enumerate(['UC', 'MC', 'LC']):
    ax.axhline(y=H_max[i], linestyle='--', 
               color=colors[i], alpha=0.3, 
               label=chamber)
    ax.axhline(y=H_min[i], linestyle='--', 
               color=colors[i], alpha=0.3, 
               label=None)
## Formatting x-axis
ax.set_xlabel('Time')
ax.set_xlim(start, end)
date_form = mdates.DateFormatter("%H:%M")
ax.xaxis.set_major_formatter(date_form)
ax.xaxis.set_tick_params(rotation=0)
for label in ax.get_xticklabels():
    label.set_horizontalalignment('center')
## Formatting legend
lines, labels = ax.get_legend_handles_labels()
leg1 = ax.legend([lines[0]], [labels[0]], frameon=False, loc='upper right',
                 bbox_to_anchor=(1.13, 1.0), title='Observed',)
leg2 = ax.legend(lines[1:4], labels[1:4], frameon=False, loc='upper right',
                 bbox_to_anchor=(1.13, 0.77), title='Simulated')
leg3 = ax.legend(lines[4:7], labels[4:7], frameon=False, loc='upper right',
                 title='Operational \n water levels',
                 bbox_to_anchor=(1.15, 0.4))
legs = [leg1, leg2, leg3]
for leg in legs:
    ax.add_artist(leg)
    leg.set_in_layout(True)
## Formatting y-ax1s
plt.ylabel('Water level (m)')
plt.ylim(-2, 28)
## Displaying plot
plt.show()

## Saving figure
# fig_name = 'sim_vs_obs_water_levels.png'
# fig.savefig(output_dir+fig_name, bbox_inches='tight', dpi=300)
# %%
