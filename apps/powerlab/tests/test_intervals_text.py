from datetime import date

import pytest

from powerlab.intervals import parse_wellness
from powerlab.intervals_text import parse_activities_text, parse_wellness_text
from powerlab.report import parse_activities

# Format wie vom Intervals-MCP (get_wellness_data, fields=["training"]) geliefert
WELLNESS = """Wellness Data:

Wellness Data:
Date: 2026-08-01

Training Metrics:
- Fitness (CTL): 46.19273
- Fatigue (ATL): 38.76316
- Ramp Rate: -2.6287117
- CTL Load: 0.0
- ATL Load: 0.0

Status: Unlocked

Wellness Data:
Date: 2026-08-02

Training Metrics:
- Fitness (CTL): 45.105892
- Fatigue (ATL): 33.60293
- Ramp Rate: -3.7432785
- CTL Load: 12.0
- ATL Load: 10.0

Status: Unlocked
"""

# Format wie vom Intervals-MCP (get_activities, compact=True) geliefert
ACTIVITIES = """Activities:

 | ?: Unnamed (ID:20308267848)
2026-09-23 | Ride: Hausrunde (ID:i190288698) | 55053m | 156min | TL:133 | HR:120 | Pwr:134W
2026-09-20 | Ride: Arles (ID:i190288701) | 18285m | 252min
2026-09-18 | VirtualRide: Zwift: Watopia (ID:i190288715) | 40000m | 60min | TL:70 | Pwr:210W
"""


# --- Wellness -----------------------------------------------------------------


def test_wellness_parses_all_days_in_api_format():
    records = parse_wellness_text(WELLNESS)
    assert records == [
        {
            "id": "2026-08-01",
            "ctl": 46.19273,
            "atl": 38.76316,
            "rampRate": -2.6287117,
            "ctlLoad": 0.0,
            "atlLoad": 0.0,
        },
        {
            "id": "2026-08-02",
            "ctl": 45.105892,
            "atl": 33.60293,
            "rampRate": -3.7432785,
            "ctlLoad": 12.0,
            "atlLoad": 10.0,
        },
    ]


def test_wellness_output_is_accepted_by_parse_wellness():
    days = parse_wellness(parse_wellness_text(WELLNESS))
    assert [d.day for d in days] == [date(2026, 8, 1), date(2026, 8, 2)]
    assert days[1].atl_load == 10.0


def test_wellness_missing_optional_field_is_none():
    text = WELLNESS.replace("- Ramp Rate: -2.6287117\n", "")
    assert parse_wellness_text(text)[0]["rampRate"] is None


def test_wellness_missing_ctl_raises():
    with pytest.raises(ValueError, match="2026-08-01"):
        parse_wellness_text(WELLNESS.replace("- Fitness (CTL): 46.19273\n", ""))


def test_wellness_without_days_raises():
    with pytest.raises(ValueError):
        parse_wellness_text("Wellness Data:\n\nkeine Daten")


def test_wellness_duplicate_day_raises():
    block = WELLNESS.split("Wellness Data:\nDate: 2026-08-02")[0]
    with pytest.raises(ValueError, match="doppelt"):
        parse_wellness_text(block + block.replace("Wellness Data:\n\n", "", 1))


# --- Aktivitäten --------------------------------------------------------------


def test_activities_parse_named_entries_only():
    acts = parse_activities_text(ACTIVITIES)
    assert [a["name"] for a in acts] == ["Hausrunde", "Arles", "Zwift: Watopia"]


def test_activities_fields():
    first, second, third = parse_activities_text(ACTIVITIES)
    assert first == {
        "date": "2026-09-23",
        "type": "Ride",
        "name": "Hausrunde",
        "id": "i190288698",
        "duration_min": 156.0,
        "load": 133.0,
        "avg_watts": 134.0,
    }
    assert second["load"] is None and second["avg_watts"] is None
    assert third["type"] == "VirtualRide"


def test_activities_output_is_accepted_by_parse_activities():
    acts = parse_activities(parse_activities_text(ACTIVITIES))
    assert acts[0].day == date(2026, 9, 18)


def test_activities_line_without_duration_raises():
    with pytest.raises(ValueError, match="Dauer"):
        parse_activities_text("2026-09-23 | Ride: X (ID:i1) | 100m | TL:5")


def test_activities_empty_list_is_fine():
    assert parse_activities_text("Activities:\n\n | ?: Unnamed (ID:1)\n") == []
