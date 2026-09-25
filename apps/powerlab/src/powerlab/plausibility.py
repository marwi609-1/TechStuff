"""Plausibilitätsprüfung von Tages-Loads und What-if-Rechnung für den PMC.

Hintergrund: Bei Fahrten ohne Leistungsmessung berechnet Intervals.icu die Load aus der
Herzfrequenz. Pulsartefakte (Sensor-Spikes) können sie mehr als verdoppeln (beobachtet:
IF ≈ 1,0 bei Ø-HR deutlich unter LTHR) und verzerren so Ramp-Rate und Form.

:func:`hr_load_estimate` liefert eine grobe Gegenrechnung nach dem hrTSS-Prinzip
(Stunden · (Ø-HR/LTHR)² · 100). Weil die Durchschnitts-HR die Zeit in hohen Zonen
unterschätzt, ist das eher eine Untergrenze; erst deutliche Abweichungen (Faktor > 1,5)
sind ein Hinweis auf Artefakte, kein Beweis.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from powerlab.intervals import WellnessDay
from powerlab.pmc import performance_management_chart

SUSPICIOUS_FACTOR = 1.5


@dataclass(frozen=True, slots=True)
class WhatIf:
    """PMC-Stand am letzten Tag der Reihe nach Ersetzen eines Tages-Loads."""

    ctl: float
    atl: float
    ramp: float
    form_next_morning: float


def hr_load_estimate(avg_hr: float, lthr: float, moving_time_s: float) -> float:
    """Grobe HR-Load: Stunden · (Ø-HR / LTHR)² · 100 (hrTSS-Prinzip, Untergrenze)."""
    for name, value in (("avg_hr", avg_hr), ("lthr", lthr)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} muss positiv sein, erhalten: {value}")
    if not math.isfinite(moving_time_s) or moving_time_s < 0:
        raise ValueError(f"moving_time_s muss >= 0 sein, erhalten: {moving_time_s}")
    return moving_time_s / 3600 * (avg_hr / lthr) ** 2 * 100


def what_if_load(wellness: Sequence[WellnessDay], day: date, new_load: float) -> WhatIf:
    """Rechnet CTL/ATL/Ramp/Form am letzten Tag neu, wenn ``day`` den Load ``new_load`` hätte.

    Seed sind die Intervals-Werte des Vortags; ab ``day`` wird exponentiell (wie Intervals)
    mit den Intervals-Tagesloads weitergerechnet. Getrennte CTL-/ATL-Loads bleiben erhalten,
    ``new_load`` ersetzt beide.
    """
    if not math.isfinite(new_load) or new_load < 0:
        raise ValueError(f"new_load muss >= 0 sein, erhalten: {new_load}")
    days = sorted(wellness, key=lambda d: d.day)
    for prev, cur in zip(days, days[1:], strict=False):
        if cur.day - prev.day != timedelta(days=1):
            raise ValueError(f"Lücke in den Wellness-Daten zwischen {prev.day} und {cur.day}")
    index = {d.day: i for i, d in enumerate(days)}
    if day not in index:
        raise ValueError(f"{day} liegt nicht in den Wellness-Daten")
    i = index[day]
    if i == 0:
        raise ValueError("Der erste Tag dient als Seed und kann nicht ersetzt werden")

    seed, rest = days[i - 1], days[i:]
    kwargs = {"ctl0": seed.ctl, "atl0": seed.atl, "method": "exponential"}
    ctl_loads = [(d.day, new_load if d.day == day else d.ctl_load) for d in rest]
    atl_loads = [(d.day, new_load if d.day == day else d.atl_load) for d in rest]
    by_ctl = performance_management_chart(ctl_loads, **kwargs)
    by_atl = performance_management_chart(atl_loads, **kwargs)

    ctl_series = [d.ctl for d in days[:i]] + [p.ctl for p in by_ctl]
    if len(ctl_series) < 8:
        raise ValueError("Für die Ramp-Rate sind mindestens 8 Tage nötig")
    ctl, atl = by_ctl[-1].ctl, by_atl[-1].atl
    return WhatIf(
        ctl=ctl,
        atl=atl,
        ramp=ctl - ctl_series[-8],
        form_next_morning=ctl - atl,
    )
