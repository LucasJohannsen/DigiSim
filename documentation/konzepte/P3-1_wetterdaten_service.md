# P3-1 — Wetterdaten-Service mit Jahres-/Standortkopplung (Befund B4)

## Problem

Die Beregnungsentscheidung ist vom Simulationswetter entkoppelt. `MoistureDataService` verwendet einen festen Fallback auf das Jahr 2022 und wählt eine **zufällige Koordinate** in Deutschland (`services/moisture_service.py`, Z. 64–90, 104–110). Für Simulationen in zukünftigen Jahren (z. B. 2027) existieren keine Daten → Entscheidungen basieren systematisch auf falschem Jahr/Standort.

Verletzte Regeln: KAR-034 (hart: Feuchtedaten müssen aus Simulationsjahr und Standort stammen), KAR-031 (nicht erfüllbar ohne korrekte Prognose).

## Zielverhalten

Wetter- und Bodenfeuchtedaten werden aus dem **tatsächlichen Simulationsjahr** und einem **konfigurierbaren Feldstandort** bezogen. Wenn Daten für das Simulationsjahr fehlen, wird das **zuletzt verfügbare Jahr** verwendet (nicht hart auf 2022, sondern dynamisch das jüngste verfügbare Jahr – z. B. für Simulation 2027 →Fallback auf 2026, wenn 2026 vorhanden). Der Feldstandort ist in der Konfiguration hinterlegt (nicht zufällig, nicht aus Feld-ID abgeleitet).

## Lösungsdesign

### Architektur-Entwurf (Provider-Modell)

**Neues Interface:** `services/weather_service.py`

```python
from typing import Protocol, runtime_checkable
from dataclasses import dataclass
import datetime

@dataclass(frozen=True)
class WeatherData:
    """Wetterdaten für einen Tag."""
    date: datetime.date
    precipitation_mm: float
    wind_speed_ms: float
    temperature_max_c: float
    temperature_min_c: float
    soil_moisture_pct_nfk: float  # Bodenfeuchte in % nFK

@runtime_checkable
class WeatherDataProvider(Protocol):
    """Provider-Interface für Wetterdaten."""
    
    def get_weather_data(
        self,
        year: int,
        coords: tuple[float, float] | None = None
    ) -> list[WeatherData]:
        """Liefert Wetterdaten für das gesamte Jahr."""
        ...

class WeatherDataService:
    """Service für Wetterdaten mit Provider-Injection."""
    
    def __init__(
        self,
        context: SimContext,
        provider: WeatherDataProvider,
        event_bus: Optional[DomainEventBus] = None
    ):
        self.context = context
        self.provider = provider
        self.event_bus = event_bus
        self._cached_data: dict[int, list[WeatherData]] = {}
    
    def get_weather_for_date(self, date: datetime.date) -> WeatherData:
        """Liefert Wetterdaten für ein einzelnes Datum."""
        year = date.year
        if year not in self._cached_data:
            self._cached_data[year] = self.provider.get_weather_data(
                year,
                self._get_field_coords()
            )
        day_index = date.timetuple().tm_yday - 1
        return self._cached_data[year][day_index]
    
    def get_forecast(self, date: datetime.date, days: int) -> list[WeatherData]:
        """Liefert Prognose für N Tage ab Datum."""
        year = date.year
        if year not in self._cached_data:
            self._cached_data[year] = self.provider.get_weather_data(
                year,
                self._get_field_coords()
            )
        day_index = date.timetuple().tm_yday - 1
        return self._cached_data[year][day_index:day_index + days]
    
    def _get_field_coords(self) -> tuple[float, float]:
        """Konfigurierbarer Feldstandort aus SimContext/Config."""
        # Feldstandort wird aus der Konfiguration gelesen (nicht zufällig,
        # nicht aus Feld-ID abgeleitet). Default: Norddeutschland
        # (Kartoffel-Region Hannover).
        return getattr(self.context, "field_coords", (52.5, 9.9))
```

### Provider-Implementierungen

**1. DWDWeatherDataProvider** (produktiv, Fallback auf letztes verfügbares Jahr)

```python
class DWDWeatherDataProvider:
    """Lädt DWD-Daten für Niederschlag, Wind, Temperatur.
    
    Fallback-Strategie: Falls das angeforderte Jahr nicht verfügbar ist,
    wird das **zuletzt verfügbare Jahr** verwendet (dynamisch ermittelt,
    nicht hart auf 2022). Beispiel: Simulation 2027 → 2026, wenn 2026
    der jüngste verfügbare Datensatz ist.
    """
    
    def __init__(self, cache_folder: str = "dwd_data"):
        self.cache_folder = cache_folder
    
    def _find_latest_available_year(self) -> int:
        """Ermittelt das jüngste verfügbare Jahr im Cache-Ordner."""
        # Scanne dwd_data/ nach grids_germany_daily_*_<year>_*.nc
        # und liefere das maximale Jahr.
        ...
    
    def get_weather_data(
        self,
        year: int,
        coords: tuple[float, float]
    ) -> list[WeatherData]:
        # Download/Cache-Logik analog MoistureDataService
        # DWD-Quellen:
        # - precipitation: grids_germany_daily_precipitation_<year>_v1.nc
        # - wind: grids_germany_daily_wind_<year>_v1.nc
        # - temperature: grids_germany_daily_airtemp_<year>_v1.nc
        # Fallback: falls <year> nicht verfügbar, verwende
        # self._find_latest_available_year() (nicht hart 2022).
        # Extraktion an coords, Zusammenbau zu WeatherData-Liste
        pass
```

**2. SyntheticWeatherDataProvider** (Fallback für Tests/Missing Years)

```python
class SyntheticWeatherDataProvider:
    """Deterministischer synthetischer Wetter-Generator."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
    
    def get_weather_data(
        self,
        year: int,
        coords: tuple[float, float]
    ) -> list[WeatherData]:
        # Deterministische Wetter-Generierung basierend auf year + coords
        # Saisonale Muster: mehr Regen im Sommer, Hitze im Juli/August
        # Perlin-Noise oder ähnlich für Realismus
        pass
```

### Integration in CalendarDrivenRunner

Analog zu `moisture_service_factory` (P2-5 C):

```python
# Type alias für optionale Weather-Service-Factory
WeatherServiceFactory = Callable[[], WeatherDataService]

class CalendarDrivenRunner:
    def __init__(
        self,
        context: SimContext,
        event_bus: Optional[DomainEventBus] = None,
        skip_scheduling_event: bool = False,
        moisture_service_factory: Optional[MoistureServiceFactory] = None,
        weather_service_factory: Optional[WeatherServiceFactory] = None  # NEU
    ):
        # ...
        self._weather_service_factory = weather_service_factory
    
    def _initialize_services(self, current_date: datetime.date) -> None:
        # ...
        if self._weather_service_factory is not None:
            self.weather_service = self._weather_service_factory()
        else:
            # Default: DWDWeatherDataProvider mit Fallback auf letztes
            # verfügbares Jahr. Feldstandort aus Konfiguration (SimContext).
            provider = DWDWeatherDataProvider(cache_folder="dwd_data")
            self.weather_service = WeatherDataService(
                context=self.context,
                provider=provider,
                event_bus=self.event_bus
            )
```

### CycleContext-Erweiterung

Für Wetter-Guards (P3-2) muss `CycleContext` Wetterdaten enthalten:

```python
@dataclass(frozen=True)
class CycleContext:
    # ... bestehende Felder ...
    current_weather: WeatherData | None = None
    weather_forecast: list[WeatherData] | None = None
```

`CalendarDrivenRunner._build_cycle_context()` befüllt diese Felder aus `weather_service`.

## Betroffene Dateien

- Neu: `services/weather_service.py` (Interface + Service + Provider)
- Neu: `services/providers/dwd_weather_provider.py`
- Neu: `services/providers/synthetic_weather_provider.py`
- Ändern: `scheduler/calendar_driven_runner.py` (Constructor, _initialize_services, _build_cycle_context)
- Ändern: `scheduler/decision_manager.py` (CycleContext)
- Ändern: `models/sim_context.py` (optionales Feld `field_coords: tuple[float, float] | None`)
- Ändern: `config/` (Feldstandort-Konfiguration, z. B. in `config/field_config.json` oder Erweiterung von `SimContext`)
- Ändern: `services/moisture_service.py` (Fallback-Logik: dynamisch letztes Jahr statt hart 2022; konfigurierbarer Standort statt Zufallskoordinate)
- Tests: `tests/test_weather_service.py`, `tests/test_providers/`

## Akzeptanzkriterien

1. `WeatherDataService` mit `SyntheticWeatherDataProvider` liefert deterministische Daten bei gleichem Seed
2. `CalendarDrivenRunner` injiziert WeatherDataService via Factory (Abwärtskompatibilität: ohne Factory wird Synthetic-Provider verwendet)
3. `CycleContext` enthält `current_weather` und `weather_forecast` für den aktuellen Tick
4. DWD-Provider lädt Daten für verfügbare Jahre (2022, 2024, 2025, 2026) und fällt **dynamisch auf das jüngste verfügbare Jahr** zurück (nicht hart 2022)
5. Feldstandort ist **konfigurierbar** (aus `SimContext.field_coords` oder Config-Datei), nicht zufällig, nicht aus Feld-ID abgeleitet
6. Plausibilitätstest xfail-B4 wird grün → Marker entfernen

## Testhinweise

Unit-Tests für Provider-Logik. Integrationstest: Simulation über 2 Jahre mit Daten-Wechsel (2022 → 2024). Determinismus-Test: gleicher Seed → gleiche Wetterdaten.

## Aufwandsschätzung

L (großes Paket: neues Service, Provider-Modell, DWD-Integration für 3 weitere Parameter Niederschlag/Wind/Temperatur, konfigurierbarer Standort, dynamischer Jahres-Fallback)

## Abhängigkeiten

Keine (architektonisches Fundament für P3-2 und P3-3)

## PO-Entscheidungen (eingearbeitet)

- **Wetterdaten-Quelle:** Echte DWD-Daten (Niederschlag, Wind, Temperatur), Fallback auf **letztes verfügbares Jahr** (dynamisch, nicht hart 2022)
- **Feldstandort:** Konfigurierbar (in `SimContext` oder Config-Datei), nicht zufällig, nicht aus Feld-ID abgeleitet
