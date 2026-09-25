"""Import-Schicht: lückenhafte Leistungs-Streams -> lückenlose 1-Hz-Reihe.

Die Metriken in :mod:`powerlab.metrics` erwarten eine lückenlose 1-Hz-Reihe. Reale
Streams (Geräte-Auto-Pause, Smart Recording, Funkaussetzer) haben Lücken. Dieses Modul
normalisiert sie in drei Schritten:

1. **Sekunden-Binning:** Jedes Sample bei ``t`` gehört zur Sekunde ``floor(t)``; mehrere
   Samples in derselben Sekunde (z. B. 2-4 Hz) werden arithmetisch gemittelt. Bei
   gleichmäßiger Abtastung ist das energieerhaltend (Arbeit in J bleibt gleich), während
   punktweise Interpolation auf ganze Sekunden Samples verwirft bzw. Spitzen verschiebt.
   Bei ungleichmäßiger Abtastung innerhalb einer Sekunde ist das Mittel sample- statt
   zeitgewichtet – für Radcomputer-Streams (konstante Rate) vernachlässigbar.
2. **Kurze Lücken** (``<= max_fill_s`` fehlende Sekunden): lineare Interpolation zwischen
   den Nachbarsekunden, analog zu GoldenCheetahs „Fix Gaps in Recording“ (lineare
   Interpolation bis zu einer Toleranz, darüber als Stopp behandelt). Gegenüber Halten
   des letzten Werts verteilt das die Arbeit symmetrisch auf beide Nachbarn und erzeugt
   keine künstlichen Plateaus; bei wenigen Sekunden ist der Einfluss auf NP marginal.
3. **Lange Lücken** (``> max_fill_s``) gelten als Pause:
   ``"drop"`` entfernt sie (Reihe = Bewegungszeit, konsistent zur Intervals.icu-
   Training-Load), ``"zero"`` füllt mit 0 W (Gesamtzeit-Sicht; senkt NP/IF, verlängert
   die Dauer für TSS und kann 0-W-Fenster in die MMP bringen).

Fehlende Leistungswerte dürfen als ``NaN``/``None`` übergeben werden (Intervals-Streams
enthalten ``null`` bei Powermeter-Aussetzern mit weiterlaufender Zeit). Sie werden wie
fehlende Samples behandelt, also je nach Länge interpoliert oder als Pause gewertet.
Andere ungültige Werte (Inf, negative Watt, nicht monotone Zeit) -> ``ValueError``.
"""

from typing import Literal, get_args

import numpy as np
from numpy.typing import ArrayLike, NDArray

PausePolicy = Literal["drop", "zero"]
_POLICIES: tuple[str, ...] = get_args(PausePolicy)


def _as_time_array(time_s: ArrayLike) -> NDArray[np.float64]:
    arr = np.asarray(time_s, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("Zeitreihe muss eindimensional sein")
    if arr.size == 0:
        raise ValueError("Zeitreihe ist leer")
    if not np.all(np.isfinite(arr)):
        raise ValueError("Zeitreihe enthält NaN oder Inf")
    if np.any(np.diff(arr) <= 0):
        raise ValueError("Zeitstempel müssen streng monoton steigen")
    return arr


def _as_watts_array(watts: ArrayLike, n: int) -> NDArray[np.float64]:
    arr = np.asarray(watts, dtype=np.float64)  # None -> NaN
    if arr.ndim != 1:
        raise ValueError("Leistungsreihe muss eindimensional sein")
    if arr.size != n:
        raise ValueError(f"Zeit- und Leistungsreihe müssen gleich lang sein: {n} vs. {arr.size}")
    if np.any(np.isinf(arr)):
        raise ValueError("Leistungsreihe enthält Inf")
    if np.any(arr < 0):  # NaN-Vergleiche sind False
        raise ValueError("Leistungsreihe enthält negative Werte")
    if np.all(np.isnan(arr)):
        raise ValueError("Leistungsreihe enthält keinen gültigen Wert")
    return arr


def _check_max_fill(max_fill_s: int) -> None:
    valid = isinstance(max_fill_s, int | np.integer) and not isinstance(max_fill_s, bool)
    if not valid or max_fill_s < 0:
        raise ValueError(f"max_fill_s muss eine ganze Zahl >= 0 sein, erhalten: {max_fill_s!r}")


def _moving_seconds(seconds: NDArray[np.int64], max_fill_s: int) -> int:
    gaps = np.diff(seconds) - 1
    span = int(seconds[-1] - seconds[0] + 1)
    return span - int(gaps[gaps > max_fill_s].sum())


def to_1hz(
    time_s: ArrayLike,
    watts: ArrayLike,
    *,
    max_fill_s: int = 5,
    pause_policy: PausePolicy = "drop",
) -> NDArray[np.float64]:
    """Lückenhaften Leistungs-Stream in eine lückenlose 1-Hz-Reihe (Watt) überführen.

    Parameter:
        time_s: Sekunden seit Start (beliebiger Offset), streng monoton steigend.
        watts: Leistung je Sample; ``NaN``/``None`` = fehlender Wert.
        max_fill_s: Längste Lücke (fehlende Sekunden), die linear interpoliert wird.
        pause_policy: ``"drop"`` entfernt längere Lücken, ``"zero"`` füllt sie mit 0 W.

    Die Reihe beginnt mit der ersten und endet mit der letzten Sekunde, die einen
    gültigen Wert enthält. Mit ``"drop"`` gilt ``len(ergebnis) == moving_time_s(...)``.
    """
    _check_max_fill(max_fill_s)
    if pause_policy not in _POLICIES:
        raise ValueError(f"Unbekannte pause_policy {pause_policy!r}, erlaubt: {_POLICIES}")
    time = _as_time_array(time_s)
    power = _as_watts_array(watts, time.size)

    valid = ~np.isnan(power)
    bins = np.floor(time[valid]).astype(np.int64)
    # Zeit ist monoton -> np.unique liefert Sekunden sortiert, inverse ordnet Samples zu.
    seconds, inverse = np.unique(bins, return_inverse=True)
    means = np.bincount(inverse, weights=power[valid]) / np.bincount(inverse)

    grid = np.arange(seconds[0], seconds[-1] + 1)
    series = np.interp(grid, seconds, means)

    pause = np.diff(seconds) - 1 > max_fill_s  # Lücken, die als Pause gelten
    # Pausen-Sekunden per Differenzen-Array markieren: +1 am Pausenbeginn, -1 am Ende.
    marks = np.zeros(grid.size + 1, dtype=np.int64)
    np.add.at(marks, seconds[:-1][pause] + 1 - seconds[0], 1)
    np.add.at(marks, seconds[1:][pause] - seconds[0], -1)
    in_pause = np.cumsum(marks[:-1]) > 0

    if pause_policy == "zero":
        series[in_pause] = 0.0
        return series
    return series[~in_pause]


def moving_time_s(
    time_s: ArrayLike,
    *,
    watts: ArrayLike | None = None,
    max_fill_s: int = 5,
) -> int:
    """Bewegungszeit in Sekunden: belegte Sekunden plus gefüllte kurze Lücken.

    Entspricht ``len(to_1hz(time_s, watts, max_fill_s=max_fill_s, pause_policy="drop"))``.
    Wird ``watts`` übergeben, zählen Samples mit ``NaN``/``None`` als fehlend (wie in
    :func:`to_1hz`); ohne ``watts`` zählt jedes Sample.

    Hinweis: Intervals.icu/Garmin bestimmen Bewegungszeit teils geschwindigkeitsbasiert;
    hier ist sie rein über Aufzeichnungslücken definiert.
    """
    _check_max_fill(max_fill_s)
    time = _as_time_array(time_s)
    if watts is not None:
        time = time[~np.isnan(_as_watts_array(watts, time.size))]
    seconds = np.unique(np.floor(time).astype(np.int64))
    return _moving_seconds(seconds, max_fill_s)
