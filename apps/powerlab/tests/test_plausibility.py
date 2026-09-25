import math
from datetime import date, timedelta

import pytest

from powerlab.intervals import WellnessDay
from powerlab.plausibility import hr_load_estimate, what_if_load

# --- HR-Load-Schätzung --------------------------------------------------------


def test_hr_load_one_hour_at_lthr_is_100():
    assert hr_load_estimate(avg_hr=167, lthr=167, moving_time_s=3600) == pytest.approx(100.0)


def test_hr_load_scales_with_squared_intensity_and_duration():
    # 4:10 h bei Ø 110 / LTHR 160 -> h · (110/160)² · 100
    expected = 15000 / 3600 * (110 / 160) ** 2 * 100
    assert hr_load_estimate(110, 160, 15000) == pytest.approx(expected)
    assert 190 < expected < 200


@pytest.mark.parametrize(
    "args", [(0, 167, 3600), (107, 0, 3600), (107, 167, -1), (math.nan, 167, 3600)]
)
def test_hr_load_invalid_raises(args):
    with pytest.raises(ValueError):
        hr_load_estimate(*args)


# --- What-if für einen Tages-Load --------------------------------------------

K42, K7 = 1 - math.exp(-1 / 42), 1 - math.exp(-1 / 7)


def wellness(n=21, end=date(2026, 9, 20), loads=None):
    """Konsistente Intervals-artige Reihe (exponentielle Glättung)."""
    loads = loads or [50.0] * n
    ctl = atl = 40.0
    ctls, days = [], []
    for i in range(n):
        ctl += K42 * (loads[i] - ctl)
        atl += K7 * (loads[i] - atl)
        ctls.append(ctl)
        ramp = ctl - ctls[i - 7] if i >= 7 else None
        days.append(
            WellnessDay(end - timedelta(days=n - 1 - i), ctl, atl, ramp, loads[i], loads[i])
        )
    return days


def test_what_if_unchanged_load_reproduces_intervals():
    days = wellness()
    r = what_if_load(days, days[-4].day, days[-4].ctl_load)
    last = days[-1]
    assert r.ctl == pytest.approx(last.ctl)
    assert r.atl == pytest.approx(last.atl)
    assert r.ramp == pytest.approx(last.ramp)
    assert r.form_next_morning == pytest.approx(last.ctl - last.atl)


def test_what_if_lower_load_lowers_ctl_atl_and_raises_form():
    loads = [50.0] * 21
    loads[-4] = 400.0
    days = wellness(loads=loads)
    r = what_if_load(days, days[-4].day, 170.0)
    assert r.ctl < days[-1].ctl and r.atl < days[-1].atl
    assert r.form_next_morning > days[-1].ctl - days[-1].atl
    # Differenz exakt: Impuls −230 klingt über 3 Folgetage ab
    assert days[-1].ctl - r.ctl == pytest.approx(230 * K42 * (1 - K42) ** 3)


def test_what_if_day_outside_range_raises():
    days = wellness()
    with pytest.raises(ValueError):
        what_if_load(days, days[0].day - timedelta(days=1), 10.0)


def test_what_if_first_day_cannot_be_replaced():
    # Tag 0 dient als Seed; ohne Vortag ist die Rückrechnung nicht eindeutig
    days = wellness()
    with pytest.raises(ValueError, match="Seed"):
        what_if_load(days, days[0].day, 10.0)


def test_what_if_negative_load_raises():
    days = wellness()
    with pytest.raises(ValueError):
        what_if_load(days, days[-4].day, -5.0)
