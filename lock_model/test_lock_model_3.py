# Testing lock model (3)
# M. G. Castrellon 
# 24 September 2024

# %%

# Load libraries
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Set the working directory
os.chdir("D:/SURFdrive/Projects/Conceptual_Model")

# Load custom modules
sys.path.append("src/model/lock_model")
from lock_model import *

# %%

# Create Agua Clara lock object

## Define lock sills and bottom elevations
lock_head_sills_ac = {'LH1': 6.40, 'LH2': -1.99, 'LH3': -10.35, 'LH4': -18.69}
lock_bottom_ac = {'LC': -18.69, 'MC': -10.35, 'UC': -1.99}

## Create NPX lock object
AguaClara = ThreeStepLock(
    lock_length = 458, # m
    lock_width = 55, # m
    lock_bottom_elevs = lock_bottom_ac,
    lock_head_sills = lock_head_sills_ac,
)

# %%

# Define initial and boundary conditions

## Boundary conditions
boundary_conditions = {
    'H_ocean': 0.11, 'H_lake': 25.9,
    'S_ocean': 31.5, 'S_lake': 0.75,
}

## Define initial salinities
initial_salinities = {'LC': 0.05, 'MC': 0.05, 'UC': 0.05}

## Calculate lock chamber operational levels
H_lake = boundary_conditions['H_lake']
H_ocean = boundary_conditions['H_ocean']
levels = AguaClara.calc_operational_levels(H_lake, H_ocean)
for key, values in levels.items():
    print(f"Operational levels for {key}: {values}")

# %%

# Define function to run multiple uplockages and downlockages

def run_multiple_lockages(V_ship, direction, tOpen, n_lockages=25):

    ## Define dictionary of lock opening times
    time_open_dict = {}
    for key in lock_head_sills_ac.keys():
        time_open_dict[key] = tOpen*60 # seconds

    ## Add initial conditions
    AguaClara.initialize(
        boundary_conditions=boundary_conditions,
        salinities=initial_salinities, 
        direction=direction
    )

    ## Perform lockages
    for i in range(0, n_lockages):
        AguaClara.transit(
            V_ship=V_ship,
            direction=direction,
            t_open_dict=time_open_dict,
            boundary_conditions=boundary_conditions,
        )

    ## Extract salinities and salt mass load
    salinities = AguaClara.get_salinities()
    salt_mass_load = AguaClara.get_salt_load()

    ## Calculate average salinity in each chamber
    avg_salinity = {}
    for key, array in salinities.items():
        salinity = array[1:] # remove initial condition
        avg_salinity[key] = sum(salinity)/len(salinity)
    
    ## Extract the final salt mass loads
    final_sml = {}
    for key, array in salt_mass_load.items():
        final_sml[key] = array[-1]

    # Return dictionary
    parameters = {'V_ship': V_ship, 'tOpen': tOpen}
    result_dict = {**parameters, **avg_salinity, **final_sml}
    return result_dict

#%%

# Experiment 1: Varying ship volume

## Define average chamber size
A = 55*458 # m2
h = 25.9 + 1.99 # m
avg_chamber_volume = A*h

## Define ship volume
V_ship_max = 0.8*avg_chamber_volume
# V_ship_max = 500000 # (490888.84 m3)
ship_volume_array = np.linspace(0, V_ship_max, 100)

## Define lock opening time
tOpen = 18 # minutes
# tOpen = 0 # minutes

## Define results dictionary
results1 = {'up': {}, 'down': {}}

## Run lockages
for direction in ['up', 'down']:
    for V_ship in ship_volume_array:
        volume_fraction = V_ship / avg_chamber_volume
        result_dict = run_multiple_lockages(V_ship, direction, tOpen)
        result_dict['Volume_Fraction'] = V_ship / avg_chamber_volume
        for key, value in result_dict.items():
            if key not in results1[direction].keys():
                results1[direction][key] = []
            results1[direction][key].append(value)
    results1[direction] = pd.DataFrame(results1[direction])

# %%

# Visualize results from experiment 1

## Plot salinity
y_columns = ['LC', 'MC', 'UC']
colors = ['royalblue', 'green', 'darkorange']
fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
for i, key in enumerate(['up', 'down']):
    results1[key].plot(ax=ax[i],  x='Volume_Fraction', y=y_columns,
                       style='-o', ms=5, alpha=0.8, color=colors)
    ax[i].set_title(f"Salinity in lock chambers during {key}lockages")
    ax[i].set_xlabel('Fraction of chamber volume displaced by vessel')
    ax[i].set_ylabel('Salinity (PSU)')
    ax[i].legend(loc='upper left')
    ax[i].set_xlim(0, 0.8)
plt.show()

## Plot salt mass load
y_columns = ['DC', 'VD', 'Total']
colors = ['navy', 'maroon', 'magenta']
fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
for i, key in enumerate(['up', 'down']):
    results1[key].plot(ax=ax[i], x='Volume_Fraction', y=y_columns,
                       style='-o', ms=5, alpha=0.8, color=colors)
    ax[i].set_title(f"Salt mass load during {key}lockages")
    ax[i].set_xlabel('Fraction of chamber volume displaced by vessel')
    ax[i].set_ylabel('Salt mass load (tonnes)')
    ax[i].legend(loc='upper left')
    ax[i].set_xlim(0, 0.8)
plt.show()

# %%

# Run Experiment 2: Varying gate opening time

## Define mean ship volume
V_ship = 61350.5 # m3
# V_ship = 0 # m3

## Define lock gate opening times
open_time_array = np.arange(5, 46, 1)

## Define results dictionary
results2 = {'up': {}, 'down': {}}

## Run lockages
for direction in ['up', 'down']:
    for tOpen in open_time_array:
        result_dict = run_multiple_lockages(V_ship, direction, tOpen)
        for key, value in result_dict.items():
            if key not in results2[direction].keys():
                results2[direction][key] = []
            results2[direction][key].append(value)
    results2[direction] = pd.DataFrame(results2[direction])

# %%

# Visualize results from experiment 2

## Plot salinity
y_columns = ['LC', 'MC', 'UC']
colors = ['royalblue', 'green', 'darkorange']
fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
for i, key in enumerate(['up', 'down']):
    results2[key].plot(ax=ax[i],  x='tOpen', y=y_columns,
                       style='-o', ms=5, alpha=0.8, color=colors)
    ax[i].set_title(f"Salinity in lock chambers during {key}lockages")
    ax[i].set_xlabel('Gate opening time (minutes)')
    ax[i].set_ylabel('Salinity (PSU)')
    ax[i].legend(loc='upper left')
    # ax[i].set_xlim(0, 0.8)
plt.show()

## Plot salt mass load
y_columns = ['DC', 'VD', 'Total']
colors = ['navy', 'maroon', 'magenta']
fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
for i, key in enumerate(['up', 'down']):
    results2[key].plot(ax=ax[i], x='tOpen', y=y_columns,
                       style='-o', ms=5, alpha=0.8, color=colors)
    ax[i].set_title(f"Salt mass load during {key}lockages")
    ax[i].set_xlabel('Gate opening time (minutes)')
    ax[i].set_ylabel('Salt mass load (tonnes)')
    ax[i].legend(loc='upper left')
    # ax[i].set_xlim(0, 0.8)
plt.show()
# %%
