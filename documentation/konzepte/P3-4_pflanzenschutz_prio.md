# P3-4 — Pflanzenschutz-Priorität mit Fälligkeitskonzept (Befund B9)

## Problem

Die Prioritätslogik unterdrückt pauschal alle Low-Prio-Operationen (Spritzen, Beregnen), wenn High-Prio-Operationen existieren. Überfällige Spritzungen werden am nächsten freien Tag gesammelt nachgeholt – bei Fungizid-Spritzfolgen (7–10 Tage) gefährdet dies die Wirksamkeit. Es gibt kein Fälligkeits-/Nachholkonzept für terminkritische Maßnahmen.

Verletzte Regel: KAR-021 (hart: Fungizidabstände ≥ 3 Tage, üblich 5–14 Tage – wird durch Stauung verletzt).

## Zielverhalten

Terminkritische Pflanzenschutz-Maßnahmen (insbesondere Fungizide) werden nicht pauschal unterdrückt, sondern erhalten ein Fälligkeitsfenster. Überschreitung des Fensters führt zu Prioritätserhöhung oder Nachhol-Logik. Die `DeadlineAwarePriorityStrategy` wird zur **Standard-Strategie** (kein optionaler Schalter). Fungizid-Spritztermine und -Abstände werden aus der **ISIP-Datenbank** bezogen (DigiZert hält die API-Zugangsdaten).

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
    isip_spray_window_days: int | None = None  # ISIP-Spritzfenster (Fungizide)
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
          "due_window_days": 5,
          "use_isip_schedule": true
        }
      ]
    }
  ]
}
```

### ISIP-Datenbank-Anbindung (Fungizid-Termine)

**Neuer Service:** `services/isip_protection_service.py`

```python
class IsipProtectionService:
    """Bezieht Fungizid-Spritztermine und -Abstände aus der ISIP-Datenbank.
    
    ISIP (Informationssystem Integrierte Pflanzenproduktion) liefert
    regionsspezifische Spritzfenster und Warnhinweise für Pflanzenschutz-
    maßnahmen. DigiZert hält die API-Zugangsdaten.
    """
    
    def __init__(
        self,
        context: SimContext,
        api_credentials: dict[str, str],  # aus DigiZert-Config
        event_bus: Optional[DomainEventBus] = None
    ):
        self.context = context
        self.api_credentials = api_credentials
        self.event_bus = event_bus
        self._cache: dict[str, list[dict]] = {}
    
    def get_fungicide_schedule(
        self,
        crop: str,
        variety: str,
        region: str,  # z. B. aus field_coords abgeleitet
        season_year: int
    ) -> list[dict]:
        """Liefert ISIP-Spritztermine für Fungizide einer Saison.
        
        Returns:
            Liste von dicts mit Keys:
            - product_name: str
            - planned_date: datetime.date
            - due_window_days: int
            - min_interval_days: int  # Mindestabstand zur vorherigen Gabe
            - max_interval_days: int  # Maximalabstand (KAR-021)
        """
        # API-Aufruf an ISIP (via DigiZert-Proxy oder direkt)
        # Caching pro (crop, variety, region, year)
        ...
    
    def apply_isip_schedule(
        self,
        operations: list[FieldOperation],
        season_year: int
    ) -> list[FieldOperation]:
        """Überschreibt geplante Fungizid-Termine mit ISIP-Daten.
        
        Nur Fungizide (application_category=27) mit use_isip_schedule=true
        werden überschrieben. Andere Protection-Operationen bleiben
        an der konfigurierten Planung.
        """
        schedule = self.get_fungicide_schedule(
            crop=self.context.crop_type,
            variety=self.context.variety,
            region=self._region_from_coords(),
            season_year=season_year
        )
        # Matche nach product_name, setze planned_date + due_window_days
        ...
```

**Integration in ProtectionPlanService:**

```python
class ProtectionPlanService:
    def __init__(
        self,
        context: SimContext,
        start_date: datetime.date,
        planting_plan: PlantingPlan,
        harvest_date: datetime.date,
        event_bus: DomainEventBus,
        isip_service: IsipProtectionService | None = None  # NEU
    ):
        # ...
        self.isip_service = isip_service
        if self.isip_service is not None:
            self._apply_isip_schedule()
    
    def _apply_isip_schedule(self) -> None:
        """Überschreibt Fungizid-Termine mit ISIP-Daten, falls verfügbar."""
        season_year = self.start_date.year
        self.operations = self.isip_service.apply_isip_schedule(
            self.operations, season_year
        )
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

Erweiterung oder Alternative zu `WorkTypePriorityStrategy`:

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
        isip_service: Optional[IsipProtectionService] = None  # NEU
    ):
        # ...
        # P3-4: DeadlineAwarePriorityStrategy ist Standard (PO-Entscheidung)
        strategy = DeadlineAwarePriorityStrategy()
        self.decision_manager = DecisionManager(
            strategy=strategy,
            event_bus=self.event_bus,
            rule_guard=rule_guard,
        )
        self._isip_service = isip_service
    
    def _initialize_services(self, current_date: datetime.date) -> None:
        # ...
        self.protection_plan_service = ProtectionPlanService(
            context=self.context,
            start_date=self.planting_plan_service.planned_planting_date,
            planting_plan=self.planting_plan_service.planting_plan,
            harvest_date=self._compute_harvest_date(),
            event_bus=self.event_bus,
            isip_service=self._isip_service,  # NEU
        )
```

**ISIP-Credentials:** DigiZert hält die API-Zugangsdaten. Diese werden aus einer Config-Datei oder Umgebungsvariablen geladen (nicht hardcoded):

```python
# config/isip_config.json (gitignored, enthält API-Credentials)
{
  "api_url": "https://api.isip.de/v1",
  "api_key": "<aus DigiZert>",
  "api_user": "<aus DigiZert>"
}
```

## Betroffene Dateien

- Ändern: `models/planting_plan.py` (FieldOperation: due_date, due_window_days, is_critical, isip_spray_window_days)
- Ändern: `services/protection_plan_service.py` (Initialisierung mit Fälligkeitsdaten, ISIP-Integration)
- Neu: `services/isip_protection_service.py` (ISIP-API-Anbindung)
- Ändern: `scheduler/decision_manager.py` (DeadlineAwarePriorityStrategy als Standard)
- Ändern: `scheduler/calendar_driven_runner.py` (ISIP-Service-Injection, Standard-Strategie)
- Ändern: `config/planting_plan_potato.json` (is_critical, due_window_days, use_isip_schedule für Fungizide)
- Neu: `config/isip_config.json` (API-Credentials, gitignored)
- Tests: `tests/test_deadline_aware_priority.py`, `tests/test_isip_protection_service.py`

## Akzeptanzkriterien

1. Fungizid-Spritzungen (cat=27) sind als `is_critical=true` markiert
2. Überfällige kritische Operationen werden auch bei High-Prio-Konkurrenz ausgeführt
3. Fungizid-Abstände bleiben im Bereich [3, 14] Tage (KAR-021), ISIP-Schedule wird berücksichtigt
4. Nicht-kritische Spritzungen werden weiterhin bei High-Prio-Konkurrenz unterdrückt (Bestandsschutz)
5. `DeadlineAwarePriorityStrategy` ist Standard (kein optionaler Schalter)
6. ISIP-Service ist optional injizierbar; ohne ISIP-Service fällt ProtectionPlanService auf konfigurierte Planung zurück
7. Plausibilitätstest für KAR-021 wird von xfail auf aktiv umgestellt

## Testhinweise

Integrationstest: Simulation mit Düngung am Tag X und Fungizid fällig am Tag X+1 → Fungizid wird nicht unterdrückt. Unit-Tests für DeadlineAwarePriorityStrategy mit verschiedenen Szenarien. ISIP-Service-Test mit Mock-API (kein echter API-Call in CI).

## Aufwandsschätzung

M–L (neue Standard-Strategie, Konfigurationserweiterung, ISIP-API-Anbindung mit Credentials-Management)

## Abhängigkeiten

Keine (kann parallel zu P3-1 entwickelt werden). ISIP-Service benötigt DigiZert-API-Credentials (PO muss bereitstellen).

## PO-Entscheidungen (eingearbeitet)

- **Standard-Strategie:** `DeadlineAwarePriorityStrategy` wird Standard (kein optionaler Schalter, kein Fallback auf `WorkTypePriorityStrategy`)
- **ISIP-Datenbank:** Fungizid-Termine und -Abstände aus ISIP beziehen; DigiZert hält API-Zugangsdaten (Credentials in gitignored Config-Datei)
