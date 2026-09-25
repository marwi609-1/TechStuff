import math

import numpy as np
import pytest

from powerlab.metrics import (
    intensity_factor,
    normalized_power,
    training_stress_score,
    variability_index,
)


def np_reference(power: list[float], window: int = 30) -> float:
    """Unabhängige Brute-Force-Implementierung nach Coggan als Test-Orakel."""
    rolling = [sum(power[i - window + 1 : i + 1]) / window for i in range(window - 1, len(power))]
    return (sum(p**4 for p in rolling) / len(rolling)) ** 0.25


def square_wave(high: float, low: float, block_s: int, repeats: int) -> list[float]:
    return ([high] * block_s + [low] * block_s) * repeats


# --- Normalized Power ---------------------------------------------------------


def test_np_constant_power_equals_power():
    assert normalized_power([250.0] * 3600) == pytest.approx(250.0)


def test_np_matches_bruteforce_reference_on_square_wave():
    power = square_wave(400, 100, block_s=60, repeats=20)
    assert normalized_power(power) == pytest.approx(np_reference(power), rel=1e-12)


def test_np_matches_bruteforce_reference_on_random_ride():
    rng = np.random.default_rng(42)
    power = rng.gamma(shape=4.0, scale=50.0, size=2400).tolist()
    assert normalized_power(power) == pytest.approx(np_reference(power), rel=1e-12)


def test_np_at_least_average_power():
    # Potenzmittel-Ungleichung: M4 >= M1, gilt auch für geglättete Werte
    power = square_wave(500, 0, block_s=15, repeats=100)
    assert normalized_power(power) >= float(np.mean(power))


def test_np_short_intervals_are_smoothed():
    # 15s/15s-Intervalle werden durch das 30s-Fenster fast vollständig geglättet
    power = square_wave(400, 0, block_s=15, repeats=120)
    assert normalized_power(power) < 1.1 * float(np.mean(power))


def test_np_accepts_numpy_array():
    assert normalized_power(np.full(600, 200.0)) == pytest.approx(200.0)


def test_np_exactly_one_window():
    assert normalized_power([100.0] * 30) == pytest.approx(100.0)


def test_np_too_short_raises():
    with pytest.raises(ValueError, match="30"):
        normalized_power([200.0] * 29)


@pytest.mark.parametrize("bad", [[float("nan")] * 60, [-10.0] * 60])
def test_np_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        normalized_power(bad)


# --- IF / TSS / VI ------------------------------------------------------------


def test_intensity_factor():
    assert intensity_factor(np_watts=225.0, ftp=250.0) == pytest.approx(0.9)


def test_tss_one_hour_at_ftp_is_100():
    assert training_stress_score([250.0] * 3600, ftp=250.0) == pytest.approx(100.0)


def test_tss_one_hour_at_80_percent():
    # TSS = h * IF^2 * 100 = 1 * 0.64 * 100
    assert training_stress_score([200.0] * 3600, ftp=250.0) == pytest.approx(64.0)


def test_tss_scales_linearly_with_duration():
    assert training_stress_score([250.0] * 7200, ftp=250.0) == pytest.approx(200.0)


def test_tss_uses_normalized_power():
    power = square_wave(400, 100, block_s=60, repeats=30)  # 3600 s
    expected_if = np_reference(power) / 300.0
    assert training_stress_score(power, ftp=300.0) == pytest.approx(100 * expected_if**2)


@pytest.mark.parametrize("ftp", [0.0, -1.0, math.nan])
def test_invalid_ftp_raises(ftp):
    with pytest.raises(ValueError):
        training_stress_score([200.0] * 3600, ftp=ftp)
    with pytest.raises(ValueError):
        intensity_factor(200.0, ftp=ftp)


def test_variability_index_steady_ride_is_one():
    assert variability_index([220.0] * 1800) == pytest.approx(1.0)


def test_variability_index_surgy_ride_above_one():
    assert variability_index(square_wave(450, 80, block_s=60, repeats=15)) > 1.1
