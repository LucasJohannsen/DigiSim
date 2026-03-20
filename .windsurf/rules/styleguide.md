---
trigger: model_decision
description: integration of new features should follow event-driven core principle
---
Handreichung für Entwickler: Event-Driven Core in DigiSim
Warum dieses Prinzip?
DigiSim entwickelt sich in Richtung einer nachvollziehbaren, erweiterbaren und analysierbaren Simulationsarchitektur.
Damit fachliche Logik, Zustandsänderungen und externe Integration nicht zu stark miteinander vermischt werden, sollen neue Features möglichst nach einem einfachen Event-Driven-Core-Prinzip umgesetzt werden.
Architekturregel
Wenn innerhalb der Simulation fachlich etwas Relevantes passiert, sollte dies zuerst als Domain Event formuliert werden.
Nicht ideal:
field.crop_status = "harvested"
dispatcher.dispatch(FieldOperationEvent(...))
Bevorzugt:
event = HarvestCompleted(field_id=field.id, date=today)
apply(event)
integration_event = map_to_integration_event(event)
dispatcher.dispatch(integration_event)
Faustregel
Bei neuer Logik immer kurz fragen:
Was ist fachlich passiert?
Kann ich dieses Ereignis benennen?
Kann der Zustand aus diesem Ereignis aktualisiert werden?
Kann die externe Payload daraus abgeleitet werden?
Wenn diese Fragen mit Ja beantwortet werden können, sollte die Logik eventbasiert umgesetzt werden.
Zielbild
Neue Logik soll möglichst diesem Muster folgen:
Command
→ Decision
→ Domain Event
→ apply(event)
→ optional Integration / Logging / Persistenz
Was nicht gemeint ist
Dieses Prinzip bedeutet nicht, dass DigiSim sofort vollständig eventgesourct werden muss.
Snapshots und bestehende Persistenzmechanismen bleiben weiterhin gültig.
Ziel ist zunächst nur:
bessere Nachvollziehbarkeit
geringere Kopplung
sauberere Erweiterbarkeit
Besonders relevant für neue Features
Dieses Prinzip ist besonders wichtig bei:
neuen Operationstypen
Bewässerungslogik
neuen Entscheidungsregeln
Replay- und Fast-Forward-Funktionen
zusätzlicher Beobachtbarkeit oder Audit-Historie

Technische Hinweise
Event Bus via Constructor Injection übergeben (nie global)
Event Bus Checks: if self.event_bus is not None (nicht if self.event_bus)
Domain Events (intern) ≠ Integration Events (extern an DigiZert)
Event Bus ist optional für Abwärtskompatibilität
