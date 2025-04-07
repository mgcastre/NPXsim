# Elements for Panama Canal's lock model
# M. G. Castrellon | 18 March 2025

class ControlVolume:

    def __init__(self, length, width, z_bottom, H0=None, S0=None):
        self.length = length
        self.width = width
        self.z_bottom = z_bottom
        self.area = length*width
        if H0 is not None and S0 is not None:
            self.add_initial_conditions(H0, S0)
    
    def add_initial_conditions(self, H0, S0):
        V0 = (H0 - self.z_bottom)*self.area
        self.water_volume = [V0]
        self.water_level = [H0]
        self.salinity = [S0]
        self.time = [0] # minutes
    
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

    def update_status(self, V, S, H, ts):
        self.time.append(ts) # minutes
        self.water_level.append(H)
        self.water_volume.append(V)
        self.salinity.append(S)
    
    def record_current_status(self, ts):
        H = self.get_current_level()
        V, S = self.get_current_status()
        self.update_status(V=V, S=S, H=H, ts=ts)
    
    def _drain(self, H_final, ts):
        V_final = (H_final - self.z_bottom)*self.area
        # Although water level changes, salinity remains constant
        self.update_status(V=V_final, S=self.salinity[-1], H=H_final, ts=ts)
    
    def _fill(self, H_final, S_lift, ts):
        V_init, S_init = self.get_current_status()
        dH = H_final - self.water_level[-1]
        V_lift = dH*self.area
        V_final = V_init + V_lift
        S_final = (V_lift*S_lift + V_init*S_init) / V_final
        self.update_status(V=V_final, S=S_final, H=H_final, ts=ts)
    
    def get_results_dictionary(self):
        results = {
            'Time': self.time,
            'Volume': self.water_volume,
            'Level': self.water_level,
            'Salinity': self.salinity
        }
        return results


class LockChamber(ControlVolume):
    
    def __init__(self, length, width, z_bottom, H0=None, S0=None):
        super().__init__(length, width, z_bottom, H0, S0)
    
    def change_length(self, new_length):
        self.length = new_length
    
    def add_ship(self, V_ship):
        self.V_ship = V_ship
    
    def drain_chamber(self, H_final, ts):
        super()._drain(H_final=H_final, ts=ts)
    
    def fill_chamber(self, H_final, S_lift, ts):
        super()._fill(H_final=H_final, S_lift=S_lift, ts=ts)
    
    def ship_enters(self, V_lhs, S_lhs, ts):
        V_init, S_init = super().get_current_status()
        V_final = V_init - self.V_ship
        S_final = (S_init*(V_init - V_lhs - self.V_ship) + V_lhs*S_lhs) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        super().update_status(V=V_final, S=S_final, H=self.water_level[-1], ts=ts)
    
    def ship_leaves(self, V_rhs, S_rhs, ts):
        V_init, S_init = super().get_current_status()
        V_final = V_init + self.V_ship
        S_final = (S_init*(V_init - V_rhs) + S_rhs*(V_rhs + self.V_ship)) / V_final
        # Although volume of water gets exchanged, the water level remains constant
        super().update_status(V=V_final, S=S_final, H=self.water_level[-1], ts=ts)


class WaterSavingBasin(ControlVolume):

    def __init__(self, length, width, z_bottom, H0=None, S0=None):
        super().__init__(length, width, z_bottom, H0, S0)
    
    def drain_basin(self, H_final, ts):
        super()._drain(H_final=H_final, ts=ts)
    
    def fill_basin(self, H_final, S_lift, ts):
        super()._fill(H_final=H_final, S_lift=S_lift, ts=ts)