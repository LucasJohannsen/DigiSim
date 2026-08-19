"""DigiZert Data-Client für SoilMoistureData (D3) und WeatherData (D4).

Überträgt tägliche Bodenfeuchte- und Wetterdaten an die DigiZert-API.
Die Endpoints D3/D4 sind noch in Entwicklung (Issues #56/#57) – dieser
Client wird über den Feature-Flag ``DIGIZERT_DATA_TRANSFER_ENABLED`` aktiviert.

API-Spec (Stand Issues #56/#57):
    POST /sensors/           – SoilMoisture-Sensor anlegen (field, depth)
    POST /weather-sensors/   – WeatherSensor anlegen (field)
    POST /soil-moisture/     – Bulk SoilMoistureData (field, depth, measurements)
    POST /weather/           – Bulk WeatherData (field, measurements)

Alle Endpoints sind idempotent (wiederholtes Anlegen/Senden gibt
Bestehendes zurück bzw. überschreibt nicht).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import httpx

from utils.logger import get_logger

__all__ = [
    "SoilMoistureMeasurement",
    "WeatherMeasurement",
    "DigiZertDataClient",
]

logger = get_logger("digizert_data_client")


@dataclass(frozen=True)
class SoilMoistureMeasurement:
    """Ein einzelner Bodenfeuchte-Messwert für einen Tag.

    Attributes:
        timestamp: Datum/Uhrzeit der Messung (UTC).
        vwc: Volumetric Water Content in % (z. B. 28.5 für 28.5%).
    """

    timestamp: datetime.datetime
    vwc: float


@dataclass(frozen=True)
class WeatherMeasurement:
    """Ein einzelner Wetter-Messwert für einen Tag.

    Attributes:
        timestamp: Datum/Uhrzeit der Messung (UTC).
        rain_fall: Niederschlag in mm/Tag.
        temperature: Temperatur in °C (optional, für Evapotranspiration).
    """

    timestamp: datetime.datetime
    rain_fall: float
    temperature: float | None = None


class DigiZertDataClient:
    """Client für SoilMoistureData- und WeatherData-Transfer an DigiZert.

    Feature-Flag: ``enabled=False`` (default) – alle Methoden sind No-Ops.
    Setze ``enabled=True`` sobald D3/D4 auf DigiZert-Seite ready sind.
    """

    def __init__(
        self,
        api_base_url: str,
        api_token: str,
        timeout: int = 30,
        enabled: bool = False,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.enabled = enabled

    # ------------------------------------------------------------------
    # Sensor-Anlage (idempotent)
    # ------------------------------------------------------------------

    def ensure_soil_moisture_sensor(
        self,
        field_id: int,
        depth: int,
    ) -> None:
        """Legt einen SoilMoisture-Sensor an (idempotent).

        Args:
            field_id: DigiZert Field-ID.
            depth: Messtiefe in cm (15 oder 30).
        """
        if not self.enabled:
            return

        url = f"{self.api_base_url}/sensors/"
        payload = {
            "field": field_id,
            "sensor_type": "soil_moisture",
            "name": f"DigiSim-Sensor-{depth}cm",
            "depth": depth,
        }
        self._post_idempotent(url, payload, context=f"soil_sensor field={field_id} depth={depth}")

    def ensure_weather_sensor(self, field_id: int) -> None:
        """Legt einen WeatherSensor an (idempotent).

        Args:
            field_id: DigiZert Field-ID.
        """
        if not self.enabled:
            return

        url = f"{self.api_base_url}/weather-sensors/"
        payload = {
            "field": field_id,
            "name": "DigiSim-Weather",
            "sensor_type": "rain",
        }
        self._post_idempotent(url, payload, context=f"weather_sensor field={field_id}")

    # ------------------------------------------------------------------
    # Bulk-Data-Transfer
    # ------------------------------------------------------------------

    def send_soil_moisture_data(
        self,
        field_id: int,
        depth: int,
        measurements: list[SoilMoistureMeasurement],
    ) -> None:
        """Sendet SoilMoistureData als Bulk-Insert.

        Args:
            field_id: DigiZert Field-ID.
            depth: Messtiefe in cm (15 oder 30).
            measurements: Liste von Tages-Messwerten.
        """
        if not self.enabled or not measurements:
            return

        url = f"{self.api_base_url}/soil-moisture/"
        payload = {
            "field": field_id,
            "depth": depth,
            "measurements": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "vwc": round(m.vwc, 2),
                }
                for m in measurements
            ],
        }
        self._post_bulk(
            url,
            payload,
            context=f"soil_moisture field={field_id} depth={depth} n={len(measurements)}",
        )

    def send_weather_data(
        self,
        field_id: int,
        measurements: list[WeatherMeasurement],
    ) -> None:
        """Sendet WeatherData als Bulk-Insert.

        Args:
            field_id: DigiZert Field-ID.
            measurements: Liste von Tages-Messwerten.
        """
        if not self.enabled or not measurements:
            return

        url = f"{self.api_base_url}/weather/"
        payload = {
            "field": field_id,
            "measurements": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "rain_fall": round(m.rain_fall, 2),
                    **({"temperature": m.temperature} if m.temperature is not None else {}),
                }
                for m in measurements
            ],
        }
        self._post_bulk(url, payload, context=f"weather field={field_id} n={len(measurements)}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }

    def _post_idempotent(self, url: str, payload: dict, context: str) -> None:
        """POST für idempotente Sensor-Anlage. 400/409 bei Duplikat ignorieren."""
        try:
            response = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            # 201 = neu angelegt, 200/409 = bereits vorhanden → ok
            if response.status_code in (200, 201):
                logger.info("Sensor ensured", context=context, status=response.status_code)
            elif response.status_code in (400, 409):
                logger.info("Sensor already exists", context=context, status=response.status_code)
            else:
                response.raise_for_status()
        except httpx.RequestError as exc:
            logger.error("Failed to ensure sensor", context=context, error=str(exc))

    def _post_bulk(self, url: str, payload: dict, context: str) -> None:
        """POST für Bulk-Data-Transfer. Loggt Fehler, crasht nicht."""
        try:
            response = httpx.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            response.raise_for_status()
            logger.info("Bulk data sent", context=context, status=response.status_code)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Bulk data transfer failed",
                context=context,
                status_code=exc.response.status_code,
                error=str(exc),
                response_body=exc.response.text[:500] if exc.response.text else None,
            )
        except httpx.RequestError as exc:
            logger.error("Bulk data connection failed", context=context, error=str(exc))
