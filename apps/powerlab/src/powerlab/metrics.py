"""Belastungsmetriken nach Coggan: NP, IF, TSS, VI.

Annahme: Leistungsdaten liegen als lückenlose 1-Hz-Reihe in Watt vor.
Resampling und Lückenbehandlung gehören in die Import-Schicht, nicht hierher.
"""

from collections.abc import Iterable, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

NP_WINDOW_S = 30

PowerSeries = ArrayLike | Sequence[float]


def _as_power_array(power: PowerSeries) -> NDArray[np.float64]:
    arr = np.asarray(power, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("Leistungsreihe muss eindimensional sein")
    if not np.all(np.isfinite(arr)):
        raise ValueError("Leistungsreihe enthält NaN oder Inf")
    if np.any(arr < 0):
        raise ValueError("Leistungsreihe enthält negative Werte")
    return arr


def _rolling_means(arr: NDArray[np.float64], window: int) -> NDArray[np.float64]:
    """Mittelwerte aller vollständigen Fenster der Länge ``window`` (via kumulierter Summe)."""
    cumsum = np.concatenate(([0.0], np.cumsum(arr)))
    return (cumsum[window:] - cumsum[:-window]) / window


def _check_ftp(ftp: float) -> None:
    if not np.isfinite(ftp) or ftp <= 0:
        raise ValueError(f"FTP muss positiv und endlich sein, erhalten: {ftp}")


def normalized_power(power: PowerSeries) -> float:
    """Normalized Power: 4. Wurzel des Mittels der 4. Potenz des 30-s-Rollmittels.

    Das Rollmittel startet erst mit dem ersten vollständigen 30-s-Fenster
    (keine Teilfenster), wie in Coggans Originaldefinition.
    """
    arr = _as_power_array(power)
    if arr.size < NP_WINDOW_S:
        raise ValueError(f"Mindestens {NP_WINDOW_S} s Daten nötig, erhalten: {arr.size}")
    rolling = _rolling_means(arr, NP_WINDOW_S)
    return float(np.mean(rolling**4) ** 0.25)


def intensity_factor(np_watts: float, ftp: float) -> float:
    """IF = NP / FTP."""
    _check_ftp(ftp)
    return np_watts / ftp


def training_stress_score(power: PowerSeries, ftp: float) -> float:
    """TSS = (Dauer_s * NP * IF) / (FTP * 3600) * 100 = Stunden * IF² * 100."""
    _check_ftp(ftp)
    arr = _as_power_array(power)
    if_ = intensity_factor(normalized_power(arr), ftp)
    return arr.size / 3600 * if_**2 * 100


def variability_index(power: PowerSeries) -> float:
    """VI = NP / Durchschnittsleistung."""
    arr = _as_power_array(power)
    avg = float(np.mean(arr))
    if avg == 0:
        raise ValueError("Durchschnittsleistung ist 0, VI undefiniert")
    return normalized_power(arr) / avg


def mean_max_power(power: PowerSeries, durations: Iterable[int]) -> NDArray[np.float64]:
    """Mean Maximal Power: höchste Durchschnittsleistung je Dauer (Sekunden, ganzzahlig)."""
    arr = _as_power_array(power)
    result = []
    for d in durations:
        valid = isinstance(d, int | float | np.number) and np.isfinite(d) and d == int(d)
        if not valid or not 1 <= d <= arr.size:
            raise ValueError(f"Dauer muss ganzzahlig in [1, {arr.size}] s liegen, erhalten: {d!r}")
        result.append(np.max(_rolling_means(arr, int(d))))
    return np.asarray(result, dtype=np.float64)
