"""Wochenreport (HTML) aus Intervals.icu-Wellness-Daten.

CTL/ATL/Ramp werden direkt aus Intervals übernommen (siehe :mod:`powerlab.intervals`:
exakt reproduzierbar mit ``method="exponential"``). Die Form für den Montagmorgen folgt
der Vortagskonvention aus :mod:`powerlab.pmc`: TSB = CTL_So − ATL_So.

Hinweise sind Heuristiken aus der Trainingspraxis (TrainingPeaks/Coggan), keine
validierten Grenzwerte: Für Ramp-Rate- oder TSB-Schwellen gibt es keine belastbare
Evidenz zu Verletzungs- oder Übertrainingsrisiko (vgl. Kritik an ACWR-Modellen,
Impellizzeri et al. 2020, Int J Sports Physiol Perform).
"""

import html
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from powerlab.intervals import WellnessDay

TREND_DAYS = 42
RAMP_HIGH = 8.0  # CTL-Punkte pro Woche
RAMP_DETRAINING = -5.0
TSB_LOW = -30.0
TSB_FRESH = (5.0, 25.0)

WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")
MONTHS = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)  # fmt: skip

Level = Literal["good", "info", "warning", "serious"]


@dataclass(frozen=True, slots=True)
class Flag:
    key: str
    level: Level
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class Activity:
    day: date
    name: str
    duration_min: float
    load: float | None
    avg_watts: float | None


@dataclass(frozen=True, slots=True)
class WeekSummary:
    week_start: date
    week_end: date
    daily_load: list[tuple[date, float]]
    total_load: float
    prev_total_load: float
    active_days: int
    ctl_end: float
    atl_end: float
    ramp_end: float | None
    ctl_change: float
    form_next_morning: float
    trend: list[WellnessDay]
    flags: list[Flag]


# --- Aufbereitung -------------------------------------------------------------


def summarize_week(wellness: Sequence[WellnessDay], week_end: date) -> WeekSummary:
    """Fasst die Woche Mo–So bis ``week_end`` (Sonntag) zusammen."""
    if week_end.weekday() != 6:
        raise ValueError(
            f"week_end muss ein Sonntag sein, erhalten: {WEEKDAYS[week_end.weekday()]} {week_end:%d.%m.%Y}"
        )
    days = sorted((d for d in wellness if d.day <= week_end), key=lambda d: d.day)
    if len(days) < 14 or days[-1].day != week_end:
        raise ValueError(f"Mindestens 14 Tage Wellness-Daten bis {week_end} nötig")
    for prev, cur in zip(days, days[1:], strict=False):
        if cur.day - prev.day != timedelta(days=1):
            raise ValueError(f"Lücke in den Wellness-Daten zwischen {prev.day} und {cur.day}")

    week, prev_week = days[-7:], days[-14:-7]
    last = days[-1]
    form = last.ctl - last.atl
    return WeekSummary(
        week_start=week[0].day,
        week_end=week_end,
        daily_load=[(d.day, d.ctl_load) for d in week],
        total_load=sum(d.ctl_load for d in week),
        prev_total_load=sum(d.ctl_load for d in prev_week),
        active_days=sum(1 for d in week if d.ctl_load > 0),
        ctl_end=last.ctl,
        atl_end=last.atl,
        ramp_end=last.ramp,
        ctl_change=last.ctl - prev_week[-1].ctl,
        form_next_morning=form,
        trend=days[-TREND_DAYS:],
        flags=_flags(last.ramp, form),
    )


def _flags(ramp: float | None, form: float) -> list[Flag]:
    flags = []
    if ramp is not None and ramp > RAMP_HIGH:
        flags.append(
            Flag(
                "ramp",
                "warning",
                f"Ramp-Rate {_num(ramp, 1, sign=True)} CTL/Woche",
                f"Über der Praxis-Faustregel von {RAMP_HIGH:.0f}. Belastungsspitzen dieser "
                "Größe lassen sich meist nicht über mehrere Wochen halten.",
            )
        )
    if ramp is not None and ramp < RAMP_DETRAINING:
        flags.append(
            Flag(
                "detraining",
                "info",
                f"CTL sinkt ({_num(ramp, 1, sign=True)}/Woche)",
                "Deutlicher Rückgang der chronischen Belastung. In Regenerations- oder "
                "Übergangsphasen erwartbar, sonst ein Zeichen für zu wenig Umfang.",
            )
        )
    if form < TSB_LOW:
        flags.append(
            Flag(
                "tsb-low",
                "serious",
                f"Form {_num(form, sign=True)} am Montagmorgen",
                f"Unter {TSB_LOW:.0f}: hohe akute Ermüdung. Intensive Einheiten erst nach "
                "Erholung einplanen.",
            )
        )
    elif TSB_FRESH[0] <= form <= TSB_FRESH[1]:
        flags.append(
            Flag(
                "tsb-fresh",
                "good",
                f"Form {_num(form, sign=True)} am Montagmorgen",
                "Erholt. Gute Ausgangslage für Schlüsseleinheiten oder Wettkampf.",
            )
        )
    return flags


def _optional_number(record: Mapping[str, Any], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Feld {key!r} ungültig: {value!r}")
    return number


def parse_activities(records: Iterable[Mapping[str, Any]]) -> list[Activity]:
    """Liest Aktivitäten im Format ``{date, name, duration_min, load?, avg_watts?}``."""
    activities = []
    for record in records:
        if "date" not in record:
            raise ValueError(f"Aktivität ohne Datum: {record}")
        duration = _optional_number(record, "duration_min")
        if duration is None:
            raise ValueError(f"Aktivität ohne Dauer: {record}")
        activities.append(
            Activity(
                day=date.fromisoformat(str(record["date"])),
                name=str(record.get("name") or "Ohne Namen"),
                duration_min=duration,
                load=_optional_number(record, "load"),
                avg_watts=_optional_number(record, "avg_watts"),
            )
        )
    return sorted(activities, key=lambda a: a.day)


# --- Formatierung -------------------------------------------------------------


def _num(value: float, digits: int = 0, sign: bool = False) -> str:
    text = f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"
    return text.replace("-", "−").replace(".", ",")


def _week_label(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{start.day}.–{end.day}. {MONTHS[end.month - 1]} {end.year}"
    return f"{start.day}. {MONTHS[start.month - 1]} – {end.day}. {MONTHS[end.month - 1]} {end.year}"


def _duration(minutes: float) -> str:
    h, m = divmod(round(minutes), 60)
    return f"{h}:{m:02d} h"


def _nice_step(span: float, target_ticks: int = 4) -> float:
    raw = max(span, 1e-9) / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 2.5, 5, 10):
        if factor * magnitude >= raw:
            return factor * magnitude
    return 10 * magnitude


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


# --- Diagramme (SVG) ----------------------------------------------------------

W = 720
PAD_L, PAD_R, PAD_T, PAD_B = 40, 72, 14, 26


def _pmc_chart(s: WeekSummary) -> str:
    days = s.trend
    h = 250
    top = max(max(d.ctl, d.atl) for d in days)
    step = _nice_step(top)
    y_max = math.ceil(top / step) * step
    n = len(days)
    plot_w, plot_h = W - PAD_L - PAD_R, h - PAD_T - PAD_B

    def x(i: float) -> float:
        return PAD_L + (i / max(n - 1, 1)) * plot_w

    def y(v: float) -> float:
        return PAD_T + plot_h * (1 - v / y_max)

    parts = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-labelledby="pmc-title">']
    # Berichtswoche hinterlegen
    i0 = next(i for i, d in enumerate(days) if d.day == s.week_start)
    parts.append(
        f'<rect class="band" x="{x(i0 - 0.5):.1f}" y="{PAD_T}" '
        f'width="{x(n - 1) - x(i0 - 0.5):.1f}" height="{plot_h}"/>'
    )
    v = 0.0
    while v <= y_max + 1e-9:
        parts.append(
            f'<line class="grid" x1="{PAD_L}" x2="{PAD_L + plot_w}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        )
        parts.append(
            f'<text class="tick" x="{PAD_L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{_num(v)}</text>'
        )
        v += step
    for i, d in enumerate(days):
        if d.day.weekday() == 0:
            parts.append(
                f'<text class="tick" x="{x(i):.1f}" y="{h - 6}" text-anchor="middle">{d.day:%d.%m.}</text>'
            )
    for key, cls in (("ctl", "ctl"), ("atl", "atl")):
        pts = " ".join(f"{x(i):.1f},{y(getattr(d, key)):.1f}" for i, d in enumerate(days))
        parts.append(f'<polyline class="line {cls}" points="{pts}"/>')
    # Endpunkte mit Direktlabels, Abstand gegen Überlappung
    ly = {"ctl": y(s.ctl_end), "atl": y(s.atl_end)}
    if abs(ly["ctl"] - ly["atl"]) < 16:
        mid = (ly["ctl"] + ly["atl"]) / 2
        upper, lower = ("ctl", "atl") if s.ctl_end >= s.atl_end else ("atl", "ctl")
        ly[upper], ly[lower] = mid - 8, mid + 8
    for key, value in (("ctl", s.ctl_end), ("atl", s.atl_end)):
        parts.append(f'<circle class="dot {key}" cx="{x(n - 1):.1f}" cy="{y(value):.1f}" r="4"/>')
        parts.append(
            f'<text class="end-label" x="{x(n - 1) + 10:.1f}" y="{ly[key] + 4:.1f}">'
            f"{key.upper()} {_num(value)}</text>"
        )
    parts.append(_hover_columns(
        [(x(i), f"{WEEKDAYS[d.day.weekday()]} {d.day:%d.%m.}|CTL {_num(d.ctl, 1)}|ATL {_num(d.atl, 1)}|Load {_num(d.ctl_load)}")
         for i, d in enumerate(days)],
        plot_w / max(n - 1, 1), PAD_T, plot_h,
    ))  # fmt: skip
    parts.append("</svg>")
    return "".join(parts)


def _tsb_chart(s: WeekSummary) -> str:
    days = s.trend
    h = 150
    # Form am Morgen von Tag i = CTL − ATL von Tag i−1
    forms = [(days[i].day, days[i - 1].ctl - days[i - 1].atl) for i in range(1, len(days))]
    forms.append((s.week_end + timedelta(days=1), s.form_next_morning))
    extent = max(abs(f) for _, f in forms)
    step = _nice_step(extent, target_ticks=2)
    lim = math.ceil(extent / step) * step
    n = len(forms)
    plot_w, plot_h = W - PAD_L - PAD_R, h - PAD_T - PAD_B
    slot = plot_w / n
    bar_w = max(slot - 2, 1)

    def y(v: float) -> float:
        return PAD_T + plot_h * (1 - (v + lim) / (2 * lim))

    parts = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-labelledby="tsb-title">']
    for v in (-lim, 0.0, lim):
        cls = "zero" if v == 0 else "grid"
        parts.append(
            f'<line class="{cls}" x1="{PAD_L}" x2="{PAD_L + plot_w}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        )
        parts.append(
            f'<text class="tick" x="{PAD_L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{_num(v, sign=v != 0)}</text>'
        )
    for i, (d, f) in enumerate(forms):
        x0 = PAD_L + i * slot + 1
        y0, y1 = sorted((y(0), y(f)))
        cls = "pos" if f >= 0 else "neg"
        parts.append(
            f'<rect class="bar {cls}" x="{x0:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{max(y1 - y0, 0.5):.1f}" rx="1.5"/>'
        )
        if d.weekday() == 0:
            parts.append(
                f'<text class="tick" x="{x0 + bar_w / 2:.1f}" y="{h - 6}" text-anchor="middle">{d:%d.%m.}</text>'
            )
    last_x = PAD_L + (n - 1) * slot + 1 + bar_w / 2
    parts.append(
        f'<text class="end-label" x="{last_x + 10:.1f}" y="{y(s.form_next_morning) + 4:.1f}">'
        f"{_num(s.form_next_morning, sign=True)}</text>"
    )
    parts.append(_hover_columns(
        [(PAD_L + i * slot + slot / 2, f"{WEEKDAYS[d.weekday()]} {d:%d.%m.} morgens|Form {_num(f, 1, sign=True)}")
         for i, (d, f) in enumerate(forms)],
        slot, PAD_T, plot_h,
    ))  # fmt: skip
    parts.append("</svg>")
    return "".join(parts)


def _load_chart(s: WeekSummary) -> str:
    h = 190
    loads = [v for _, v in s.daily_load]
    top = max(max(loads), 1.0)
    step = _nice_step(top)
    y_max = math.ceil(top / step) * step
    right = 16
    plot_w, plot_h = W - PAD_L - right, h - PAD_T - PAD_B - 8
    slot = plot_w / 7
    bar_w = slot * 0.56

    def y(v: float) -> float:
        return PAD_T + 8 + plot_h * (1 - v / y_max)

    parts = [f'<svg viewBox="0 0 {W} {h}" role="img" aria-labelledby="load-title">']
    v = 0.0
    while v <= y_max + 1e-9:
        parts.append(
            f'<line class="grid" x1="{PAD_L}" x2="{PAD_L + plot_w}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        )
        parts.append(
            f'<text class="tick" x="{PAD_L - 8}" y="{y(v) + 4:.1f}" text-anchor="end">{_num(v)}</text>'
        )
        v += step
    i_max = loads.index(max(loads))
    tips = []
    for i, (d, load) in enumerate(s.daily_load):
        cx = PAD_L + i * slot + slot / 2
        if load > 0:
            # oben 4px gerundet, unten an der Basislinie eckig
            x0, yt, yb = cx - bar_w / 2, y(load), y(0)
            r = min(4.0, (yb - yt) / 2)
            parts.append(
                f'<path class="bar load" d="M{x0:.1f},{yb:.1f} V{yt + r:.1f} '
                f"Q{x0:.1f},{yt:.1f} {x0 + r:.1f},{yt:.1f} H{x0 + bar_w - r:.1f} "
                f'Q{x0 + bar_w:.1f},{yt:.1f} {x0 + bar_w:.1f},{yt + r:.1f} V{yb:.1f} Z"/>'
            )
        if i == i_max and load > 0:
            parts.append(
                f'<text class="value-label" x="{cx:.1f}" y="{y(load) - 7:.1f}" text-anchor="middle">{_num(load)}</text>'
            )
        parts.append(
            f'<text class="tick" x="{cx:.1f}" y="{h - 6}" text-anchor="middle">{WEEKDAYS[i]} {d:%d.}</text>'
        )
        tips.append((cx, f"{WEEKDAYS[i]} {d:%d.%m.}|Load {_num(load)}"))
    parts.append(_hover_columns(tips, slot, PAD_T, plot_h + 8))
    parts.append("</svg>")
    return "".join(parts)


def _hover_columns(points: list[tuple[float, str]], width: float, top: float, height: float) -> str:
    return "".join(
        f'<rect class="hit" x="{cx - width / 2:.1f}" y="{top}" width="{width:.1f}" '
        f'height="{height}" data-tip="{_esc(tip)}" data-x="{cx:.1f}"/>'
        for cx, tip in points
    )


# --- Seite --------------------------------------------------------------------

CSS = """
:root {
  --bg: #f4f6f7; --surface: #ffffff; --ink: #15191d; --muted: #58606a; --faint: #8b929b;
  --grid: #e1e5e9; --band: #eef2f6; --line: #d5dbe1;
  --ctl: #2a78d6; --atl: #eb6834; --pos: #2a78d6; --neg: #e34948; --load: #4d5b6b;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --info: #58606a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #111416; --surface: #1a1e21; --ink: #eef1f3; --muted: #a5acb4; --faint: #7a828b;
    --grid: #2a3035; --band: #20262b; --line: #313840;
    --ctl: #3987e5; --atl: #d95926; --pos: #3987e5; --neg: #e66767; --load: #9aa7b6;
    --info: #a5acb4;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #111416; --surface: #1a1e21; --ink: #eef1f3; --muted: #a5acb4; --faint: #7a828b;
  --grid: #2a3035; --band: #20262b; --line: #313840;
  --ctl: #3987e5; --atl: #d95926; --pos: #3987e5; --neg: #e66767; --load: #9aa7b6;
  --info: #a5acb4;
}
body { background: var(--bg); color: var(--ink); font: 400 15px/1.55 "Barlow", system-ui, sans-serif; }
.wrap { max-width: 880px; margin: 0 auto; padding: 32px 16px 48px; display: grid; gap: 28px; }
h1, h2, .stat-value, .eyebrow, .end-label, .value-label { font-family: "Barlow Semi Condensed", "Barlow", system-ui, sans-serif; }
h1 { font-size: clamp(26px, 5vw, 36px); line-height: 1.1; font-weight: 600; margin: 4px 0 6px; text-wrap: balance; }
h2 { font-size: 19px; font-weight: 600; margin: 0; }
.eyebrow { text-transform: uppercase; letter-spacing: .08em; font-size: 13px; font-weight: 600; color: var(--muted); }
.sub { color: var(--muted); margin: 0; font-size: 14px; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px; background: var(--line);
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.stat { background: var(--surface); padding: 14px 16px; display: grid; gap: 2px; align-content: start; }
.stat-label { font-size: 13px; color: var(--muted); }
.stat-value { font-size: 30px; font-weight: 600; line-height: 1.15; font-variant-numeric: tabular-nums; }
.stat-note { font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; }
section { display: grid; gap: 10px; }
.section-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; color: var(--muted); }
.key { display: inline-flex; align-items: center; gap: 6px; }
.swatch { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
.swatch.box { height: 10px; width: 10px; }
.chart { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 8px 4px 2px; position: relative; overflow-x: auto; }
.chart svg { display: block; width: 100%; min-width: 600px; height: auto; }
.grid { stroke: var(--grid); stroke-width: 1; }
.zero { stroke: var(--faint); stroke-width: 1; }
.band { fill: var(--band); }
.tick { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.end-label, .value-label { fill: var(--ink); font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }
.line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.line.ctl { stroke: var(--ctl); } .line.atl { stroke: var(--atl); }
.dot { stroke: var(--surface); stroke-width: 2; } .dot.ctl { fill: var(--ctl); } .dot.atl { fill: var(--atl); }
.bar.pos { fill: var(--pos); } .bar.neg { fill: var(--neg); } .bar.load { fill: var(--load); }
.hit { fill: transparent; cursor: crosshair; }
.hit:hover { fill: var(--ink); fill-opacity: .05; }
.tip { position: absolute; pointer-events: none; background: var(--ink); color: var(--bg); font-size: 13px;
  padding: 6px 9px; border-radius: 6px; white-space: nowrap; transform: translate(-50%, 0); z-index: 1;
  font-variant-numeric: tabular-nums; line-height: 1.4; }
.flags { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.flag { display: grid; grid-template-columns: auto 1fr; gap: 2px 12px; background: var(--surface);
  border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; }
.pill { grid-row: span 2; align-self: start; display: inline-flex; align-items: center; gap: 6px; font-size: 12px;
  font-weight: 600; text-transform: uppercase; letter-spacing: .06em; padding: 3px 8px; border-radius: 999px;
  border: 1px solid currentColor; }
.pill::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.pill.good { color: var(--good); } .pill.warning { color: var(--warning); }
.pill.serious { color: var(--serious); } .pill.info { color: var(--info); }
.flag strong { font-weight: 600; }
.flag span { color: var(--muted); font-size: 14px; }
.empty { color: var(--muted); margin: 0; }
.table-wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid var(--grid); white-space: nowrap; }
th { color: var(--muted); font-weight: 500; font-size: 13px; }
td.num, th.num { text-align: right; }
tr:last-child td { border-bottom: none; }
td.name { white-space: normal; min-width: 12ch; }
details summary { cursor: pointer; color: var(--muted); font-size: 14px; }
details summary:focus-visible, .hit:focus-visible { outline: 2px solid var(--ctl); outline-offset: 2px; }
details[open] summary { margin-bottom: 8px; }
@media (max-width: 520px) {
  .stats { grid-template-columns: 1fr 1fr; }
  .stat:last-child:nth-child(odd) { grid-column: 1 / -1; }
}
.method { color: var(--muted); font-size: 13px; max-width: 70ch; display: grid; gap: 6px; }
.method p { margin: 0; }
"""

JS = """
document.querySelectorAll('.chart').forEach(function (chart) {
  var tip = document.createElement('div'); tip.className = 'tip'; tip.hidden = true; chart.appendChild(tip);
  var svg = chart.querySelector('svg');
  function show(el) {
    var box = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal, host = chart.getBoundingClientRect();
    var sx = box.width / vb.width, x = (+el.dataset.x) * sx + box.left - host.left + chart.scrollLeft;
    var yTop = (+el.getAttribute('y')) * (box.height / vb.height) + box.top - host.top;
    tip.innerHTML = el.dataset.tip.split('|').map(function (t, i) {
      var s = document.createElement('span'); s.textContent = t;
      return (i ? '<br>' : '<strong>') + s.innerHTML + (i ? '' : '</strong>');
    }).join('');
    tip.style.left = Math.min(Math.max(x, 70), chart.scrollWidth - 70) + 'px'; tip.style.top = (yTop + 4) + 'px';
    tip.hidden = false;
  }
  chart.querySelectorAll('.hit').forEach(function (el) {
    el.addEventListener('pointerenter', function () { show(el); });
    el.addEventListener('focus', function () { show(el); });
  });
  chart.addEventListener('pointerleave', function () { tip.hidden = true; });
});
"""


def _stat(label: str, value: str, note: str = "") -> str:
    note_html = f'<span class="stat-note">{note}</span>' if note else ""
    return (
        f'<div class="stat"><span class="stat-label">{label}</span>'
        f'<span class="stat-value">{value}</span>{note_html}</div>'
    )


LEVEL_LABEL = {"good": "Gut", "info": "Info", "warning": "Achtung", "serious": "Kritisch"}


def render_html(
    s: WeekSummary, activities: Sequence[Activity] = (), generated: datetime | None = None
) -> str:
    """Rendert den Wochenreport als eigenständiges HTML (Artifact-Seitenformat)."""
    iso_week = s.week_start.isocalendar().week
    delta = s.total_load - s.prev_total_load
    delta_pct = (
        f" ({_num(100 * delta / s.prev_total_load, sign=True)} %)" if s.prev_total_load else ""
    )
    ramp = "–" if s.ramp_end is None else _num(s.ramp_end, 1, sign=True)
    generated = generated or datetime.now()

    flags = (
        '<ul class="flags">'
        + "".join(
            f'<li class="flag"><span class="pill {f.level}">{LEVEL_LABEL[f.level]}</span>'
            f"<strong>{_esc(f.title)}</strong><span>{_esc(f.text)}</span></li>"
            for f in s.flags
        )
        + "</ul>"
        if s.flags
        else '<p class="empty">Keine Auffälligkeiten nach den Faustregeln unten.</p>'
    )

    week_acts = [a for a in activities if s.week_start <= a.day <= s.week_end]
    if week_acts:
        rows = "".join(
            f"<tr><td>{WEEKDAYS[a.day.weekday()]} {a.day:%d.%m.}</td>"
            f'<td class="name">{_esc(a.name)}</td><td class="num">{_duration(a.duration_min)}</td>'
            f'<td class="num">{"–" if a.load is None else _num(a.load)}</td>'
            f'<td class="num">{"–" if a.avg_watts is None else _num(a.avg_watts) + " W"}</td></tr>'
            for a in week_acts
        )
        acts_html = (
            '<div class="table-wrap"><table><thead><tr><th>Tag</th><th>Aktivität</th>'
            '<th class="num">Dauer</th><th class="num">Load</th><th class="num">Ø Leistung</th>'
            f"</tr></thead><tbody>{rows}</tbody></table></div>"
        )
    else:
        acts_html = '<p class="empty">Keine Aktivitätsliste übergeben.</p>'

    trend_rows = "".join(
        f"<tr><td>{d.day:%d.%m.%Y}</td><td class='num'>{_num(d.ctl_load)}</td>"
        f"<td class='num'>{_num(d.ctl, 1)}</td><td class='num'>{_num(d.atl, 1)}</td>"
        f"<td class='num'>{'–' if d.ramp is None else _num(d.ramp, 1, sign=True)}</td></tr>"
        for d in reversed(s.trend)
    )

    return f"""<title>Powerlab Wochenreport</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Semi+Condensed:wght@600&display=swap">
<style>{CSS}</style>
<main class="wrap">
  <header>
    <div class="eyebrow">Wochenreport · KW {iso_week}</div>
    <h1>{_week_label(s.week_start, s.week_end)}</h1>
    <p class="sub">Daten: Intervals.icu · erstellt {generated:%d.%m.%Y, %H:%M} Uhr</p>
  </header>

  <div class="stats">
    {_stat("Wochen-Load", _num(s.total_load), f"Vorwoche {_num(s.prev_total_load)}{delta_pct}")}
    {_stat("Aktive Tage", f"{s.active_days}/7")}
    {_stat("Fitness (CTL)", _num(s.ctl_end, 1), f"{_num(s.ctl_change, 1, sign=True)} zur Vorwoche")}
    {_stat("Form Montagmorgen", _num(s.form_next_morning, sign=True), f"ATL {_num(s.atl_end, 1)}")}
    {_stat("Ramp-Rate", ramp, "CTL-Punkte / 7 Tage")}
  </div>

  <section>
    <h2>Hinweise</h2>
    {flags}
  </section>

  <section>
    <div class="section-head">
      <h2 id="pmc-title">Fitness und Ermüdung, {len(s.trend)} Tage</h2>
      <div class="legend">
        <span class="key"><span class="swatch" style="background:var(--ctl)"></span>CTL (τ 42 d)</span>
        <span class="key"><span class="swatch" style="background:var(--atl)"></span>ATL (τ 7 d)</span>
        <span class="key"><span class="swatch box" style="background:var(--band)"></span>Berichtswoche</span>
      </div>
    </div>
    <div class="chart">{_pmc_chart(s)}</div>
  </section>

  <section>
    <div class="section-head">
      <h2 id="tsb-title">Form am Morgen (TSB)</h2>
      <div class="legend">
        <span class="key"><span class="swatch box" style="background:var(--pos)"></span>erholt (&gt; 0)</span>
        <span class="key"><span class="swatch box" style="background:var(--neg)"></span>ermüdet (&lt; 0)</span>
      </div>
    </div>
    <div class="chart">{_tsb_chart(s)}</div>
  </section>

  <section>
    <h2 id="load-title">Load pro Tag</h2>
    <div class="chart">{_load_chart(s)}</div>
  </section>

  <section>
    <h2>Aktivitäten</h2>
    {acts_html}
  </section>

  <details>
    <summary>Tageswerte als Tabelle</summary>
    <div class="table-wrap"><table>
      <thead><tr><th>Datum</th><th class="num">Load</th><th class="num">CTL</th>
      <th class="num">ATL</th><th class="num">Ramp</th></tr></thead>
      <tbody>{trend_rows}</tbody>
    </table></div>
  </details>

  <footer class="method">
    <p>CTL und ATL stammen aus Intervals.icu (exponentielle Glättung, k = 1 − e<sup>−1/τ</sup>).
    Form am Morgen = CTL − ATL des Vortags. Ramp-Rate = CTL<sub>t</sub> − CTL<sub>t−7</sub>.</p>
    <p>Die Hinweise nutzen Faustregeln aus der Trainingspraxis (Ramp &gt; {_num(RAMP_HIGH)},
    Form &lt; {_num(TSB_LOW)}, frisch bei {_num(TSB_FRESH[0], sign=True)} bis {_num(TSB_FRESH[1], sign=True)}).
    Für diese Schwellen gibt es keine belastbare Evidenz zu Verletzungs- oder Übertrainingsrisiko.
    Das Impulse-Response-Modell beschreibt die Belastungshistorie gut, sagt individuelle Leistung
    aber nur mäßig voraus (Banister et al. 1975; Vermeire et al. 2022; Impellizzeri et al. 2020).</p>
  </footer>
</main>
<script>{JS}</script>
"""
