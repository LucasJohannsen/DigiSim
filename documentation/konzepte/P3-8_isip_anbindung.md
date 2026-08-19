# P3-8 — ISIP-Datenbank-Anbindung für Fungizid-Spritztermine (Folge-Package)

> **Stufe:** Nächste Simulationsstufe (nach MS6/P3). Kein Bestandteil von MS6 P3-1…P3-7. Wird separat beauftragt, wenn P3-4 (Fälligkeits-Framework) stabil ist.

## Problem

P3-4 etabliert das Fälligkeits-Framework für terminkritische Pflanzenschutz-Maßnahmen, aber die Fälligkeitsfenster und Spritzabstände stammen noch aus der statischen Konfiguration (`config/planting_plan_potato.json`). Echte, regionsspezifische Fungizid-Spritztermine und Warnhinweise liefert die **ISIP-Datenbank** (Informationssystem Integrierte Pflanzenproduktion). DigiZert hält die API-Zugangsdaten.

Verletzte Regel: KAR-021 (hart: Fungizidabstände ≥ 3 Tage, üblich 5–14 Tage) – mit statischer Konfiguration nur näherungsweise abgedeckt.

## Zielverhalten

Fungizid-Spritztermine und -Abstände werden aus der ISIP-Datenbank bezogen (regionsspezifisch, saisonaktuell). Die Daten ersetzen die statischen Konfigurationswerte für Fungizide (`application_category=27`) mit `use_isip_schedule=true`. Andere Protection-Operationen bleiben an der konfigurierten Planung.

## Lösungsdesign

### Neuer Service: IsipProtectionService

```python
# services/isip_protection_service.py


class IsipProtectionService:
    """Bezieht Fungizid-Spritztermine und -Abstände aus der ISIP-Datenbank.

    ISIP (Informationssystem Integrierte Pflanzenproduktion) liefert
    regionsspezifische Spritzfenster und Warnhinweise für Pflanzenschutz-
    maßnahmen. DigiZert hält die API-Zugangsdaten.
    """

    def __init__(
        self,
        context: SimContext,
        api_credentials: dict[str, str],  # aus config/isip_config.json
        event_bus: Optional[DomainEventBus] = None,
    ):
        self.context = context
        self.api_credentials = api_credentials
        self.event_bus = event_bus
        self._cache: dict[str, list[dict]] = {}

    def get_fungicide_schedule(
        self,
        crop: str,
        variety: str,
        region: str,  # aus field_coords abgeleitet
        season_year: int,
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
        self, operations: list[FieldOperation], season_year: int
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
            season_year=season_year,
        )
        # Matche nach product_name, setze planned_date + due_window_days
        ...
```

### Integration in ProtectionPlanService

```python
class ProtectionPlanService:
    def __init__(
        self,
        context: SimContext,
        start_date: datetime.date,
        planting_plan: PlantingPlan,
        harvest_date: datetime.date,
        event_bus: DomainEventBus,
        isip_service: IsipProtectionService | None = None,  # NEU (P3-8)
    ):
        # ...
        self.isip_service = isip_service
        if self.isip_service is not None:
            self._apply_isip_schedule()

    def _apply_isip_schedule(self) -> None:
        """Überschreibt Fungizid-Termine mit ISIP-Daten, falls verfügbar."""
        season_year = self.start_date.year
        self.operations = self.isip_service.apply_isip_schedule(self.operations, season_year)
```

### Konfiguration

**`config/planting_plan_potato.json`** – `use_isip_schedule`-Flag für Fungizide:

```json
{
  "protections": [
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
```

**`config/isip_config.json`** (gitignored, enthält API-Credentials):

```json
{
  "api_url": "https://api.isip.de/v1",
  "api_key": "<aus DigiZert>",
  "api_user": "<aus DigiZert>"
}
```

### CalendarDrivenRunner-Erweiterung

```python
class CalendarDrivenRunner:
    def __init__(
        self,
        context: SimContext,
        event_bus: Optional[DomainEventBus] = None,
        isip_service: Optional[IsipProtectionService] = None,  # NEU (P3-8)
    ):
        # ...
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

## Betroffene Dateien

- Neu: `services/isip_protection_service.py` (ISIP-API-Anbindung)
- Ändern: `services/protection_plan_service.py` (optionale ISIP-Integration)
- Ändern: `scheduler/calendar_driven_runner.py` (ISIP-Service-Injection)
- Ändern: `config/planting_plan_potato.json` (`use_isip_schedule`-Flag)
- Neu: `config/isip_config.json` (API-Credentials, gitignored)
- Tests: `tests/test_isip_protection_service.py` (mit Mock-API, kein echter API-Call in CI)

## Akzeptanzkriterien

1. `IsipProtectionService` liefert deterministische Fungizid-Schedules für (crop, variety, region, year)
2. Fungizide mit `use_isip_schedule=true` werden mit ISIP-Terminen überschrieben
3. Andere Protection-Operationen bleiben an der konfigurierten Planung
4. ISIP-Service ist optional injizierbar; ohne ISIP-Service fällt ProtectionPlanService auf konfigurierte Planung zurück
5. API-Credentials werden aus `config/isip_config.json` geladen (nicht hardcoded, gitignored)
6. CI-Tests verwenden Mock-API (kein echter ISIP-Call)

## Testhinweise

Mock-API-Test für `IsipProtectionService` (kein Netzwerk in CI). Integrationstest: Simulation mit ISIP-Service → Fungizid-Termine entsprechen ISIP-Schedule. Fallback-Test: ohne ISIP-Service → konfigurierte Planung.

## Aufwandsschätzung

M (API-Anbindung, Credentials-Management, Mock-Tests)

## Abhängigkeiten

- **P3-4** (Fälligkeits-Framework) muss implementiert sein – P3-8 dockt ISIP als Datenquelle an das bestehende Framework an.
- **P3-1** (Wetterdaten-Service) für `field_coords`-basierte Region-Ableitung.
- **PO muss ISIP-API-Credentials bereitstellen** (DigiZert hält sie).

## PO-Entscheidungen (eingearbeitet)

- **ISIP als separates Arbeitspaket:** Aus P3-4 ausgelagert in P3-8 (nächste Stufe). P3-4 liefert das Framework, P3-8 die echte Datenquelle.
- **DigiZert API-Credentials:** Werden in gitignored `config/isip_config.json` abgelegt.
