"""W′-Balance (W′bal): verbleibende anaerobe Arbeitskapazität über CP im Zeitverlauf.

Zwei Modelle nach Skiba:

- ``integral`` (Skiba et al. 2012, Med Sci Sports Exerc 44(8):1526–1532)::

      W′bal(t) = W′ − Σ_{u ≤ t, P(u) > CP} (P(u) − CP) · e^{−(t − u)/τ}
      τ = 546 · e^{−0.01 · D_CP} + 316      (s)

  D_CP = CP − mittlere Leistung der Sekunden unter CP. τ wurde empirisch aus
  intermittierenden Tests abgeleitet und ist im Original *eine* Konstante für die
  gesamte Einheit (D_CP aus allen Sekunden unter CP der ganzen Einheit, also auch
  aus Sekunden, die erst *nach* dem betrachteten Zeitpunkt liegen – nicht kausal).
  Verbrauchtes W′ klingt immer mit τ ab, auch während Arbeit über CP; das Modell
  erholt damit bereits während langer Belastungen über CP.

- ``differential`` (Skiba, Fulford, Clarke, Vanhatalo & Jones 2015,
  Eur J Appl Physiol 115(4):703–713)::

      P > CP:  dW′bal/dt = −(P − CP)
      P ≤ CP:  dW′bal/dt = (W′ − W′bal) · (CP − P) / W′

  Erholung nur unter CP, mit leistungsabhängiger Zeitkonstante W′/(CP − P)
  (bei P = 0: W′/CP). Diskretisiert als expliziter Euler-Schritt mit Δt = 1 s,
  wie in den gängigen Implementierungen (z. B. GoldenCheetah). Der relative
  Fehler der Erholung gegenüber der analytischen Exponentialfunktion beträgt
  nach n Sekunden ≈ 1 − exp(−n·k²/2) mit k = (CP − P)/W′.

Konventionen:
- Eingabe ist eine lückenlose 1-Hz-Reihe in Watt; Index i ist der Zustand am
  *Ende* von Sekunde i + 1 (Start mit vollem W′ vor dem ersten Sample).
- W′bal wird nicht bei 0 abgeschnitten. Negative Werte bedeuten, dass mehr Arbeit
  über CP geleistet wurde, als das Modell mit den gegebenen CP/W′ zulässt – ein
  Hinweis auf zu niedrig geschätzte CP bzw. W′, der nicht verdeckt werden soll.
"""

import math
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from powerlab.metrics import PowerSeries, _as_power_array

Method = Literal["differential", "integral"]

_TAU_A, _TAU_B, _TAU_C = 546.0, 0.01, 316.0
"""Konstanten der τ-Regression nach Skiba et al. 2012 (s, 1/W, s)."""


def _check_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} muss positiv und endlich sein, erhalten: {value}")


def _as_nonempty_power(power: PowerSeries) -> NDArray[np.float64]:
    arr = _as_power_array(power)
    if arr.size == 0:
        raise ValueError("Leistungsreihe ist leer")
    return arr


def skiba_tau(power: PowerSeries, cp: float) -> float:
    """Zeitkonstante der W′-Rekonstitution nach Skiba et al. 2012 (s).

    τ = 546 · e^{−0.01 · D_CP} + 316 mit D_CP = CP − mittlere Leistung aller Sekunden
    mit P < CP über die *gesamte* Einheit (wie im Original). Sekunden mit P ≥ CP gehen
    nicht ein. Wertebereich: 316 s (D_CP → ∞) bis 862 s (D_CP → 0).

    Enthält die Reihe keine Sekunde unter CP, ist D_CP undefiniert -> ``ValueError``
    (τ dann explizit an :func:`w_prime_balance` übergeben).
    """
    _check_positive("CP", cp)
    arr = _as_nonempty_power(power)
    below = arr[arr < cp]
    if below.size == 0:
        raise ValueError("Keine Sekunde unter CP: D_CP und damit τ undefiniert")
    d_cp = cp - float(np.mean(below))
    return _TAU_A * math.exp(-_TAU_B * d_cp) + _TAU_C


def w_prime_balance(
    power: PowerSeries,
    cp: float,
    w_prime: float,
    *,
    method: Method = "differential",
    tau: float | None = None,
) -> NDArray[np.float64]:
    """W′bal je Sekunde (J) für eine lückenlose 1-Hz-Leistungsreihe (W).

    Modelle und Quellen siehe Moduldocstring: ``differential`` (Skiba et al. 2015,
    Default) und ``integral`` (Skiba et al. 2012).

    Args:
        power: Leistung in W, 1 Hz, lückenlos, nicht leer.
        cp: Critical Power (W).
        w_prime: W′ (J).
        method: ``"differential"`` oder ``"integral"``.
        tau: Nur ``integral``: Zeitkonstante in s. ``None`` bestimmt τ aus der
            gesamten Einheit via :func:`skiba_tau` (Original); ein expliziter Wert
            erlaubt z. B. ein τ aus einer anderen Einheit oder individuell kalibriert.

    Returns:
        W′bal in J, gleiche Länge wie ``power``; nicht bei 0 abgeschnitten.

    Raises:
        ValueError: ungültige Reihe (leer, NaN/Inf, negativ, nicht 1-D), CP/W′/τ nicht
            positiv-endlich, unbekannte Methode, ``tau`` bei ``differential``, oder
            ``differential`` mit W′ < CP·1 s (Euler-Schritt würde überschießen).
    """
    _check_positive("CP", cp)
    _check_positive("W′", w_prime)
    arr = _as_nonempty_power(power)
    if method == "differential":
        if tau is not None:
            raise ValueError("tau gilt nur für method='integral'")
        return _differential(arr, cp, w_prime)
    if method == "integral":
        if tau is None:
            tau = skiba_tau(arr, cp)
        _check_positive("τ", tau)
        return _integral(arr, cp, w_prime, tau)
    raise ValueError(f"Unbekannte Methode: {method!r} (erlaubt: 'differential', 'integral')")


def _differential(arr: NDArray[np.float64], cp: float, w_prime: float) -> NDArray[np.float64]:
    # Erholungsfaktor (CP − P)/W′ pro Sekunde ist maximal CP/W′ (bei P = 0). Über 1 würde
    # der Euler-Schritt über W′ hinausschießen; physiologisch entspräche das W′/CP < 1 s.
    if cp > w_prime:
        raise ValueError(
            f"W′/CP = {w_prime / cp:.3g} s < 1 s: Diskretisierung mit Δt = 1 s instabil"
        )
    # Lineare Rekursion x_t = a_t·x_{t−1} + b_t mit zeitvariablem a_t. Eine Vektorisierung
    # über kumulierte Produkte Π a_t ist numerisch instabil (Unterlauf/Auslöschung bei
    # langen Erholungsphasen), scipy ist keine Abhängigkeit. Daher bewusst eine Schleife
    # über Python-Floats (O(n), ~10⁴ Samples/h – wie beim PMC vertretbar).
    excess = arr - cp
    bal = w_prime
    out = np.empty_like(arr)
    for i, e in enumerate(excess.tolist()):
        if e > 0:
            bal -= e
        else:
            bal += (w_prime - bal) * (-e) / w_prime
        out[i] = bal
    return out


def _integral(
    arr: NDArray[np.float64], cp: float, w_prime: float, tau: float
) -> NDArray[np.float64]:
    # Da τ konstant ist, gilt rekursiv S_t = d·S_{t−1} + x_t mit d = e^{−1/τ} und
    # x_t = max(P_t − CP, 0); W′bal = W′ − S. Blockweise geschlossen gelöst:
    # S_{s+k} = d^k · (d·S_{s−1} + Σ_{j≤k} x_{s+j}·d^{−j}). Die Blocklänge ≤ τ begrenzt
    # d^{−j} auf ≤ e, damit bleibt die kumulierte Summe numerisch unkritisch.
    x = np.maximum(arr - cp, 0.0)
    block = int(min(max(tau, 1.0), x.size))
    j = np.arange(block, dtype=np.float64)
    grow = np.exp(j / tau)  # d^{−j}
    decay = np.exp(-j / tau)  # d^{j}
    d = math.exp(-1.0 / tau)
    expended = np.empty_like(x)
    carry = 0.0
    for start in range(0, x.size, block):
        chunk = x[start : start + block]
        m = chunk.size
        seg = decay[:m] * (d * carry + np.cumsum(chunk * grow[:m]))
        expended[start : start + m] = seg
        carry = float(seg[-1])
    return w_prime - expended
