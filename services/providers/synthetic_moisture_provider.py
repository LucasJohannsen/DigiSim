"""Synthetischer Bodenfeuchte-Provider für D3 (SoilMoistureData).

Generiert realistische, zeitlich variable VWC-Werte für 15cm und 30cm Tiefe
mit saisonalem Muster (Feuchter im Winter, trockener im Sommer).

Wird verwendet, wenn DWD-Daten nicht verfügbar sind oder nur -9999
(Sentinel) enthalten. Deterministisch (Seed-basiert).

Saisonales Muster (analog SyntheticWeatherDataProvider):
- 15cm: stärkere Schwankung (Oberflächennähe, Verdunstung)
- 30cm: gedämpfter, verzögert (tiefere Schicht reagiert langsamer)
"""

from __future__ import annotations

import datetime
import math
import random

__all__ = ["SyntheticMoistureProvider"]


class SyntheticMoistureProvider:
    """Deterministischer synthetischer Bodenfeuchte-Generator.

    Liefert tägliche VWC-Werte (%) für 15cm und 30cm Tiefe.
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def get_moisture_data_dual_depth(
        self,
        year: int,
        coords: tuple[float, float] | None = None,
    ) -> dict:
        """Liefert synthetische Bodenfeuchte für 15cm + 30cm.

        Args:
            year: Simulationsjahr.
            coords: Feldkoordinate (ignoriert, für Kompatibilität).

        Returns:
            dict mit 'coords', 'dates', 'depth_15', 'depth_30'.
        """
        rng = random.Random(self.seed ^ year)

        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
        n_days = (end - start).days + 1

        dates: list[datetime.date] = []
        depth_15: list[float] = []
        depth_30: list[float] = []

        for i in range(n_days):
            date = start + datetime.timedelta(days=i)
            day_of_year = date.timetuple().tm_yday
            dates.append(date)

            # Saisonale Temperatur (analog SyntheticWeatherDataProvider)
            temp_avg = 10.0 + 15.0 * math.sin(
                2.0 * math.pi * (day_of_year - 80) / 365.0
            )

            # 15cm: stärkere Schwankung, korreliert mit Verdunstung
            # Winter: 55-75% VWC, Sommer: 25-45% VWC
            moisture_15_base = 65.0 - 0.8 * (temp_avg + 5.0)
            moisture_15 = moisture_15_base + rng.uniform(-6.0, 6.0)
            moisture_15 = max(15.0, min(85.0, moisture_15))
            depth_15.append(round(moisture_15, 1))

            # 30cm: gedämpfter, verzögert (~10 Tage Shift), weniger Schwankung
            temp_avg_shifted = 10.0 + 15.0 * math.sin(
                2.0 * math.pi * (day_of_year - 90) / 365.0  # 10 Tage später
            )
            moisture_30_base = 68.0 - 0.6 * (temp_avg_shifted + 5.0)
            moisture_30 = moisture_30_base + rng.uniform(-3.0, 3.0)
            moisture_30 = max(20.0, min(80.0, moisture_30))
            depth_30.append(round(moisture_30, 1))

        return {
            "coords": [coords[0], coords[1]] if coords else [52.5, 9.9],
            "dates": dates,
            "depth_15": depth_15,
            "depth_30": depth_30,
        }
