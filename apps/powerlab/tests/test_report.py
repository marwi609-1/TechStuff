from datetime import date, timedelta

import pytest

from powerlab.intervals import WellnessDay
from powerlab.report import Activity, parse_activities, render_html, summarize_week

SUNDAY = date(2026, 9, 20)


def wellness(n: int = 49, end: date = SUNDAY, load=lambda i: 50.0, ctl=40.0, atl=45.0):
    start = end - timedelta(days=n - 1)
    return [
        WellnessDay(
            day=start + timedelta(days=i),
            ctl=ctl + i * 0.1,
            atl=atl + i * 0.2,
            ramp=1.5,
            ctl_load=load(i),
            atl_load=load(i),
        )
        for i in range(n)
    ]


# --- summarize_week -----------------------------------------------------------


def test_week_is_monday_to_sunday():
    s = summarize_week(wellness(), SUNDAY)
    assert s.week_start == date(2026, 9, 14)
    assert s.week_start.weekday() == 0
    assert [d for d, _ in s.daily_load] == [date(2026, 9, 14) + timedelta(days=i) for i in range(7)]


def test_week_end_must_be_sunday():
    with pytest.raises(ValueError, match="Sonntag"):
        summarize_week(wellness(end=date(2026, 9, 25)), date(2026, 9, 25))


def test_totals_and_previous_week():
    # letzte 7 Tage Load 100, davor 50
    s = summarize_week(wellness(load=lambda i: 100.0 if i >= 42 else 50.0), SUNDAY)
    assert s.total_load == pytest.approx(700.0)
    assert s.prev_total_load == pytest.approx(350.0)
    assert s.active_days == 7


def test_active_days_ignore_zero_load():
    s = summarize_week(wellness(load=lambda i: 0.0 if i % 2 else 80.0), SUNDAY)
    assert s.active_days == sum(1 for _, v in s.daily_load if v > 0)


def test_end_values_from_intervals_and_monday_form():
    days = wellness()
    s = summarize_week(days, SUNDAY)
    last = days[-1]
    assert (s.ctl_end, s.atl_end, s.ramp_end) == (last.ctl, last.atl, last.ramp)
    # Form am Montagmorgen = CTL − ATL vom Sonntag (Vortagskonvention)
    assert s.form_next_morning == pytest.approx(last.ctl - last.atl)
    assert s.ctl_change == pytest.approx(last.ctl - days[-8].ctl)


def test_trend_covers_six_weeks():
    s = summarize_week(wellness(n=60), SUNDAY)
    assert len(s.trend) == 42
    assert s.trend[-1].day == SUNDAY


def test_requires_two_weeks_of_data():
    with pytest.raises(ValueError, match="14"):
        summarize_week(wellness(n=10), SUNDAY)


def test_requires_contiguous_days():
    days = wellness()
    del days[-3]
    with pytest.raises(ValueError, match="Lücke"):
        summarize_week(days, SUNDAY)


def test_short_history_shortens_trend():
    s = summarize_week(wellness(n=20), SUNDAY)
    assert len(s.trend) == 20


# --- Hinweise (Heuristiken) ---------------------------------------------------


def _with_end(ctl: float, atl: float, ramp: float):
    days = wellness()
    last = days[-1]
    days[-1] = WellnessDay(last.day, ctl, atl, ramp, last.ctl_load, last.atl_load)
    return summarize_week(days, SUNDAY)


def test_flag_high_ramp():
    assert "ramp" in {f.key for f in _with_end(50, 50, 9.0).flags}
    assert "ramp" not in {f.key for f in _with_end(50, 50, 5.0).flags}


def test_flag_deep_fatigue():
    assert "tsb-low" in {f.key for f in _with_end(40, 75, 2.0).flags}


def test_flag_fresh():
    assert "tsb-fresh" in {f.key for f in _with_end(50, 35, 0.0).flags}


def test_flag_detraining():
    assert "detraining" in {f.key for f in _with_end(40, 30, -6.0).flags}


# --- Aktivitäten --------------------------------------------------------------


def test_parse_activities():
    acts = parse_activities(
        [
            {"date": "2026-09-17", "name": "Flamingos", "duration_min": 311, "load": 414},
            {"date": "2026-09-15", "name": "Annecy", "duration_min": 195, "load": None},
        ]
    )
    assert [a.day for a in acts] == [date(2026, 9, 15), date(2026, 9, 17)]
    assert acts[0].load is None and acts[0].avg_watts is None


@pytest.mark.parametrize(
    "record",
    [
        {"name": "x", "duration_min": 10},
        {"date": "2026-09-15", "name": "x", "duration_min": -1},
        {"date": "2026-09-15", "name": "x", "duration_min": 10, "load": float("nan")},
    ],
)
def test_parse_activities_invalid(record):
    with pytest.raises(ValueError):
        parse_activities([record])


# --- HTML ---------------------------------------------------------------------


def test_render_contains_key_figures_and_themes():
    s = summarize_week(wellness(), SUNDAY)
    html = render_html(s)
    assert "<title>" in html and "KW 38" in html
    assert f"{s.total_load:.0f}" in html
    assert "prefers-color-scheme: dark" in html and '[data-theme="dark"]' in html
    assert "<svg" in html


def test_render_escapes_activity_names():
    s = summarize_week(wellness(), SUNDAY)
    act = Activity(date(2026, 9, 15), "<script>alert(1)</script>", 60.0, 50.0, None)
    html = render_html(s, [act])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_only_week_activities():
    s = summarize_week(wellness(), SUNDAY)
    inside = Activity(date(2026, 9, 15), "Drinnen", 60.0, 50.0, 180.0)
    outside = Activity(date(2026, 9, 22), "Draußen", 60.0, 50.0, 180.0)
    html = render_html(s, [inside, outside])
    assert "Drinnen" in html and "Draußen" not in html
