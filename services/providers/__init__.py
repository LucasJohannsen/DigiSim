"""Provider-Implementierungen für Wetterdaten (P3-1, Issue #79).

Produktive und synthetische Provider für das ``WeatherDataProvider``-Protocol.
"""

from services.providers.dwd_weather_provider import DWDWeatherDataProvider
from services.providers.synthetic_weather_provider import (
    SyntheticWeatherDataProvider,
)

__all__ = [
    "DWDWeatherDataProvider",
    "SyntheticWeatherDataProvider",
]
