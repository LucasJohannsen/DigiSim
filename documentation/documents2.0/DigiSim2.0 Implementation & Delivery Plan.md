
```
Empfohlene Umsetzungsreihenfolge

1. MS1 – Stabilisierung
2. MS2 – Decision Engine
3. MS3 – Event Core
4. MS4 – Erweiterungen
```

# 1. Ziel der Weiterentwicklung

DigiSim 2.0 ist ein regelbasierter Simulator eines virtuellen landwirtschaftlichen Betriebs.  
Das System erzeugt kontinuierlich plausible landwirtschaftliche Betriebsereignisse und übermittelt diese automatisiert an DigiZert.

Der Simulator dient dabei als:

- Entwicklungsumgebung für DigiZert
- Demo- und Präsentationssystem
- Szenario-Plattform
- Generator synthetischer Betriebsdaten

Die Simulation läuft als dauerhafte Serveranwendung und erzeugt täglich neue Ereignisse im virtuellen Betrieb.

### Ziel der Weiterentwicklung

Die Weiterentwicklung von DigiSim 2.0 verfolgt drei Hauptziele:

1. **Stabilisierung des laufenden Simulationsbetriebs**
2. **Verbesserung der internen Architektur**
3. **Erweiterbarkeit der Simulationslogik**

Diese Ziele ergeben sich aus bekannten Einschränkungen der aktuellen Architektur sowie aus geplanten funktionalen Erweiterungen.

# Prioritätsübersicht der Entwicklungsphasen

|Milestone|Umfang|Abhängigkeiten|Ziel des Milestones|
|---|---|---|---|
|**MS1 – Stabilisierung des Simulators**|Klein|Keine|Sicherstellen, dass der Simulator dauerhaft stabil läuft und keine Zustände verliert.|
|**MS2 – Vereinheitlichung der Decision Engine**|Mittel|MS1 empfohlen|Alle Operationen werden über eine gemeinsame Entscheidungslogik verarbeitet.|
|**MS3 – Event Driven Simulation Core**|Mittel|Grundlage für MS4|Simulationsentscheidungen werden über Domain Events nachvollziehbar modelliert.|
|**MS4 – Erweiterte Simulation**|Groß|Setzt MS3 voraus|Erweiterung um Replay-Simulation, Fast-Forward und zusätzliche Datenquellen.|

---

# Kurzbeschreibung der Prioritäten

### MS1 – Stabilisierung des Simulators

Fokus auf technische Stabilität und Konsistenz der Simulation.

Wesentliche Punkte:

- Persistenz des IrrigationSimulators
- kontinuierliche Retry-Verarbeitung für Event Dispatch
- Anpassung des MoistureDataService
- Bereinigung ungenutzter Felder im Eventmodell
- Anpassung der Docker Healthcheck Konfiguration


Ziel:  
Der Simulator kann dauerhaft laufen, ohne Zustände zu verlieren oder Events zu verlieren.  
Diese Maßnahmen adressieren bekannte Einschränkungen der aktuellen Implementierung. 

---

### MS2 – Vereinheitlichung der Decision Engine

Aktuell existieren zwei parallele Entscheidungswege für Operationen.
Die Simulation soll künftig eine gemeinsame Pipeline verwenden:

Candidate Generation  
↓  
Decision Engine  
↓  
Execution

Dazu wird insbesondere der Sonderpfad für Bewässerung entfernt und vollständig in die Entscheidungslogik integriert.

Ziel:  
Eine einheitliche Entscheidungsstruktur für alle Operationstypen.

---

### MS3 – Event Driven Simulation Core

Einführung eines Domain-Event-Modells für zentrale Simulationsereignisse.

Beispiele:
- DailyTickStarted
- OperationConsidered
- OperationApproved
- OperationRejected
- HarvestCompleted 

Ziel:
- Nachvollziehbarkeit von Simulationsentscheidungen
- bessere Analyse und Debugging
- Grundlage für spätere Replay-Simulationen. 

---

### MS4 – Erweiterte Simulation

Auf Basis des Event-Modells können zusätzliche Funktionen eingeführt werden:

- Replay-Simulation vergangener Zeiträume
- Fast-Forward-Simulation ganzer Saisons
- Integration zusätzlicher Datenquellen (z.B. Wetter oder Sensordaten). 

Ziel:  
DigiSim wird von einem reinen Daten-Simulator zu einer Plattform für Szenario-Simulationen.

---

# 2. Ausgangszustand der Architektur (IST)

DigiSim ist als dauerhaft laufende Serveranwendung konzipiert und wird typischerweise als Docker-Container betrieben.

Der grundlegende Ablauf der Simulation ist:

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

Bei jedem täglichen Simulationslauf werden für alle Felder des virtuellen Betriebs mögliche landwirtschaftliche Maßnahmen bestimmt, bewertet und gegebenenfalls ausgeführt. Die resultierenden Ereignisse werden anschließend an DigiZert übertragen.

---

# 3. Bekannte Einschränkungen der aktuellen Implementierung

Die bestehende Implementierung weist mehrere technische Einschränkungen auf.

### Persistenzlücken

Der Zustand des IrrigationSimulators wird derzeit nicht gespeichert.  
Nach einem Neustart gehen interne Zustände der Bewässerungssimulation verloren.

---

### Retry Queue Verarbeitung

Fehlgeschlagene Event-Übertragungen werden aktuell nur beim Start des Systems erneut verarbeitet.  
Während des laufenden Betriebs erfolgt keine erneute Queue-Verarbeitung.

---

### Zwei parallele Entscheidungslogiken

Die Simulation verwendet derzeit zwei Entscheidungswege:

```
Planting / Protection → Candidate Pipeline → DecisionManager
Irrigation → separater Sonderpfad
```

Dadurch entsteht zusätzliche Komplexität in der Simulationslogik.

---

### Fehlende vollständige Event-Historie

Das aktuelle System speichert nur Integrations-Events für DigiZert, jedoch keine vollständige interne Ereignishistorie des virtuellen Betriebs.

---

### Weitere technische Einschränkungen

- MoistureDataService nutzt derzeit historische Daten eines festen Jahres
- ein Teil der simulierten Daten wird nicht an DigiZert übertragen
- Healthcheck-Konfiguration des Containers ist ungewöhnlich lang konfiguriert

---

# 4. Zielarchitektur

Die Weiterentwicklung von DigiSim orientiert sich an einer Architektur, in der fachliche Zustandsänderungen als Ereignisse modelliert werden.

Dabei gilt folgende Leitlinie:

```
Decision
→ Domain Event
→ State Update
→ optional Integration Event
```

Damit werden drei Ebenen klar getrennt:

- fachliche Entscheidungen innerhalb der Simulation
- interne Zustandsänderungen
- Kommunikation mit externen Systemen wie DigiZert

Diese Struktur erleichtert insbesondere:

- Nachvollziehbarkeit von Simulationsentscheidungen
- Debugging und Analyse
- reproduzierbare Simulationen
- spätere Szenario- und Replay-Simulationen.

---

# 5. Entwicklungsphasen

Die Weiterentwicklung von DigiSim wird in mehrere Entwicklungsphasen strukturiert.

Diese Phasen bilden die Grundlage für Milestones und Issue-Strukturen.

---

# Phase 1 — Stabilisierung des Simulationsbetriebs

Ziel dieser Phase ist ein robuster und stabil laufender Simulator.

### Features

**Persistenz des IrrigationSimulators**

Der Simulator verwaltet intern:

- moisture
- updated_moisture
- irrigation

Für eine korrekte Wiederherstellung müssen folgende Daten persistiert werden:

- updated_moisture
- irrigation.

---

**Continuous Retry Queue**

Die Event-Queue soll zusätzlich nach jedem Daily Tick verarbeitet werden.

```
Daily Tick
↓
Event Dispatch
↓
Retry Queue Processing
```

Damit werden fehlgeschlagene Events auch während des laufenden Betriebs erneut übertragen.

---

**MoistureDataService – dynamisches Jahr**

Der aktuell fest verdrahtete Wert

```
year = 2022
```

soll durch das aktuelle Simulationsjahr ersetzt werden.

---

**Docker Healthcheck Anpassung**

Die aktuelle Konfiguration führt dazu, dass fehlerhafte Container lange unentdeckt bleiben können.  
Die Parameter sollen entsprechend angepasst werden.

---

**Batch Feld im FieldOperationEvent**

Das Feld wird aktuell nicht verwendet und sollte entweder:

- implementiert oder
- aus dem Modell entfernt werden.

---

### Milestone

**MS1 — Stabiler Simulationsbetrieb**

---

# Phase 2 — Vereinheitlichung der Entscheidungslogik

Ziel dieser Phase ist eine einheitliche Pipeline für alle Operationstypen.

Aktuell existiert ein separater Entscheidungszweig für Bewässerung.

Zielstruktur:

```
Candidate Generation
↓
Decision Engine
↓
Execution
```

---

### Notwendige Änderungen

1. IrrigationSimulator erzeugt Candidate Operations
2. Sonderpfad im CalendarDrivenRunner entfällt
3. Prioritätslogik wird vollständig in den DecisionManager integriert.

---

### Milestone

**MS2 — Unified Decision Engine**

---

# Phase 3 — Einführung eines Domain Event Modells

Ziel dieser Phase ist eine bessere Nachvollziehbarkeit der Simulation.

Die Simulation soll zentrale fachliche Ereignisse explizit modellieren.

---

### Beispiel Domain Events

Core Events:

- DailyTickStarted
- DailyTickCompleted
- CropCycleStarted
- HarvestCompleted

Operation Events:

- OperationConsidered
- OperationApproved
- OperationRejected    
- OperationApplied.

---

### Event Struktur

Ein generisches Event enthält:

```
event_id
event_type
timestamp
field_id
payload
```

Damit können Ereignisse eindeutig identifiziert und analysiert werden.

---

### Milestone

**MS3 — Event Driven Simulation Core**

---

# Phase 4 — Erweiterungen der Simulation

Auf Basis der verbesserten Architektur können weitere Funktionen implementiert werden.

---

### Replay Simulation

Simulation vergangener Zeiträume zur Analyse oder Demonstration.

---

### Fast-Forward Simulation

Beschleunigte Simulation mehrerer Tage oder Saisons.

---

### Integration zusätzlicher Datenquellen

Beispielsweise:

- Wetterdaten
- Sensordaten
- Bodenparameter.

---

### Milestone

**MS4 — Erweiterte Simulationsplattform**

---

# 6. Architekturleitlinien für zukünftige Entwicklung

Für neue Erweiterungen gelten folgende Leitlinien.

### Domain Events

Fachliche Zustandsänderungen sollen über Domain Events modelliert werden.

Direkte Statusänderungen sollten vermieden werden.

Beispiel:

nicht bevorzugt:

```
field.status = "harvested"
```

bevorzugt:

```
event = HarvestCompleted(...)
apply(event)
publish(event)
```

---

### Trennung von Verantwortlichkeiten

Die Simulation trennt klar:

- Simulationslogik
- Entscheidungslogik
- Persistenz
- Integration mit DigiZert.

---

# 7. Nutzung des Dokuments für Projektplanung

Dieses Dokument dient als Grundlage für:

- Definition von Milestones
- Erstellung von Jira Issues
- Planung der Entwicklungsphasen
- Abstimmung zwischen Architektur und Entwicklung.

Die beschriebenen Entwicklungsphasen können direkt als **Milestones im Projektmanagement-System** abgebildet werden.

Innerhalb der Milestones werden die beschriebenen Features in einzelne Issues überführt.
