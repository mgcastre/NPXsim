# Testing lock model (2)
# M. G. Castrellon 
# 12 September 2024

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
    'S_ocean': 31.5, 'S_lake': 0.50,
}

## Initial salinities
S_ocean = 31.5
S_lc = S_ocean*2/3
S_mc = S_lc*2/3
S_uc = S_mc*2/3

## Initial salinities dictionary
initial_salinities = {'LC': S_lc, 'MC': S_mc, 'UC': S_uc}
for key, value in initial_salinities.items():
    print(f"Initial salinity in {key}: {value} PSU")


# %%

# Define function to run multiple uplockages and downlockages
def run_multiple_lockages(V_ship, direction, tOpen, T, n_lockages):

    ## Define dictionary of lock opening times
    time_open_dict = {}
    for key in lock_head_sills_ac.keys():
        time_open_dict[key] = tOpen*60 # seconds

    ## Add initial conditions
    AguaClara.initialize(
        boundary_conditions=boundary_conditions,
        salinities=initial_salinities, 
        direction=direction,
        temperature=T
    )

    ## Perform lockages
    for i in range(0, n_lockages):
        AguaClara.transit(
            V_ship=V_ship,
            direction=direction,
            t_open_dict=time_open_dict,
            boundary_conditions=boundary_conditions,
        )
    
    ## Get output in a dictionary
    results = {
        'water_levels': AguaClara.get_water_levels(),
        'salinities': AguaClara.get_salinities(),
        'salt_mass_load': AguaClara.get_salt_load(),
        'V_ex': AguaClara.salt_mass_load['V_ex'],
        'S_uc': AguaClara.salt_mass_load['S_uc']
    }

    ## Return results in a dictionary
    return results

#%% 

# Run multiple lockages

## Define ship volume
V_ship = 61350.5 # m3
# V_ship = 0 # m3

## Run lockages
results_dict = {}
for direction in ['up', 'down']:
    results = run_multiple_lockages(
        V_ship=V_ship, direction=direction, 
        tOpen=20, T=29, n_lockages=15
    )
    results_dict[direction] = results


# %%

# Visualize water levels

## Pick colors
colors = ['royalblue', 'green', 'darkorange']

## Make plots
y_top = [9.38, 18.28, 27.13]
y_bottom = [-0.39, 7.95, 16.31]
for direction in ["up", "down"]:
    plt.figure(figsize=(6, 5))
    for i, ch in enumerate(['LC', 'MC', 'UC']):
        water_levels = results_dict[direction]['water_levels'][ch]
        plt.plot(water_levels, label=ch, color=colors[i], alpha=1.0)
        plt.axhline(y=y_top[i], linestyle='-.', color=colors[i], alpha=0.5)
        plt.axhline(y=y_bottom[i], linestyle='-.', color=colors[i], alpha=0.5)
    plt.title(f'Water level in lock chambers during {direction}lockage')
    plt.ylabel('Water level (m)')
    plt.legend(loc='upper left')
    plt.ylim(-2, 30)
    plt.show()

#%%

# Visualize salinities in all lock chambers

## Pick colors
colors = ['royalblue', 'green', 'darkorange']

## Plot chamber calinities
for direction in ["up", "down"]:
    plt.figure(figsize=(8, 5))
    for i, ch in enumerate(['LC', 'MC', 'UC']):
        salinities = results_dict[direction]['salinities'][ch]
        plt.plot(salinities, label=ch, color=colors[i], alpha=1.0)
    plt.title(f'Salinity in lock chambers during {direction}lockage')
    plt.ylabel('Salinity (PSU)')
    plt.xlabel('Number of lock cycles')
    plt.legend(loc='upper left')
    plt.show()

## Calculate average salinity in lock chambers
for direction in ["up", "down"]:
    print(f"\nAverage chamber salinity during {direction}lockage:")
    for ch in ['LC', 'MC', 'UC']:
        salt_list = results_dict[direction]['salinities'][ch]
        salt_list = salt_list[1:] # remove initial condition
        avg_salinity = np.mean(salt_list)
        std_salinity = np.std(salt_list)
        print(f"{ch}: {avg_salinity:0.2f} +/- {std_salinity:0.2f} PSU")

# %%

# Visualize salinity in upper chamber

# Visualize salinity in upper chamber just before lock exchange

## Pick colors
colors = ['gold', 'orangered']

## Plot salinity in upper chamber just before lock exchange
plt.figure(figsize=(8, 5))
for i, direction in enumerate(["up", "down"]):
    my_label = f"{direction.capitalize()}lockage"
    y = results_dict[direction]['S_uc']
    plt.plot(y, color=colors[i], label=my_label,
              alpha=0.8, marker='o', linestyle='--')
plt.title(f'Salinity in upper chamber just before exchange with lake')
plt.legend(loc='upper right', title='Direction')
plt.xlabel('Number of lockages')
plt.ylabel('Salinity (PSU)')
plt.show()

## Print steady-state salinity in upper chamber
print(f"Steady-state salinity in upper chamber just before lock exchange:")
for direction in ["up", "down"]:
    suc = results_dict[direction]['S_uc'][-1]
    print(f"During {direction}lockages: {suc:0.2f} PSU")

## Plot upper chamber salinities for uplockages and downlockages
plt.figure(figsize=(8, 5))
for i, direction in enumerate(["up", "down"]):
    my_label = f"{direction.capitalize()}lockage"
    y = results_dict[direction]['salinities']['UC']
    plt.plot(y, color=colors[i], label=my_label,   
             alpha=0.8, marker='o', linestyle='--', )
plt.title(f'Salinity in upper chamber for all lock cycles')
plt.legend(loc='upper right', title='Direction')
plt.xlabel('Number of lock cycles')
plt.ylabel('Salinity (PSU)')
plt.show()

# %%

# Visualize salt mass load

## Pick colors
colors = ['magenta', 'red', 'maroon']

## Plot salt mass load 
for direction in ["up", "down"]:
    plt.figure(figsize=(8, 5))
    for i, key in enumerate(['DC', 'VD', 'Total']):
        salt_mass_load = results_dict[direction]['salt_mass_load']
        plt.plot(salt_mass_load[key], label=key, color=colors[i], 
                 alpha=1.0, marker='o', linestyle='--')
    plt.title(f'Salt load per lockage during {direction}lockage')
    plt.ylabel('Salt mass load (tonnes)')
    plt.xlabel('Number of lockages')
    plt.legend(loc='upper right')
    plt.show()

## Print steady-state salt mass load
for direction in ["up", "down"]:
    salt_mass_load_dict = results_dict[direction]['salt_mass_load']
    print(f"\nSalt mass load during {direction}lockage:")
    for key, values in salt_mass_load_dict.items():
        print(f"{key}: {values[-1]:0.2f} tonnes." )

#%% 

# Visualize volume of water exchanged

## Plot volume of water exchanged
for direction in ["up", "down"]:
    plt.figure(figsize=(8, 5))
    volume_exchanged = np.array(results_dict[direction]['V_ex'])/1e6
    plt.plot(volume_exchanged, color='navy', 
             alpha=1.0,  marker='o', linestyle='--')
    plt.title(f'Volume of water exchanged witn lake during {direction}lockages')
    plt.xlabel('Number of lockages')
    plt.ylabel('Volume exchanged (hm3)')
    plt.show()

## Print steady-state volume exchanged
print(f"\nSteady-state volume exchanged with lake:")
for direction in ["up", "down"]:
    V_ex = results_dict[direction]['V_ex'][-1]/1e6
    print(f"During {direction}lockages: {V_ex:0.2f} hm3")
# %%
