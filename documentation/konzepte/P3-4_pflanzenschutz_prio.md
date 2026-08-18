# P3-4 — Pflanzenschutz-Priorität mit Fälligkeitskonzept (Befund B9)

## Problem

Die Prioritätslogik unterdrückt pauschal alle Low-Prio-Operationen (Spritzen, Beregnen), wenn High-Prio-Operationen existieren. Überfällige Spritzungen werden am nächsten freien Tag gesammelt nachgeholt – bei Fungizid-Spritzfolgen (7–10 Tage) gefährdet dies die Wirksamkeit. Es gibt kein Fälligkeits-/Nachholkonzept für terminkritische Maßnahmen.

Verletzte Regel: KAR-021 (hart: Fungizidabstände ≥ 3 Tage, üblich 5–14 Tage – wird durch Stauung verletzt).

## Zielverhalten

Terminkritische Pflanzenschutz-Maßnahmen (insbesondere Fungizide) werden nicht pauschal unterdrückt, sondern erhalten ein Fälligkeitsfenster. Überschreitung des Fensters führt zu Prioritätserhöhung oder Nachhol-Logik. Die `DeadlineAwarePriorityStrategy` wird zur **Standard-Strategie** (kein optionaler Schalter). Fälligkeitsfenster und `is_critical`-Markierung kommen aus der Konfiguration (`config/planting_plan_potato.json`).

**Hinweis:** Die ISIP-Datenbank-Anbindung für echte Fungizid-Spritztermine ist in **P3-8** (nächste Stufe) ausgelagert. P3-4 liefert das Fälligkeits-Framework, P3-8 dockt ISIP als Datenquelle an.

## Lösungsdesign

### Erweiterung von ProtectionPlanService

**Fälligkeits-Metadaten für Protection-Operationen:**

```python
# models/planting_plan.py

@dataclass
class FieldOperation:
    # ... bestehende Felder ...
    due_date: datetime.date | None = None  # Fälligkeitsdatum
    due_window_days: int = 7  # Fälligkeitsfenster in Tagen
    is_critical: bool = False  # Terminkritisch (z. B. Fungizid)
```

**Konfiguration in `config/planting_plan_potato.json`:**

```json
{
  "protection_plans": [
    {
      "name": "Protection Plan Belana 1",
      "protections": [
        {
          "day": 0,
          "type": 26,
          "name": "Bandur Artist",
          "amount": "2.5+2",
          "is_critical": false
        },
        {
          "day": 21,
          "type": 27,
          "name": "Zorvec",
          "amount": "0.25",
          "is_critical": true,
          "due_window_days": 5
        }
      ]
    }
  ]
}
```

**Berechnung von Fälligkeitsdaten:**

`ProtectionPlanService` berechnet `due_date` aus `planned_date` + `due_window_days`:

```python
class ProtectionPlanService:
    def _initialize_protections(self):
        for op in self.operations:
            if op.planned_date:
                op.due_date = op.planned_date + timedelta(days=op.due_window_days)
```

### Neue Prioritätsstrategie: DeadlineAwarePriorityStrategy

Ersetzt `WorkTypePriorityStrategy` als Standard:

```python
# scheduler/decision_manager.py

@dataclass
class DeadlineAwarePriorityStrategy:
    """Prioritätsstrategie mit Fälligkeitsberücksichtigung."""
    
    def select_operation(self, operations: List[Any]) -> Any:
        if not operations:
            return None
        
        today = datetime.date.today()  # oder aus Kontext
        
        # Trenne in kritisch überfällig, kritisch im Fenster, andere
        overdue_critical = []
        in_window_critical = []
        others = []
        
        for op in operations:
            is_critical = getattr(op, "is_critical", False)
            due_date = getattr(op, "due_date", None)
            wt = getattr(op, "worktype", None)
            
            if is_critical and due_date:
                if today > due_date:
                    overdue_critical.append(op)
                elif today >= (due_date - timedelta(days=2)):  # Vorwarn-Fenster
                    in_window_critical.append(op)
                else:
                    others.append(op)
            else:
                others.append(op)
        
        # Priorität: überfällig kritisch > im Fenster kritisch > high-prio andere > low-prio andere
        if overdue_critical:
            return overdue_critical  # Alle überfälligen kritischen ausführen
        if in_window_critical:
            # Kritische im Fenster zusammen mit high-prio anderen
            high_prio = [op for op in others if op.worktype not in LOW_PRIORITY_WORKTYPES]
            return in_window_critical + high_prio
        
        # Fallback auf ursprüngliche Logik
        low_prio_worktypes = LOW_PRIORITY_WORKTYPES
        filtered = [op for op in others if op.worktype not in low_prio_worktypes]
        if not filtered:
            return others
        return filtered
```

### Integration (Standard-Strategie, kein optionaler Schalter)

`CalendarDrivenRunner` verwendet **immer** `DeadlineAwarePriorityStrategy` (kein Fallback auf `WorkTypePriorityStrategy`):

```python
class CalendarDrivenRunner:
    def __init__(
        self,
        context: SimContext,
        event_bus: Optional[DomainEventBus] = None,
    ):
        # ...
        # P3-4: DeadlineAwarePriorityStrategy ist Standard (PO-Entscheidung)
        strategy = DeadlineAwarePriorityStrategy()
        self.decision_manager = DecisionManager(
            strategy=strategy,
            event_bus=self.event_bus,
            rule_guard=rule_guard,
        )
```

## Betroffene Dateien

- Ändern: `models/planting_plan.py` (FieldOperation: due_date, due_window_days, is_critical)
- Ändern: `services/protection_plan_service.py` (Initialisierung mit Fälligkeitsdaten)
- Ändern: `scheduler/decision_manager.py` (DeadlineAwarePriorityStrategy als Standard)
- Ändern: `scheduler/calendar_driven_runner.py` (Standard-Strategie)
- Ändern: `config/planting_plan_potato.json` (is_critical, due_window_days für Fungizide)
- Tests: `tests/test_deadline_aware_priority.py`

## Akzeptanzkriterien

1. Fungizid-Spritzungen (cat=27) sind als `is_critical=true` markiert
2. Überfällige kritische Operationen werden auch bei High-Prio-Konkurrenz ausgeführt
3. Fungizid-Abstände bleiben im Bereich [3, 14] Tage (KAR-021)
4. Nicht-kritische Spritzungen werden weiterhin bei High-Prio-Konkurrenz unterdrückt (Bestandsschutz)
5. `DeadlineAwarePriorityStrategy` ist Standard (kein optionaler Schalter)
6. Plausibilitätstest für KAR-021 wird von xfail auf aktiv umgestellt

## Testhinweise

Integrationstest: Simulation mit Düngung am Tag X und Fungizid fällig am Tag X+1 → Fungizid wird nicht unterdrückt. Unit-Tests für DeadlineAwarePriorityStrategy mit verschiedenen Szenarien.

## Aufwandsschätzung

M (neue Standard-Strategie, Konfigurationserweiterung)

## Abhängigkeiten

Keine (kann parallel zu P3-1 entwickelt werden). P3-8 (ISIP-Anbindung) baut auf P3-4 auf.

## PO-Entscheidungen (eingearbeitet)

- **Standard-Strategie:** `DeadlineAwarePriorityStrategy` wird Standard (kein optionaler Schalter, kein Fallback auf `WorkTypePriorityStrategy`)
- **ISIP ausgelagert:** ISIP-Datenbank-Anbindung in separates Arbeitspaket P3-8 (nächste Stufe) verschoben. P3-4 liefert das Fälligkeits-Framework, P3-8 dockt ISIP als Datenquelle an.
