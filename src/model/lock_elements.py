# Elements for Panama Canal's lock model
# M. G. Castrellon | 18 March 2025

# Required libraries
from dataclasses import dataclass

@dataclass
class LockHead:
    z_sill: float
    upper_boundary: str
    lower_boundary: str

    def get_chamber_order(self, direction):
        if direction == 'up':
            return self.lower_boundary, self.upper_boundary
        elif direction == 'down':
            return self.upper_boundary, self.lower_boundary
        else:
            raise ValueError("Direction must be either 'up' or 'down'")


class ControlVolume:

    def __init__(self, length, width, z_bottom, z_top,
                 H_min, H_max, H0=None, S0=None):
        self.length = length
        self.width = width
        self.z_top = z_top
        self.z_bottom = z_bottom
        self.area = length*width
        self.H_min = H_min
        self.H_max = H_max
        if H0 is not None and S0 is not None:
            self.add_initial_conditions(H0, S0)
  
    def add_initial_conditions(self, H0, S0):
        V0 = (H0 - self.z_bottom)*self.area
        self.water_volume = [V0]
        self.water_level = [H0]
        self.salinity = [S0]
        self.time = [0] # minutes
    
    def get_operating_limits(self):
        return self.H_min, self.H_max

    def get_dimensions(self):
        return self.length, self.width
    
    def get_current_salinity(self):
        return self.salinity[-1]
    
    def get_current_volume(self):
        return self.water_volume[-1]
    
    def get_current_level(self):
        return self.water_level[-1]
    
    def get_current_status(self):
        V = self.get_current_volume()
        S = self.get_current_salinity()
        return V, S

    def update_status(self, V, S, H, time):
        self.time.append(time) # minutes
        self.water_level.append(H)
        self.water_volume.append(V)
        self.salinity.append(S)
    
    def record_current_status(self, time):
        H = self.get_current_level()
        V, S = self.get_current_status()
        self.update_status(V=V, S=S, H=H, time=time)
    
    def _drain(self, H_final, time):
        V_final = (H_final - self.z_bottom)*self.area
        # Although water level changes, salinity remains constant
        self.update_status(V=V_final, S=self.salinity[-1], H=H_final, time=time)
    
    def _fill(self, H_final, S_lift, time):
        V_init, S_init = self.get_current_status()
        dH = H_final - self.water_level[-1]
        V_lift = dH*self.area
        V_final = V_init + V_lift
        S_final = (V_lift*S_lift + V_init*S_init) / V_final
        self.update_status(V=V_final, S=S_final, H=H_final, time=time)
    
    def get_results_dictionary(self):
        results = {
            'Time': self.time,
            'Volume': self.water_volume,
            'Level': self.water_level,
            'Salinity': self.salinity
        }
        return results


class LockChamber(ControlVolume):
    
    def __init__(self, length, width, z_bottom, z_top, H_min, H_max, H0=None, S0=None):
        super().__init__(length, width, z_bottom, z_top, H_min, H_max, H0, S0)
    
    def change_length(self, new_length):
        self.length = new_length
    
    def add_ship(self, V_ship):
        self.V_ship = V_ship
    
    def drain_chamber(self, H_final, time):
        super()._drain(H_final=H_final, time=time)
    
    def fill_chamber(self, H_final, S_lift, time):
        super()._fill(H_final=H_final, S_lift=S_lift, time=time)
    
    def ship_enters(self, V_lhs, S_lhs, time):
        V_init, S_init = super().get_current_status()
        V_final = V_init - self.V_ship
        S_final = (S_init*(V_init - V_lhs - self.V_ship) + V_lhs*S_lhs) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        super().update_status(V=V_final, S=S_final, H=self.water_level[-1], time=time)
    
    def ship_leaves(self, V_rhs, S_rhs, time):
        V_init, S_init = super().get_current_status()
        V_final = V_init + self.V_ship
        S_final = (S_init*(V_init - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        super().update_status(V=V_final, S=S_final, H=self.water_level[-1], time=time)


class WaterSavingBasin(ControlVolume):

    def __init__(self, length, width, z_bottom, z_top, H_min, H_max):
        super().__init__(length, width, z_bottom, z_top, H_min, H_max)
    
    def drain_basin(self, H_final, time):
        super()._drain(H_final=H_final, time=time)
    
    def fill_basin(self, H_final, S_lift, time):
        super()._fill(H_final=H_final, S_lift=S_lift, time=time)
