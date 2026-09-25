"""Abgleich powerlab ↔ Intervals.icu auf lokalen Exporten in data/ (nicht versioniert).

data/wellness.json          – Intervals-Wellness-Records (id, ctl, atl, rampRate, ctlLoad)
data/power_curve_ride.json  – {"Dauer_s": Watt} aus der Intervals-Leistungskurve
"""

import json
from pathlib import Path

from powerlab import fit_cp_2p, fit_cp_3p
from powerlab.intervals import compare_pmc, parse_wellness

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    wellness = parse_wellness(json.loads((DATA / "wellness.json").read_text()))
    print(f"PMC-Abgleich {wellness[0].day} – {wellness[-1].day}")
    header = ("Methode", "ΔCTL max", "ΔCTL Ø", "ΔATL max", "ΔATL Ø", "ΔRamp max")
    print(f"{header[0]:12}" + "".join(f"{h:>10}" for h in header[1:]))
    for method in ("exponential", "coggan"):
        c = compare_pmc(wellness, method=method)
        ramp = "–" if c.max_abs_ramp is None else f"{c.max_abs_ramp:.4f}"
        print(
            f"{method:12}{c.max_abs_ctl:10.4f}{c.mean_abs_ctl:10.4f}"
            f"{c.max_abs_atl:10.4f}{c.mean_abs_atl:10.4f}{ramp:>10}"
        )

    raw = json.loads((DATA / "power_curve_ride.json").read_text())
    curve = {int(k): float(v) for k, v in raw.items()}
    mid = [d for d in sorted(curve) if 180 <= d <= 1200]
    full = [d for d in sorted(curve) if 5 <= d <= 1200]
    fits = [
        ("2P inverse-time, 3–20 min", lambda: fit_cp_2p(mid, [curve[d] for d in mid])),
        (
            "2P work-time, 3–20 min",
            lambda: fit_cp_2p(mid, [curve[d] for d in mid], method="work-time"),
        ),
        ("3P Morton, 5 s – 20 min", lambda: fit_cp_3p(full, [curve[d] for d in full])),
    ]
    print("\nCP-Fit auf Intervals-Leistungskurve (Saisonbestwerte)")
    for name, fit_fn in fits:
        try:
            fit = fit_fn()
        except ValueError as e:
            print(f"  {name:27} nicht bestimmbar: {e}")
            continue
        se = f" ± {fit.cp_se:.1f}" if fit.cp_se else ""
        pmax = f", Pmax {fit.pmax:.0f} W" if fit.pmax else ""
        print(
            f"  {name:27} CP {fit.cp:5.1f} W{se}, W′ {fit.w_prime / 1000:4.1f} kJ{pmax}, "
            f"RMSE {fit.rmse:4.1f} W"
        )
        if 3600 in curve:
            print(
                f"  {'':27} Vorhersage 60 min: {fit.power_at(3600):.0f} W "
                f"(MMP: {curve[3600]:.0f} W)"
            )


if __name__ == "__main__":
    main()
