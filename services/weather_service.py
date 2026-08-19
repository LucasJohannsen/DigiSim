"""Wetterdaten-Service mit Provider-Injection (P3-1, Issue #79).

Stellt das Interface für Wetterdaten bereit: ``WeatherData`` (Value Object),
``WeatherDataProvider`` (Protocol) und ``WeatherDataService`` (Service mit
Caching). Der Service bezieht Wetterdaten für ein konkretes Simulationsjahr
und einen konfigurierbaren Feldstandort aus ``SimContext.field_coords``.

Provider-Modell: Der Service ist von der Datenquelle entkoppelt. Produktiv
wird ``DWDWeatherDataProvider`` verwendet, der bei fehlenden DWD-Dateien auf
``SyntheticWeatherDataProvider`` zurückfällt. Tests können einen beliebigen
Provider injizieren (z. B. ``SyntheticWeatherDataProvider``).

Konzept: ``documentation/konzepte/P3-1_wetterdaten_service.md``
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from events.domain_event_bus import DomainEventBus
from models.sim_context import SimContext
from utils.logger import get_logger

__all__ = [
    "WeatherData",
    "WeatherDataProvider",
    "WeatherDataService",
]

logger = get_logger("weather_service")

# Default-Feldstandort: Norddeutschland (Region Hannover, Kartoffel-Anbau).
_DEFAULT_FIELD_COORDS: tuple[float, float] = (52.5, 9.9)


@dataclass(frozen=True)
class WeatherData:
    """Wetterdaten für einen einzelnen Tag.

    Attributes:
        date: Datum des Tages.
        precipitation_mm: Niederschlag in mm.
        wind_speed_ms: Windgeschwindigkeit in m/s.
        temperature_max_c: Tageshöchsttemperatur in °C.
        temperature_min_c: Tagestiefsttemperatur in °C.
        soil_moisture_pct_nfk: Bodenfeuchte in % nFK.
    """

    date: datetime.date
    precipitation_mm: float
    wind_speed_ms: float
    temperature_max_c: float
    temperature_min_c: float
    soil_moisture_pct_nfk: float


@runtime_checkable
class WeatherDataProvider(Protocol):
    """Provider-Interface für Wetterdaten.

    Implementierungen liefern Wetterdaten für ein gesamtes Jahr an einer
    gegebenen Koordinate. Der Provider ist zustandslos bzgl. des
    Simulationskontexts – Caching erfolgt im ``WeatherDataService``.
    """

    def get_weather_data(
        self,
        year: int,
        coords: tuple[float, float] | None = None,
    ) -> list[WeatherData]:
        """Liefert Wetterdaten für das gesamte Jahr (1.1.–31.12.).

        Args:
            year: Simulationsjahr.
            coords: (lat, lon) der Feldkoordinate, oder None für Default.

        Returns:
            Liste von ``WeatherData``, ein Eintrag pro Tag (365/366).
        """
        ...


class WeatherDataService:
    """Service für Wetterdaten mit Provider-Injection und Caching.

    Cacht Wetterdaten pro Jahr. Der Feldstandort wird aus
    ``SimContext.field_coords`` gelesen (Default: Norddeutschland).
    """

    def __init__(
        self,
        context: SimContext,
        provider: WeatherDataProvider,
        event_bus: DomainEventBus | None = None,
    ) -> None:
        self.context = context
        self.provider = provider
        self.event_bus = event_bus
        self._cached_data: dict[int, list[WeatherData]] = {}

    def get_weather_for_date(self, date: datetime.date) -> WeatherData:
        """Liefert Wetterdaten für ein einzelnes Datum.

        Args:
            date: Das angefragte Datum.

        Returns:
            ``WeatherData`` für den Tag.

        Raises:
            IndexError: Wenn das Datum außerhalb der verfügbaren Daten liegt.
        """
        year_data = self._get_year_data(date.year)
        day_index = date.timetuple().tm_yday - 1
        return year_data[day_index]

    def get_forecast(self, date: datetime.date, days: int) -> list[WeatherData]:
        """Liefert eine Prognose für N Tage ab dem gegebenen Datum.

        Bei Jahreswechsel wird das Folgejahr automatisch nachgeladen.

        Args:
            date: Startdatum der Prognose.
            days: Anzahl der Prognosetage.

        Returns:
            Liste von ``WeatherData`` mit bis zu ``days`` Einträgen.
        """
        result: list[WeatherData] = []
        current = date
        for _ in range(days):
            year_data = self._get_year_data(current.year)
            day_index = current.timetuple().tm_yday - 1
            if day_index >= len(year_data):
                break
            result.append(year_data[day_index])
            current = current + datetime.timedelta(days=1)
        return result

    def _get_year_data(self, year: int) -> list[WeatherData]:
        """Lädt und cacht Wetterdaten für ein Jahr."""
        if year not in self._cached_data:
            coords = self._get_field_coords()
            logger.debug(
                "Loading weather data",
                year=year,
                coords=coords,
            )
            self._cached_data[year] = self.provider.get_weather_data(year, coords)
        return self._cached_data[year]

    def _get_field_coords(self) -> tuple[float, float]:
        """Konfigurierbarer Feldstandort aus SimContext.

        Default: Norddeutschland (52.5, 9.9) – Region Hannover.
        """
        coords = getattr(self.context, "field_coords", None)
        if coords is not None:
            return coords
        return _DEFAULT_FIELD_COORDS
