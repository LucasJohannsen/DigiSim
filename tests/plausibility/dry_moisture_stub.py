"""Synthetischer Moisture-Stub für die Dry-Plausibilitätssuite (Issue #71).

``DryMoistureDataService`` implementiert die Schnittstelle von
``MoistureDataService`` (services/moisture_service.py – Methode
``get_moisture_data(**kwargs)``), liefert aber **deterministische,
synthetische** Bodenfeuchte-Daten ohne Netzwerk- oder Dateizugriff.

Der Stub erzeugt einen **abfallenden** nFK-Verlauf über die
Vegetationsperiode (Mai–September): ein Sägezahn-Muster, das von 45 %
nFK täglich um 1.5 % fällt (Floor 30 %, dann Reset auf 45 %). Dadurch
sinkt die ``updated_moisture`` nach jeder Beregnung innerhalb von ~4
Tagen wieder unter den Trigger-Schwellwert (50 %), sodass der
``IrrigationSimulator`` **mehrere** Beregnungs-Events erzeugt – mit
Intervallen von ≥ 4 Tagen (KAR-022). Außerhalb der Vegetationsperiode
liegt der nFK bei 60 % (über Schwellwert → kein Trigger).

Das ``moisture_data``-Array deckt das gesamte Kalenderjahr (1.1.–31.12.)
ab, da ``IrrigationSimulator.get_status_for_day`` via
``day = date.timetuple().tm_yday`` auf beliebige Tage zugreift und bei
``day >= len(self.moisture)`` einen ``IndexError`` wirft.
"""

from __future__ import annotations

import datetime
from typing import Any

from models.sim_context import SimContext
from services.moisture_service import MoistureDataService

__all__ = ["DryMoistureDataService"]


# Schwellwert des IrrigationSimulator (services/irrigation_service.py).
_MIN_MOISTURE_LEVEL = 50  # % nFK

# Vegetationsperiode: Mai–September (Monate 5–9).
_VEG_MONTHS = frozenset(range(5, 10))

# Synthetische nFK-Werte.
_WET_MOISTURE = 60.0  # % nFK – über Schwellwert → kein Trigger

# Sägezahn-Parameter für die Vegetationsperiode.
_SAWTOOTH_START = 45.0  # % nFK – Startwert (knapp über Trigger-Defizit)
_SAWTOOTH_FLOOR = 30.0  # % nFK – Floor, dann Reset auf Start
_SAWTOOTH_STEP = 1.5  # % nFK/Tag – täglicher Abfall


def _sawtooth_moisture(day_index_in_veg: int) -> float:
    """Sägezahn-Verlauf für einen Tag in der Vegetationsperiode.

    Der nFK fällt von ``_SAWTOOTH_START`` täglich um ``_SAWTOOTH_STEP``,
    bis der Floor erreicht ist, dann Reset auf ``_SAWTOOTH_START``.

    Args:
        day_index_in_veg: 0-basierter Index des Tages innerhalb der
            Vegetationsperiode (Mai–Sep).

    Returns:
        nFK-Wert in % für diesen Tag.
    """
    cycle_len = int((_SAWTOOTH_START - _SAWTOOTH_FLOOR) / _SAWTOOTH_STEP) + 1
    pos = day_index_in_veg % cycle_len
    return _SAWTOOTH_START - pos * _SAWTOOTH_STEP


class DryMoistureDataService(MoistureDataService):
    """Deterministischer Stub für ``MoistureDataService``.

    Liefert synthetisch trockene Bodenfeuchte-Daten (Sägezahn 45→30 % nFK
    in Mai–Sep, 60 % sonst) über das gesamte Kalenderjahr. Kein Netzwerk,
    kein Zufall – zwei Aufrufe mit gleichem Jahr liefern identische Daten.

    Erbt von ``MoistureDataService`` für Schnittstellenkompatibilität
    (Typ-Sicherheit im Factory-Hook), überschreibt aber ``get_moisture_data``
    vollständig – kein Netzwerk-, Datei- oder Zufallszugriff.
    """

    def __init__(self, context: SimContext, **kwargs: Any) -> None:
        super().__init__(context=context, **kwargs)

    def get_moisture_data(self, **kwargs: Any) -> dict[str, Any]:
        """Liefert synthetische Bodenfeuchte-Daten für ein ganzes Jahr.

        Args:
            year: Simulationsjahr (default 2022, analog zum echten Service).
            depth_range: Tiefenbereich (ignoriert, für Kompatibilität).

        Returns:
            Dict mit Keys ``coords`` (feste Koordinate), ``dates``
            (Liste von ``datetime.date``, 1.1.–31.12.) und
            ``moisture_data`` (Liste von float, Sägezahn in Mai–Sep,
            60 % sonst).
        """
        year: int = int(kwargs.get("year", 2022))

        # 1.1. bis 31.12. des Jahres (berücksichtigt Schaltjahre).
        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
        n_days = (end - start).days + 1

        dates: list[datetime.date] = [
            start + datetime.timedelta(days=i) for i in range(n_days)
        ]

        # Sägezahn-Verlauf in der Vegetationsperiode, konstant 60 % sonst.
        veg_day_index = 0
        moisture: list[float] = []
        for d in dates:
            if d.month in _VEG_MONTHS:
                moisture.append(_sawtooth_moisture(veg_day_index))
                veg_day_index += 1
            else:
                moisture.append(_WET_MOISTURE)

        # Feste, deterministische Koordinate (keine Zufallsauswahl, kein
        # Netzwerk). Werte orientieren sich an einer typischen deutschen
        # Feld-Koordinate (WGS84).
        return {
            "coords": [50.0, 10.0],
            "dates": dates,
            "moisture_data": moisture,
        }
