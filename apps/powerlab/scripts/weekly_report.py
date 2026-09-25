"""Erzeugt den Wochenreport als HTML aus lokalen Intervals-Exporten.

    python3 scripts/weekly_report.py [--week-end YYYY-MM-DD] [--data-dir data] [--out …]

Eingaben (in --data-dir, Standard data/, nicht versioniert):
    wellness.json    Intervals-Wellness-Records (id, ctl, atl, rampRate, ctlLoad, atlLoad),
                     mindestens 14 Tage bis zum Sonntag der Berichtswoche, besser 42+
    activities.json  optional: [{date, name, duration_min, load?, avg_watts?}]
Standard für --week-end: der letzte abgeschlossene Sonntag.
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from powerlab.intervals import parse_wellness
from powerlab.report import parse_activities, render_html, summarize_week

DATA = Path(__file__).resolve().parents[1] / "data"


def last_sunday(today: date) -> date:
    return today - timedelta(days=today.weekday() + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--week-end", type=date.fromisoformat, default=last_sunday(date.today()))
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--out", type=Path, help="Standard: <data-dir>/report.html")
    args = parser.parse_args()
    out = args.out or args.data_dir / "report.html"

    wellness = parse_wellness(json.loads((args.data_dir / "wellness.json").read_text()))
    activities_file = args.data_dir / "activities.json"
    activities = (
        parse_activities(json.loads(activities_file.read_text()))
        if activities_file.exists()
        else []
    )
    summary = summarize_week(wellness, args.week_end)
    out.write_text(render_html(summary, activities), encoding="utf-8")
    print(f"KW {summary.week_start.isocalendar().week}: {out}")
    print(
        f"  Load {summary.total_load:.0f} (Vorwoche {summary.prev_total_load:.0f}), "
        f"CTL {summary.ctl_end:.1f}, Form Mo {summary.form_next_morning:+.0f}"
    )
    for flag in summary.flags:
        print(f"  [{flag.level}] {flag.title}")


if __name__ == "__main__":
    main()
