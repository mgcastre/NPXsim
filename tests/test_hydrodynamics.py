"""Tests for the basic functions in hydrodynamics.py."""

import pytest

import npxsim.utilities.hydrodynamics as hd


def test_calc_equalization_level_is_area_weighted_average():
    Hf = hd.calc_equalization_level(A1=100, A2=300, H1=10, H2=20)
    assert Hf == pytest.approx((100 * 10 + 300 * 20) / (100 + 300))


def test_calc_equalization_level_matches_when_levels_are_equal():
    Hf = hd.calc_equalization_level(A1=100, A2=200, H1=15, H2=15)
    assert Hf == pytest.approx(15)


def test_density_velocity_is_zero_when_densities_are_equal():
    U = hd.density_velocity(rho1=1000, rho2=1000, H=10)
    assert U == pytest.approx(0)


def test_density_velocity_increases_with_density_difference():
    U_small_diff = hd.density_velocity(rho1=999, rho2=1000, H=10)
    U_large_diff = hd.density_velocity(rho1=980, rho2=1000, H=10)
    assert 0 < U_small_diff < U_large_diff


def test_exchange_coefficient_is_between_zero_and_one():
    Eff = hd.exchange_coefficient(rho1=1000, rho2=1025, H=10, L=300, tOpen=600)
    assert 0 < Eff < 1


def test_rho_from_psu_increases_with_salinity():
    rho_fresh = hd.Rho_from_PSU(Salt=0, Temp=28)
    rho_salty = hd.Rho_from_PSU(Salt=35, Temp=28)
    assert rho_salty > rho_fresh


def test_rho_from_psu_invalid_method_raises():
    with pytest.raises(ValueError):
        hd.Rho_from_PSU(Salt=10, Temp=28, method='NotAMethod')


def test_psu_from_rho_round_trips_with_rho_from_psu():
    salinity = 20.0
    temperature = 25.0
    rho = hd.Rho_from_PSU(Salt=salinity, Temp=temperature)
    recovered = hd.PSU_from_Rho(Rho=rho, Temp=temperature)
    # The forward/backward conversions go through different salinity scales
    # (practical vs. absolute), so the round trip is only approximate.
    assert recovered == pytest.approx(salinity, rel=0.02)


def test_convert_salt_concentration_is_positive_and_scales_with_salinity():
    c_low = hd.convert_salt_concentration(S_practical=10, temperature=28)
    c_high = hd.convert_salt_concentration(S_practical=20, temperature=28)
    assert c_low > 0
    assert c_high > c_low
