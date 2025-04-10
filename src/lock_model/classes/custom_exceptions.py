# Custom error messages for lock model
# M. G. Castrellon | 10 April 2025

class EmptyReservoirError(ValueError):
    """Exception raised when the reservoir water level is below its bottom."""
    def __init__(self, Hf, z_bottom, res_name):
        message = (
            f"Equalization level ({Hf:0.2f} m) below {res_name} bottom "
            f"elevation ({z_bottom:0.2f} m)."
        )
        super().__init__(message)

class ReservoirOverflowError(ValueError):
    """Exception raised when the reservoir water level is above its top."""
    def __init__(self, Hf, z_top, res_name):
        message = (
            f"Equalization level ({Hf:0.2f} m) above top wall of "
            f"{res_name} ({z_top:0.2f} m)."
        )
        super().__init__(message)

class WaterLevelError(ValueError):
    """Exception raised when the reservoir water level is outside its operating range."""
    def __init__(self, Hf, H_min, H_max, res_name):
        message = (
            f"Water level after equalization in {res_name} ({Hf:0.2f} m) "
            f"is outside its operating range of ({H_min:0.2f}, {H_max:0.2f})."
        )
        super().__init__(message)