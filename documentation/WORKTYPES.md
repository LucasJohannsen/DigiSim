# Worktype-Konstanten in DigiSim

## Übersicht

Die Datei `models/worktypes.py` enthält alle offiziellen Worktype-IDs aus DigiZert als Python-Enum-Konstanten.

## Wichtiger Unterschied: Worktypes vs. Application Categories

**NICHT verwechseln:**

- **Worktypes** (0-61): Beschreiben die **Art der Arbeit** (z.B. Pflügen, Säen, Spritzen)
  - Definiert in: `models/worktypes.py`
  - Verwendet in: `FieldOperation.worktype`, `FieldOperationEvent.worktype`
  
- **Application Categories** (22-34): Beschreiben die **Art des Materials** (z.B. Herbizid, Fungizid, Dünger)
  - Definiert in: `config/category.json`
  - Verwendet in: `FieldOperation.application_category`, `FieldOperationEvent.application_category`

## Verwendung

```python
from models.worktypes import WorkType

# Statt hard-codierter IDs:
operation.worktype = 14  # ❌ Nicht empfohlen

# Verwende Konstanten:
operation.worktype = WorkType.SPRITZEN  # ✅ Empfohlen
```

## Häufig verwendete Worktypes

### Bodenbearbeitung
- `WorkType.PFLUEGEN` (5)
- `WorkType.GRUBBERN` (6)
- `WorkType.EGGEN` (7)
- `WorkType.FRAESEN` (9)

### Aussaat/Pflanzung
- `WorkType.SAEEN` (11)
- `WorkType.PFLANZEN` (12)
- `WorkType.KARTOFFELN_LEGEN` (26)

### Düngung
- `WorkType.ORGANISCHE_DUENGUNG` (13)
- `WorkType.MINERALISCHE_DUENGUNG` (23)

### Pflanzenschutz
- `WorkType.SPRITZEN` (14)
- `WorkType.BEREGNEN` (15)

### Ernte
- `WorkType.DRESCHEN` (50)
- `WorkType.RODEN` (27)

### Transport/Logistik
- `WorkType.TRANSPORTIEREN` (18)
- `WorkType.VERLADEN` (58)
- `WorkType.BE_UND_ENTLADEN` (59)

## Worktype-Gruppen

Die Datei definiert auch vorgefertigte Listen für häufig benötigte Worktype-Gruppen:

```python
from models.worktypes import SOIL_PREPARATION_WORKTYPES, PLANTING_WORKTYPES

# Alle Bodenbearbeitungs-Worktypes
if operation.worktype in SOIL_PREPARATION_WORKTYPES:
    # ...
```

Verfügbare Gruppen:
- `SOIL_PREPARATION_WORKTYPES`
- `PLANTING_WORKTYPES`
- `FERTILIZATION_WORKTYPES`
- `PROTECTION_WORKTYPES`
- `HARVEST_WORKTYPES`
- `TRANSPORT_WORKTYPES`
- `LOW_PRIORITY_WORKTYPES`

## Behobene Bugs (Issue #49)

### Bug 1: Falsche Worktypes in Konfigurationen

**Gefundene Fehler:**
- ✅ `Separieren` (worktype: 28) - **korrekt**
- ✅ `Häufeln` (worktype: 29) - **korrekt** (Dammfräsen)
- ❌ `Lagerung` (worktype: 18) - **korrigiert zu 58** (Verladen)

**Korrekturen:**
1. `config/planting_plan_potato.json`: Worktype für "Lagerung" von 18 auf 58 geändert
2. Sequenznummern in `sowing_planting` Phase korrigiert (2,3 → 1,2)
3. Worktype-Konstanten in `models/worktypes.py` eingeführt
4. Hard-codierte IDs in `protection_plan_service.py` und `decision_manager.py` durch Konstanten ersetzt

## Alle DigiZert Worktypes

| ID | Bezeichnung |
|----|-------------|
| 0 | Leerfahrt |
| 1 | Rundballen pressen |
| 2 | Quaderballen pressen |
| 3 | Presswickeln |
| 4 | Ballen wickeln |
| 5 | Pflügen |
| 6 | Grubbern |
| 7 | Eggen |
| 8 | Tiefgrubbern |
| 9 | Fräsen |
| 10 | Walzen |
| 11 | Säen |
| 12 | Pflanzen |
| 13 | Organische Düngung |
| 14 | Spritzen |
| 15 | Beregnen |
| 16 | Mähen |
| 17 | Wenden |
| 18 | Transportieren |
| 19 | Kehren |
| 20 | Schnee räumen |
| 21 | Salz streuen |
| 22 | Hacken |
| 23 | Mineralische Düngung |
| 24 | Gülle pumpen |
| 25 | Gülle rühren |
| 26 | Kartoffeln legen |
| 27 | Roden |
| 28 | Separieren |
| 29 | Dammfräsen |
| 30 | Kraut schlagen |
| 31 | Schwaden |
| 32 | Striegeln |
| 33 | Schleppen |
| 34 | Mulchen |
| 35 | Kehren |
| 36 | Schnee fräsen |
| 37 | Güllecontainer umsetzen |
| 38 | Beetformen |
| 39 | Füttern |
| 40 | Holz rücken |
| 41 | Holz sägen |
| 42 | Holz spalten |
| 43 | Baumstumpffräsen |
| 44 | Schüttgut laden |
| 45 | Paletten laden |
| 46 | Ballen laden |
| 47 | CCM-Mühle umsetzen |
| 48 | Schieben |
| 49 | Front-/Heckgewicht |
| 50 | Dreschen |
| 51 | Häckseln |
| 52 | Hochdruckballen pressen |
| 53 | Entblättern |
| 54 | Planieren |
| 55 | Bodenbearbeitung |
| 56 | Gehölzpflege |
| 57 | Pflege-/Montagearbeiten |
| 58 | Verladen |
| 59 | Be- und entladen |
| 60 | Waschen |
| 61 | Verdichten |
