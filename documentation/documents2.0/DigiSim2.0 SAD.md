
# DigiSim 2.0 – Software Architecture Document

## 1. Zweck des Systems

DigiSim 2.0 ist ein regelbasierter Simulator eines virtuellen landwirtschaftlichen Betriebs.  
Das System erzeugt kontinuierlich plausible landwirtschaftliche Betriebsereignisse und übermittelt diese automatisch an DigiZert.

Der Simulator dient als **virtueller Referenzbetrieb** für:

- Entwicklung und Tests von DigiZert
- Demonstrationen
- Forschung und Szenarioanalysen
- Generierung konsistenter Agrardaten ohne reale Betriebsdaten

Die Simulation läuft als **dauerhafte Serveranwendung** und erzeugt täglich neue Ereignisse im virtuellen Betrieb.

---

# 2. Systemkonzept

## 2.1 Grundprinzip der Simulation

DigiSim verwendet eine **kalenderbasierte Simulation**.

Ein Simulationsschritt entspricht exakt **einem realen Kalendertag**.

Der tägliche Ablauf wird zu einem definierten Zeitpunkt ausgelöst (Standard: 06:00 Uhr).

Dabei wird geprüft:

- welche Maßnahmen grundsätzlich möglich sind
- welche Maßnahmen priorisiert werden
- welche Maßnahmen tatsächlich ausgeführt werden

Das Ergebnis sind **Betriebsereignisse**, die anschließend an DigiZert übertragen werden.

---

## 2.2 Hauptfunktionen

DigiSim erfüllt vier zentrale Funktionen:

### Entwicklungsumgebung

DigiZert kann gegen realistische Live-Daten getestet werden.

### Demo- und Präsentationssystem

Ein virtueller Betrieb erzeugt kontinuierlich neue Maßnahmen und Ereignisse.

### Szenario-Plattform

Unterschiedliche Bewirtschaftungsstrategien können simuliert werden.

### Datengenerator

Es entstehen vollständige Betriebsdatensätze ohne Abhängigkeit von realen Betrieben.

---

## 2.3 Zentrale Systemeigenschaften

Der virtuelle Betrieb besitzt folgende Eigenschaften:

**Persistenz**

Der Zustand des Betriebs entwickelt sich über die Zeit und wird gespeichert.

**Regelbasierte Simulation**

Maßnahmen entstehen aus agronomischen Regeln und Betriebsplänen.

**Stochastische Variabilität**

Natürliche Variationen können berücksichtigt werden.

**Erweiterbarkeit**

Neue Kulturen, Maßnahmen oder Entscheidungsregeln können modular ergänzt werden.

---

# 3. Domänenmodell

Das Domänenmodell beschreibt die fachliche Struktur des virtuellen Betriebs.

Die Modellierung ist unabhängig von der konkreten Implementierung.

## 3.1 Domänenentitäten

### Farm

Die Farm repräsentiert den gesamten landwirtschaftlichen Betrieb.

Sie enthält:

- mehrere Felder
- Betriebsparameter
- globale Simulationsregeln

---

### Field

Ein Field (Schlag) repräsentiert eine landwirtschaftliche Fläche innerhalb des Betriebs.

Auf dieser Ebene werden operative Entscheidungen getroffen.

---

### CropCycle

Ein CropCycle beschreibt die saisonale Nutzung eines Feldes.

Typische Phasen:

- Bodenbearbeitung
- Aussaat oder Pflanzung
- Pflege und Pflanzenschutz
- Bewässerung
- Ernte

---

### Operation

Eine Operation ist eine landwirtschaftliche Maßnahme.

Beispiele:

- Bodenbearbeitung
- Pflanzung
- Pflanzenschutz
- Bewässerung
- Ernte

---

### Event

Events beschreiben Veränderungen im virtuellen Betrieb.

Beispiele:

- Operation durchgeführt
- Kulturzyklus gestartet
- Ernte abgeschlossen

---

## 3.2 Hierarchische Struktur

```
Farm
 └ Field
    └ CropCycle
       └ Operation
```

---

# 4. Simulationslogik

Die Simulationslogik bestimmt täglich, welche Maßnahmen stattfinden.

## 4.1 Daily Tick

Der zentrale Mechanismus der Simulation ist der **Daily Tick**.

Ablauf:

```
Daily Tick
 ↓
Candidate Generation
 ↓
Decision Logic
 ↓
Operation Execution
 ↓
Event Creation
 ↓
Event Dispatch
 ↓
State Persistence
```

---

## 4.2 Candidate Generation

Für jedes Feld wird zunächst eine Liste möglicher Maßnahmen erstellt.

Diese basiert auf:

- Kulturzyklus
- Betriebsplan
- bereits ausgeführten Maßnahmen

Das Ergebnis ist eine Liste möglicher **Operation Candidates**.

---

## 4.3 Entscheidungslogik

Die Entscheidungslogik bestimmt, welche Kandidaten tatsächlich ausgeführt werden.

Der aktuelle Entscheidungsmechanismus basiert auf einer Prioritätsstrategie.

Dabei werden bestimmte Operationstypen nur dann ausgeführt, wenn keine höher priorisierte Maßnahme vorliegt.

Die Entscheidungslogik berücksichtigt derzeit keine externen Faktoren wie:

- Wetterbedingungen
- Bodenparameter
- probabilistische Modelle

---

## 4.4 Ausführung von Maßnahmen

Wird eine Maßnahme ausgewählt, wird sie ausgeführt und anschließend ein Ereignis erzeugt.

Dieses Ereignis beschreibt die durchgeführte Operation und wird später an DigiZert übertragen.

---
# 4A – Architekturdiagramme (C4-light)

## 4A.1 System Context Diagram

```
                 +----------------------+
                 |     Entwickler       |
                 |  Tests / Demo / Dev  |
                 +----------+-----------+
                            |
                            |
                     +------+------+
                     |   DigiSim   |
                     | Virtual Farm|
                     +------+------+
                            |
                            |
                     Events / API
                            |
                            v
                    +-------+-------+
                    |     DigiZert   |
                    | Zertifizierung |
                    +-------+-------+
                            |
                            |
                     Zertifikate / UI
                            |
                            v
                    +-------+-------+
                    |   Anwendungen |
                    |  Frontend /   |
                    |  Auswertung   |
                    +---------------+
```

Rolle von DigiSim:

- erzeugt **synthetische, aber plausible Betriebsdaten**
- dient als **virtueller Referenzbetrieb**
- speist kontinuierlich Events in DigiZert ein

---
## 4A.2 Component Architecture

Dieses Diagramm beschreibt die internen Hauptkomponenten.
```
+----------------------------------------------------+
|                    DigiSim                         |
|                                                    |
|  +-------------+                                   |
|  |   Daemon    |                                   |
|  +------+------+
|         |
|         v
|  +------+------+
|  | TickScheduler|
|  +------+------+
|         |
|         v
|  +------+-----------------------------+
|  |        Simulation Engine           |
|  |                                    |
|  |  +------------------------------+  |
|  |  | CalendarDrivenRunner         |  |
|  |  +--------------+---------------+  |
|  |                 |
|  |        +--------+---------+
|  |        | Service Layer    |
|  |        |                  |
|  |        | PlantingService  |
|  |        | ProtectionService|
|  |        | IrrigationSim    |
|  |        | MoistureService  |
|  |        +--------+---------+
|  |                 |
|  |        +--------+---------+
|  |        | DecisionManager  |
|  |        +------------------+
|  |
|  +-----------------------------------+
|              |
|              v
|       +------+------+
|       | EventLogger |
|       +------+------+
|              |
|              v
|      +-------+-------+
|      | RetryDispatcher|
|      +-------+-------+
|              |
|              v
|         DigiZert API
|
|  +--------------------+
|  | StateManager       |
|  | JSON Snapshots     |
|  +--------------------+
|
+----------------------------------------------------+
```

**Hauptverantwortlichkeiten**

|Komponente|Aufgabe|
|---|---|
|Daemon|Start und Lifecycle Management|
|Scheduler|täglicher Simulationsstart|
|Simulation Engine|Koordination der Simulation|
|Services|fachliche Simulationslogik|
|DecisionManager|Auswahl der Operationen|
|EventLogger|interne Ereignisprotokollierung|
|RetryDispatcher|sichere Übertragung an DigiZert|
|StateManager|Persistenz des Simulationszustands|

---

## 4A.3 Simulationsablauf

Das folgende Diagramm zeigt den Ablauf eines Simulationsschrittes.
```
Daily Tick
    |
    v
+----------------------+
| Candidate Generation |
| mögliche Operationen |
+----------+-----------+
           |
           v
+----------------------+
| Decision Engine      |
| Prioritätslogik      |
+----------+-----------+
           |
           v
+----------------------+
| Operation Execution  |
| Statusänderung Feld  |
+----------+-----------+
           |
           v
+----------------------+
| Event Creation       |
| Operation Event      |
+----------+-----------+
           |
           v
+----------------------+
| Event Dispatch       |
| RetryDispatcher      |
+----------+-----------+
           |
           v
+----------------------+
| State Persistence    |
| Snapshot speichern   |
+----------------------+
```


---

# 5. IST-Architektur

Dieses Kapitel beschreibt die aktuelle technische Implementierung von DigiSim.

## 5.1 Architekturüberblick

DigiSim läuft als dauerhafte Serveranwendung innerhalb eines Docker-Containers.

Der zentrale Datenfluss ist:

```
Daemon
 ↓
Scheduler
 ↓
Daily Tick
 ↓
Simulation Engine
 ↓
Event Dispatch
 ↓
State Persistence
```

---

## 5.2 Scheduler

Der Scheduler löst täglich einen Simulationslauf aus.

Der Standardzeitpunkt ist:

06:00 Uhr.

---

## 5.3 Simulation Engine

Für jedes Feld wird eine eigene Simulation durchgeführt.

Die Simulation koordiniert mehrere Services, die unterschiedliche Aspekte der landwirtschaftlichen Prozesse modellieren.

---

## 5.4 Service-Komponenten

Die Simulationslogik ist in mehrere Services aufgeteilt.

### Planting Service

Verantwortlich für Pflanzoperationen.

### Protection Service

Verantwortlich für Pflanzenschutzmaßnahmen.

### Irrigation Service

Simuliert Bewässerungsentscheidungen und Bodenfeuchtigkeitsverläufe.

### Moisture Data Service

Liefert historische Feuchtigkeitsdaten.

---

## 5.5 Event Dispatch

Die erzeugten Ereignisse werden über einen Dispatcher an DigiZert übertragen.

Der Dispatcher stellt sicher, dass fehlgeschlagene Übertragungen erneut versucht werden.

---

## 5.6 Parallelisierung

Die Simulation mehrerer Felder erfolgt parallel.

Dadurch können auch größere Betriebsstrukturen effizient simuliert werden.

---

## 5.7 Persistenz

Der aktuelle Zustand des virtuellen Betriebs wird regelmäßig gespeichert.

Die Persistenz erfolgt über JSON-basierte Snapshots.

Diese enthalten unter anderem:

- letzten Simulationszeitpunkt
- Feldzustände
- bereits ausgeführte Maßnahmen    

---

## 5.8 Bekannte Einschränkungen der aktuellen Architektur

Die aktuelle Implementierung weist einige Einschränkungen auf:

**Unvollständige Persistenz**

Nicht alle internen Zustände werden gespeichert.

**Fehlende vollständige Event-Historie**

Der vollständige Verlauf der Simulation wird nicht dauerhaft gespeichert.

**Retry-Queue**

Fehlgeschlagene Events werden derzeit nur beim Start des Systems erneut verarbeitet.

**Statische Feuchtigkeitsdaten**

Der Moisture Data Service nutzt historische Daten eines festen Jahres.

---

# 6. Zielarchitektur

Dieses Kapitel beschreibt mögliche Weiterentwicklungen der Architektur.

---

## 6.1 Eventbasierte Modellierung

Eine zukünftige Architektur basiert stärker auf einem Event-Modell.

Dabei werden alle relevanten Änderungen im System als Domain Events gespeichert.

Beispiele:

- DailyTickStarted
- OperationConsidered
- OperationApproved
- OperationRejected
- HarvestCompleted

Ein Event-Log ermöglicht:

- vollständige Nachvollziehbarkeit
- reproduzierbare Simulation
- Debugging und Analyse

---

## 6.2 Event-Ebenen

Die Zielarchitektur unterscheidet drei Ebenen von Ereignissen.

### Domain Events

Fachliche Ereignisse innerhalb der Simulation.

### State Projections

Abgeleitete Zustände, die aus Events berechnet werden.

### Integration Events

Ereignisse für externe Systeme wie DigiZert.

---

## 6.3 Vereinheitlichte Entscheidungslogik

Die aktuelle Architektur verwendet mehrere Entscheidungswege.

Ziel ist eine einheitliche Pipeline:

```
Candidate Generation
 ↓
Decision Engine
 ↓
Execution
```

Alle Operationstypen werden durch denselben Entscheidungsmechanismus bewertet.

---

## 6.4 Erweiterte Entscheidungsmodelle

Zukünftige Erweiterungen könnten zusätzliche Faktoren berücksichtigen:

- Wetterbedingungen
- Bodenparameter
- probabilistische Modelle
- Sensordaten

---

## 6.5 Szenariosimulation

Zusätzlich zum Live-Modus können weitere Betriebsmodi eingeführt werden:

**Replay-Modus**

Simulation vergangener Zeiträume.

**Fast-Forward-Modus**

Beschleunigte Simulation mehrerer Tage oder Saisons.

--- 
## 6.6 Architekturleitlinie: Event-Driven Core

Für die Weiterentwicklung von DigiSim soll schrittweise ein leichtgewichtiges **Event-Driven-Core-Prinzip**berücksichtigt werden.

Ziel ist, fachliche Zustandsänderungen innerhalb der Simulation klar von technischer Integration und Persistenz zu trennen.

### Grundprinzip

Fachlich relevante Änderungen im System sollen nach Möglichkeit nicht direkt durch beliebige Statusmutationen erfolgen, sondern über ein fachliches Ereignis beschrieben werden.

Beispiel:

Nicht bevorzugt:
operation.actual_date = today  
field.status = "harvested"

Bevorzugt:
event = HarvestCompleted(field_id=field.id, date=today)  
apply(event)  
publish(event)

### Leitidee

Der gewünschte Ablauf innerhalb der Simulationslogik ist:

Decision  
→ Domain Event  
→ State Update  
→ optional Integration Event

Damit wird getrennt zwischen:

- der fachlichen Entscheidung
- der internen Zustandsänderung
- der externen Kommunikation mit DigiZert

### Zielsetzung

Dieses Prinzip dient insbesondere dazu,

- Zustandsänderungen nachvollziehbarer zu machen
- Simulationsentscheidungen besser zu protokollieren
- die Kopplung zwischen Fachlogik und API-Integration zu reduzieren
- eine spätere Event-Historie, Replay-Funktion und Szenariosimulation vorzubereiten

### Pragmatische Einführung

DigiSim soll dafür **nicht sofort vollständig auf Event Sourcing umgestellt** werden.

Stattdessen wird eine schrittweise Einführung angestrebt:

1. Domain Events für zentrale Entscheidungen einführen
2. Zustandsänderungen zunehmend über `apply(event)` modellieren
3. Integration Events aus Domain Events ableiten
4. Snapshots weiterhin als primären Persistenzmechanismus beibehalten

### Mindestregel für neue Erweiterungen

Für neue fachliche Logik gilt als architektonische Leitlinie:

- keine neue fachliche Zustandsänderung ohne fachlich benennbares Event
- keine direkte Kopplung von Fachentscheidung und DigiZert-Payload
- Integration Events sollen nach Möglichkeit aus Domain Events abgeleitet werden

### Erste relevante Eventtypen

Für eine initiale Umsetzung sind insbesondere folgende Eventtypen geeignet:

- `OperationApproved`
- `OperationRejected`
- `OperationApplied`

Diese drei Ereignisse decken bereits einen großen Teil der täglichen Simulationsentscheidungen ab und schaffen eine gute Grundlage für spätere Erweiterungen.

---

## 6A.1 Domain Events

Domain Events beschreiben fachliche Ereignisse innerhalb der Simulation.

### Beispiele

|Event|Bedeutung|
|---|---|
|DailyTickStarted|Simulationsschritt beginnt|
|DailyTickCompleted|Simulationsschritt beendet|
|CropCycleStarted|neue Kultur beginnt|
|OperationConsidered|Operation wurde geprüft|
|OperationApproved|Operation wurde ausgewählt|
|OperationRejected|Operation wurde verworfen|
|HarvestCompleted|Ernte abgeschlossen|

---

## 6A.2 Operation Events

Diese Events beschreiben landwirtschaftliche Maßnahmen.

Beispiele:

- SoilPreparationApplied
- PlantingApplied
- PesticideApplied
- IrrigationApplied
- HarvestingApplied

---

# 6A.3 Integration Events

Integration Events sind Ereignisse für externe Systeme.

Für DigiSim ist das hauptsächlich:

```FieldOperationEvent```

Dieses Event wird an DigiZert übertragen.

---

# 6A.4 Event Struktur

Ein generisches Event kann folgende Struktur haben:
```
{  
  "event_id": "uuid",  
  "event_type": "OperationApproved",  
  "timestamp": "2026-04-15T06:00:00Z",  
  "field_id": "field_12",  
  "payload": {  
    "operation_type": "planting",  
    "crop": "potato",  
    "area": 2.4  
  }  
}
```

### Felder

|Feld|Beschreibung|
|---|---|
|event_id|eindeutige Event-ID|
|event_type|Typ des Ereignisses|
|timestamp|Zeitpunkt|
|field_id|betroffenes Feld|
|payload|fachliche Zusatzdaten|

---

## 6A.5 Event Log

Ein zukünftiges Event Log speichert alle Domain Events.

Dies ermöglicht:

- vollständige Nachvollziehbarkeit
- Replay der Simulation
- Szenarioanalysen
- Debugging komplexer Entscheidungsprozesse

Der aktuelle Zustand eines Feldes kann dann aus der Event-Historie rekonstruiert werden.

---
# 7. Zusammenfassung

DigiSim 2.0 ist ein regelbasierter Simulator eines virtuellen landwirtschaftlichen Betriebs.

Das System erzeugt kontinuierlich realistische Betriebsereignisse und dient als Referenzdatenquelle für DigiZert.

Die aktuelle Architektur ist bewusst pragmatisch und auf Stabilität sowie Erweiterbarkeit ausgelegt.

Die langfristige Weiterentwicklung konzentriert sich auf:

- eventbasierte Modellierung
- verbesserte Entscheidungslogik
- integration zusätzlicher Datenquellen
- erweiterte Simulationsmodi.
