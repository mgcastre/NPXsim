# Script for Panama Canal's Lock Model
# M. G. Castrellon | 2 September 2024

# Required Libraries
import numpy as np
import hydrodynamics as hd

# Define classes

class LockTransfer:
    """
    Class to calculate salt mass intrusion through the locks using
    estimates or measurements of salinity at the upper lock chamber
    of the Panamax and Neo-Panamax Locks.

    Inputs for class initialization:
    
    prop: Dictionary for lock properties. It requires 
    the following keys:
        'DimPax': Dimensions of a Panamax lock chambers in meters (L, W, H).
        'DimNeo': Dimensions of a Neo-Panamax lock chambers in meters (L, W, H).
        'RhoGL_AguaClara': Average water density of Gatun Lake right outside Agua Clara (kg/m3).
        'RhoGL_Cocoli': Average water density of Gatun Lake right outside Cocoli (kg/m3).
        'RhoGL_Gatun': Average water density of Gatun Lake right outside Gatun (kg/m3).
        'RhoGL_PedroMiguel': Average water density of Miraflores Lake right outside Pedro Miguel (kg/m3).
    
    params: Dictionary with static model parameters. It requires 
    the following keys:
        'omega_ac' - Fraction of ocean salinity for the Agua Clara locks
        'omega_cc' - Fraction of ocean salinity for the Cocoli locks
        'omega_gt' - Fraction of ocean salinity for the Gatun locks
        'omega_pm' - Fraction of ocean salinity for the Pedro Miguel locks

    df: A data frame containing time series of inflows, outflows and
    input salinity. It requires the following columns:
        'Transits_NeoPanamax' - Number of NeoPanamax transits (#/day)
        'Transits_Panamax' - Number of Panamax transits (#/day)
        'S_Atlantic_Ocean' - Salinity of the Atlantic Ocean (PSU)
        'S_Pacific_Ocean' - Salinity of the Pacific Ocean (PSU)
        'S_Miraflores' - Salinity of the Miraflores Lake (PSU)
    """
    
    # Initialize the class
    def __init__(self, prop, params, df):
        self.prop = prop # Lake/lock properties
        self.params = params # Model parameters
        self.df = df # Data frame with time series data
        self.unpack_lock_dimensions() # Unpack lock dimensions
        self.unpack_densities() # Unpack Gatun Lake densities
        self.calc_lock_density() # Calculate lock densities
    
    # Unpacl Gatun Lake densities
    def unpack_densities(self):
        self.Rgl_ac = self.prop['RhoGL_AguaClara']
        self.Rgl_cc = self.prop['RhoGL_Cocoli']
        self.Rgl_gt = self.prop['RhoGL_Gatun']
        self.Rgl_pm = self.prop['RhoGL_PedroMiguel']

    # Unpack dimensions of lock chambers
    def unpack_lock_dimensions(self):
        self.LNeo = self.prop['DimNeo'][0]
        self.Lpax = self.prop['DimPax'][0]
        self.Wneo = self.prop['DimNeo'][1]
        self.Wpax = self.prop['DimPax'][1]
        self.Hneo = self.prop['DimNeo'][2]
        self.Hpax = self.prop['DimPax'][2]
    
    # Calculate salinity in lock chambers
    def calc_lock_salinity(self):
        Cac = self.params['omega_ac'] * self.df['S_Atlantic_Ocean'].to_numpy()
        Cgt = self.params['omega_gt'] * self.df['S_Atlantic_Ocean'].to_numpy()
        Ccc = self.params['omega_cc'] * self.df['S_Pacific_Ocean'].to_numpy()
        Cpm = self.params['omega_pm'] * self.df['S_Miraflores'].to_numpy()
        return Cac, Ccc, Cgt, Cpm

    # Calculate density in lock chambers
    def calc_lock_density(self):
        Densities = []
        Salinities = self.calc_lock_salinity()
        Temperature = self.df['Temperature'].to_numpy()
        for salt in enumerate(Salinities):
            Densities.append(hd.Rho_from_PSU(Salt=salt, Temp=Temperature))
        ## Extract in this order: Rac, Rcc, Rgt, Rpm
        self.Rac, self.Rcc, self.Rgt, self.Rpm = Densities
    
    # Calculate lock exchange coefficients
    def calc_exchange_coefficients(self):
        tPax = self.prop['tOpen_Panamax']
        tNeo = self.prop['tOpen_NeoPanamax']
        Eac = hd.exchange_coefficient(rho1=self.Rgl_ac, rho2=self.Rac, H=self.Hneo, L=self.LNeo, tOpen=tNeo)
        Ecc = hd.exchange_coefficient(rho1=self.Rgl_cc, rho2=self.Rcc, H=self.Hneo, L=self.LNeo, tOpen=tNeo)
        Egt = hd.exchange_coefficient(rho1=self.Rgl_gt, rho2=self.Rgt, H=self.Hpax, L=self.Lpax, tOpen=tPax)
        Epm = hd.exchange_coefficient(rho1=self.Rgl_pm, rho2=self.Rpm, H=self.Hpax, L=self.Lpax, tOpen=tPax)
        return Eac, Ecc, Egt, Epm

    # Calculate salt mass flux in due to density currents
    def calc_salt_flux_in(self):
        ## Get number of transits
        Nneo = self.df['Transits_NeoPanamax'].to_numpy()
        Npax = self.df['Transits_Panamax'].to_numpy()
        ## Calculate lock exchange coefficients
        Eac, Ecc, Egt, Epm = self.calc_exchange_coefficients()
        ## Calculate volume of lock chambers
        Vneo = self.LNeo * self.Wneo * self.Hneo
        Vpax = self.Lpax * self.Wpax * self.Hpax
        ## Calculate net salt mass flux in (kg/day)
        flux_ac = Nneo * (self.Rac - self.Rgl_ac) * Eac * Vneo
        flux_cc = Nneo * (self.Rcc - self.Rgl_cc) * Ecc * Vneo
        flux_gt = Npax * (self.Rgt - self.Rgl_gt) * Egt * Vpax
        flux_pm = Npax * (self.Rpm - self.Rgl_pm) * Epm * Vpax
        return flux_ac, flux_cc,  flux_gt, flux_pm