"""Import und Abgleich von Intervals.icu-Daten.

Erwartet das JSON-Format der Intervals-API (`/athlete/{id}/wellness`):
``id`` = Datum (ISO), ``ctl``, ``atl``, ``rampRate``, ``ctlLoad``, ``atlLoad``.

Befunde aus dem Abgleich mit echten Daten (Sept. 2026):
- Intervals glättet exponentiell: an Ruhetagen gilt CTL_t / CTL_{t−1} = e^(−1/42),
  ATL_t / ATL_{t−1} = e^(−1/7) → ``method="exponential"`` verwenden.
- Ramp-Rate = CTL_t − CTL_{t−7}, identisch zu :mod:`powerlab.pmc`.
- Training Load einer Aktivität basiert auf der Bewegungszeit, nicht der Gesamtzeit.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from powerlab.pmc import Method, performance_management_chart


@dataclass(frozen=True, slots=True)
class WellnessDay:
    day: date
    ctl: float
    atl: float
    ramp: float | None
    ctl_load: float
    """Tagesbelastung für CTL (``ctlLoad``); fehlend = Ruhetag = 0."""
    atl_load: float
    """Tagesbelastung für ATL (``atlLoad``); kann per Sportart-Einstellung von ctl_load
    abweichen, fehlend = ctl_load."""


@dataclass(frozen=True, slots=True)
class PmcComparison:
    method: Method
    n_days: int
    max_abs_ctl: float
    mean_abs_ctl: float
    max_abs_atl: float
    mean_abs_atl: float
    max_abs_ramp: float | None
    """Ab dem 7. Tag nach dem Seed; None, wenn kein Tag vergleichbar war."""


def _optional_float(record: Mapping[str, Any], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Feld {key!r} ist nicht endlich in {record.get('id')}: {value}")
    return number


def _required_float(record: Mapping[str, Any], key: str) -> float:
    number = _optional_float(record, key)
    if number is None:
        raise ValueError(f"Feld {key!r} fehlt in {record.get('id')}")
    return number


def parse_wellness(records: Iterable[Mapping[str, Any]]) -> list[WellnessDay]:
    """Wandelt Intervals-Wellness-Records in :class:`WellnessDay` um, sortiert nach Datum."""
    days = []
    for record in records:
        if "id" not in record:
            raise ValueError(f"Record ohne Datum ('id'): {record}")
        try:
            day = date.fromisoformat(str(record["id"]))
        except ValueError as e:
            raise ValueError(f"Ungültiges Datum: {record['id']!r}") from e
        ctl_load = _optional_float(record, "ctlLoad") or 0.0
        atl_load = _optional_float(record, "atlLoad")
        days.append(
            WellnessDay(
                day=day,
                ctl=_required_float(record, "ctl"),
                atl=_required_float(record, "atl"),
                ramp=_optional_float(record, "rampRate"),
                ctl_load=ctl_load,
                atl_load=ctl_load if atl_load is None else atl_load,
            )
        )
    return sorted(days, key=lambda d: d.day)


def compare_pmc(wellness: Sequence[WellnessDay], method: Method = "exponential") -> PmcComparison:
    """Rechnet den PMC aus den Intervals-Tagesloads nach und vergleicht CTL/ATL/Ramp.

    Der erste Tag dient als Seed (``ctl0``/``atl0``), verglichen werden die folgenden Tage.
    Die Tage müssen lückenlos sein, sonst wäre der Vergleich nicht eindeutig.
    """
    if len(wellness) < 2:
        raise ValueError("Mindestens zwei Tage nötig (Seed + Vergleich)")
    for prev, cur in zip(wellness, wellness[1:], strict=False):
        if cur.day - prev.day != timedelta(days=1):
            raise ValueError(f"Lücke in den Wellness-Daten zwischen {prev.day} und {cur.day}")

    seed, rest = wellness[0], wellness[1:]
    kwargs = {"ctl0": seed.ctl, "atl0": seed.atl, "method": method}
    # Zwei Läufe, weil Intervals CTL und ATL aus getrennten Tagesloads speist
    by_ctl = performance_management_chart([(d.day, d.ctl_load) for d in rest], **kwargs)
    by_atl = performance_management_chart([(d.day, d.atl_load) for d in rest], **kwargs)
    d_ctl = [abs(o.ctl - w.ctl) for o, w in zip(by_ctl, rest, strict=True)]
    d_atl = [abs(o.atl - w.atl) for o, w in zip(by_atl, rest, strict=True)]
    d_ramp = [
        abs(o.ramp - w.ramp)
        for o, w in zip(by_ctl, rest, strict=True)
        if o.ramp is not None and w.ramp is not None
    ]
    return PmcComparison(
        method=method,
        n_days=len(rest),
        max_abs_ctl=max(d_ctl),
        mean_abs_ctl=sum(d_ctl) / len(d_ctl),
        max_abs_atl=max(d_atl),
        mean_abs_atl=sum(d_atl) / len(d_atl),
        max_abs_ramp=max(d_ramp, default=None),
    )
