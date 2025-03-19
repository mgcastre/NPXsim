# Script for hydrodynamic functions
# M. G. Castrellon | 30 May 2024

# Load libraries
import gsw
import numpy as np

# Define functions

def Rho_from_PSU(Salt, Temp, method='FullGibbs2010'):
    """
    Calculates the density of water given salinity (expressed in the practical scale) and temperature (degrees C).
    Two methods can be used to calculate the density of water: Millero and Poisson (1981) or the full TEOS-10 Gibbs function. 
    For Millero and Poisson (1981), the function was copied from the formulation that appears on the website:
    <https://www.translatorscafe.com/unit-converter/en-US/calculator/salt-water-density/#definitions-And-formulas>.
    For the full TEOS-10 Gibbs function, the Gibbs-SeaWater (GSW) Oceanographic Toolbox, implemented in the GSW-Python 
    library, was used.
    Inputs for this function are:
    - Salt: Salinity of the water (PSU)
    - Temp: Temperature of the water (Celsius)
    - method: FullGibbs2010 (default) or 'MilleroPoisson1981'.
    Outputs for this function are:
    - rho: Density of the water (kg/m3)
    """	
    
    if method == 'MilleroPoisson1981':
        ## Calculate reference density
        rho_0 = 999.84259 + 6.793952e-02*Temp \
                - 9.095290e-03*Temp**2 + 1.001685e-04*Temp**3 \
                - 1.120083e-06*Temp**4 + 6.536332e-09*Temp**5
        ## Calculate first coefficient
        A = 8.24493e-01 - 4.0899e-03*Temp + 7.6438e-05*Temp**2 \
            - 8.2467e-07*Temp**3 + 5.3875e-09*Temp**4
        ## Calculate second coefficient
        B = -5.72466e-03 + 1.0227e-04*Temp - 1.6546e-06*Temp**2
        ## Define third coefficient
        C = 4.8314e-04
        ## Calculate density
        rho = rho_0 + A*Salt + B*Salt**(3/2) + C*Salt**2
    
    elif method == 'FullGibbs2010':
        ## Transform practical salinity to absolute salinity
        Salt = gsw.conversions.SA_from_SP(SP=Salt, p=0, lon=0, lat=0)
        ## Calculate density (using the full TEOS-10 Gibbs function)
        rho = gsw.density.rho_t_exact(SA=Salt, t=Temp, p=0)
    
    else:
        raise ValueError('The method selected is not available. Please select either "MilleroPoisson1981" or "FullGibbs2020".')
    
    ## Return value
    return rho

def PSU_from_Rho(Rho, Temp):
    """
    Transforms salinity concentration expressed in density units (kg/m3) to practical salinity units (PSU).
    Requires density (Rho) and water temperature (Temp) as arrays of the same dimensions. This function uses 
    the Gibbs-SeaWater (GSW) Oceanographic Toolbox implemented in the GSW-Python library.
    """
    SaltAbsolute = gsw.conversions.SA_from_rho(rho=Rho, CT=Temp, p=0)
    SaltPractical = gsw.conversions.SP_from_SA(SaltAbsolute, p=0, lon=0, lat=0)
    return SaltPractical

def density_velocity(rho1, rho2, H, g=9.81):
    """
    Calculates velocity of a density current accordingto Benjamin (1968).
    Inputs for this function are:
    - rho1: Density of the lighter fluid (kg/m3)
    - rho2: Density of the heavier fluid (kg/m3)
    - H: Depth of the water column in the lock chamber (m)
    - g: Acceleration due to gravity (m/s2) (default = 9.81 m/s2)
    """	
    gamma = rho1/rho2 # Density ratio
    U = 0.5*np.sqrt(g*H*(1-gamma)/gamma)
    return U


def exchange_coefficient(rho1, rho2, H, L, tOpen, eta=0.8):
    """
    Calculates the exchange coefficient for a lock chamber.
    Inputs for this function are:
    -  rho1: Density of the lighter fluid (kg/m3)
    - rho2: Density of the heavier fluid (kg/m3)
    - H: Depth of the water column in the lock chamber (m)
    - L: Length of the lock chamber (m)
    - tOpen: Time the lock chamber gate is open (s)
    - eta: Correction factor that takes into account intrusion reduction measures (default = 0.8)
    """	
    U = density_velocity(rho1, rho2, H, g=9.81) # Velocity of the density current
    tLE = 2 * (L/U) # Theoretical time for full lock exchange
    e_coeff = np.tanh(eta*(tOpen/tLE)) # Lock exchange coefficient
    return e_coeff

def convert_salt_concentration(S_practical, temperature):
        """
        Converts practical salinity units to salinity concentration
        in kg/m3. Requires the user to specify a temperature.
        """
        S_absolute = gsw.conversions.SA_from_SP(SP=S_practical, p=0, lon=0, lat=0)
        rho = gsw.density.rho_t_exact(SA=S_absolute, t=temperature, p=0)
        c_kg_m3 = S_absolute*rho/1000
        return c_kg_m3