"""ISIP-Infektionsdruck-Service (P4, Issue #59).

Ruft ISIP/Simphyt3-Infektionsdruck-Daten von der DigiZert-API ab und
cached sie lokal. DigiSim nutzt ``is_justified_window`` um Fungizid-
Spritzungen druck-gesteuert zu verschieben (statt deterministisch).

Endpoint:
    GET /api/v1/simulator/isip/<field_id>/
    ?start_date=...&end_date=...  (Batch)
    ?date=...                      (Single-Day)

Feature-Flag: ``ISIP_PRESSURE_GATING_ENABLED`` (default: false).
Falls deaktiviert oder DigiZert nicht erreichbar → deterministisch.
"""

from __future__ import annotations

import datetime

import httpx

from utils.logger import get_logger

__all__ = ["ISIPDayData", "ISIPPressureService"]

logger = get_logger("isip_pressure_service")

# Application-Category für Fungizide (DropdownData pk=27).
FUNGIZID_CATEGORY = 27


class ISIPDayData:
    """ISIP-Daten für einen einzelnen Tag.

    Attributes:
        date: Datum des Tages.
        infection_pressure: Infektionsdruck (0-100).
        infection_action: Handlungsbedarf (0=keiner, 1=mittel, 2=hoch).
        is_justified_window: True wenn Tag innerhalb ±2 Tagen eines
            Risiko-Tags (infection_action > 0).
    """

    __slots__ = ("date", "infection_pressure", "infection_action", "is_justified_window")

    def __init__(
        self,
        date: datetime.date,
        infection_pressure: float,
        infection_action: int,
        is_justified_window: bool,
    ) -> None:
        self.date = date
        self.infection_pressure = infection_pressure
        self.infection_action = infection_action
        self.is_justified_window = is_justified_window


class ISIPPressureService:
    """Service für ISIP-Infektionsdruck-Daten mit lokalem Caching.

    Cacht ISIP-Daten pro Field-ID. Im Batch-Modus (Bootstrap) wird die
    ganze Saison auf einmal abgerufen; im Single-Day-Modus (Daily-Tick)
    wird ein einzelner Tag abgefragt (oder aus dem Batch-Cache bedient).

    Fallback: Falls DigiZert nicht erreichbar → ``is_justified_window=True``
    für alle Tage (deterministisches Verhalten, Spritzungen werden nicht
    blockiert).
    """

    def __init__(
        self,
        api_base_url: str,
        api_token: str,
        field_id: int,
        timeout: int = 30,
        enabled: bool = False,
    ) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token
        self.field_id = field_id
        self.timeout = timeout
        self.enabled = enabled

        # Cache: date → ISIPDayData
        self._cache: dict[datetime.date, ISIPDayData] = {}

    def fetch_season(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> None:
        """Lädt ISIP-Daten für die ganze Saison (Batch-Modus) in den Cache.

        Wird typischerweise beim Bootstrap aufgerufen.

        Args:
            start_date: Startdatum der Saison.
            end_date: Enddatum der Saison.
        """
        if not self.enabled:
            return

        url = f"{self.api_base_url}/isip/{self.field_id}/"
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        try:
            response = httpx.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            for day in data.get("daily", []):
                day_date = datetime.date.fromisoformat(day["date"])
                self._cache[day_date] = ISIPDayData(
                    date=day_date,
                    infection_pressure=day.get("infection_pressure", 0.0),
                    infection_action=day.get("infection_action", 0),
                    is_justified_window=day.get("is_justified_window", False),
                )
            logger.info(
                "ISIP season data fetched",
                field_id=self.field_id,
                days=len(self._cache),
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                "ISIP season fetch failed, using deterministic fallback",
                field_id=self.field_id,
                error=str(exc),
            )

    def is_justified(self, date: datetime.date) -> bool:
        """Prüft ob eine Fungizid-Spritzung an diesem Tag gerechtfertigt ist.

        Fallback: Falls ISIP nicht verfügbar → True (deterministisch).

        Args:
            date: Das zu prüfende Datum.

        Returns:
            True wenn ``is_justified_window=True`` oder ISIP nicht verfügbar.
        """
        if not self.enabled:
            return True

        # Aus Cache bedienen
        if date in self._cache:
            return self._cache[date].is_justified_window

        # Single-Day-Modus: einzelnen Tag nachladen
        url = f"{self.api_base_url}/isip/{self.field_id}/"
        params = {"date": date.isoformat()}

        try:
            response = httpx.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            daily = data.get("daily", [])
            if daily:
                day = daily[0]
                day_date = datetime.date.fromisoformat(day["date"])
                isip_day = ISIPDayData(
                    date=day_date,
                    infection_pressure=day.get("infection_pressure", 0.0),
                    infection_action=day.get("infection_action", 0),
                    is_justified_window=day.get("is_justified_window", False),
                )
                self._cache[day_date] = isip_day
                return isip_day.is_justified_window
            return True  # Keine Daten → deterministisch
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning(
                "ISIP single-day fetch failed, using deterministic fallback",
                field_id=self.field_id,
                date=str(date),
                error=str(exc),
            )
            return True

    def find_next_justified_date(
        self,
        start_date: datetime.date,
        max_days: int = 7,
    ) -> datetime.date | None:
        """Findet den nächsten Tag ab start_date mit is_justified_window=true.

        Args:
            start_date: Startdatum der Suche.
            max_days: Maximale Suchreichweite in Tagen.

        Returns:
            Nächstes justified Datum, oder None falls keines innerhalb
            von max_days gefunden wurde.
        """
        for offset in range(max_days + 1):
            check_date = start_date + datetime.timedelta(days=offset)
            if self.is_justified(check_date):
                return check_date
        return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
        }
