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

Annahme: lückenlose 1-Hz-Reihe. Quelle: Allen & Coggan, *Training and Racing with a Power Meter*.
