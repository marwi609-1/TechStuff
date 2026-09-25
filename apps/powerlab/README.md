# powerlab

Leistungsdaten-Analyse für den Radsport. Lernprojekt für Claude Code.

## Setup

```bash
cd apps/powerlab
pip install -e ".[dev]"
python3 -m pytest -q
```

## Beispiel

```python
from powerlab import normalized_power, training_stress_score

power = [250.0] * 3600          # 1 h konstant, 1 Hz
normalized_power(power)          # 250.0
training_stress_score(power, ftp=250)  # 100.0
```

## Metriken

| Funktion | Definition |
|---|---|
| `normalized_power` | (mean(rolling30s(P)⁴))^¼, erst ab vollständigem 30-s-Fenster |
| `intensity_factor` | NP / FTP |
| `training_stress_score` | Stunden · IF² · 100 |
| `variability_index` | NP / Ø-Leistung |

## Performance Management Chart

```python
from datetime import date
from powerlab import performance_management_chart

load = [(date(2026, 9, 1), 85.0), (date(2026, 9, 2), 120.0), (date(2026, 9, 4), 60.0)]
for d in performance_management_chart(load, ctl0=70, atl0=75):
    print(d.day, round(d.ctl, 1), round(d.atl, 1), round(d.tsb, 1))
```

| Größe | Definition |
|---|---|
| CTL / ATL | X_t = X_{t−1} + k·(TSS_t − X_{t−1}), τ = 42 d / 7 d |
| `k` | `coggan`: 1/τ (TrainingPeaks) · `exponential`: 1 − e^(−1/τ) |
| TSB | CTL_{t−1} − ATL_{t−1} (Form am Morgen) |
| Ramp | CTL_t − CTL_{t−7} |

Fehlende Tage zählen als TSS 0, mehrere Einheiten pro Tag werden summiert.

Annahme Metriken: lückenlose 1-Hz-Reihe. Quellen: Allen & Coggan, *Training and Racing with a Power Meter*; Banister et al. 1975.
