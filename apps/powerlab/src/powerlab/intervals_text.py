"""Parser für die Textausgabe des Intervals.icu-MCP.

Das MCP liefert Wellness-Daten und Aktivitätslisten als formatierten Text, nicht als JSON.
Diese Funktionen wandeln den Text verlustfrei in die Formate um, die
:func:`powerlab.intervals.parse_wellness` bzw. :func:`powerlab.report.parse_activities`
erwarten. So muss niemand Zahlen von Hand abschreiben.
"""

import re
from typing import Any

_DATE_LINE = re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
_WELLNESS_FIELDS = {
    "ctl": r"Fitness \(CTL\)",
    "atl": r"Fatigue \(ATL\)",
    "rampRate": r"Ramp Rate",
    "ctlLoad": r"CTL Load",
    "atlLoad": r"ATL Load",
}
_REQUIRED = ("ctl", "atl")
_NUMBER = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"

_ACTIVITY_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2}) \| (.+)$")
_TITLE = re.compile(r"^(?P<type>[^:]+): (?P<name>.*) \(ID:(?P<id>[^)]+)\)$")
_DURATION = re.compile(r"^(\d+(?:\.\d+)?)min$")
_LOAD = re.compile(r"^TL:(\d+(?:\.\d+)?)$")
_POWER = re.compile(r"^Pwr:(\d+(?:\.\d+)?)W$")


def parse_wellness_text(text: str) -> list[dict[str, Any]]:
    """Wellness-Text (``get_wellness_data``) → Records im Intervals-API-Format.

    Ein Block beginnt mit ``Date: YYYY-MM-DD``. Fehlende optionale Felder werden ``None``;
    fehlt CTL oder ATL oder kommt ein Datum doppelt vor → ``ValueError``.
    """
    starts = list(_DATE_LINE.finditer(text))
    if not starts:
        raise ValueError("Keine Wellness-Tage ('Date: …') im Text gefunden")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, match in enumerate(starts):
        day = match.group(1)
        if day in seen:
            raise ValueError(f"Datum {day} kommt doppelt vor")
        seen.add(day)
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[match.end() : end]
        record: dict[str, Any] = {"id": day}
        for key, label in _WELLNESS_FIELDS.items():
            found = re.search(rf"^-\s*{label}:\s*{_NUMBER}\s*$", block, re.MULTILINE)
            record[key] = float(found.group(1)) if found else None
        missing = [k for k in _REQUIRED if record[k] is None]
        if missing:
            raise ValueError(f"{day}: Pflichtfeld(er) fehlen: {', '.join(missing)}")
        records.append(record)
    return records


def parse_activities_text(text: str) -> list[dict[str, Any]]:
    """Aktivitätsliste (``get_activities``, ``compact=True``) → Records für den Report.

    Zeilen ohne Datum (unbenannte Einträge) werden übersprungen. Jede Aktivität braucht
    eine Dauer (``…min``); Load (``TL:``) und Leistung (``Pwr:…W``) sind optional.
    """
    activities = []
    for line in text.splitlines():
        match = _ACTIVITY_LINE.match(line.strip())
        if not match:
            continue
        day, rest = match.groups()
        parts = [p.strip() for p in rest.split(" | ")]
        title = _TITLE.match(parts[0])
        if not title:
            raise ValueError(f"Aktivitätszeile nicht lesbar: {line!r}")
        record: dict[str, Any] = {
            "date": day,
            "type": title["type"],
            "name": title["name"],
            "id": title["id"],
            "duration_min": None,
            "load": None,
            "avg_watts": None,
        }
        for part in parts[1:]:
            for key, pattern in (
                ("duration_min", _DURATION),
                ("load", _LOAD),
                ("avg_watts", _POWER),
            ):
                found = pattern.match(part)
                if found:
                    record[key] = float(found.group(1))
        if record["duration_min"] is None:
            raise ValueError(f"Aktivität ohne Dauer: {line!r}")
        activities.append(record)
    return activities
