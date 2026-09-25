# powerlab – Hinweise für Claude

Analyse-Toolkit für Rad-Leistungsdaten. Nutzer ist mit Trainingswissenschaft vertraut:
keine vereinfachenden Erklärungen, Modellannahmen und Quellen explizit benennen.

## Befehle (aus `apps/powerlab/`)
- Setup: in Web-Sessions automatisch via `.claude/hooks/session-start.sh` (Repo-Root);
  lokal `pip install -e ".[dev]"`
- Tests: `python3 -m pytest -q`
- Lint: `python3 -m ruff check .` · Format: `python3 -m ruff format .`
  (immer `python3 -m ruff`: im Container liegt ein älteres globales `ruff` mit anderem Format-Verhalten)
- Vor jedem Commit: Tests + Lint + Format-Check müssen grün sein.

## Struktur
- `src/powerlab/metrics.py` – NP, IF, TSS, VI (Coggan), Mean Maximal Power
- `src/powerlab/cp.py` – CP-Fit: 2P (`inverse-time` Default, `work-time`), 3P Morton; `CpFit.power_at`/`time_to_exhaustion`
- `src/powerlab/pmc.py` – CTL/ATL/TSB/Ramp (`method="coggan"|"exponential"`, TSB = Vortagswerte)
- `src/powerlab/intervals.py` – Parser für Intervals-Wellness-JSON, `compare_pmc`
- `src/powerlab/report.py` – Wochenreport (HTML, Artifact-Format), Heuristik-Hinweise
- `scripts/weekly_report.py` – Report aus `data/wellness.json` (+ optional `data/activities.json`)
- `scripts/compare_intervals.py` – Abgleich auf lokalen Exporten in `data/`
- `tests/` – pytest; jede Metrik braucht analytische Referenzwerte oder ein unabhängiges Orakel

## Konventionen
- Eingangsdaten: lückenlose 1-Hz-Leistungsreihe in Watt. Resampling/Lücken gehören in die
  Import-Schicht, nicht in die Metrik-Funktionen.
- Ungültige Eingaben (NaN, negative Watt, FTP <= 0, zu kurze Reihen) -> `ValueError`, nie stillschweigend korrigieren.
- numpy vektorisiert, keine Python-Schleifen über Samples im Produktivcode (in Test-Orakeln erlaubt).
  Ausnahme: rekursive Tagesreihen wie der PMC (wenige tausend Werte) dürfen als Schleife laufen.
- TDD: erst Test mit Referenzwert, dann Implementierung.
- Docstrings, Fehlermeldungen und Kommentare auf Deutsch.
- Physiologische Modelle (CP, W'bal, PMC) mit Quelle im Docstring (Autor, Jahr).

## Fachliche Stolpersteine
- MMP ist nicht monoton in der Dauer; garantiert nur MMP(n·d) <= MMP(d).

- Intervals.icu rechnet den PMC exponentiell (k = 1 − e^(−1/τ)), Ramp = CTL_t − CTL_{t−7};
  mit `method="exponential"` exakt reproduziert (Abgleich 07–09/2026). Default bleibt `coggan` (TrainingPeaks).
- Intervals-Training-Load basiert auf Bewegungszeit; Streams haben Lücken (Auto-Pause).
- Das Intervals-MCP liefert Streams nur als Zusammenfassung (erste/letzte 5 Werte) – kein NP-Abgleich auf Sample-Ebene möglich.

## Datenschutz
- Echte Trainings-/Gesundheitsdaten nur in `data/` (gitignored), nie committen. Tests nur mit synthetischen Daten.

## Roadmap
(Phase 4 des Lernplans – SessionStart-Hook – ist erledigt, liegt außerhalb dieser Liste.)
1. ✅ Grundgerüst, NP/IF/TSS/VI
2. ✅ PMC (CTL/ATL/TSB, EWMA 42/7 d)
3. ✅ CP-Fit (Monod-Scherrer 2P, optional Morton 3P)
4. W'bal (Skiba 2012 / 2015)
5. ✅ Intervals.icu-Import via MCP, Abgleich mit Intervals-Werten
6. ✅ Wochenreport (HTML); läuft montags als Routine und aktualisiert das private Artifact
   https://claude.ai/artifact/Hp7Jw9fwLh9YqGRf487khJ
