"""Wandelt rohe Intervals-MCP-Textausgaben in die JSON-Eingaben des Wochenreports um.

    python3 scripts/intervals_text_to_json.py --wellness raw_wellness.txt \
        [--activities raw_activities.txt] [--data-dir data]

Schreibt <data-dir>/wellness.json und (falls angegeben) <data-dir>/activities.json.
"""

import argparse
import json
from pathlib import Path

from powerlab.intervals_text import parse_activities_text, parse_wellness_text

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wellness", type=Path, required=True)
    parser.add_argument("--activities", type=Path)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)

    wellness = parse_wellness_text(args.wellness.read_text(encoding="utf-8"))
    (args.data_dir / "wellness.json").write_text(json.dumps(wellness, indent=1))
    print(f"wellness.json: {len(wellness)} Tage ({wellness[0]['id']} – {wellness[-1]['id']})")

    if args.activities:
        acts = parse_activities_text(args.activities.read_text(encoding="utf-8"))
        (args.data_dir / "activities.json").write_text(
            json.dumps(acts, indent=1, ensure_ascii=False)
        )
        print(f"activities.json: {len(acts)} Aktivitäten")


if __name__ == "__main__":
    main()
