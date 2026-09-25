import math

import numpy as np
import pytest

from powerlab.metrics import training_stress_score
from powerlab.timeseries import moving_time_s, to_1hz


def to_1hz_reference(
    time_s: list[float], watts: list[float], max_fill_s: int, pause_policy: str
) -> list[float]:
    """Unabhängiges Schleifen-Orakel: Sekunden-Mittel, lineare Füllung, Pausenbehandlung."""
    buckets: dict[int, list[float]] = {}
    for t, w in zip(time_s, watts, strict=True):
        if not math.isnan(w):
            buckets.setdefault(math.floor(t), []).append(w)
    secs = sorted(buckets)
    vals = [sum(buckets[s]) / len(buckets[s]) for s in secs]
    out = [vals[0]]
    for i in range(1, len(secs)):
        missing = secs[i] - secs[i - 1] - 1
        if missing <= max_fill_s:
            for k in range(1, missing + 1):
                frac = k / (missing + 1)
                out.append(vals[i - 1] + frac * (vals[i] - vals[i - 1]))
        elif pause_policy == "zero":
            out.extend([0.0] * missing)
        out.append(vals[i])
    return out


def realistic_gappy_ride() -> tuple[np.ndarray, np.ndarray]:
    """Synthetischer Stream analog zum echten Intervals-Fall: 845 Samples auf 1339 s.

    Aufbau: 845 belegte Sekunden, 37 s in kurzen Aussetzern (<= 5 s, werden gefüllt),
    457 s in drei Auto-Pausen (> 5 s) -> Bewegungszeit 845 + 37 = 882 s.
    """
    segments = [  # (Anzahl Samples, danach fehlende Sekunden)
        (100, 3),
        (100, 5),
        (100, 200),
        (100, 4),
        (100, 5),
        (100, 157),
        (100, 5),
        (40, 5),
        (40, 100),
        (30, 5),
        (30, 5),
        (5, 0),
    ]
    times: list[int] = []
    t = 0
    for n, missing in segments:
        times.extend(range(t, t + n))
        t += n + missing
    time = np.asarray(times, dtype=np.float64)
    watts = np.full(time.size, 250.0)
    return time, watts


# --- Grundverhalten -----------------------------------------------------------


def test_gapless_1hz_input_is_unchanged():
    rng = np.random.default_rng(1)
    watts = rng.gamma(4.0, 50.0, size=600)
    result = to_1hz(np.arange(600), watts)
    np.testing.assert_array_equal(result, watts)
    assert result.dtype == np.float64


def test_offset_start_time_is_irrelevant():
    watts = [100.0, 200.0, 300.0]
    np.testing.assert_array_equal(to_1hz([1000, 1001, 1002], watts), watts)


def test_short_gap_is_linearly_interpolated():
    # t=2..4 fehlen (3 s <= 5 s): lineare Rampe 100 -> 300
    result = to_1hz([0, 1, 5, 6], [100.0, 100.0, 300.0, 300.0])
    np.testing.assert_allclose(result, [100, 100, 150, 200, 250, 300, 300])


def test_gap_exactly_max_fill_is_filled():
    result = to_1hz([0, 3], [0.0, 300.0], max_fill_s=2)
    np.testing.assert_allclose(result, [0, 100, 200, 300])


def test_max_fill_zero_treats_every_gap_as_pause():
    np.testing.assert_allclose(to_1hz([0, 2], [100.0, 200.0], max_fill_s=0), [100, 200])
    np.testing.assert_allclose(
        to_1hz([0, 2], [100.0, 200.0], max_fill_s=0, pause_policy="zero"), [100, 0, 200]
    )


def test_long_gap_drop_removes_pause():
    time = [0, 1, 2, 10, 11]
    watts = [100.0, 110.0, 120.0, 200.0, 210.0]
    result = to_1hz(time, watts, max_fill_s=5, pause_policy="drop")
    np.testing.assert_allclose(result, watts)
    assert result.size == 5


def test_long_gap_zero_fills_with_zero_watts():
    time = [0, 1, 2, 10, 11]
    watts = [100.0, 110.0, 120.0, 200.0, 210.0]
    result = to_1hz(time, watts, max_fill_s=5, pause_policy="zero")
    np.testing.assert_allclose(result, [100, 110, 120, 0, 0, 0, 0, 0, 0, 0, 200, 210])
    assert result.size == 12  # Gesamtzeit t=0..11


def test_default_policy_is_drop():
    time = [0, 1, 20, 21]
    np.testing.assert_array_equal(
        to_1hz(time, [1.0] * 4), to_1hz(time, [1.0] * 4, pause_policy="drop")
    )


# --- Sub-Sekunden-Zeitstempel -------------------------------------------------


def test_subsecond_samples_are_averaged_per_second():
    # 2 Hz: Sekunde 0 = Mittel(100, 200), Sekunde 1 = Mittel(300, 500)
    result = to_1hz([0.0, 0.5, 1.0, 1.5], [100.0, 200.0, 300.0, 500.0])
    np.testing.assert_allclose(result, [150, 400])


def test_subsecond_average_preserves_energy_for_regular_sampling():
    rng = np.random.default_rng(3)
    time = np.arange(0, 300, 0.25)
    watts = rng.gamma(4.0, 50.0, size=time.size)
    result = to_1hz(time, watts)
    assert result.size == 300
    # Arbeit (J) bleibt erhalten: sum(P_1Hz * 1 s) == sum(P_4Hz * 0.25 s)
    assert result.sum() == pytest.approx(watts.sum() * 0.25, rel=1e-12)


def test_fractional_timestamps_without_duplicates_are_floored():
    result = to_1hz([0.3, 1.7, 2.2], [100.0, 200.0, 300.0])
    np.testing.assert_allclose(result, [100, 200, 300])


# --- Fehlende Leistungswerte (NaN / None) --------------------------------------


def test_nan_watts_are_treated_as_missing_and_interpolated():
    result = to_1hz([0, 1, 2, 3], [100.0, float("nan"), float("nan"), 400.0])
    np.testing.assert_allclose(result, [100, 200, 300, 400])


def test_none_watts_are_treated_like_nan():
    result = to_1hz([0, 1, 2], [100.0, None, 300.0])
    np.testing.assert_allclose(result, [100, 200, 300])


def test_long_nan_run_counts_as_pause():
    watts = [100.0] + [float("nan")] * 10 + [200.0]
    time = list(range(12))
    np.testing.assert_allclose(to_1hz(time, watts), [100, 200])
    assert moving_time_s(time, watts=watts) == 2


def test_leading_and_trailing_nan_are_trimmed():
    result = to_1hz([0, 1, 2, 3], [float("nan"), 100.0, 200.0, float("nan")])
    np.testing.assert_allclose(result, [100, 200])


def test_nan_within_second_is_ignored_in_average():
    result = to_1hz([0.0, 0.5, 1.0], [100.0, float("nan"), 300.0])
    np.testing.assert_allclose(result, [100, 300])


# --- Orakel -------------------------------------------------------------------


@pytest.mark.parametrize("policy", ["drop", "zero"])
def test_matches_loop_reference_on_random_gappy_stream(policy):
    rng = np.random.default_rng(7)
    steps = rng.choice([0.5, 1.0, 1.0, 1.0, 2.0, 4.0, 7.0, 30.0], size=800)
    time = np.cumsum(steps)
    watts = rng.gamma(4.0, 50.0, size=time.size)
    watts[rng.random(time.size) < 0.05] = np.nan
    expected = to_1hz_reference(time.tolist(), watts.tolist(), 5, policy)
    result = to_1hz(time, watts, max_fill_s=5, pause_policy=policy)
    np.testing.assert_allclose(result, expected, rtol=1e-12)


# --- Bewegungszeit ------------------------------------------------------------


def test_moving_time_gapless():
    assert moving_time_s(np.arange(3600)) == 3600


def test_moving_time_counts_short_gaps_excludes_long():
    # 0..2 (3 s) + Lücke 3 s gefüllt (3..5) + 6 (1 s) + Pause 7..19 + 20..21 (2 s)
    assert moving_time_s([0, 1, 2, 6, 20, 21], max_fill_s=5) == 9


def test_moving_time_returns_int():
    assert isinstance(moving_time_s([0, 1, 2]), int)


@pytest.mark.parametrize("max_fill_s", [0, 1, 5, 30])
def test_moving_time_equals_length_of_dropped_series(max_fill_s):
    rng = np.random.default_rng(11)
    time = np.cumsum(rng.choice([0.5, 1.0, 1.0, 3.0, 6.0, 40.0], size=500))
    watts = rng.gamma(4.0, 50.0, size=time.size)
    watts[rng.random(time.size) < 0.05] = np.nan
    series = to_1hz(time, watts, max_fill_s=max_fill_s, pause_policy="drop")
    assert moving_time_s(time, watts=watts, max_fill_s=max_fill_s) == series.size


def test_realistic_intervals_like_stream():
    time, watts = realistic_gappy_ride()
    assert time.size == 845
    assert time[-1] - time[0] + 1 == 1339
    assert moving_time_s(time) == 882
    assert to_1hz(time, watts).size == 882
    assert to_1hz(time, watts, pause_policy="zero").size == 1339


# --- Integration mit metrics --------------------------------------------------


def test_tss_uses_moving_time_with_drop_policy():
    time, watts = realistic_gappy_ride()
    ftp = 250.0  # konstant 250 W -> IF = 1 -> TSS = Stunden * 100
    tss = training_stress_score(to_1hz(time, watts), ftp)
    assert tss == pytest.approx(882 / 3600 * 100, rel=1e-12)


def test_tss_with_zero_policy_differs_from_drop():
    time, watts = realistic_gappy_ride()
    tss_drop = training_stress_score(to_1hz(time, watts, pause_policy="drop"), 250.0)
    tss_zero = training_stress_score(to_1hz(time, watts, pause_policy="zero"), 250.0)
    assert tss_zero != pytest.approx(tss_drop)


# --- Fehlerfälle --------------------------------------------------------------


def test_rejects_unequal_lengths():
    with pytest.raises(ValueError, match="gleich lang"):
        to_1hz([0, 1, 2], [100.0, 100.0])


@pytest.mark.parametrize("time", [[0, 2, 1], [0, 1, 1], [0.0, 0.5, 0.5]])
def test_rejects_non_monotonic_time(time):
    with pytest.raises(ValueError, match="monoton"):
        to_1hz(time, [100.0] * 3)
    with pytest.raises(ValueError, match="monoton"):
        moving_time_s(time)


def test_rejects_negative_watts():
    with pytest.raises(ValueError, match="negativ"):
        to_1hz([0, 1, 2], [100.0, -1.0, 100.0])


def test_rejects_infinite_watts():
    with pytest.raises(ValueError, match="Inf"):
        to_1hz([0, 1, 2], [100.0, float("inf"), 100.0])


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_rejects_non_finite_time(bad):
    with pytest.raises(ValueError, match="Zeit"):
        to_1hz([0, bad, 2], [100.0] * 3)


def test_rejects_empty_input():
    with pytest.raises(ValueError, match="leer"):
        to_1hz([], [])
    with pytest.raises(ValueError, match="leer"):
        moving_time_s([])


def test_rejects_all_nan_watts():
    with pytest.raises(ValueError, match="gültigen"):
        to_1hz([0, 1], [float("nan"), float("nan")])


def test_rejects_multidimensional_input():
    with pytest.raises(ValueError, match="eindimensional"):
        to_1hz([[0, 1]], [[100.0, 100.0]])


@pytest.mark.parametrize("bad", [-1, 2.5, True, "5"])
def test_rejects_invalid_max_fill(bad):
    with pytest.raises(ValueError, match="max_fill_s"):
        to_1hz([0, 1], [100.0, 100.0], max_fill_s=bad)
    with pytest.raises(ValueError, match="max_fill_s"):
        moving_time_s([0, 1], max_fill_s=bad)


def test_rejects_unknown_policy():
    with pytest.raises(ValueError, match="pause_policy"):
        to_1hz([0, 1], [100.0, 100.0], pause_policy="hold")  # type: ignore[arg-type]
