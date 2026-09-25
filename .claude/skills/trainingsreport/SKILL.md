---
name: trainingsreport
description: Erzeugt den wöchentlichen Radsport-Trainingsreport (Load vs. Vorwoche, CTL/ATL, Form am Montagmorgen, Ramp-Rate, Hinweise) aus Intervals.icu-Daten mit apps/powerlab und aktualisiert das private Report-Artifact. Verwende diesen Skill immer, wenn der Nutzer nach dem Wochenreport, der letzten Trainingswoche, seiner Form/Fitness/Ermüdung der Woche, „wie war meine Woche“ oder der Trainingsbelastung einer bestimmten KW fragt, wenn die Montags-Routine „Powerlab Wochenreport“ feuert, oder wenn /trainingsreport aufgerufen wird – auch wenn das Wort „Report“ nicht fällt.
---

# Trainingsreport

Baut den Wochenreport (Mo–So) aus Intervals.icu-Daten und veröffentlicht ihn als privates
Artifact. Der Nutzer ist sportwissenschaftlich versiert: fachlich präzise antworten, auf
Deutsch, ohne vereinfachende Erklärungen.

## Argumente

`$ARGUMENTS` ist optional und kann enthalten:
- ein Datum `YYYY-MM-DD` → Sonntag der Berichtswoche (muss ein Sonntag sein)
- `nicht veröffentlichen` / `--no-publish` → nur Report erzeugen, Artifact nicht anfassen
- `--data-dir <pfad>` → Arbeitsverzeichnis statt `apps/powerlab/data/`

Ohne Datum: der zuletzt abgeschlossene Sonntag (Europe/Berlin). Heute Sonntag → Vorwoche,
weil die laufende Woche noch nicht fertig ist.

## Ablauf

Arbeite in `apps/powerlab/`. Falls `import powerlab` fehlschlägt: `pip install -e ".[dev]"`.

1. **Wellness laden.** Intervals-MCP `get_wellness_data` mit `start_date = week_end − 55 Tage`,
   `end_date = week_end`, `fields = ["training"]`. 56 Tage decken die 42-Tage-Trendgrafik plus
   Vor- und Berichtswoche ab.
2. **Aktivitäten laden.** `get_activities` mit `start_date` = Montag, `end_date = week_end`,
   `limit = 50`, `compact = true`, `include_unnamed = false`.
3. **Rohtext speichern, nicht abtippen.** Schreibe den Text aus dem `result`-Feld jeder
   MCP-Antwort unverändert (mit echten Zeilenumbrüchen) nach `<data-dir>/raw_wellness.txt`
   bzw. `<data-dir>/raw_activities.txt`. Die Umwandlung in JSON erledigt der Parser;
   Werte von Hand in JSON zu übertragen war in der Praxis die häufigste Fehlerquelle.
4. **In JSON umwandeln:**
   ```bash
   python3 scripts/intervals_text_to_json.py --wellness <data-dir>/raw_wellness.txt \
       --activities <data-dir>/raw_activities.txt --data-dir <data-dir>
   ```
   Prüfe die Ausgabe: 56 Tage, letzter Tag = `week_end`. Fehlen Tage, lade sie erneut vom
   MCP, statt Werte zu ergänzen.
5. **Report bauen:**
   ```bash
   python3 scripts/weekly_report.py --week-end <week_end> --data-dir <data-dir>
   ```
   Ein `ValueError` (Lücke, kein Sonntag, < 14 Tage) weist auf ein Datenproblem hin: Ursache in
   den Daten beheben, nicht im Code.
6. **Veröffentlichen** (außer bei `--no-publish`): `<data-dir>/report.html` ins Scratchpad als
   `powerlab-wochenreport.html` kopieren, das Artifact
   `https://claude.ai/artifact/Hp7Jw9fwLh9YqGRf487khJ` mit `action: "read"` lesen und dann mit
   `url` = dieser URL und `file_path` = der Kopie publishen. So bleibt der Link stabil; ohne
   `url` entstünde ein neues Artifact. Kein `icon` mitgeben.

## Ergebnis melden

3–5 Zeilen, z. B.:

> **KW 38** (14.–20.09.): Load 695 (Vorwoche 127), CTL 43,4 (+10,0), Form Montagmorgen −22.
> Hinweis: Ramp-Rate +10,0 über der Faustregel von 8.
> Report: https://claude.ai/artifact/Hp7Jw9fwLh9YqGRf487khJ

Die Hinweise sind Praxis-Faustregeln ohne belastbare Evidenz (steht so auch im Report).
Formuliere sie als Beobachtung, nicht als Trainingsempfehlung oder Warnung vor Verletzung.

## Grenzen und Regeln

- **Datenschutz:** `data/` und alle Rohtexte enthalten Gesundheitsdaten. Nie committen, nie in
  Tests oder Doku übernehmen.
- **Werte aus Intervals übernehmen:** CTL/ATL/Ramp kommen aus Intervals (exponentielle
  Glättung). Nicht mit `performance_management_chart` neu rechnen; das weicht mit dem
  Default `method="coggan"` ab.
- **Intervals-MCP nicht verfügbar:** genau das melden und abbrechen. Keine Werte schätzen.
- Keine Code-Änderungen im Rahmen dieses Skills. Fällt ein Bug auf, benennen und separat lösen.
