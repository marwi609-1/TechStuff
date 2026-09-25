import math
from datetime import date, timedelta

import pytest

from powerlab.intervals import WellnessDay, compare_pmc, parse_wellness

D0 = date(2026, 7, 1)


def synthetic_wellness(method: str, n: int = 60) -> list[dict]:
    """Wellness-Records im Intervals-API-Format, erzeugt mit bekanntem Modell."""
    k = (lambda tau: 1 / tau) if method == "coggan" else (lambda tau: 1 - math.exp(-1 / tau))
    loads = [(i * 37) % 160 if i % 3 else 0 for i in range(n)]
    ctl, atl, ctls, records = 45.0, 50.0, [], []
    for i, load in enumerate(loads):
        if i:
            ctl += k(42) * (load - ctl)
            atl += k(7) * (load - atl)
        ctls.append(ctl)
        ramp = ctl - ctls[i - 7] if i >= 7 else None
        records.append(
            {
                "id": (D0 + timedelta(days=i)).isoformat(),
                "ctl": ctl,
                "atl": atl,
                "rampRate": ramp,
                "ctlLoad": float(load),
            }
        )
    return records


# --- parse_wellness -----------------------------------------------------------


def test_parse_maps_api_fields():
    days = parse_wellness(
        [{"id": "2026-08-03", "ctl": 45.2, "atl": 35.8, "rampRate": -2.5, "ctlLoad": 50.0}]
    )
    assert days == [WellnessDay(date(2026, 8, 3), ctl=45.2, atl=35.8, ramp=-2.5, load=50.0)]


def test_parse_sorts_by_date():
    records = synthetic_wellness("exponential", n=5)
    assert parse_wellness(reversed(records)) == parse_wellness(records)


def test_parse_missing_load_is_rest_day():
    days = parse_wellness([{"id": "2026-08-01", "ctl": 46.0, "atl": 38.0, "ctlLoad": None}])
    assert days[0].load == 0.0
    assert days[0].ramp is None


@pytest.mark.parametrize(
    "record",
    [
        {"id": "2026-08-01", "atl": 38.0},  # ctl fehlt
        {"id": "2026-08-01", "ctl": None, "atl": 38.0},
        {"id": "kein-datum", "ctl": 46.0, "atl": 38.0},
        {"ctl": 46.0, "atl": 38.0},
    ],
)
def test_parse_invalid_record_raises(record):
    with pytest.raises(ValueError):
        parse_wellness([record])


# --- compare_pmc --------------------------------------------------------------


def test_compare_same_method_reproduces_exactly():
    days = parse_wellness(synthetic_wellness("exponential"))
    result = compare_pmc(days, method="exponential")
    assert result.n_days == 59  # erster Tag dient als Seed
    assert result.max_abs_ctl == pytest.approx(0.0, abs=1e-9)
    assert result.max_abs_atl == pytest.approx(0.0, abs=1e-9)
    assert result.max_abs_ramp == pytest.approx(0.0, abs=1e-9)


def test_compare_wrong_method_shows_deviation():
    days = parse_wellness(synthetic_wellness("exponential"))
    result = compare_pmc(days, method="coggan")
    assert result.max_abs_atl > 0.1
    assert result.max_abs_ctl > result.mean_abs_ctl > 0


def test_compare_detects_coggan_source():
    days = parse_wellness(synthetic_wellness("coggan"))
    assert compare_pmc(days, method="coggan").max_abs_ctl < 1e-9
    assert compare_pmc(days, method="exponential").max_abs_ctl > 1e-3


def test_compare_requires_consecutive_days():
    records = synthetic_wellness("exponential", n=10)
    del records[4]
    with pytest.raises(ValueError, match="Lücke"):
        compare_pmc(parse_wellness(records))


def test_compare_needs_two_days():
    with pytest.raises(ValueError):
        compare_pmc(parse_wellness(synthetic_wellness("exponential", n=1)))
