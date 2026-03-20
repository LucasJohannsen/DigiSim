---
# Konzeptpapier DigiSim 2.0
_Stand: 10.03.2026_

## Gliederung
1. Zielbild 
2. Systemkonzept
3. Domänenmodell
4. Simulationsmechanik
5. Systemarchitektur
6. Weiterentwicklung
---


# 1. Zielbild – DigiSim 2.0

## DigiSim 2.0 als virtueller Referenzbetrieb für DigiZert

DigiSim 2.0 ist ein **regelbasierter virtueller landwirtschaftlicher Betrieb**, der kontinuierlich realistische Agrardaten erzeugt und automatisiert an DigiZert übermittelt.

Der Simulator bildet typische landwirtschaftliche Prozesse wie Anbauplanung, Bewirtschaftungsmaßnahmen und saisonale Abläufe auf Basis agronomischer Regeln nach. Dadurch entstehen **plausible Zeitreihen von Maßnahmen und Betriebsereignissen**, die den Datenfluss eines realen Betriebs abbilden.

Das System läuft als **dauerhafte Serveranwendung** im Docker-Container und erzeugt täglich neue Ereignisse im virtuellen Betrieb. Diese werden automatisch an DigiZert übermittelt und stehen dort für Entwicklung, Tests, Demonstrationen und Forschung zur Verfügung.

DigiSim fungiert damit als **virtueller Referenzbetrieb**, der DigiZert kontinuierlich mit konsistenten Echtzeitdaten versorgt.

## Hauptfunktionen

DigiSim 2.0 erfüllt vier zentrale Aufgaben:

### Entwicklungsumgebung
DigiZert kann gegen realistisch wirkende Live-Daten getestet werden.

### Demo- und Präsentationssystem
Ein virtueller Betrieb erzeugt kontinuierlich neue Maßnahmen, Ereignisse und Zertifikate.

### Szenario-Plattform
Unterschiedliche Bewirtschaftungsstrategien und Parameter können getestet werden.

### Datengenerator
Es entstehen vollständige und konsistente Datensätze ohne Abhängigkeit von realen Betriebsdaten.

## Zentrale Systemeigenschaften
**Persistenz**  
Der Betrieb besitzt einen internen Zustand, der sich über die Zeit fortschreibt.

**Regelbasiert**  
Maßnahmen entstehen aus agronomischen Regeln und definierten Betriebsabläufen.

**Stochastische Variabilität**  
Natürliche Variationen, etwa Wetter oder zeitliche Streuung von Maßnahmen, können berücksichtigt werden.

**Erweiterbarkeit**  
Neue Maßnahmen, Kulturen und Regeln können modular ergänzt werden.

## Abgrenzung

DigiSim 2.0 simuliert primär:
- landwirtschaftliche **Maßnahmen**
- betriebliche **Ereignisse**
- grundlegende **Systemzustände**

Die detaillierte Simulation biologischer oder physikalischer Prozesse, etwa Pflanzenwachstum oder Bodenprozesse, ist **nicht primäres Ziel dieser Version**, kann aber später ergänzt werden.

---

# 2. Systemkonzept

## 2.1 Grundprinzip der Simulation

DigiSim 2.0 modelliert einen **virtuellen landwirtschaftlichen Betrieb**, dessen Zustand sich kontinuierlich über die Zeit entwickelt. Anders als klassische Simulationssysteme arbeitet DigiSim nicht mit beschleunigten Simulationsläufen, sondern folgt dem **realen Kalender**.

Ein Simulationsschritt entspricht **einem realen Kalendertag**. Zu einem definierten Zeitpunkt, standardmäßig **06:00 Uhr**, wird täglich ein Simulationslauf gestartet. Dabei wird geprüft, welche Maßnahmen oder Ereignisse an diesem Tag im virtuellen Betrieb stattfinden.

Die Simulation basiert auf:

- agronomischen Regeln
- vordefinierten Betriebsplänen
- konfigurierbaren Entscheidungslogiken

Als Ergebnis entstehen **Betriebsereignisse und Maßnahmen**, die anschließend an DigiZert übermittelt werden.

## 2.2 Architekturübersicht

DigiSim ist als **dauerhafte Serveranwendung** konzipiert und kann als Docker-Container betrieben werden. Die Architektur folgt einem einfachen, wiederkehrenden Ablauf:

Daemon-Prozess  
      │  
Scheduler (APScheduler)  
      │  
Daily Tick  
      │  
Simulation Engine  
      │  
Event Dispatcher  
      │  
DigiZert API

Die Anwendung läuft kontinuierlich im Hintergrund und erzeugt täglich neue Ereignisse für den virtuellen Betrieb.

## 2.3 Simulationszyklus (Daily Tick)

Der zentrale Mechanismus von DigiSim ist der **Daily Tick**, ausgelöst durch einen Cron-Trigger des Schedulers.

Der Ablauf eines Daily Tick ist:

1. Bestimmung des aktuellen Simulationsdatums
2. Iteration über alle Felder des virtuellen Betriebs
3. Bestimmung möglicher Maßnahmen je Feld
4. Bewertung dieser Maßnahmen durch die Entscheidungslogik
5. Auswahl der tatsächlich auszuführenden Maßnahmen
6. Generierung der entsprechenden Ereignisse
7. Übermittlung der Ereignisse an DigiZert
8. Persistenz des aktualisierten Betriebszustands

Die Felder werden parallel verarbeitet, damit auch größere Betriebsstrukturen effizient simuliert werden können.

## 2.4 Konfiguration des virtuellen Betriebs

Der virtuelle Betrieb wird über **Konfigurationsdaten** beschrieben. Dazu gehören unter anderem:

- Betriebsstruktur
- Felder und Flächengrößen
- angebaute Kulturen
- Fruchtfolgen
- mögliche Bewirtschaftungsmaßnahmen
- Entscheidungsregeln für Maßnahmen

Diese Trennung von **Konfiguration und Simulationslogik** ermöglicht eine flexible Anpassung und Erweiterung des virtuellen Betriebs.

## 2.5 Persistenz und Betriebszustand

Der virtuelle Betrieb besitzt einen **persistenten Zustand**, der über die Zeit fortgeschrieben wird. Dazu gehören beispielsweise:

- bereits ausgeführte Maßnahmen
- aktuelle Kulturstadien
- vergangene Betriebsereignisse
- Simulationshistorie

Der Zustand wird aktuell über einen **StateManager** in JSON-basierten Snapshots gespeichert. So kann DigiSim nach einem Neustart den Betrieb ohne Verlust des bisherigen Simulationsverlaufs fortführen.

## 2.6 Integration mit DigiZert

Nach jedem Simulationslauf werden die erzeugten Ereignisse über eine API an DigiZert übermittelt:

Simulation  
     ↓  
Event-Generierung  
     ↓  
RetryDispatcher  
     ↓  
DigiZert API

Der Dispatcher stellt sicher, dass fehlgeschlagene Übertragungen erneut versucht werden und keine Ereignisse verloren gehen.

## 2.7 Beobachtbarkeit und Logging

Da DigiSim als dauerhaft laufendes System betrieben wird, ist eine ausreichende Beobachtbarkeit notwendig. Das System erzeugt daher:

- Systemlogs
- Simulationslogs
- Ereignishistorien
- Statusinformationen zum virtuellen Betrieb

Diese Informationen unterstützen:

- Debugging
- Nachvollziehbarkeit von Entscheidungen
- Analyse von Betriebsabläufen
- Systemmonitoring

## 2.8 Betriebsmodi

Der aktuelle Produktionsmodus ist der **Live-Modus**, bei dem täglich ein Simulationsschritt ausgeführt wird. Perspektivisch sind weitere Modi vorgesehen:

**Replay-Modus**  
Simulation vergangener Zeiträume zur Analyse oder Demonstration.

**Fast-Forward-Modus**  
Beschleunigte Simulation mehrerer Tage oder ganzer Anbausaisons.

---

# 3. Domänenmodell

## 3.1 Zielsetzung des Betriebsmodells

Das Betriebsmodell beschreibt die fachliche Struktur des virtuellen landwirtschaftlichen Betriebs und definiert die zentralen Entitäten sowie deren Beziehungen.

Es bildet insbesondere ab:

- Betriebsstruktur
- Felder
- Kulturzyklen
- landwirtschaftliche Maßnahmen
- Entscheidungslogik
- daraus entstehende Ereignisse

Das Modell bildet die Grundlage für Simulationslogik und Weiterentwicklung.

## 3.2 Grundstruktur des virtuellen Betriebs

Farm  
 ├ Field  
 │   ├ CropCycle  
 │   ├ OperationPlan  
 │   └ OperationEvents

### Farm

Die **Farm** repräsentiert den gesamten virtuellen Betrieb und bildet den Rahmen für alle Felder, Kulturen und Regeln.  
Auf Implementierungsebene entspricht sie aktuell einer Sammlung von **Simulationskontexten (`SimContext`)**.

### Field

Ein **Field** repräsentiert eine landwirtschaftliche Fläche innerhalb des Betriebs. Die meisten operativen Entscheidungen werden auf Feldebene getroffen.  
Im aktuellen System wird jedes Feld durch eine Instanz des **CalendarDrivenRunner** repräsentiert.

### CropCycle

Der **CropCycle** beschreibt die saisonale Nutzung eines Feldes, einschließlich:

- Bodenvorbereitung
- Aussaat oder Pflanzung
- Pflege- und Schutzmaßnahmen
- Bewässerung
- Ernte


Im aktuellen Code wird der Kulturzyklus durch `PlantingPlan` und `FieldOperationCycle` modelliert.

### Operation

Eine **Operation** ist eine mögliche landwirtschaftliche Maßnahme, etwa:

- Bodenbearbeitung
- Aussaat
- Düngung
- Pflanzenschutz
- Bewässerung
- Ernte

Im aktuellen System wird sie durch **FieldOperation** repräsentiert. Dieses Objekt enthält unter anderem:

- `worktype`
- geplantes Datum (`planned_date`)
- tatsächliches Ausführungsdatum (`actual_date`)

## 3.3 Entscheidungslogik

Die Simulation entscheidet täglich, welche Maßnahmen tatsächlich ausgeführt werden. Der Prozess folgt drei Schritten:

Command → Decision → Execution

### Command

Der tägliche Tick löst die Simulation aus. Für jedes Feld wird geprüft, welche Maßnahmen grundsätzlich möglich sind.

### Decision

Die möglichen Maßnahmen werden durch den **DecisionManager** bewertet. Dabei fließen unter anderem ein:

- Prioritäten von Maßnahmen    
- Regeln des Betriebsplans
- mögliche Filterkriterien

### Execution

Die ausgewählten Maßnahmen werden ausgeführt und anschließend als Ereignisse erzeugt, die an DigiZert übertragen werden.

## 3.4 Aktuelles Ereignismodell (Ist-Zustand)

Im aktuellen System existiert bereits das Objekt:

FieldOperationEvent

Es wird erzeugt, wenn eine Maßnahme ausgeführt wurde, und dient als **Integrationsobjekt für die DigiZert-API**. Es enthält unter anderem:

- Feld-ID
- Maßnahmentyp (`worktype`)
- bearbeitete Fläche
- Kraftstoffverbrauch
- zurückgelegte Distanz

Das aktuelle System speichert damit **nicht alle fachlichen Ereignisse des Betriebs**, sondern primär jene, die an DigiZert übertragen werden.

## 3.5 Zielbild: Event-basierte Modellierung

Für die Weiterentwicklung von DigiSim wird eine **eventbasierte Modellierung** angestrebt. Relevante Veränderungen im Betrieb werden dabei als Ereignisse modelliert, zum Beispiel:

- eine Maßnahme wurde geprüft
- eine Maßnahme wurde ausgeführt
- eine Saison hat begonnen
- ein Feld wurde geerntet

Der aktuelle Zustand eines Feldes lässt sich dann aus der Historie dieser Ereignisse ableiten.

Das ermöglicht:

- bessere Nachvollziehbarkeit
- reproduzierbare Simulationsverläufe
- verbesserte Analyse- und Debugging-Funktionen    
- flexiblere Erweiterung der Simulationslogik

## 3.6 Ereignisebenen in DigiSim

### Domain Events

Domain Events beschreiben fachliche Ereignisse innerhalb des virtuellen Betriebs, z. B.:

- `DailyTickStarted`
- `DailyTickCompleted`
- `OperationConsidered`
- `OperationApproved`
- `OperationRejected`
- `HarvestCompleted`
- `CropCycleStarted`

### State Projections

State Projections sind abgeleitete Zustände, die aus Domain Events berechnet werden, z. B.:

- aktueller Kulturstatus eines Feldes
- letzte Maßnahme
- aktuelle Saisonphase
- Status der Simulation

### Integration Events

Integration Events beschreiben die Kommunikation mit externen Systemen. In DigiSim ist dies vor allem die Kommunikation mit DigiZert. Das Objekt **FieldOperationEvent** gehört zu dieser Kategorie.

## 3.7 Initiales Event-Modell

Ein erstes Set möglicher Domain Events umfasst:

### Core Events

- `DailyTickStarted`
- `DailyTickCompleted`
- `CropCycleStarted`
- `HarvestCompleted`
- `SeasonReset`

### Operation Events

- `OperationConsidered`
- `OperationApproved`
- `OperationRejected`
- `SoilPreparationApplied`
- `PlantingApplied`
- `PesticideApplied`
- `IrrigationApplied`
- `HarvestingApplied`

### Integration Events

- `EventDispatchedToDigiZert`
- `EventDispatchFailed`
- `EventQueued`
- `EventDispatchRetried`

Teile dieser Logik existieren bereits in der aktuellen Implementierung, werden bislang aber überwiegend über Logging abgebildet.

## 3.8 Persistenz des Betriebszustands

Der aktuelle Zustand des virtuellen Betriebs wird durch den **StateManager** in JSON-basierten Snapshots gespeichert. Diese enthalten beispielsweise:

- letzten Simulationszeitpunkt
- Zustand einzelner Felder
- ausgeführte Maßnahmen

Die Snapshots erlauben einen Neustart ohne vollständige Neuberechnung.

## 3.9 Weiterentwicklung zum Event-Modell

Ein möglicher erster Schritt ist die Einführung eines generischen Event-Typs, etwa:

SimEvent

Dieser könnte enthalten:

- Eventtyp
- Zeitstempel
- Feld-ID
- optionale Payload

Darauf aufbauend ließe sich ein Event-Log etablieren, das den vollständigen Verlauf des virtuellen Betriebs dokumentiert. Bestehende Integrationsobjekte für DigiZert blieben erhalten und würden aus Domain Events abgeleitet.

---

# 4. Simulationsmechanik

## 4.1 Ziel der Simulationslogik

Die Simulationslogik beschreibt, wie DigiSim täglich entscheidet, welche landwirtschaftlichen Maßnahmen im virtuellen Betrieb stattfinden.

Die Simulation folgt einem **kalenderbasierten Ansatz**, bei dem ein Simulationsschritt genau einem realen Kalendertag entspricht. Das aktuelle Simulationsdatum wird direkt aus dem Systemdatum bestimmt:

today = datetime.date.today()

Eine Simulation von Zeiträumen in Vergangenheit oder Zukunft ist im aktuellen Stand nicht vorgesehen.

Während eines täglichen Simulationslaufs wird für jedes Feld geprüft:

- welche Maßnahmen grundsätzlich möglich sind
- welche Maßnahmen priorisiert werden
- welche Maßnahmen tatsächlich ausgeführt werden

Das Ergebnis sind **Operation Events**, die anschließend an DigiZert übermittelt werden.

## 4.2 Überblick über den Simulationsablauf

Daily Tick  
    ↓  
Candidate Generation  
    ↓  
Decision Logic  
    ↓  
Operation Execution + Event Creation  
    ↓  
Event Dispatch  
    ↓  
State Persistence

Im aktuellen System sind **Operation Execution und Event Creation nicht getrennt**, sondern innerhalb derselben Funktion gekoppelt.

## 4.3 Daily Tick

Der tägliche Simulationslauf wird durch den Scheduler mit einem **CronTrigger** ausgelöst. Standardmäßig startet der Daily Tick um **06:00 Uhr**.

Währenddessen erfolgen:

1. Bestimmung des aktuellen Datums (`today`)
2. Iteration über alle Felder
3. Ausführung der Feldsimulation
4. Sammlung der erzeugten Events
5. Dispatch an DigiZert
6. Persistenz des Zustands

Die Feldsimulation erfolgt über `CalendarDrivenRunner.tick()`.

### Persistenzlücke: Irrigation-State

Der aktuelle Persistenzmechanismus speichert:

- Planting Operations
- Protection Operations
- Kontextinformationen

Der Zustand des **IrrigationSimulator** wird jedoch nicht persistiert. Dadurch gehen nach einem Neustart verloren:

- bisherige Bewässerungstage
- interne Feuchtigkeitszustände
- Verlauf der Bewässerungssimulation

## 4.4 Candidate Generation

Der erste Schritt der Feldsimulation ist die Bestimmung möglicher Maßnahmen. Diese basieren auf:

- `PlantingPlan`
- aktuellem Kulturzyklus
- bereits ausgeführten Operationen

Das Ergebnis ist eine Liste möglicher Maßnahmen:

List[FieldOperation]

### Sonderpfad: Bewässerung

Bewässerung folgt aktuell **nicht derselben Kandidatenpipeline** wie Planting- und Protection-Operationen.

Candidate Operations  
    ↓  
DecisionManager  
    ↓  
Selected Operations  
    ↓  
Irrigation Check  
    ↓  
_handle_irrigation()

Bewässerung wird nur ausgeführt, wenn **keine höher priorisierte Operation** vorliegt. Damit existieren im aktuellen System zwei parallele Entscheidungslogiken:

1. Kandidatenpipeline für reguläre Operationen
2. separater Entscheidungszweig für Bewässerung

## 4.5 Entscheidungslogik

Die Entscheidungslogik wird vom **DecisionManager** umgesetzt. Aktuell ist sie bewusst einfach gehalten und verwendet die Strategie:

WorkTypePriorityStrategy

Die Worktypes `14` und `15` gelten dabei als **niedrige Priorität** und werden nur ausgewählt, wenn keine höher priorisierten Operationen vorhanden sind.

Derzeit berücksichtigt die Logik **keine weiteren Faktoren**, insbesondere nicht:

- Wetterbedingungen
- Bodenbedingungen
- probabilistische Modelle
- konfigurierbare Regelwerke

## 4.6 Ausführung von Maßnahmen

Die Ausführung erfolgt innerhalb der Service-Komponenten. Dabei werden gleichzeitig:

1. der Operationszustand mutiert
2. ein Integrations-Event erzeugt

Beispiel:

operation.actual_date = date  
event = FieldOperationEvent(...)

Ausführung und Event-Erzeugung sind also aktuell **eng gekoppelt**.

## 4.7 Ereigniserzeugung

Nach der Ausführung einer Operation wird ein `FieldOperationEvent` erzeugt. Dieses enthält unter anderem:

- Feld-ID
- Maßnahmentyp (`worktype`)
- bearbeitete Fläche
- Kraftstoffverbrauch
- Distanz
- Applikationsparameter

Es dient als **Integrationsobjekt für DigiZert**.

### Unterschied zwischen Eventmodell und API-Payload

Das `FieldOperationEvent` enthält mehr Felder als tatsächlich an DigiZert übertragen werden. Der `DigiZertClient` nutzt aktuell nur:

field  
worktype  
start_date  
end_date  
area  
fuel  
worktype_text

Weitere simulierte Felder werden derzeit nicht übertragen, darunter:

- `distance`
- `application_amount`
- `application_type`
- `application_category`
- `machine`
- `duration`

### Unverwendetes Feld

Das Feld `batch` im `FieldOperationEvent` wird derzeit weder befüllt noch verwendet.

## 4.8 Parallelisierung der Feldsimulation

Die Simulation der Felder erfolgt parallel über asynchrone Verarbeitung mit begrenzter Parallelität:

asyncio.Semaphore(max_concurrent_fields)  
asyncio.gather()

Dieses Modell ermöglicht eine effiziente Verarbeitung auch bei größeren Betriebsstrukturen.

## 4.9 Integration mit DigiZert

Nach der Simulation werden die erzeugten Events über einen **RetryDispatcher** an DigiZert übertragen:

Simulation  
    ↓  
FieldOperationEvent  
    ↓  
RetryDispatcher  
    ↓  
DigiZert API

Der RetryDispatcher speichert fehlgeschlagene Übertragungen in einer Queue.

### Einschränkung der aktuellen Queue-Verarbeitung

Die Queue wird derzeit **nur beim Start des Daemons** verarbeitet:

dispatcher.process_queue()

Fehlgeschlagene Events während des laufenden Betriebs werden daher erst beim **nächsten Neustart** erneut übertragen.

## 4.10 Persistenz des Simulationszustands

Nach Abschluss eines Daily Tick wird der Simulationszustand über den **StateManager** gespeichert. Der Snapshot enthält unter anderem:

- Feld-ID
- letzter Simulationszeitpunkt
- Kontextinformationen
- Planting Operations
- Protection Operations

Nicht gespeichert werden derzeit:

- Zustand des IrrigationSimulators
- Event-Historie
- Dispatch-Historie
- vollständiger Event-Log

Der Snapshot dient damit primär der **Fortsetzung der Simulation**, nicht der vollständigen Rekonstruktion.

## 4.11 Erweiterungsmöglichkeiten

### Erweiterte Entscheidungsmodelle

Perspektivisch können zusätzliche Entscheidungsfaktoren integriert werden, etwa:

- Wetterbedingungen
- Bodenparameter
- probabilistische Modelle

Erste Vorstufen existieren bereits, z. B. historische Feuchtigkeitsdaten (`MoistureDataService`) oder zufällige Variationen beim Kraftstoffverbrauch.

### Vereinheitlichung der Entscheidungslogik

Langfristig könnten alle Operationstypen in eine gemeinsame Kandidatenpipeline integriert werden, einschließlich Bewässerung.

### Einführung eines Event-Modells

Ein internes Domain-Event-Modell würde insbesondere Entscheidungsprozesse, abgelehnte Operationen, saisonale Zustandswechsel und die vollständige Event-Historie dokumentieren.

---

# 5. Systemarchitektur

## 5.1 Architekturüberblick

DigiSim ist als **dauerhaft laufende Serveranwendung** konzipiert, die einen virtuellen landwirtschaftlichen Betrieb kontinuierlich fortschreibt.

Die Anwendung wird typischerweise als **Docker-Container** betrieben und läuft als Hintergrundprozess. Die Container-Konfiguration sorgt für automatischen Neustart:

restart: unless-stopped

Der Einstiegspunkt des Containers ist der Daemon-Prozess:

ENTRYPOINT ["python", "daemon.py"]

Der zentrale Datenfluss ist:

Daemon  
   ↓  
TickScheduler  
   ↓  
CalendarDrivenRunner  
   ↓  
Service-Komponenten  
   ↓  
Event Dispatch  
   ↓  
State Persistence

Diese Struktur trennt Zeitsteuerung, Simulationslogik, Integrationslogik und Persistenz.

## 5.2 Daemon-Prozess

Der **Daemon-Prozess** (`daemon.py`) übernimmt:

- Initialisierung der Simulationskontexte (`SimContext`)
- Initialisierung des RetryDispatchers
- Verarbeitung der Event-Queue
- Initialisierung und Start des Schedulers
- Registrierung von Signal-Handlern (`SIGTERM`, `SIGINT`)

Die tatsächliche Startreihenfolge ist:

RetryDispatcher initialisieren  
↓  
Queue verarbeiten (dispatcher.process_queue())  
↓  
TickScheduler initialisieren  
↓  
Scheduler starten

Dadurch werden ausstehende DigiZert-Events **vor dem nächsten Simulationslauf** verarbeitet.

## 5.3 TickScheduler

Der **TickScheduler** steuert die zeitliche Ausführung der Simulation. Er verwendet **APScheduler** mit einem `CronTrigger`, um den täglichen Simulationslauf auszulösen.

Der Standardwert ist:

06:00 Uhr

Dieser Wert ist jedoch **konfigurierbar** und wird aus Konfiguration bzw. `.env` geladen.

## 5.4 CalendarDrivenRunner

Der **CalendarDrivenRunner** ist die zentrale Komponente für die Simulation eines einzelnen Feldes. Für jedes Feld existiert eine eigene Runner-Instanz.

Er übernimmt:

- Durchführung der täglichen Feldsimulation (`tick()`)
- Koordination der Service-Komponenten
- Generierung von Operation Events
- Verwaltung des Feldzustands

### Lazy Initialization der Services

Nicht alle Services werden beim Start initialisiert. Bestimmte Services werden **lazy** erzeugt, sobald eine bestimmte Kulturphase erreicht wird, insbesondere:

- `ProtectionPlanService`
- `IrrigationSimulator`

Die Initialisierung erfolgt erst in der Phase **CROP_MANAGEMENT**. Der `PlantingPlanService` wird dagegen bereits beim Start erzeugt.

## 5.5 Service-Komponenten

### PlantingPlanService

Verantwortlich für:

- Planung und Ausführung von Pflanzoperationen
- Fortschritt im Kulturzyklus
- Generierung entsprechender Operation Events

### ProtectionPlanService

Verantwortlich für:

- Pflanzenschutzmaßnahmen
- Planung von Spritzoperationen
- Integration in den Kulturzyklus

### IrrigationSimulator

Verantwortlich für:

- Simulation der Bewässerung
- Berechnung von Bodenfeuchtigkeitszuständen
- Entscheidung über Bewässerungsmaßnahmen

Der IrrigationSimulator wird aktuell **nicht über den DecisionManager**, sondern über einen separaten Entscheidungszweig im `CalendarDrivenRunner` gesteuert.

### MoistureDataService

Der MoistureDataService liefert Feuchtigkeitsdaten für den IrrigationSimulator. Aktuell basiert er auf **historischen Feuchtigkeitsdaten aus dem Jahr 2022**. Eine Integration aktueller Wetter- oder Bodendatenquellen existiert nicht.

### EventLogger

Jeder `CalendarDrivenRunner` besitzt eine eigene **EventLogger-Instanz**, die erzeugte Events unabhängig vom Dispatch protokolliert und der internen Nachvollziehbarkeit dient.

## 5.6 DecisionManager

Der **DecisionManager** bestimmt, welche Operationen aus der Kandidatenliste tatsächlich ausgeführt werden. Aktuell verwendet er:

WorkTypePriorityStrategy

Die Worktypes `14` (Pflanzenschutz) und `15` (Bewässerung) gelten dabei als **niedrige Priorität**. Diese Operationen werden nur gewählt, wenn keine höher priorisierten Operationen vorliegen.

Die Regeln sind derzeit **hardcodiert** und nicht konfigurierbar. Zudem steuert der DecisionManager **nicht alle Operationstypen**, da Bewässerung in einem separaten Pfad behandelt wird.

## 5.7 Event Dispatch

Die erzeugten `FieldOperationEvent`-Objekte werden über den **RetryDispatcher** an DigiZert übertragen.

Der Dispatcher übernimmt:

- direkte Übertragung von Events
- Speicherung fehlgeschlagener Events in einer Queue
- erneute Verarbeitung der Queue beim Systemstart

### Payload-Transformation

Das `FieldOperationEvent` enthält mehr Felder als tatsächlich an DigiZert übertragen werden. Die reduzierte API-Payload umfasst:

field  
worktype  
start_date  
end_date  
area  
fuel  
worktype_text

Nicht übertragen werden aktuell u. a.:

- `distance`
- `duration`
- `machine`
- `application_amount`
- `application_name`

## 5.8 Parallelisierung der Feldsimulation

Die Simulation mehrerer Felder erfolgt parallel über:

asyncio.Semaphore(max_concurrent_fields)  
asyncio.gather()

So bleibt die Verarbeitung auch bei größeren virtuellen Betrieben effizient.

## 5.9 Persistenz des Systemzustands

Der aktuelle Zustand der Simulation wird über den **StateManager** in Form von **JSON-basierten Snapshots**gespeichert.

Die Snapshots enthalten:

- Kontextinformationen
- Planting Operations
- Protection Operations
- letzten Simulationszeitpunkt

Sie dienen dazu, die Simulation nach einem Neustart fortzusetzen.

## 5.10 Bekannte architektonische Einschränkungen

### Unvollständige Persistenz

Der Zustand des **IrrigationSimulators** wird nicht gespeichert und geht nach einem Neustart verloren.

### Fehlende vollständige Event-Historie

Es existiert derzeit kein vollständiger Event-Log des Simulationsverlaufs.

### Queue-Verarbeitung nur beim Start

Fehlgeschlagene Events während des laufenden Betriebs werden erst beim nächsten Neustart erneut verarbeitet.

### Payload-Truncation bei DigiZert-Integration

Ein Teil der simulierten Daten wird nicht an DigiZert übertragen.

### Historische Feuchtigkeitsdaten

Der `MoistureDataService` verwendet derzeit Feuchtigkeitsdaten aus dem Jahr **2022**.

### Healthcheck-Konfiguration

Der Docker-Healthcheck ist aktuell ungewöhnlich konfiguriert:

interval: 60m  
start_period: 70m

Der erste Healthcheck erfolgt damit erst nach mehr als einer Stunde Laufzeit.

---

# 6. Weiterentwicklung

Die Weiterentwicklung von DigiSim lässt sich in drei Kategorien gliedern:

1. **Kurzfristige Stabilisierung**
2. **Architektonische Weiterentwicklung**
3. **Funktionale Erweiterungen**

Damit werden operative Verbesserungen, strukturelle Architekturthemen und neue Funktionen sauber getrennt.

## 6.1 Kurzfristige Stabilisierung

### Irrigation-Persistenz

Der Zustand des `IrrigationSimulator` wird aktuell nicht gespeichert. Intern verwaltet der Simulator:

- `moisture` – Basisfeuchtigkeitsdaten
- `updated_moisture` – Feuchtigkeit nach Bewässerung
- `irrigation` – Bewässerungshistorie pro Tag

Da die Basisdaten jederzeit über den `MoistureDataService` neu geladen werden können, müssen für eine korrekte Wiederherstellung nur folgende Daten persistiert werden:

- `updated_moisture`
- `irrigation`

Diese sollten im `StateManager` serialisiert und beim Start wiederhergestellt werden.

### Continuous Retry Queue

Der `RetryDispatcher` verarbeitet fehlgeschlagene Events derzeit nur beim Start des Daemons. Eine einfache Verbesserung wäre, die Queue-Verarbeitung zusätzlich am Ende jedes `daily_tick()` auszuführen:

Daily Tick  
    ↓  
Event Dispatch  
    ↓  
Retry Queue Processing

Der interne `tenacity`-Retrymechanismus bleibt dabei unverändert.

### Payload-Konsistenz DigiZert

Das Objekt `FieldOperationEvent` enthält deutlich mehr Informationen als derzeit an DigiZert übertragen werden. Die bevorzugte Lösung ist **Option A: Erweiterung der API-Payload**, sofern das DigiZert-API diese Felder unterstützt. Vor einer Umsetzung sollte daher das DigiZert-API-Schema geprüft werden.

### Batch-Feld im FieldOperationEvent

Das Feld `batch` wird aktuell nie gesetzt und bleibt stets `None`. Falls DigiZert Batch-Informationen erwartet, kann das zu stillen Datenfehlern führen. Das Feld sollte daher entweder:

- implementiert oder
- aus dem Modell entfernt

werden.

### MoistureDataService – dynamische Jahresauswahl

Der `MoistureDataService` verwendet derzeit ein fest verdrahtetes Jahr:

year = 2022

Kurzfristig sollte das Jahr dynamisch aus dem aktuellen Simulationsdatum abgeleitet werden:

year = current_date.year

### Docker Healthcheck-Konfiguration

Die aktuelle Konfiguration:

interval: 60m  
start_period: 70m

führt dazu, dass fehlerhafte Container lange unentdeckt bleiben können. Eine Anpassung der Parameter wird empfohlen.

## 6.2 Architektonische Weiterentwicklung

### Unified Candidate Pipeline

Der aktuelle Simulationsablauf nutzt zwei Entscheidungswege:

Planting/Protection → Candidate Pipeline → DecisionManager  
Irrigation → Sonderpfad im CalendarDrivenRunner

Ziel ist eine gemeinsame Pipeline:

Candidate Generation  
       ↓  
Decision Engine  
       ↓  
Execution

Dafür sind erforderlich:

1. `IrrigationSimulator` muss Kandidatenoperationen erzeugen können
2. die Prioritätslogik (`has_high_prio`) wird in den `DecisionManager` integriert
3. `_handle_irrigation()` als Sonderpfad entfällt

### Konfigurierbare Entscheidungsregeln

Der `DecisionManager` nutzt aktuell hardcodierte Regeln. Künftig sollten Entscheidungsregeln extern definierbar sein, z. B. über Konfigurationsdateien. Neben Prioritäten sollten auch Bedingungen unterstützt werden, etwa:

- Bodenfeuchtigkeit unter Schwellwert
- Kulturphase
- Wetterbedingungen

### Event-Modell und Event-Log

Kapitel 3 beschreibt ein mögliches Event-Modell für DigiSim. Bereits heute besitzt jeder `CalendarDrivenRunner` einen `EventLogger`, der erzeugte `FieldOperationEvent`-Objekte protokolliert. Diese Infrastruktur könnte zu einem vollständigen Event-Log ausgebaut werden, das zusätzlich interne Ereignisse wie Simulations-Ticks, Entscheidungsprozesse und abgelehnte Operationen speichert.

## 6.3 Funktionale Erweiterungen

### Wetterintegration

Der aktuelle `MoistureDataService` nutzt historische Feuchtigkeitsdaten. Perspektivisch sind möglich:

- dynamische historische Wetterreihen
- Integration externer Wetter-APIs
- Integration von Sensordaten

Die bestehende Datenabstraktion erleichtert den Austausch des Backends.

### Bodenmodell

Der `SimContext` enthält bereits das Feld `soil_type`, das aktuell nicht genutzt wird. Ein Bodenmodell könnte Einfluss haben auf:

- Bewässerungsbedarf
- Pflanzenschutzstrategien
- Nährstoffmanagement

### Szenariosimulation

DigiSim läuft derzeit ausschließlich im **Live-Modus**. Perspektivisch sind möglich:

- Replay-Simulation vergangener Zeiträume
- beschleunigte Simulation mehrerer Tage (Fast-Forward)
- alternative Bewirtschaftungsszenarien

Diese Funktionen setzen jedoch eine vollständige **Event-Historie** voraus und hängen daher direkt von der Einführung eines Event-Logs ab.