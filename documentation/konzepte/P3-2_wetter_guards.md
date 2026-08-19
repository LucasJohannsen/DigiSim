# P3-2 — Wetter-Guards für Spritzen und Bodenbearbeitung (Befund B8)

## Problem

Der DecisionManager kennt ausschließlich eine Worktype-Priorität, keinerlei Regen-, Wind- oder Bodenfeuchteregeln. Spritzungen bei Regen/Wind sind nicht ausgeschlossen, Bodenbearbeitung auf nassem Boden wird nicht verhindert.

Verletzte Regeln: KAR-030 (hart: kein Spritzen bei Regen >1 mm während Applikation / >5 mm am Tag oder Wind >5 m/s), KAR-032 (hart: keine Bodenbearbeitung/Legen auf nassem Boden >90 % nFK oder Vortagesniederschlag >10 mm), KAR-035 (soft: keine Sikkation bei Hitze >30°C oder auf nassen Bestand).

## Zielverhalten

Operationen werden bei ungünstigen Wetterbedingungen abgelehnt (Guard-Regeln). Die Entscheidung basiert auf den Wetterdaten aus P3-1.

## Lösungsdesign

### Erweiterung des Guard-Systems

Der RuleGuard-Mechanismus aus P2-4 wird um Wetter-Guards erweitert. Neue Guard-Regel-Klassen:

**1. WeatherConditionGuard** (KAR-030, KAR-035)

```python
@dataclass(frozen=True)
class WeatherConditionGuard:
    """Prüft Wetterbedingungen für Spritzoperationen."""

    rule_id: str
    description: str
    worktype: int
    application_category: int | None = None  # None = alle Kategorien
    max_precipitation_mm_day: float = 5.0
    max_wind_ms: float = 5.0
    max_temperature_c: float | None = None  # None = keine Temperatur-Prüfung

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "WeatherConditionGuard":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktype=entry["worktype"],
            application_category=entry.get("application_category"),
            max_precipitation_mm_day=entry.get("max_precipitation_mm_day", 5.0),
            max_wind_ms=entry.get("max_wind_ms", 5.0),
            max_temperature_c=entry.get("max_temperature_c"),
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.current_weather is None:
            return None  # Guard deaktiviert ohne Wetterdaten

        wt = getattr(operation, "worktype", None)
        if wt != self.worktype:
            return None

        if self.application_category is not None:
            cat = getattr(operation, "application_category", None)
            if cat != self.application_category:
                return None

        weather = cycle_context.current_weather

        # Niederschlag-Prüfung
        if weather.precipitation_mm > self.max_precipitation_mm_day:
            return f"{self.rule_id}: {self.description} (Niederschlag {weather.precipitation_mm} mm > {self.max_precipitation_mm_day} mm)"

        # Wind-Prüfung
        if weather.wind_speed_ms > self.max_wind_ms:
            return f"{self.rule_id}: {self.description} (Wind {weather.wind_speed_ms} m/s > {self.max_wind_ms} m/s)"

        # Temperatur-Prüfung (optional)
        if (
            self.max_temperature_c is not None
            and weather.temperature_max_c > self.max_temperature_c
        ):
            return f"{self.rule_id}: {self.description} (Temperatur {weather.temperature_max_c}°C > {self.max_temperature_c}°C)"

        return None
```

**2. SoilConditionGuard** (KAR-032)

```python
@dataclass(frozen=True)
class SoilConditionGuard:
    """Prüft Bodenfeuchte für Bodenbearbeitung/Legen."""
    
    rule_id: str
    description: str
    worktypes: list[int]
    max_soil_moisture_pct_nfk: float = 90.0
    max_previous_day_precipitation_mm: float = 10.0
    
    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "SoilConditionGuard":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktypes=list(entry["worktypes"]),
            max_soil_moisture_pct_nfk=entry.get("max_soil_moisture_pct_nfk", 90.0),
            max_previous_day_precipitation_mm=entry.get("max_previous_day_precipitation_mm", 10.0),
        )
    
    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.current_weather is None:
            return None
        
        wt = getattr(operation, "worktype", None)
        if wt not in self.worktypes:
            return None
        
        weather = cycle_context.current_weather
        
        # Bodenfeuchte-Prüfung
        if weather.soil_moisture_pct_nfk > self.max_soil_moisture_pct_nfk:
            return f"{self.rule_id}: {self.description} (Bodenfeuchte {weather.soil_moisture_pct_nfk}% nFK > {self.max_soil_moisture_pct_nfk}% nFK)"
        
        # Vortagesniederschlag-Prüfung (benötigt Zugriff auf Vortag)
        # Implementierung via Forecast-Liste oder separatem Service-Aufruf
        # Für MVP: Vortag aus forecast[-1] wenn verfügbar
        
        return None
```

**3. ForecastConditionGuard** (KAR-031 für Beregnung)

```python
@dataclass(frozen=True)
class ForecastConditionGuard:
    """Prüft Prognose für Beregnung (kein Niederschlag in den nächsten N Tagen)."""

    rule_id: str
    description: str
    worktype: int
    forecast_days: int = 4
    max_cumulative_precipitation_mm: float = 10.0

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "ForecastConditionGuard":
        return cls(
            rule_id=entry["rule_id"],
            description=entry["description"],
            worktype=entry["worktype"],
            forecast_days=entry.get("forecast_days", 4),
            max_cumulative_precipitation_mm=entry.get("max_cumulative_precipitation_mm", 10.0),
        )

    def check(
        self,
        operation: Any,
        cycle_context: CycleContext | None,
        date: datetime.datetime,
    ) -> str | None:
        if cycle_context is None or cycle_context.weather_forecast is None:
            return None

        wt = getattr(operation, "worktype", None)
        if wt != self.worktype:
            return None

        forecast = cycle_context.weather_forecast[: self.forecast_days]
        cumulative_precip = sum(day.precipitation_mm for day in forecast)

        if cumulative_precip > self.max_cumulative_precipitation_mm:
            return f"{self.rule_id}: {self.description} (Prognose-Niederschlag {cumulative_precip} mm > {self.max_cumulative_precipitation_mm} mm)"

        return None
```

### Konfiguration

Erweiterung von `config/decision_guards_potato.json`:

```json
{
  "crop": "Potato",
  "version": "2.0",
  "guards": [
    {
      "rule_id": "KAR-030",
      "check_type": "weather_condition",
      "description": "Kein Spritzen bei Regen oder Wind > 5 m/s",
      "worktype": 14,
      "max_precipitation_mm_day": 5,
      "max_wind_ms": 5
    },
    {
      "rule_id": "KAR-035",
      "check_type": "weather_condition",
      "description": "Keine Sikkation bei Hitzestress",
      "worktype": 14,
      "application_category": 26,
      "max_temperature_c": 30,
      "max_precipitation_mm_day": 1
    },
    {
      "rule_id": "KAR-032",
      "check_type": "soil_condition",
      "description": "Keine Bodenbearbeitung auf nassem Boden",
      "worktypes": [5, 6, 7, 26, 28],
      "max_soil_moisture_pct_nfk": 90,
      "max_previous_day_precipitation_mm": 10
    },
    {
      "rule_id": "KAR-031",
      "check_type": "forecast_condition",
      "description": "Keine Beregnung bei prognostiziertem Niederschlag",
      "worktype": 15,
      "forecast_days": 4,
      "max_cumulative_precipitation_mm": 10
    }
  ]
}
```

### Integration

`GuardRuleLoader` wird um die neuen `check_type`-Werte erweitert:

```python
class GuardRuleLoader:
    @staticmethod
    def load_default() -> RuleGuard:
        config = load_json("config/decision_guards_potato.json")
        rules = []
        for entry in config["guards"]:
            check_type = entry["check_type"]
            if check_type == "no_worktype_after_harvest":
                rules.append(NoWorktypeAfterHarvestRule.from_config(entry))
            elif check_type == "min_gap_before_harvest_op":
                rules.append(MinGapBeforeHarvestOpRule.from_config(entry))
            elif check_type == "no_siccation_after_harvest":
                rules.append(NoSiccationAfterHarvestRule.from_config(entry))
            elif check_type == "weather_condition":
                rules.append(WeatherConditionGuard.from_config(entry))
            elif check_type == "soil_condition":
                rules.append(SoilConditionGuard.from_config(entry))
            elif check_type == "forecast_condition":
                rules.append(ForecastConditionGuard.from_config(entry))
        return RuleGuard(rules)
```

## Betroffene Dateien

- Neu: `scheduler/guards/weather_guards.py` (WeatherConditionGuard, SoilConditionGuard, ForecastConditionGuard)
- Ändern: `scheduler/decision_manager.py` (CycleContext bereits in P3-1 erweitert)
- Ändern: `scheduler/guard_rule_loader.py` (neue check_type-Handler)
- Ändern: `scheduler/calendar_driven_runner.py` (_build_cycle_context: Wetterdaten befüllen)
- Ändern: `config/decision_guards_potato.json`
- Tests: `tests/test_weather_guards.py`

## Akzeptanzkriterien

1. Spritz-Operation (wt=14) wird bei Regen >5 mm oder Wind >5 m/s abgelehnt (KAR-030)
2. Sikkation (wt=14, cat=26) wird bei Temperatur >30°C abgelehnt (KAR-035)
3. Bodenbearbeitung (wt=5,6,7,28) wird bei Bodenfeuchte >90 % nFK abgelehnt (KAR-032)
4. Beregnung (wt=15) wird bei Prognose-Niederschlag >10 mm in 4 Tagen abgelehnt (KAR-031)
5. Guards sind deaktiviert, wenn `cycle_context.current_weather` None ist (Abwärtskompatibilität ohne P3-1)
6. Plausibilitätstests für KAR-030/032/035 werden von skip auf aktiv umgestellt

## Testhinweise

Unit-Tests für jede Guard-Klasse mit verschiedenen Wetter-Szenarien. Integrationstest mit SyntheticWeatherDataProvider, der Regen/Wind/Hitze simuliert.

## Aufwandsschätzung

M (Guard-Logik ist klar, Integration in bestehendes System)

## Abhängigkeiten

P3-1 (Wetterdaten-Service) – ohne Wetterdaten können Guards nicht aktiviert werden
