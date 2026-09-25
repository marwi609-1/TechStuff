"""Performance Management Chart: CTL (Fitness), ATL (Ermüdung), TSB (Form).

Modell: Impulse-Response nach Banister et al. (1975), in der vereinfachten Form von
Coggan (TrainingPeaks-PMC) als zwei exponentiell gewichtete gleitende Mittel der
Tages-TSS mit Zeitkonstanten 42 d (CTL) und 7 d (ATL).

Einordnung: heuristisches Modell mit guter Beschreibung der Belastungshistorie,
aber nur mäßiger prädiktiver Validität für individuelle Leistung
(Übersicht: Vermeire et al. 2022, Int J Sports Physiol Perform).
"""

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Method = Literal["coggan", "exponential"]

RAMP_WINDOW_D = 7


@dataclass(frozen=True, slots=True)
class PmcDay:
    day: date
    tss: float
    ctl: float
    atl: float
    tsb: float
    """Form am Morgen: CTL_{t-1} − ATL_{t-1} (TrainingPeaks-Konvention)."""
    ramp: float | None
    """CTL_t − CTL_{t-7}; ab dem 7. Tag verfügbar (CTL_{t-7} = ``ctl0``), davor None."""


def _smoothing_factor(tau_days: float, method: Method) -> float:
    if not math.isfinite(tau_days) or tau_days <= 0:
        raise ValueError(f"Zeitkonstante muss positiv sein, erhalten: {tau_days}")
    if method == "coggan":
        return 1 / tau_days
    if method == "exponential":
        return 1 - math.exp(-1 / tau_days)
    raise ValueError(f"Unbekannte Methode: {method!r} (erlaubt: 'coggan', 'exponential')")


def _aggregate_daily(daily_load: Iterable[tuple[date, float]]) -> dict[date, float]:
    totals: dict[date, float] = defaultdict(float)
    for day, tss in daily_load:
        if not math.isfinite(tss) or tss < 0:
            raise ValueError(f"Ungültiger TSS-Wert am {day}: {tss}")
        totals[day] += tss
    if not totals:
        raise ValueError("Keine Belastungsdaten übergeben")
    return totals


def performance_management_chart(
    daily_load: Iterable[tuple[date, float]],
    *,
    ctl_days: float = 42,
    atl_days: float = 7,
    ctl0: float = 0.0,
    atl0: float = 0.0,
    method: Method = "coggan",
    end: date | None = None,
) -> list[PmcDay]:
    """Berechnet den PMC Tag für Tag.

    Rekursion: X_t = X_{t−1} + k · (TSS_t − X_{t−1}) mit
    k = 1/τ (``coggan``, TrainingPeaks) oder k = 1 − e^(−1/τ) (``exponential``,
    zeitdiskrete Lösung des kontinuierlichen Banister-Modells).

    Mehrere Einträge pro Tag werden summiert, fehlende Tage als Ruhetag (TSS 0)
    behandelt. ``end`` verlängert die Reihe mit Ruhetagen, kürzt sie aber nie.
    ``ctl0``/``atl0`` sind die Werte am Vortag des ersten Eintrags.
    """
    k_ctl = _smoothing_factor(ctl_days, method)
    k_atl = _smoothing_factor(atl_days, method)
    if not (math.isfinite(ctl0) and math.isfinite(atl0)):
        raise ValueError("Startwerte ctl0/atl0 müssen endlich sein")

    totals = _aggregate_daily(daily_load)
    first, last = min(totals), max(totals)
    if end is not None:
        if end < first:
            raise ValueError(f"end ({end}) liegt vor dem ersten Eintrag ({first})")
        last = max(last, end)

    # Rekursiv und nur wenige tausend Tage: Python-Schleife statt numpy.
    result: list[PmcDay] = []
    ctl, atl = float(ctl0), float(atl0)
    ctl_history = [ctl]  # ctl_history[i] = CTL am Vortag von Tag i
    for i in range((last - first).days + 1):
        day = first + timedelta(days=i)
        tss = totals.get(day, 0.0)
        tsb = ctl - atl
        ctl += k_ctl * (tss - ctl)
        atl += k_atl * (tss - atl)
        ctl_history.append(ctl)
        ramp = ctl - ctl_history[i + 1 - RAMP_WINDOW_D] if i + 1 >= RAMP_WINDOW_D else None
        result.append(PmcDay(day=day, tss=tss, ctl=ctl, atl=atl, tsb=tsb, ramp=ramp))
    return result
