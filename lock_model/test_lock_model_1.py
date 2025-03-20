# Testing lock model (1)
# M. G. Castrellon 
# 2 September 2024

# %%

# Load libraries
import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Set the working directory
os.chdir("D:/SURFdrive/Projects/Conceptual_Model")

# Load custom modules
sys.path.append("src/model/lock_model")
from lock_model import *

# %%

# Define lock sills and bottom elevations
lock_head_sills_ac = {'LH1': 6.40, 'LH2': -1.99, 'LH3': -10.35, 'LH4': -18.69}
lock_bottom_ac = {'LC': -18.69, 'MC': -10.35, 'UC': -1.99}

# Create NPX lock object
AguaClara = ThreeStepLock(
    lock_length = 458, # m
    lock_width = 55, # m
    lock_bottom_elevs = lock_bottom_ac,
    lock_head_sills = lock_head_sills_ac,
)

# %%

# Define constants

## Calculate ship volume
s_length = 275 # m
s_width = 30 # m
s_draft = 10 # m
block_coeff = 0.75 # unitless
V_ship = s_length*s_width*s_draft*block_coeff # m3

## Define dictionary of lock opening times
time_open_dict = {}
for key in lock_head_sills_ac.keys():
    time_open_dict[key] = 23*60 # seconds

## Define boundary conditions dictionary
boundary_conditions = {
    'H_ocean': 0.11, 'H_lake': 25.9,
    'S_ocean': 19, 'S_lake': 0.5,
}

## Define initial salinities
salinities = {'LC': 0, 'MC': 0, 'UC': 0}

# %%

# Run lockages

## Add initial conditions
AguaClara.initialize(
    boundary_conditions=boundary_conditions,
    salinities=salinities, 
    direction='down'
)

## Perform uplockages
for i in range(0, 25):
    AguaClara.transit_down(
        V_ship=0, 
        t_open_dict=time_open_dict,
        boundary_conditions=boundary_conditions
    )

# %%

# View results (water level and salinity)

## Pick colors
colors = ['royalblue', 'green', 'darkorange']

## Plot simulated water level in lock chambers
y_top = [9.38, 18.28, 27.13]
y_bottom = [-0.39, 7.95, 16.31]
for i, ch in enumerate(['LC', 'MC', 'UC']):
    water_level = AguaClara.chambers[ch].water_level
    plt.plot(water_level, label=ch, color=colors[i], alpha=1.0)
    plt.axhline(y=y_top[i], linestyle='-.', color=colors[i], alpha=0.5)
    plt.axhline(y=y_bottom[i], linestyle='-.', color=colors[i], alpha=0.5)
plt.title('Water level in lock chambers')
plt.ylabel('Water level (m)')
plt.legend(loc='upper left')
plt.ylim(-2, 30)
plt.show()

## Plot simulated salinity in lock chambers
for i, ch in enumerate(['LC', 'MC', 'UC']):
    plt.plot(AguaClara.chambers[ch].salinity, label=ch, color=colors[i])
plt.title('Salinity in lock chambers')
plt.ylabel('Salinity (PSU)')
plt.legend(loc='upper left')
plt.show()

## Calculate average salinity in lock chambers
for chamber in ['LC', 'MC', 'UC']:
    salinity = AguaClara.chambers[chamber].salinity
    salinity = salinity[1:] # remove initial condition
    avg_salinity = sum(salinity)/len(salinity)
    print(f"Average salinity in {chamber}: {avg_salinity:0.2f} PSU")


# %%

# View results (salt mass load)

## Extract salt mass load data
salt_mass_load = AguaClara.get_salt_load(Units='ton', Dictionary=True)
x = range(1, len(salt_mass_load['Total'])+1)

## Plot salt mass load data
colors = ['navy', 'maroon', 'magenta']
for i, key in enumerate(salt_mass_load.keys()):
    plt.plot(x, salt_mass_load[key], label=key, alpha=1.0,
             marker='o', linestyle='--', color=colors[i])
plt.title('Salt load per lockage')
plt.ylabel('Salt mass load (tonnes)')
plt.xlabel('Number of lockages')
plt.legend(loc='upper left')
plt.show()

## Print salt mass load data
for key, values in salt_mass_load.items():
    print(f"Salt mass load ({key}): {values[-1]:0.2f} tonnes." )

# %%
