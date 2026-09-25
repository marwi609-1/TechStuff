# powerlab – Hinweise für Claude

Analyse-Toolkit für Rad-Leistungsdaten. Nutzer ist mit Trainingswissenschaft vertraut:
keine vereinfachenden Erklärungen, Modellannahmen und Quellen explizit benennen.

## Befehle (aus `apps/powerlab/`)
- Tests: `python3 -m pytest -q`
- Lint: `ruff check .` · Format: `ruff format .`
- Vor jedem Commit: Tests + Lint + Format-Check müssen grün sein.

## Struktur
- `src/powerlab/metrics.py` – NP, IF, TSS, VI (Coggan)
- `tests/` – pytest; jede Metrik braucht analytische Referenzwerte oder ein unabhängiges Orakel

## Konventionen
- Eingangsdaten: lückenlose 1-Hz-Leistungsreihe in Watt. Resampling/Lücken gehören in die
  Import-Schicht, nicht in die Metrik-Funktionen.
- Ungültige Eingaben (NaN, negative Watt, FTP <= 0, zu kurze Reihen) -> `ValueError`, nie stillschweigend korrigieren.
- numpy vektorisiert, keine Python-Schleifen über Samples im Produktivcode (in Test-Orakeln erlaubt).
- TDD: erst Test mit Referenzwert, dann Implementierung.
- Docstrings, Fehlermeldungen und Kommentare auf Deutsch.
- Physiologische Modelle (CP, W'bal, PMC) mit Quelle im Docstring (Autor, Jahr).

## Roadmap
1. ✅ Grundgerüst, NP/IF/TSS/VI
2. PMC (CTL/ATL/TSB, EWMA 42/7 d)
3. CP-Fit (Monod-Scherrer 2P, optional Morton 3P)
4. W'bal (Skiba 2012 / 2015)
5. Intervals.icu-Import via MCP, Abgleich mit Intervals-Werten
6. Wochenreport (HTML)
