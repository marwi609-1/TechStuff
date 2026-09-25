"""Critical-Power-Modelle: Fit von CP und W′ an Mean-Maximal-Power-Punkte.

2-Parameter-Modell (Monod & Scherrer 1965; Hill 1993): P(t) = CP + W′/t.
Die üblichen Linearisierungen liefern auf realen Daten *unterschiedliche* Werte,
weil sie die Residuen verschieden gewichten (Mattioni Maturana et al. 2018):
- ``inverse-time``: P gegen 1/t. Da das Modell linear in CP und W′ ist, entspricht
  das exakt dem nichtlinearen Least-Squares-Fit der Hyperbel im Leistungsraum.
- ``work-time``: Arbeit W = P·t gegen t. Lange Efforts dominieren den Fit.

3-Parameter-Modell (Morton 1996): P(t) = CP + W′/(t − k) mit k = W′/(CP − Pmax) < 0.
Bildet auch Sprint-Dauern ab; ohne kurze Efforts (< ~60 s) ist Pmax schlecht bestimmt.

Datenauswahl: Für das 2P-Modell Efforts zwischen ~2 und 20 min verwenden
(Jones et al. 2010, Med Sci Sports Exerc). Die Funktionen prüfen das nicht.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

Model = Literal["2p-inverse-time", "2p-work-time", "3p-morton"]
Method2p = Literal["inverse-time", "work-time"]

# Suchbereich für Mortons k (s). k → 0⁻ entspricht dem 2P-Modell (Pmax → ∞).
_K_MIN, _K_MAX = -600.0, -1e-3
_GOLDEN = (math.sqrt(5) - 1) / 2
# Liegt das Optimum innerhalb von 1 % am Rand, gilt k als nicht bestimmt.
_BOUNDARY_TOL = 0.99


@dataclass(frozen=True, slots=True)
class CpFit:
    model: Model
    cp: float
    """Critical Power (W)."""
    w_prime: float
    """W′ (J)."""
    pmax: float | None
    """Nur 3P-Modell: theoretische Maximalleistung bei t → 0 (W)."""
    rmse: float
    """Wurzel des mittleren quadratischen Residuums im Leistungsraum (W)."""
    cp_se: float | None
    """Standardfehler von CP aus der Regression; None bei < 3 Punkten oder 3P."""
    w_prime_se: float | None

    @property
    def _k(self) -> float:
        return 0.0 if self.pmax is None else self.w_prime / (self.cp - self.pmax)

    def power_at(self, t: float) -> float:
        """Vorhergesagte Maximalleistung für die Dauer t (s)."""
        if not math.isfinite(t) or t <= 0:
            raise ValueError(f"Dauer muss positiv und endlich sein, erhalten: {t}")
        return self.cp + self.w_prime / (t - self._k)

    def time_to_exhaustion(self, power: float) -> float:
        """Vorhergesagte Zeit bis zur Erschöpfung bei konstanter Leistung (s)."""
        if not math.isfinite(power):
            raise ValueError(f"Leistung muss endlich sein, erhalten: {power}")
        if power <= self.cp:
            return math.inf
        if self.pmax is not None and power >= self.pmax:
            return 0.0
        return self.w_prime / (power - self.cp) + self._k


def _as_points(
    durations: ArrayLike | Sequence[float], powers: ArrayLike | Sequence[float], min_points: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    t = np.asarray(durations, dtype=np.float64)
    p = np.asarray(powers, dtype=np.float64)
    if t.ndim != 1 or t.shape != p.shape:
        raise ValueError("durations und powers müssen eindimensional und gleich lang sein")
    if t.size < min_points:
        raise ValueError(f"Mindestens {min_points} Punkte nötig, erhalten: {t.size}")
    if not (np.all(np.isfinite(t)) and np.all(np.isfinite(p))):
        raise ValueError("Punkte enthalten NaN oder Inf")
    if np.any(t <= 0) or np.any(p <= 0):
        raise ValueError("Dauern und Leistungen müssen positiv sein")
    if np.unique(t).size < 2:
        raise ValueError("Mindestens zwei verschiedene Dauern nötig")
    return t, p


def _ols(
    x: NDArray[np.float64], y: NDArray[np.float64]
) -> tuple[float, float, float | None, float | None]:
    """Einfache lineare Regression y = a + b·x mit Standardfehlern von a und b."""
    n = x.size
    x_mean = x.mean()
    sxx = float(np.sum((x - x_mean) ** 2))
    b = float(np.sum((x - x_mean) * (y - y.mean())) / sxx)
    a = float(y.mean() - b * x_mean)
    if n < 3:
        return a, b, None, None
    s2 = float(np.sum((y - a - b * x) ** 2)) / (n - 2)
    se_b = math.sqrt(s2 / sxx)
    se_a = math.sqrt(s2 * (1 / n + x_mean**2 / sxx))
    return a, b, se_a, se_b


def _check_plausible(cp: float, w_prime: float) -> None:
    if cp <= 0 or w_prime <= 0:
        raise ValueError(
            f"Physiologisch unplausibler Fit (CP={cp:.1f} W, W′={w_prime:.0f} J) – "
            "Leistung muss mit der Dauer fallen"
        )


def _rmse(
    t: NDArray[np.float64], p: NDArray[np.float64], cp: float, w_prime: float, k: float = 0.0
) -> float:
    return float(np.sqrt(np.mean((p - cp - w_prime / (t - k)) ** 2)))


def fit_cp_2p(
    durations: ArrayLike | Sequence[float],
    powers: ArrayLike | Sequence[float],
    *,
    method: Method2p = "inverse-time",
) -> CpFit:
    """Fittet das 2-Parameter-CP-Modell. Siehe Modul-Docstring zur Methodenwahl."""
    t, p = _as_points(durations, powers, min_points=2)
    if method == "inverse-time":
        cp, w_prime, cp_se, w_se = _ols(1 / t, p)
    elif method == "work-time":
        w_prime, cp, w_se, cp_se = _ols(t, p * t)
    else:
        raise ValueError(f"Unbekannte Methode: {method!r} (erlaubt: 'inverse-time', 'work-time')")
    _check_plausible(cp, w_prime)
    return CpFit(f"2p-{method}", cp, w_prime, None, _rmse(t, p, cp, w_prime), cp_se, w_se)


def _fit_given_k(
    t: NDArray[np.float64], p: NDArray[np.float64], k: float
) -> tuple[float, float, float]:
    """Für festes k ist Morton linear in CP und W′: P = CP + W′·1/(t − k)."""
    cp, w_prime, _, _ = _ols(1 / (t - k), p)
    rss = float(np.sum((p - cp - w_prime / (t - k)) ** 2))
    return cp, w_prime, rss


def fit_cp_3p(durations: ArrayLike | Sequence[float], powers: ArrayLike | Sequence[float]) -> CpFit:
    """Fittet Mortons 3-Parameter-Modell per Profil-Likelihood über k.

    Für jedes k ist das Problem linear; k selbst wird per Log-Gitter und
    anschließendem Goldenen Schnitt auf k ∈ [−600 s, 0) bestimmt.
    """
    t, p = _as_points(durations, powers, min_points=3)
    grid = -np.geomspace(-_K_MAX, -_K_MIN, 400)
    rss = [_fit_given_k(t, p, k)[2] for k in grid]
    i = int(np.argmin(rss))
    lo, hi = grid[min(i + 1, grid.size - 1)], grid[max(i - 1, 0)]

    # Goldener Schnitt im Intervall um das Gitterminimum
    a, b = lo, hi
    c, d = b - _GOLDEN * (b - a), a + _GOLDEN * (b - a)
    fc, fd = _fit_given_k(t, p, c)[2], _fit_given_k(t, p, d)[2]
    while b - a > 1e-9:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - _GOLDEN * (b - a)
            fc = _fit_given_k(t, p, c)[2]
        else:
            a, c, fc = c, d, fd
            d = a + _GOLDEN * (b - a)
            fd = _fit_given_k(t, p, d)[2]
    k = (a + b) / 2
    if not _K_MIN * _BOUNDARY_TOL < k < _K_MAX / _BOUNDARY_TOL:
        raise ValueError(
            f"3P-Fit am Rand des Suchbereichs (k = {k:.3g} s): Pmax nicht bestimmbar – "
            "kurze Efforts (< 60 s) ergänzen oder 2P-Modell verwenden"
        )

    cp, w_prime, _ = _fit_given_k(t, p, k)
    _check_plausible(cp, w_prime)
    pmax = cp - w_prime / k
    return CpFit("3p-morton", cp, w_prime, pmax, _rmse(t, p, cp, w_prime, k), None, None)
