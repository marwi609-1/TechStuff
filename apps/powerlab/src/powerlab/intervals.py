"""Import und Abgleich von Intervals.icu-Daten.

Erwartet das JSON-Format der Intervals-API (`/athlete/{id}/wellness`):
``id`` = Datum (ISO), ``ctl``, ``atl``, ``rampRate``, ``ctlLoad``.

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
    load: float
    """Tages-Trainingsbelastung (``ctlLoad``); fehlend = Ruhetag = 0."""


@dataclass(frozen=True, slots=True)
class PmcComparison:
    method: Method
    n_days: int
    max_abs_ctl: float
    mean_abs_ctl: float
    max_abs_atl: float
    mean_abs_atl: float
    max_abs_ramp: float
    """Nur über Tage mit ≥ 7 Tagen Vorlauf im eigenen Lauf; 0 wenn keine."""


def _required_float(record: Mapping[str, Any], key: str) -> float:
    value = record.get(key)
    if value is None or not math.isfinite(float(value)):
        raise ValueError(f"Feld {key!r} fehlt oder ist ungültig in {record.get('id')}")
    return float(value)


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
        ramp = record.get("rampRate")
        load = record.get("ctlLoad")
        days.append(
            WellnessDay(
                day=day,
                ctl=_required_float(record, "ctl"),
                atl=_required_float(record, "atl"),
                ramp=None if ramp is None else float(ramp),
                load=0.0 if load is None else float(load),
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
    ours = performance_management_chart(
        [(d.day, d.load) for d in rest], ctl0=seed.ctl, atl0=seed.atl, method=method
    )
    d_ctl = [abs(o.ctl - w.ctl) for o, w in zip(ours, rest, strict=True)]
    d_atl = [abs(o.atl - w.atl) for o, w in zip(ours, rest, strict=True)]
    d_ramp = [
        abs(o.ramp - w.ramp)
        for o, w in zip(ours, rest, strict=True)
        if o.ramp is not None and w.ramp is not None
    ]
    return PmcComparison(
        method=method,
        n_days=len(rest),
        max_abs_ctl=max(d_ctl),
        mean_abs_ctl=sum(d_ctl) / len(d_ctl),
        max_abs_atl=max(d_atl),
        mean_abs_atl=sum(d_atl) / len(d_atl),
        max_abs_ramp=max(d_ramp, default=0.0),
    )
