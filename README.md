[![CI](https://github.com/LucasJohannsen/DigiSim/actions/workflows/ci.yml/badge.svg)](https://github.com/LucasJohannsen/DigiSim/actions/workflows/ci.yml)

## Inhaltsverzeichnis

- [DigiSim](#digisim)
   - [Minimal Viable Product (MVP)](#minimal-viable-product-mvp)
      - [Ziele des MVP](#ziele-des-mvp)
      - [Nicht enthalten im MVP](#nicht-enthalten-im-mvp)
      - [Technische Hinweise](#technische-hinweise)
   - [Installation](#installation)
      - [Mit Python lokal installiert](#mit-python-lokal-installiert)
      - [Installation mit conda](#installation-mit-conda)
   - [Docker Deployment](#docker-deployment)
      - [Voraussetzungen](#voraussetzungen)
      - [Setup](#setup)
      - [Persistente Daten](#persistente-daten)
      - [Image-Größe](#image-größe)
      - [Troubleshooting](#troubleshooting)
   - [Einrichtung der Konfiguration](#einrichtung-der-konfiguration)
      - [Manuelle Konfiguration](#manuelle-konfiguration)
      - [Konfiguration über JSON-Datei](#konfiguration-über-json-datei)
      - [Konfiguration über DigiZert API](#konfiguration-über-digizert-api)
      - [Konfiguration der Anbaupläne](#konfiguration-der-anbaupläne)
   - [Anwendung starten](#anwendung-starten)
      - [Simulation eines eigenen Feldes](#simulation-eines-eigenen-feldes)
      - [Simulation eines vordefinierten Feldes](#simulation-eines-vordefinierten-feldes)
      - [Simulation eines Betriebs/ Batch-Simulation](#simulation-eines-betriebs-batch-simulation)
   - [Mock-API verwenden](#mock-api-verwenden)
   - [Ablauf der Simulation](#ablauf-der-simulation)
      - [Festlegung der Simulationsparameter](#festlegung-der-simulationsparameter)
      - [Ermittlung der Operationen](#ermittlung-der-operationen)
  - [Output-Format](#output-format)
  - [Code-Architektur und Klassenübersicht](#code-architektur-und-klassenübersicht)
      - [Gesamtarchitektur](#gesamtarchitektur)
      - [Kernklassen und ihre Beziehungen](#kernklassen-und-ihre-beziehungen)
      - [Datenfluss](#datenfluss)
      - [Abhängigkeitsmatrix](#abhängigkeitsmatrix)
   - [Contributing](#contributing)
   - [Lizenz](#lizenz)
   - [Danksagungen](#danksagungen)

# DigiSim

## Minimal Viable Product (MVP)

Das MVP von DigiSim verfolgt das Ziel, eine erste lauffähige Version der Simulationssoftware bereitzustellen, die den Kernnutzen demonstriert und als Grundlage für Feedback und Weiterentwicklung dient.

**Ziele des MVP:**
- Simuliert ein Beispiel-Feld und einen vordefinierten Zeitraum (z.B. eine Saison, feste Parameter).
- Bildet mindestens eine Maßnahme (z.B. Düngung oder Pflanzenschutz) mit einfachen Regeln ab.
- Gibt die simulierten Ereignisse als strukturierte Zeitreihe im JSON-Format aus.
- Speichert die Daten lokal als JSON-Datei (die spätere Anbindung an die Event Sourcing Datenbank erfolgt auf Basis dieses Formats).
- Erkennt und meldet Fehler bei ungültigen Eingaben verständlich.

**Nicht enthalten im MVP:**
- Keine komplexe Konfiguration oder Batch-Funktionalität.
- Kein Import echter Betriebsdaten.
- Keine Anbindung an die ESDB (diese folgt später).

**Technische Hinweise:**
- Die Architektur ist modular, um spätere Erweiterungen (weitere Felder, Maßnahmen, Validierung, UI) zu erleichtern.
- Das JSON-Ausgabeformat wird so gestaltet, dass es für die spätere Integration in die ESDB geeignet ist.

## Installation

Die Anwendung wurde mit Python 3.13.5 entwickelt. Je nach dem, ob Python local installiert ist oder conda verwendet wird, kann die Installation unterschiedlich erfolgen.

### Mit Python lokal installiert
1. Stelle sicher, dass Python 3.13.5 oder höher installiert ist.
2. Lege ein virtuelles Environment an:
   ```bash
   python -m venv .venv
   ```
3. Aktiviere das virtuelle Environment:
   - Auf Windows:
     ```bash
     .venv\Scripts\activate
     ```
    - Auf Linux/macOS:
    ```bash
    source .venv/bin/activate
    ```

4. Installiere die Abhängigkeiten:
```bash
pip install .
```
5. Führe die Anwendung aus:
   ```bash
   python main.py
   ```
6. Um das virtuelle Environment zu verlassen, führe `deactivate` aus.

Hinweis: sollte es zu Problemen bei der Installation kommen, kann die Umgebung mit dem folgenden Befehl gelöscht werden:
Windows:
```bash
rmdir /s /q .venv
```
Linux/macOS:
```bash
rm -rf .venv
```


## Installation mit conda
1. Stelle sicher, dass conda installiert ist.
2. Erstelle ein neues conda-Environment:
   ```bash
   conda create -n digisim python=3.13.5
   ```
3. Aktiviere das Environment:
   ```bash
    conda activate digisim
    ```
4. Installiere die Abhängigkeiten:
    ```bash
    pip install .
    ```
5. Führe die Anwendung aus:
    ```bash
    python main.py
    ```
6. Um das Environment zu verlassen, führe `conda deactivate` aus.


## Docker Deployment

### Voraussetzungen
- Docker 24.0+
- Docker Compose 2.0+

### Setup

1. **Konfiguration erstellen:**
   ```bash
   cp .env.example .env
   # .env editieren: DIGIZERT_API_URL, DIGIZERT_API_TOKEN, FARM_ID setzen
   ```

2. **Container bauen und starten:**
   ```bash
   docker-compose up --build -d
   ```

3. **Logs verfolgen:**
   ```bash
   docker-compose logs -f digisim
   ```

4. **Status prüfen:**
   ```bash
   docker-compose ps
   ```

5. **Stoppen:**
   ```bash
   docker-compose down
   ```

### Persistente Daten

Die folgenden Verzeichnisse werden als Volumes gemountet:
- `./state` – Simulationszustand pro Feld
- `./retry_queue` – Fehlgeschlagene API-Requests
- `./logs` – Strukturierte JSON-Logs

**Backup:** Einfach diese 3 Verzeichnisse sichern.

### Image-Größe

Das finale Image ist **< 300MB** dank Multi-Stage-Build:
```bash
docker images digisim
```

### Troubleshooting

**Container startet nicht:**
```bash
docker-compose logs digisim
# Prüfe auf fehlende Env-Vars in .env
```

**Keine Events werden gesendet:**
```bash
# Prüfe retry_queue/ auf fehlgeschlagene Events
ls -la retry_queue/
```

**State geht verloren:**
```bash
# Prüfe Volume-Mounts
docker inspect digisim | grep -A 10 Mounts
```


## Einrichtung der Konfiguration
Die Simmulation wird für ein oder mehrere Felder eines Betriebs durchgeführt. Die Felder und die zugehörigen Parameter werden in der Konfiguration festgelegt - entweder manuell über die Kommandozeile, über eine lokale JSON-Datei oder über die API von DigiZert.
### Manuelle Konfiguration
Die Konfiguration kann manuell über die Kommandozeile angepasst werden. Hierzu wird der Befehl `plan` verwendet. Dieser Befehl ermöglicht es, die Simulationsparameter für das ausgewählte Feld anzupassen. Die Änderungen werden in der aktuellen Sitzung gespeichert und können bei Bedarf erneut angepasst werden.
### Konfiguration über JSON-Datei
Die Konfiguration kann auch über eine lokale JSON-Datei erfolgen. Diese Datei ```farms.json``` im Ordner ```config``` enthält die Felder und deren Parameter. `
Die Struktur der Datei sollte wie folgt aussehen:

```json
{
    "farms": [
        {
            "id": 1,
            "name": "Diddly Squat Farm",
            "fields": [
               {
                    "id": 999919,
                    "name": "Campfield",
                    "distance_to_barn": 4,
                    "area": 12.46,
                    "soil_type": "sand"
                },
                {
                    "id": 999918,
                    "name": "Deadman",
                    "distance_to_barn": 4.0,
                    "area": 7.6,
                    "soil_type": "sand"
                },
...
```

Über das Kommando `pick_field` kann ein Feld aus der JSON-Datei ausgewählt werden. Die Konfiguration wird dann für dieses Feld verwendet.

### Konfiguration über DigiZert API
Die Konfiguration kann auch über die API von DigiZert erfolgen. Hierzu wird im Stammverzeichnis eine ```.env``-Datei benötigt, die die URL der API enthält und ggf. auch Authentifizierungsmerkmale. 

Hinweis: Derzeit wird nur der lokale Mock-Server unterstützt!

Die `.env`-Datei sollte folgende Struktur haben:

```bash
# API Endpoint für DigiZert
API_URL=127.0.0.1:5001
```

### Konfiguration der Anbaupläne

Für jede Kultur muss ein Anbauplan hinterlegt werden. HIerzu wird im config Order eine neue Datei mit dem Namen `planting_plan_<crop_name>.json` angelegt. 
Die json-Date 


#### Template für neue Kulturen

Um Agrar-Expert:innen Schritt für Schritt durch die benötigten Angaben zu führen, liegt im Ordner [`config/`](config) die Datei [`planting_plan_template.json`](config/planting_plan_template.json). Sie enthält:

1. eine erklärende `__instructions`-Sektion mit allen Pflichtfeldern,
2. vordefinierte Phasen (Bodenbearbeitung, Aussaat, Pflege, Ernte, Nachernte),
3. Platzhalter-Operationen inklusive typischer Parameter (z. B. `min_days_to_target`, `application_*`).

**Vorgehen:**

1. Datei kopieren und als `planting_plan_<kultur>.json` speichern.
2. Alle `TODO`-Werte durch reale Angaben ersetzen (Monate als Zahlen 1–12, Dauer/Fuel per Hektar, optionale Schutzpläne).
3. Datei im Repository einchecken und im Simulationstest verwenden.

Als Referenz ist bereits ein zusätzlicher Plan [`planting_plan_winter_wheat.json`](config/planting_plan_winter_wheat.json) enthalten. Er wurde mit dem Template erstellt und zeigt, wie ein vollständiger Satz an Operationen (z. B. Stoppelsturz, Drillsaat, Fungizid, Dreschen) für eine neue Kultur aussieht.


```json
{
    "crop": "Potato",
    "variety": "Belana",
    "planting_period_months": [
        4,
        5
    ],
    "harvest_period_months": [
        9,
        10
    ],
    "growth_duration": 90,
    "phases": [
        {
            "soil_preparation": {
                "target_date_name": "Planting",
                "operations": [
                    {
                        "sequence": 1,
                        "operation": "Grubbern",
                        "min_days_to_target": -27,
                        "max_days_to_target": -23,
                        "duration_per_ha": 0.89,
                        "working_width": 2.5,
                        "fuel_consumption": 12.7,
                        "worktype": 6
                    },
                    {
[...]

],
    "protection_plans": [
        {
            "name": "Protection Plan Belana 1",
            "description": "Erster Plan für Belana",
            "days_to_target": 17,
            "protections": [
                {
                    "day": 0,
                    "type": 26,
                    "name": "Bandur Artist",
                    "amount": "2.5+2"
                },
                {
                    "day": 21,
                    "type": 27,
                    "name": "Zorvec",
                    "amount": "0.25"
                },
```


Die Eigenschaften `crop` und `variety` werden für die Auswahl des Anbauplans verwendet. Die `planting_period_months` und `harvest_period_months` geben die Monate an, in denen die Pflanzung und Ernte stattfinden können. Die `growth_duration` gibt die Wachstumsdauer in Tagen an.
Die `phases` enthalten die verschiedenen Phasen des Anbaus, wie Bodenbearbeitung, Düngung und Pflanzenschutz. Jede Phase kann mehrere Operationen enthalten, die in einer bestimmten Reihenfolge ausgeführt werden.
Die Phasen sind auf ein bestimmtes Datum bezogen, das in der Simulation als `target_date_name` angegeben wird. Die `operations` enthalten Details zu den durchzuführenden Arbeiten, wie z.B. Grubbern, Düngen oder Pflanzenschutzmaßnahmen.
Zusätzlich werden die Parameter der Operation für die DigiZert-Anwendung definiert, wie z.B. die Dauer pro Hektar, der Arbeitsbreite, der Kraftstoffverbrauch und der Arbeitstyp.

## Anwendung starten
Um die Anwendung zu starten, führe im Terminal den folgenden Befehl aus:

```bash
python main.py
```
Anschließend wird der Prompt mit ```(digisim)``` angezeigt und die Anwendung ist bereit.

Über das Kommand ```help``` kannst du eine Übersicht der verfügbaren Befehle erhalten. Mit dem Kommando ```exit``` kannst du die Anwendung beenden.
Aktuell sind die folgenden Befehle verfügbar:
- `show_config`: Zeigt die aktuelle Konfiguration der Simulation an.
- `plan`: Erlaubt das Anpassen der Simulationsparameter.
- `pick_field`: Wählt ein vordefiniertes Feld für die Simulation aus (aus DigiZert oder lokal)
- `run`: Startet die Simulation und gibt die Ergebnisse als JSON aus.
- `run_batch`: Führt eine Batch-Simulation für alle Felder aus und gibt die Ergebnisse als JSON aus.
- `replay`: Re-simuliert einen vergangenen Zeitraum (siehe MS4 Features)
- `fast_forward`: Schnelle Simulation für mehrere Tage ohne Real-Time-Delay (siehe MS4 Features)

### Simulation eines eigenen Feldes
Um ein eigenes Feld zu simulieren, kannst du die `plan`-Funktion verwenden, um die Parameter für das Feld festzulegen. Hierbei kannst du die folgenden Parameter anpassen:
- `id`: Eindeutige ID des Feldes
- `name`: Name des Feldes
- `size`: Größe des Feldes in Hektar
- `soil_type`: Bodentyp des Feldes (z.B. "sand", "clay")
- `start_date`: Startdatum der Simulation (im Format "YYYY-MM-DD")
- `crop`: Anbaukultur des Feldes (z.B. "Potato")
- `variety`: Sorte der Anbaukultur (z.B. "Belana")

Wenn sich einzelne Parameter wie id oder Name nicht ändern sollen, kann der bestehende Wert einfach mit Enter bestätigt werden.
Anschließend kann über den Befehl `run` die Simulation gestartet werden.

### Simulation eines vordefinierten Feldes
Um ein vordefiniertes Feld zu simulieren, kannst du den Befehl `pick_field` verwenden. Sofern die ```.env``` Datei hinterlegt ist, wird diese verwendet, andernfalls die `farms.json`   aus dem config Ordner. Nach der Auswahl des Feldes kannst du die Parameter anpassen und die Simulation mit dem Befehl `run` starten.

### Simulation eines Betriebs/ Batch-Simulation
Um eine Batch-Simulation für alle Felder eines Betriebs durchzuführen, kannst du den Befehl `run_batch` verwenden. Dieser Befehl führt die Simulation für alle vordefinierten Felder aus und gibt die Ergebnisse als JSON aus.

## Mock-API verwenden
Für lokale Tests der DigiZert-API kann der Mock-Server verwendet werden. Dieser ist im Ordner `poc` enthalten und kann mit dem Befehl `python poc/mock_api_backend.py` gestartet werden. Der Server läuft standardmäßig lokal auf Port 5001.

## Ablauf der Simulation

Die Simulation erfolgt mithilfe von Simpy (https://simpy.readthedocs.io/en/latest/) und läuft rundenbasiert ab. Je Runde/ Simulationsschritt (hier: 1 Schritt -> 1 Tag) werden die durchführbaren Operationen der jeweiligen Services ermittelt und je nach Strategie ein bzw. mehrere Ereignis erzeugt. Diese Ereignisse werden in einer Zeitreihe gespeichert und am Ende der Simulation als JSON ausgegeben.

### Festlegung der Simulationsparameter

Die Simulation erfolgt in mehreren Schritten. Durch die Nutzereingaben werden die Parameter für die Simulation im `SimContext` festgelegt. 

```python
@dataclass
class SimContext:
    """
    Parameters for the SimPy simulation environment.
    """
    field_size: float = 10.0  # Default field size for the simulation
    soil_type: str = 'sand'  # Default soil type for the simulation
    start_date: datetime = datetime.datetime(2024, 10, 1)  # Default start date for the simulation
    crop_type: str = 'Potato'  # Default crop type for the simulation
    variety: str = 'Belana'  # Default crop variety
    field_id: int = 1
    field_name: str = 'Kiel'
    fuel_variation: float = 0.1  # Default variation in fuel consumption for batch simulations
``` 

Für den Batch-Lauf wird eine Liste von `SimContext`-Objekten erstellt, die jeder für sich separat ausgeführt werden.

### Ermittlung der Operationen 

Der SimulationRunner orchestriert die verschiedenen Services und führt die Simulation durch. 

Der zentrale Service ist der `PlantingPlanService`, der die Anbaupläne für die jeweilige Kultur bereitstellt. Dieser ermittelt für den jeweiligen Tag der Simulation, welche Operationen durchgeführt werden könnten und stellt diese bereit. Parallel geben auch der `IrrigationService` und der `ProtectionPlanService` ihre möglichen Operationen zurück.
Der `DecisionManager`entscheidet auf Basis der Strategie, welche Operationen tatsächlich durchgeführt werden.

Der SimulationRunner sorgt dafür, dass der IrrigationService und der ProtectionPlanService nur in der Wachstumsphase der Kultur aktiv sind. Sobald die Erntephase erreicht ist, werden diese Services deaktiviert und die entsprechenden Operationen nicht mehr berücksichtigt.

Jede durchgeführte Operation wird als `SimulationEvent` in der Zeitreihe gespeichert und am Ende der Simulation durch den `EventLogger` ausgegeben.

**PlantingPlanService**:
Der PlantingPlanService wählt nach dem Laden des Anbauplans zuerst ein zufälliges Datum für das Legen/ Aussat/ die Pflanzung fest. Basierend auf diesem Daten werden dann die Datumsangaben für die Operationen der aktuellen Phase zufällig gewählt. Sobald das jeweilige Datum erreicht ist, werden die Operationen der Phase zurückgegeben.

**IrrigationService**:
Zur Ermittlung der Bodenfeuchte verwendet der IrrigationService historische Modelldaten des DWD.
Für einen zufälligen Punkt im Jahr wird die Bodenfeuchte ermittelt und auf Basis der aktuellen Phase und der Bodenfeuchte wird entschieden, ob eine Bewässerung notwendig ist.
Sinkt der Wert unter einen bestimmten Schwellenwert, wird eine Bewässerung durchgeführt. Die Bewässerung wird als `SimulationEvent` in der Zeitreihe gespeichert. Ist in der Zeitreihe eine Erhöhung der Bodenfeuchte in einem kurzen Intervall von 4 Tagen erwartet, wird trotz Unterschreiten des Schwellenwerts keine Bewässerung durchgeführt um realistischer zu simulieren, dass bei erwartetem Regen ggf. eine geringfügige Unterschreitung zugelassen wird.

**ProtectionPlanService**:
Der ProtectionPlanService ermittelt aus der Liste der definieren Schutzmaßnahmen eine zufällige. Ab Pflanzdatum wird der Zeitpunkt des Schadensereignisses ermittelt und die Schutzmaßnahme zeitlich wie im Plan definiert durchgeführt. 

## MS4 Features - Erweiterte Simulationsplattform

Mit Milestone 4 wurden drei wichtige Erweiterungen implementiert:

### 1. Replay Simulation (Issue #44)

Re-simuliere vergangene Zeiträume deterministisch:

```bash
replay --from 2024-01-01 --to 2024-12-31 --output json
```

**Verwendung:**
- Nachträgliche Simulation vergangener Perioden
- Validierung gegen historische Daten
- Generierung von Event-Daten für Analysen

### 2. Fast-Forward Simulation (Issue #45)

Schnelle Simulation ohne Real-Time-Delay:

```bash
fast_forward --days 365 --output json
```

**Verwendung:**
- Demo-Vorbereitung
- Synthetische Datengenerierung
- Testen von Saison-Szenarien
- Batch-Processing

### 3. Externe Datenquellen (Issue #46)

Integration von Wetter-, Boden- und Sensordaten:

**Weather Data (Open-Meteo API):**
```python
from services.weather_adapters import OpenMeteoWeatherAdapter

adapter = OpenMeteoWeatherAdapter(latitude=52.52, longitude=13.41)
weather_data = adapter.get_data(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31)
)
```

**Soil Parameters (Config File):**
```python
from services.soil_adapters import ConfigFileSoilAdapter

adapter = ConfigFileSoilAdapter(config_path="config/soil_parameters.json")
soil_data = adapter.get_data(field_id="12345")
```

**Features:**
- Automatischer Fallback auf synthetische Daten
- Konfigurierbar über `.env` oder Code
- Keine API-Keys erforderlich (Open-Meteo)

Detaillierte Dokumentation: [documentation/MS4_FEATURES.md](documentation/MS4_FEATURES.md)

## Output-Format

Die Simulation exportiert alle Operationen nach Abschluss in das Verzeichnis `export/<YYYY-MM-DD>/`. Der Dateiname folgt dem Schema `simulation_<field_id>_<field_name>.json`, wobei der Feldname für Dateisysteme bereinigt wird. Jede Datei enthält:

1. `field`: Metadaten zum simulierten Feld (ID, Name, Fläche).
2. `harvest_cycle`: Zeitraum der simulierten Saison.
3. `operations`: Liste aller durchgeführten Maßnahmen inklusive Maschinen, Dauer, Verbrauch und optionalem Applikationskontext.

### Beispiel-Output

```json
{
  "field": {
    "exa_id": 1,
    "name": "Testfeld Nord",
    "area": 12.5
  },
  "harvest_cycle": {
    "id": 0,
    "start_date": "",
    "end_date": ""
  },
  "operations": [
    {
      "model": "pipeline.operation",
      "pk": 0,
      "fields": {
        "batch": null,
        "field": 1,
        "worktype": 6,
        "exa_id": 0,
        "start_date": "2025-04-01 08:51:24",
        "end_date": "2025-04-01 19:58:54",
        "machine": "Fendt 719 Vario",
        "area": 12.5,
        "distance": 50.0,
        "distanceWorked": 47.5,
        "duration": 40050.0,
        "durationWorked": 38047.5,
        "fuel": 170.49,
        "application_type": null,
        "application_category": null,
        "application_name": null,
        "application_amount": 0.0,
        "application_unit": null,
        "worktype_text": "Grubbern"
      }
    },
  ]
}
```

Ein vollständiges Beispiel inklusive aller Operationen findest du unter [documentation/example_output.json](documentation/example_output.json).


## Code-Architektur und Klassenübersicht

### Gesamtarchitektur

Die DigiSim-Anwendung folgt einer modularen Event-Driven-Architektur, die in folgende Hauptbereiche unterteilt ist:

```
DigiSim/
├── main.py                 # Entry Point mit CLI
├── config/                 # Konfigurationsdateien
├── src/
│   ├── simulation/         # Simulationslogik
│   ├── models/            # Datenmodelle
│   ├── services/          # Business Services
│   └── utils/             # Hilfsfunktionen
└── poc/                   # Mock-API für Tests
```

### Kernklassen und ihre Beziehungen

#### 1. SimContext (Simulationskontext)
```python
@dataclass
class SimContext:
    field_size: float
    soil_type: str
    start_date: datetime
    crop_type: str
    variety: str
    field_id: int
    field_name: str
    fuel_variation: float
```
**Zweck**: Zentrale Datenstruktur für alle Simulationsparameter
**Beziehungen**: Wird von allen Simulationskomponenten verwendet

#### 2. Simulation Engine
**Hauptklassen**:
- `SimulationRunner`: Orchestriert den gesamten Simulationsprozess
- `EventGenerator`: Erzeugt Ereignisse basierend auf Anbauplänen
- `WeatherSimulator`: Simuliert Wetterbedingungen

**Workflow**:
```
SimContext → SimulationEngine → EventGenerator → Events → JSON Output
                ↓
         WeatherSimulator → Weather Events
```

#### 3. Datenmodelle

**Field Model**:
```python
@dataclass
class Field:
    id: int
    name: str
    area: float
    soil_type: str
    distance_to_barn: float
```

**Event Model**:
```python
@dataclass
class SimulationEvent:
    timestamp: datetime
    event_type: str
    field_id: int
    operation: str
    parameters: dict
```

**PlantingPlan Model**:
```python
@dataclass
class PlantingPlan:
    crop: str
    variety: str
    planting_period_months: List[int]
    harvest_period_months: List[int]
    growth_duration: int
    phases: List[Phase]
    protection_plans: List[ProtectionPlan]
```

#### 4. Services

**ConfigService**:
- Lädt Konfigurationen aus JSON-Dateien
- Verwaltet Anbauplan-Konfigurationen
- Stellt Feldkonfigurationen bereit

**APIService**:
- Kommuniziert mit DigiZert API
- Lädt Betriebsdaten und Feldkonfigurationen
- Unterstützt Mock-API für lokale Tests

**ValidationService**:
- Validiert Eingabeparameter
- Prüft Konsistenz der Konfiguration
- Meldet Fehler verständlich

#### 5. CLI Interface

**CommandLineInterface**:
- Stellt interaktive Befehle bereit (`plan`, `run`, `pick_field`, etc.)
- Orchestriert die Benutzerinteraktion
- Ruft entsprechende Services auf

### Datenfluss

#### Einzelsimulation:
```
1. User Input (CLI) → SimContext
2. SimContext → ConfigService → PlantingPlan laden
3. SimContext + PlantingPlan → SimulationEngine
4. SimulationEngine → EventGenerator → Events erstellen
5. Events → JSON Serializer → Ausgabe
```

#### Batch-Simulation:
```
1. APIService/ConfigService → Liste von Fields
2. Für jedes Field: SimContext erstellen
3. Parallele/Sequenzielle Ausführung der Einzelsimulationen
4. Aggregation der Ergebnisse → JSON Output
```


### Abhängigkeitsmatrix

| Komponente | Abhängig von | Verwendet von |
|------------|--------------|---------------|
| SimContext | - | Alle Simulation Components |
| ConfigService | JSON Files | CLI, SimulationEngine |
| APIService | DigiZert API | CLI, ConfigService |
| SimulationEngine | SimContext, PlantingPlan | CLI |
| EventGenerator | PlantingPlan, SimContext | SimulationEngine |
| ValidationService | - | Alle Input-Handler |
| CLI | Alle Services | main.py |

Diese Architektur ermöglicht eine klare Trennung der Verantwortlichkeiten und erleichtert zukünftige Erweiterungen.

---

## 🤝 Contributing

Wir freuen uns über Beiträge zur Weiterentwicklung von DigiSim! 

### Wie kann ich beitragen?
- **Bugs melden**: Nutze unsere [Issue-Templates](.github/ISSUE_TEMPLATE/)
- **Features vorschlagen**: Erstelle ein Feature-Request
- **Code beitragen**: Lies unsere [Contributing Guidelines](CONTRIBUTING.md)
- **Dokumentation verbessern**: Tippfehler, Beispiele, Klarheit

### Quick Start für Contributors
1. Fork das Repository
2. Erstelle einen Feature-Branch: `git checkout -b feature/SIM-XX-mein-feature`
3. Committe deine Änderungen: `git commit -m "SIM-XX: Beschreibung"`
4. Push zum Branch: `git push origin feature/SIM-XX-mein-feature`
5. Erstelle einen Pull Request

Weitere Details findest du in [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 Lizenz

Dieses Projekt ist Teil des DigiZert-Forschungsprojekts. Details zur Lizenz findest du in der [LICENSE](LICENSE) Datei.

---

## 🙏 Danksagungen

Entwickelt im Rahmen des DigiZert-Forschungsprojekts von [FARMWISSEN](https://github.com/FARMWISSEN).

Besonderer Dank an alle Contributors, die dieses Projekt unterstützen!