import math
import random
from datetime import date, timedelta

import pytest

from powerlab.pmc import performance_management_chart

D0 = date(2026, 1, 1)


def days(n: int, tss: float = 100.0, start: date = D0) -> list[tuple[date, float]]:
    return [(start + timedelta(days=i), tss) for i in range(n)]


def pmc_reference(
    load: dict[date, float],
    start: date,
    end: date,
    ctl_days: float,
    atl_days: float,
    method: str,
) -> list[tuple[float, float]]:
    """Naive Referenz: Tag für Tag, fehlende Tage als 0."""

    def k(tau: float) -> float:
        return 1 / tau if method == "coggan" else 1 - math.exp(-1 / tau)

    ctl = atl = 0.0
    out = []
    d = start
    while d <= end:
        tss = load.get(d, 0.0)
        ctl = ctl + k(ctl_days) * (tss - ctl)
        atl = atl + k(atl_days) * (tss - atl)
        out.append((ctl, atl))
        d += timedelta(days=1)
    return out


# --- Dynamik ------------------------------------------------------------------


@pytest.mark.parametrize("method", ["coggan", "exponential"])
def test_constant_load_converges(method):
    result = performance_management_chart(days(400, 80.0), method=method)
    last = result[-1]
    assert last.ctl == pytest.approx(80.0, rel=1e-3)
    assert last.atl == pytest.approx(80.0, rel=1e-9)
    assert last.tsb == pytest.approx(0.0, abs=0.1)


def test_step_response_coggan_after_tau():
    result = performance_management_chart(days(42, 1.0))
    assert result[-1].ctl == pytest.approx(1 - (41 / 42) ** 42)


def test_step_response_exponential_after_tau():
    result = performance_management_chart(days(42, 1.0), method="exponential")
    assert result[-1].ctl == pytest.approx(1 - math.exp(-1))


def test_atl_reacts_faster_than_ctl():
    result = performance_management_chart(days(7, 100.0))
    assert result[-1].atl > result[-1].ctl


def test_first_day_values_coggan():
    first = performance_management_chart([(D0, 84.0)], ctl0=10.0, atl0=30.0)[0]
    assert first.ctl == pytest.approx(10.0 + (84.0 - 10.0) / 42)
    assert first.atl == pytest.approx(30.0 + (84.0 - 30.0) / 7)
    assert first.tsb == pytest.approx(10.0 - 30.0)


def test_tsb_uses_previous_day():
    rng = random.Random(1)
    load = [(D0 + timedelta(days=i), rng.uniform(0, 200)) for i in range(60)]
    result = performance_management_chart(load)
    for prev, cur in zip(result, result[1:], strict=False):
        assert cur.tsb == pytest.approx(prev.ctl - prev.atl)


def test_ramp_rate():
    result = performance_management_chart(days(30, 100.0))
    assert all(r.ramp is None for r in result[:6])
    for t in range(7, len(result)):
        assert result[t].ramp == pytest.approx(result[t].ctl - result[t - 7].ctl)


def test_ramp_on_day_seven_uses_seed():
    # ctl0 ist CTL am Vortag des ersten Eintrags = CTL_{t-7} für den 7. Tag
    result = performance_management_chart(days(10, 100.0), ctl0=40.0, atl0=40.0)
    assert result[6].ramp == pytest.approx(result[6].ctl - 40.0)


def test_seeded_steady_state_stays_constant():
    result = performance_management_chart(days(100, 65.0), ctl0=65.0, atl0=65.0)
    for r in result:
        assert (r.ctl, r.atl, r.tsb) == pytest.approx((65.0, 65.0, 0.0))


@pytest.mark.parametrize("method", ["coggan", "exponential"])
def test_matches_reference(method):
    rng = random.Random(7)
    load: dict[date, float] = {}
    for i in range(365):
        if rng.random() < 0.7:  # ~30 % Ruhetage
            load[D0 + timedelta(days=i)] = rng.uniform(20, 250)
    start, end = min(load), max(load)
    result = performance_management_chart(load.items(), method=method)
    expected = pmc_reference(load, start, end, 42, 7, method)
    assert len(result) == len(expected)
    for r, (ctl, atl) in zip(result, expected, strict=True):
        assert (r.ctl, r.atl) == pytest.approx((ctl, atl), rel=1e-12)


# --- Aufbereitung der Eingabe ---------------------------------------------------


def test_gaps_filled_with_zero():
    result = performance_management_chart([(D0, 100.0), (D0 + timedelta(days=3), 50.0)])
    assert [r.day for r in result] == [D0 + timedelta(days=i) for i in range(4)]
    assert [r.tss for r in result] == [100.0, 0.0, 0.0, 50.0]


def test_same_day_entries_are_summed():
    result = performance_management_chart([(D0, 60.0), (D0, 40.0)])
    assert len(result) == 1
    assert result[0].tss == pytest.approx(100.0)


def test_unsorted_input_equals_sorted():
    load = [(D0 + timedelta(days=i), float(i * 10)) for i in range(20)]
    assert performance_management_chart(reversed(load)) == performance_management_chart(load)


def test_end_extends_with_rest_days():
    result = performance_management_chart(days(60, 100.0), end=D0 + timedelta(days=89))
    assert len(result) == 90
    detraining = [r.ctl for r in result[60:]]
    assert all(b < a for a, b in zip(detraining, detraining[1:], strict=False))


def test_end_before_last_entry_does_not_truncate():
    result = performance_management_chart(days(10), end=D0 + timedelta(days=3))
    assert len(result) == 10


# --- Fehlerfälle --------------------------------------------------------------


@pytest.mark.parametrize(
    ("load", "kwargs"),
    [
        ([], {}),
        ([(D0, -1.0)], {}),
        ([(D0, math.nan)], {}),
        ([(D0, math.inf)], {}),
        ([(D0, 50.0)], {"ctl_days": 0}),
        ([(D0, 50.0)], {"atl_days": -7}),
        ([(D0, 50.0)], {"method": "banister"}),
        ([(D0, 50.0)], {"end": D0 - timedelta(days=1)}),
        ([(D0, 50.0)], {"ctl0": math.nan}),
    ],
)
def test_invalid_input_raises(load, kwargs):
    with pytest.raises(ValueError):
        performance_management_chart(load, **kwargs)
