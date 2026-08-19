"""Synthetischer Wetter-Provider (P3-1, Issue #79).

Deterministischer Stub, der synthetische Wetterdaten für ein ganzes Jahr
liefert – analog ``DryMoistureDataService`` (tests/plausibility/dry_moisture_stub.py),
aber für das ``WeatherDataProvider``-Protocol.

Saisonale Muster:
- Niederschlag: mehr Regen im Sommer (Mai–Aug), weniger im Winter.
- Temperatur: Höchstwerte im Juli/August, Tiefstwerte im Jan/Dez.
- Wind: variiert leicht, etwas windiger im Herbst/Winter.
- Bodenfeuchte: korreliert negativ mit Temperatur (Sommer → trockener).

Deterministisch: Seed-basiert, kein Netzwerk, keine Dateizugriffe.
Zwei Aufrufe mit gleichem Seed + Jahr liefern identische Daten.

Wohnort: ``services/providers/`` (produktiver Fallback, nicht nur Test).
"""

from __future__ import annotations

import datetime
import math
import random

from services.weather_service import WeatherData

__all__ = ["SyntheticWeatherDataProvider"]


class SyntheticWeatherDataProvider:
    """Deterministischer synthetischer Wetter-Generator.

    Implementiert das ``WeatherDataProvider``-Protocol. Liefert für jedes
    Jahr 365/366 Tage mit saisonal plausiblen Werten.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def get_weather_data(
        self,
        year: int,
        coords: tuple[float, float] | None = None,
    ) -> list[WeatherData]:
        """Liefert synthetische Wetterdaten für ein ganzes Jahr.

        Args:
            year: Simulationsjahr (bestimmt Schaltjahr und Datum-Range).
            coords: Feldkoordinate (ignoriert – deterministisch ohne
                Standortbezug, aber für Protocol-Kompatibilität akzeptiert).

        Returns:
            Liste von ``WeatherData`` für 1.1.–31.12. des Jahres.
        """
        rng = random.Random(self.seed ^ year)

        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
        n_days = (end - start).days + 1

        data: list[WeatherData] = []
        for i in range(n_days):
            date = start + datetime.timedelta(days=i)
            day_of_year = date.timetuple().tm_yday

            # Saisonale Temperatur: Sinus-Kurve, Peak bei Tag ~200 (Mitte Juli).
            # Basis 10°C, Amplitude 15°C → Range ca. -5°C bis 25°C (Durchschnitt).
            temp_avg = 10.0 + 15.0 * math.sin(2.0 * math.pi * (day_of_year - 80) / 365.0)
            temp_noise = rng.uniform(-3.0, 3.0)
            temp_max = temp_avg + 5.0 + temp_noise
            temp_min = temp_avg - 5.0 + temp_noise

            # Niederschlag: 25% Wahrscheinlichkeit, im Sommer (Mai–Aug) 40%.
            month = date.month
            rain_prob = 0.40 if month in (5, 6, 7, 8) else 0.25
            if rng.random() < rain_prob:
                precipitation = rng.uniform(1.0, 15.0)
                if month in (6, 7, 8):
                    precipitation *= 1.3  # Sommerregen stärker
            else:
                precipitation = 0.0

            # Wind: Basis 3 m/s, im Herbst/Winter etwas windiger.
            wind_base = 3.0
            if month in (10, 11, 12, 1, 2):
                wind_base = 5.0
            wind_speed = wind_base + rng.uniform(-1.5, 2.5)
            wind_speed = max(0.0, wind_speed)

            # Bodenfeuchte: korreliert negativ mit Temperatur.
            # Winter: 60-80% nFK, Sommer: 30-50% nFK.
            moisture_base = 70.0 - 0.8 * (temp_avg + 5.0)
            moisture = moisture_base + rng.uniform(-5.0, 5.0)
            moisture = max(15.0, min(95.0, moisture))

            data.append(
                WeatherData(
                    date=date,
                    precipitation_mm=round(precipitation, 2),
                    wind_speed_ms=round(wind_speed, 2),
                    temperature_max_c=round(temp_max, 1),
                    temperature_min_c=round(temp_min, 1),
                    soil_moisture_pct_nfk=round(moisture, 1),
                )
            )

        return data
