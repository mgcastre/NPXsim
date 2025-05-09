# Quick test for lock model objects
# M. G. Castrellon 
# 18 March 2025

# %%

# Load libraries
import os
import sys
import matplotlib.pyplot as plt

# Set the working directory
os.chdir("D:/SURFdrive/Projects/Conceptual_Model")

# Load custom modules
sys.path.append("src/model/lock_model")
import hydrodynamics as hd
from lock_model import LockChamber
# %%

# Initialize class and change length
upper_chamber = LockChamber(length=300, width=35, z_bottom=11.37, H0=22, S0=1.0)
upper_chamber.change_length(305)


# %%

# Perform one lock cycle (downlockage):
upper_chamber.add_ship(V_ship=300*30*12)
upper_chamber.fill_chamber(H_final=25.5, S_lift=0.5, t_min=10)
V_ex = 0.25*upper_chamber.water_volume[-1]
upper_chamber.ship_enters(V_lhs=V_ex, S_lhs=0.5, t_min=25)
upper_chamber.drain_chamber(H_final=24, t_min=35)
upper_chamber.ship_leaves(V_rhs=V_ex, S_rhs=3.5, t_min=50)
# %%

plt.plot(upper_chamber.time, upper_chamber.salinity)
plt.show()
# %%
