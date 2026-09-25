import math

import numpy as np
import pytest

from powerlab.cp import fit_cp_2p, fit_cp_3p
from powerlab.metrics import mean_max_power

CP, W_PRIME, PMAX = 280.0, 20_000.0, 1100.0
DUR_2P = np.array([180, 300, 600, 1200], dtype=float)
DUR_3P = np.array([5, 15, 30, 60, 180, 300, 600, 1200], dtype=float)


def hyperbolic(t, cp=CP, w=W_PRIME):
    return cp + w / np.asarray(t, dtype=float)


def morton(t, cp=CP, w=W_PRIME, pmax=PMAX):
    k = w / (cp - pmax)
    return cp + w / (np.asarray(t, dtype=float) - k)


def mmp_reference(power: list[float], d: int) -> float:
    return max(sum(power[i : i + d]) / d for i in range(len(power) - d + 1))


# --- Mean Maximal Power -------------------------------------------------------


def test_mmp_block_in_constant_ride():
    power = [200.0] * 600 + [400.0] * 60 + [200.0] * 600
    mmp = mean_max_power(power, [30, 60, 120])
    assert mmp.tolist() == pytest.approx([400.0, 400.0, 300.0])


def test_mmp_matches_bruteforce():
    rng = np.random.default_rng(3)
    power = rng.gamma(4.0, 50.0, size=1500).tolist()
    durations = [1, 5, 60, 301, 1500]
    expected = [mmp_reference(power, d) for d in durations]
    assert mean_max_power(power, durations).tolist() == pytest.approx(expected, rel=1e-12)


def test_mmp_non_increasing_for_integer_multiples():
    # Garantiert ist nur MMP(n·d) <= MMP(d): der beste n·d-Block zerfällt in n d-Blöcke
    rng = np.random.default_rng(4)
    power = rng.gamma(4.0, 50.0, size=3600)
    for d in (1, 7, 30, 60):
        mmp = mean_max_power(power, [d * n for n in range(1, 3600 // d + 1)])
        assert np.all(mmp[1:] <= mmp[0] + 1e-9)


def test_mmp_is_not_monotonic_in_general():
    # Gegenbeispiel: MMP(3) > MMP(2)
    assert mean_max_power([10.0, 0.0, 10.0], [2, 3]).tolist() == pytest.approx([5.0, 20 / 3])


@pytest.mark.parametrize("durations", [[0], [-5], [601], [1.5]])
def test_mmp_invalid_durations(durations):
    with pytest.raises(ValueError):
        mean_max_power([200.0] * 600, durations)


# --- 2-Parameter-Modell ---------------------------------------------------------


@pytest.mark.parametrize("method", ["inverse-time", "work-time"])
def test_2p_recovers_exact_parameters(method):
    fit = fit_cp_2p(DUR_2P, hyperbolic(DUR_2P), method=method)
    assert fit.cp == pytest.approx(CP)
    assert fit.w_prime == pytest.approx(W_PRIME)
    assert fit.pmax is None
    assert fit.rmse == pytest.approx(0.0, abs=1e-9)
    assert fit.cp_se == pytest.approx(0.0, abs=1e-6)


def test_2p_methods_differ_on_noisy_data():
    noisy = hyperbolic(DUR_2P) + np.array([6.0, -4.0, 3.0, -2.0])
    a = fit_cp_2p(DUR_2P, noisy, method="inverse-time")
    b = fit_cp_2p(DUR_2P, noisy, method="work-time")
    assert a.cp != pytest.approx(b.cp, abs=0.01)
    assert abs(a.cp - CP) < 10 and abs(b.cp - CP) < 10
    assert a.cp_se > 0 and a.w_prime_se > 0


def test_2p_inverse_time_minimises_power_residuals():
    noisy = hyperbolic(DUR_2P) + np.array([6.0, -4.0, 3.0, -2.0])
    a = fit_cp_2p(DUR_2P, noisy, method="inverse-time")
    b = fit_cp_2p(DUR_2P, noisy, method="work-time")
    assert a.rmse <= b.rmse


def test_2p_two_points_has_no_standard_error():
    fit = fit_cp_2p([180, 720], hyperbolic([180, 720]))
    assert fit.cp == pytest.approx(CP)
    assert fit.cp_se is None and fit.w_prime_se is None


def test_power_at_and_time_to_exhaustion():
    fit = fit_cp_2p(DUR_2P, hyperbolic(DUR_2P))
    assert fit.power_at(400) == pytest.approx(CP + W_PRIME / 400)
    assert fit.time_to_exhaustion(CP + 100) == pytest.approx(W_PRIME / 100)
    assert fit.time_to_exhaustion(CP) == math.inf


# --- 3-Parameter-Modell (Morton) ------------------------------------------------


def test_3p_recovers_exact_parameters():
    fit = fit_cp_3p(DUR_3P, morton(DUR_3P))
    assert fit.cp == pytest.approx(CP, rel=1e-4)
    assert fit.w_prime == pytest.approx(W_PRIME, rel=1e-3)
    assert fit.pmax == pytest.approx(PMAX, rel=1e-3)
    assert fit.rmse < 0.05


def test_3p_fits_short_efforts_better_than_2p():
    power = morton(DUR_3P)
    assert fit_cp_3p(DUR_3P, power).rmse < fit_cp_2p(DUR_3P, power).rmse


def test_3p_time_to_exhaustion_is_inverse_of_power_at():
    fit = fit_cp_3p(DUR_3P, morton(DUR_3P))
    for t in (10.0, 120.0, 900.0):
        assert fit.time_to_exhaustion(fit.power_at(t)) == pytest.approx(t, rel=1e-9)
    assert fit.time_to_exhaustion(fit.pmax + 1) == 0.0


# --- Ende-zu-Ende: Fahrt -> MMP -> Fit -----------------------------------------


def test_end_to_end_ride_to_cp():
    # Maximale Efforts gemäß Hyperbel, getrennt durch 10 min Erholung bei 150 W
    ride: list[float] = []
    for d in DUR_2P.astype(int):
        ride += [150.0] * 600 + [float(hyperbolic(d))] * d
    mmp = mean_max_power(ride, DUR_2P.astype(int))
    fit = fit_cp_2p(DUR_2P, mmp)
    assert fit.cp == pytest.approx(CP)
    assert fit.w_prime == pytest.approx(W_PRIME)


# --- Fehlerfälle --------------------------------------------------------------


@pytest.mark.parametrize(
    ("durations", "powers"),
    [
        ([300], [350.0]),  # zu wenige Punkte
        ([180, 300], [400.0]),  # Längen ungleich
        ([300, 300], [350.0, 340.0]),  # nur eine Dauer -> singulär
        ([0, 300], [900.0, 350.0]),  # Dauer <= 0
        ([180, 300], [400.0, math.nan]),
        ([180, 600], [300.0, 350.0]),  # Leistung steigt mit Dauer -> W' < 0
    ],
)
def test_2p_invalid_input_raises(durations, powers):
    with pytest.raises(ValueError):
        fit_cp_2p(durations, powers)


def test_2p_unknown_method_raises():
    with pytest.raises(ValueError):
        fit_cp_2p(DUR_2P, hyperbolic(DUR_2P), method="nonlinear")


def test_3p_needs_three_points():
    with pytest.raises(ValueError):
        fit_cp_3p([60, 300], [500.0, 350.0])
