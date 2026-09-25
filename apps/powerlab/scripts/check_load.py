"""Plausibilitätscheck einer HR-basierten Aktivitäts-Load plus What-if für die Berichtswoche.

    python3 scripts/check_load.py --date 2026-03-19 --load 310 --avg-hr 112 --lthr 165 \
        --moving-time 12600 --week-end 2026-03-22 [--data-dir data]

Vergleicht die Load mit einer groben hrTSS-Schätzung und rechnet, falls auffällig
(Faktor > 1,5), CTL/Ramp/Form zum Wochenende mit der Schätzung statt der Intervals-Load.
Der Tages-Load wird dabei um die Differenz verringert (andere Aktivitäten des Tages bleiben).
"""

import argparse
import json
from datetime import date
from pathlib import Path

from powerlab.intervals import parse_wellness
from powerlab.plausibility import SUSPICIOUS_FACTOR, hr_load_estimate, what_if_load

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--load", type=float, required=True)
    parser.add_argument("--avg-hr", type=float, required=True)
    parser.add_argument("--lthr", type=float, required=True)
    parser.add_argument("--moving-time", type=float, required=True, help="Sekunden")
    parser.add_argument("--week-end", type=date.fromisoformat, required=True)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()

    estimate = hr_load_estimate(args.avg_hr, args.lthr, args.moving_time)
    factor = args.load / estimate if estimate else float("inf")
    suspicious = factor > SUSPICIOUS_FACTOR
    print(
        f"Load {args.load:.0f} vs. hrTSS-Schätzung {estimate:.0f} (Faktor {factor:.2f}): "
        f"{'AUFFÄLLIG' if suspicious else 'plausibel'}"
    )
    if not suspicious:
        return

    records = json.loads((args.data_dir / "wellness.json").read_text())
    days = [d for d in parse_wellness(records) if d.day <= args.week_end]
    day_total = next(d.ctl_load for d in days if d.day == args.date)
    new_total = max(day_total - (args.load - estimate), 0.0)
    r = what_if_load(days, args.date, new_total)
    last = days[-1]
    print(f"Tages-Load {args.date}: {day_total:.0f} -> {new_total:.0f}")
    print(
        f"Intervals: CTL {last.ctl:.1f}, Ramp {last.ramp:+.1f}, Form Mo {last.ctl - last.atl:+.0f}"
    )
    print(f"What-if:   CTL {r.ctl:.1f}, Ramp {r.ramp:+.1f}, Form Mo {r.form_next_morning:+.0f}")


if __name__ == "__main__":
    main()
