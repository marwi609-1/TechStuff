import math

import numpy as np
import pytest

from powerlab.wbal import skiba_tau, w_prime_balance

CP, W_PRIME = 280.0, 20_000.0
METHODS = ["differential", "integral"]


def integral_oracle(power, cp, w_prime, tau):
    """Direkte O(n²)-Summe nach Skiba et al. 2012, unabhängig von der Rekursion."""
    power = [float(p) for p in power]
    result = []
    for t in range(len(power)):
        expended = sum(
            (power[u] - cp) * math.exp(-(t - u) / tau) for u in range(t + 1) if power[u] > cp
        )
        result.append(w_prime - expended)
    return result


def differential_oracle(power, cp, w_prime):
    bal, result = w_prime, []
    for p in power:
        if p > cp:
            bal -= p - cp
        else:
            bal += (w_prime - bal) * (cp - p) / w_prime
        result.append(bal)
    return result


# --- Grundverhalten -----------------------------------------------------------


@pytest.mark.parametrize("method", METHODS)
def test_constant_below_cp_keeps_full_w_prime(method):
    bal = w_prime_balance([200.0] * 600, CP, W_PRIME, method=method)
    assert bal.shape == (600,)
    assert bal.dtype == np.float64
    assert bal.tolist() == pytest.approx([W_PRIME] * 600, abs=1e-9)


@pytest.mark.parametrize("method", METHODS)
def test_at_cp_keeps_full_w_prime(method):
    # P == CP: weder Verbrauch noch (differential) Erholung
    kwargs = {"tau": 400.0} if method == "integral" else {}
    bal = w_prime_balance([CP] * 100, CP, W_PRIME, method=method, **kwargs)
    assert bal.tolist() == pytest.approx([W_PRIME] * 100)


@pytest.mark.parametrize("method", METHODS)
def test_accepts_list_and_array_identically(method):
    power = [300.0, 400.0, 100.0, 0.0, 350.0]
    a = w_prime_balance(power, CP, W_PRIME, method=method)
    b = w_prime_balance(np.array(power), CP, W_PRIME, method=method)
    assert a.tolist() == b.tolist()


# --- differential (Skiba et al. 2015) ------------------------------------------


def test_differential_constant_above_cp_linear_depletion():
    # Wert bei Index i = Zustand am Ende von Sekunde i+1
    p, n = 380.0, 300
    bal = w_prime_balance([p] * n, CP, W_PRIME)
    t = np.arange(1, n + 1)
    assert bal.tolist() == pytest.approx((W_PRIME - (p - CP) * t).tolist(), abs=1e-9)


def test_differential_can_go_negative():
    # 100 W über CP für 250 s = 25 kJ > W′ = 20 kJ: kein Clipping bei 0
    bal = w_prime_balance([CP + 100.0] * 250, CP, W_PRIME)
    assert bal[199] == pytest.approx(0.0, abs=1e-9)
    assert bal[-1] == pytest.approx(-5_000.0)
    assert np.all(np.diff(bal) < 0)


def test_differential_recovery_at_zero_watts():
    # Nach Depletion um D0 bei P = 0: kontinuierlich D(t) = D0·e^(−t·CP/W′),
    # diskret (Euler, Δt = 1 s) exakt D_n = D0·(1 − CP/W′)^n.
    work = [CP + 100.0] * 100  # D0 = 10 kJ
    n_rec = 600
    bal = w_prime_balance(work + [0.0] * n_rec, CP, W_PRIME)
    d0 = W_PRIME - bal[99]
    assert d0 == pytest.approx(10_000.0)

    n = np.arange(1, n_rec + 1)
    deficit = W_PRIME - bal[100:]
    discrete = d0 * (1 - CP / W_PRIME) ** n
    # abs: Auslöschung in W′ − W′bal (≈ eps·W′)
    assert deficit.tolist() == pytest.approx(discrete.tolist(), rel=1e-12, abs=1e-9)

    analytic = d0 * np.exp(-n * CP / W_PRIME)
    # Relativer Diskretisierungsfehler: (1 − k)^n / e^(−kn) = exp(n·(ln(1−k) + k)) ≈ exp(−n·k²/2)
    k = CP / W_PRIME
    rel_err = 1 - np.exp(n * (np.log1p(-k) + k))
    assert (1 - deficit / analytic).tolist() == pytest.approx(rel_err.tolist(), abs=1e-9)
    assert np.all(np.abs(rel_err) < n * k**2)  # < 1.2 % nach 10 min
    # Zeitkonstante W′/CP ≈ 71 s: nach einer Zeitkonstante ist der Rest ≈ D0/e
    tc = round(W_PRIME / CP)
    assert deficit[tc - 1] / d0 == pytest.approx(math.exp(-tc * k), rel=0.01)


def test_differential_matches_oracle_random():
    rng = np.random.default_rng(11)
    power = rng.gamma(3.0, 90.0, size=2000)
    expected = differential_oracle(power.tolist(), CP, W_PRIME)
    assert w_prime_balance(power, CP, W_PRIME).tolist() == pytest.approx(expected, rel=1e-12)


def test_differential_rejects_w_prime_below_cp_times_dt():
    # (CP − P)/W′ > 1 s⁻¹ ließe den expliziten Euler-Schritt überschießen
    with pytest.raises(ValueError):
        w_prime_balance([0.0, 500.0], cp=300.0, w_prime=200.0)


# --- integral (Skiba et al. 2012) ----------------------------------------------


def test_skiba_tau_reference_value():
    # D_CP = 280 − 180 = 100 W  ->  τ = 546·e^(−1) + 316 ≈ 516.862 s
    power = [180.0] * 300 + [400.0] * 60 + [180.0] * 300
    assert skiba_tau(power, CP) == pytest.approx(546 * math.exp(-1) + 316, rel=1e-12)
    assert skiba_tau(power, CP) == pytest.approx(516.862, abs=1e-3)


def test_skiba_tau_uses_only_samples_strictly_below_cp():
    # Sekunden über und genau auf CP gehen nicht in D_CP ein; Mittel über 100 und 200 W
    power = [100.0] * 10 + [200.0] * 10 + [CP] * 50 + [600.0] * 50
    assert skiba_tau(power, CP) == pytest.approx(546 * math.exp(-0.01 * 130.0) + 316)


def test_skiba_tau_limits():
    # D_CP -> 0: τ -> 862 s; P = 0 bei großem CP: τ -> 316 s
    assert skiba_tau([CP - 1e-9, 500.0], CP) == pytest.approx(862.0)
    assert skiba_tau([0.0], 2000.0) == pytest.approx(316.0, abs=1e-3)


def test_skiba_tau_without_sub_cp_samples_raises():
    with pytest.raises(ValueError):
        skiba_tau([300.0, 400.0], CP)
    with pytest.raises(ValueError):
        w_prime_balance([300.0, 400.0], CP, W_PRIME, method="integral")


def test_integral_matches_on2_oracle_random():
    rng = np.random.default_rng(7)
    power = rng.gamma(3.0, 90.0, size=1500)
    tau = skiba_tau(power, CP)
    expected = integral_oracle(power, CP, W_PRIME, tau)
    got = w_prime_balance(power, CP, W_PRIME, method="integral")
    assert got.tolist() == pytest.approx(expected, rel=1e-12, abs=1e-9)


@pytest.mark.parametrize("tau", [0.3, 1.0, 37.5, 5000.0])
def test_integral_matches_oracle_with_explicit_tau(tau):
    rng = np.random.default_rng(8)
    power = rng.gamma(3.0, 90.0, size=700)
    expected = integral_oracle(power, CP, W_PRIME, tau)
    got = w_prime_balance(power, CP, W_PRIME, method="integral", tau=tau)
    assert got.tolist() == pytest.approx(expected, rel=1e-12, abs=1e-9)


def test_integral_recovery_after_effort_is_exponential_with_tau():
    power = [400.0] * 60 + [100.0] * 600
    tau = skiba_tau(power, CP)
    bal = w_prime_balance(power, CP, W_PRIME, method="integral")
    deficit = W_PRIME - bal
    ratio = deficit[60:] / deficit[59:-1]
    assert ratio.tolist() == pytest.approx([math.exp(-1 / tau)] * 600, rel=1e-12)


# --- Vergleich der Methoden ------------------------------------------------------


def test_methods_differ_during_continuous_depletion():
    # Das Integral lässt verbrauchtes W′ auch *während* Arbeit über CP mit τ abklingen;
    # das Differentialmodell erholt nur unter CP. Identisch nur in der ersten Sekunde
    # bzw. im Grenzfall τ -> ∞.
    p, n, tau = 380.0, 300, 500.0
    diff = w_prime_balance([p] * n, CP, W_PRIME)
    integ = w_prime_balance([p] * n, CP, W_PRIME, method="integral", tau=tau)
    d = math.exp(-1 / tau)
    k = np.arange(1, n + 1)
    expected = W_PRIME - (p - CP) * (1 - d**k) / (1 - d)
    assert integ.tolist() == pytest.approx(expected.tolist(), rel=1e-12, abs=1e-9)
    assert integ[0] == pytest.approx(diff[0])
    assert np.all(integ[1:] > diff[1:])
    huge = w_prime_balance([p] * n, CP, W_PRIME, method="integral", tau=1e12)
    # Restabweichung ≈ (P − CP)·n²/(2τ) ≈ 5e-6 J
    assert huge.tolist() == pytest.approx(diff.tolist(), rel=0, abs=1e-4)


def test_tau_rejected_for_differential():
    with pytest.raises(ValueError):
        w_prime_balance([300.0], CP, W_PRIME, method="differential", tau=500.0)


# --- Fehlerfälle ------------------------------------------------------------------


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "kwargs",
    [
        {"cp": 0.0},
        {"cp": -10.0},
        {"cp": math.nan},
        {"cp": math.inf},
        {"w_prime": 0.0},
        {"w_prime": -1.0},
        {"w_prime": math.nan},
        {"w_prime": math.inf},
    ],
)
def test_invalid_parameters(method, kwargs):
    args = {"cp": CP, "w_prime": W_PRIME} | kwargs
    with pytest.raises(ValueError):
        w_prime_balance([200.0, 300.0], method=method, **args)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize(
    "power",
    [[], [200.0, math.nan], [200.0, math.inf], [200.0, -1.0], [[200.0, 300.0]]],
)
def test_invalid_power(method, power):
    with pytest.raises(ValueError):
        w_prime_balance(power, CP, W_PRIME, method=method)


def test_unknown_method():
    with pytest.raises(ValueError):
        w_prime_balance([200.0], CP, W_PRIME, method="bartram")  # type: ignore[arg-type]


@pytest.mark.parametrize("tau", [0.0, -5.0, math.nan, math.inf])
def test_invalid_tau(tau):
    with pytest.raises(ValueError):
        w_prime_balance([200.0], CP, W_PRIME, method="integral", tau=tau)


@pytest.mark.parametrize("cp", [0.0, math.nan])
def test_skiba_tau_invalid_cp(cp):
    with pytest.raises(ValueError):
        skiba_tau([100.0], cp)
