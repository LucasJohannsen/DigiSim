"""Unit-Tests für die Wetter-Regel-Checker (KAR-030 … KAR-035).

Test-first: Diese Tests wurden vor der Implementierung der Handler
geschrieben und prüfen die 4 Check-Types direkt über ``check_rule``
mit einem ``weather_lookup``.

Check-Types:
- ``weather_condition`` (KAR-030, KAR-035)
- ``soil_condition`` (KAR-032, KAR-033)
- ``forecast_condition`` (KAR-031)
- ``irrigation_trigger`` (KAR-034)
"""

from __future__ import annotations

import datetime

import pytest

from services.weather_service import WeatherData
from tests.plausibility.rule_checks import (
    check_rule,
    hard_violations,
    soft_violations,
)

__all__ = [
    "TestWeatherCondition",
    "TestSoilCondition",
    "TestForecastCondition",
    "TestIrrigationTrigger",
]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _wd(
    date: datetime.date,
    *,
    precip: float = 0.0,
    wind: float = 3.0,
    t_max: float = 20.0,
    t_min: float = 10.0,
    moisture: float = 60.0,
) -> WeatherData:
    """Baue ein WeatherData-Objekt mit Defaults."""
    return WeatherData(
        date=date,
        precipitation_mm=precip,
        wind_speed_ms=wind,
        temperature_max_c=t_max,
        temperature_min_c=t_min,
        soil_moisture_pct_nfk=moisture,
    )


def _event(
    worktype: int,
    date: datetime.date,
    *,
    category: int | None = None,
    amount: float = 0.0,
) -> dict[str, object]:
    """Baue ein normalisiertes Event-Dict."""
    return {
        "worktype": worktype,
        "start": datetime.datetime.combine(date, datetime.time(8, 0)),
        "end": None,
        "category": category,
        "amount": amount,
        "unit": None,
        "area": 0.0,
        "name": None,
        "worktype_text": None,
        "raw": None,
    }


# ---------------------------------------------------------------------------
# weather_condition (KAR-030, KAR-035)
# ---------------------------------------------------------------------------


class TestWeatherCondition:
    """KAR-030 / KAR-035: weather_condition Checker."""

    @pytest.fixture
    def rule_kar030(self) -> dict[str, object]:
        return {
            "id": "KAR-030",
            "category": "weather",
            "severity": "hard",
            "check": {
                "type": "weather_condition",
                "worktype": 14,
                "max_precipitation_mm_day": 5,
                "max_wind_ms": 5,
            },
        }

    @pytest.fixture
    def rule_kar035(self) -> dict[str, object]:
        return {
            "id": "KAR-035",
            "category": "weather",
            "severity": "soft",
            "check": {
                "type": "weather_condition",
                "worktype": 14,
                "application_category": 26,
                "max_temperature_c": 30,
                "max_precipitation_mm_day": 1,
            },
        }

    def test_no_violation_on_good_weather(self, rule_kar030: dict[str, object]) -> None:
        """KAR-030: Spritzen bei trockenem, windstillem Wetter → keine Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, precip=0.0, wind=3.0)}
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar030, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_violation_on_rain(self, rule_kar030: dict[str, object]) -> None:
        """KAR-030: Spritzen bei >5 mm Niederschlag → harte Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, precip=6.0, wind=3.0)}
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar030, cycles, weather_lookup=lookup)
        hard = hard_violations(result)
        assert len(hard) == 1
        assert "Niederschlag" in hard[0].message or "precip" in hard[0].message.lower()

    def test_violation_on_wind(self, rule_kar030: dict[str, object]) -> None:
        """KAR-030: Spritzen bei Wind >5 m/s → harte Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, precip=0.0, wind=6.0)}
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar030, cycles, weather_lookup=lookup)
        hard = hard_violations(result)
        assert len(hard) == 1
        assert "Wind" in hard[0].message or "wind" in hard[0].message.lower()

    def test_no_violation_other_worktype(self, rule_kar030: dict[str, object]) -> None:
        """KAR-030: Events mit anderem Worktype werden ignoriert."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, precip=10.0, wind=10.0)}
        cycles = [[_event(26, d)]]
        result = check_rule(rule_kar030, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_kar035_violation_on_heat(self, rule_kar035: dict[str, object]) -> None:
        """KAR-035: Sikkation (cat=26) bei Tmax >30°C → weiche Verletzung."""
        d = datetime.date(2026, 7, 15)
        lookup = {d: _wd(d, t_max=32.0, precip=0.0)}
        cycles = [[_event(14, d, category=26)]]
        result = check_rule(rule_kar035, cycles, weather_lookup=lookup)
        soft = soft_violations(result)
        assert len(soft) == 1
        assert "Temperatur" in soft[0].message or "temp" in soft[0].message.lower()

    def test_kar035_ignores_non_sikkation(self, rule_kar035: dict[str, object]) -> None:
        """KAR-035: Spritzen mit cat != 26 wird ignoriert (nur Sikkation)."""
        d = datetime.date(2026, 7, 15)
        lookup = {d: _wd(d, t_max=32.0, precip=0.0)}
        cycles = [[_event(14, d, category=27)]]
        result = check_rule(rule_kar035, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_kar035_violation_on_rain(self, rule_kar035: dict[str, object]) -> None:
        """KAR-035: Sikkation bei >1 mm Niederschlag → weiche Verletzung."""
        d = datetime.date(2026, 7, 15)
        lookup = {d: _wd(d, t_max=20.0, precip=2.0)}
        cycles = [[_event(14, d, category=26)]]
        result = check_rule(rule_kar035, cycles, weather_lookup=lookup)
        soft = soft_violations(result)
        assert len(soft) == 1

    def test_missing_weather_data_no_violation(self, rule_kar030: dict[str, object]) -> None:
        """Kein Wetterdatum im Lookup → kein Fehler (graceful degradation)."""
        d = datetime.date(2026, 6, 1)
        lookup: dict[datetime.date, WeatherData] = {}
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar030, cycles, weather_lookup=lookup)
        assert result.violations == []


# ---------------------------------------------------------------------------
# soil_condition (KAR-032, KAR-033)
# ---------------------------------------------------------------------------


class TestSoilCondition:
    """KAR-032 / KAR-033: soil_condition Checker."""

    @pytest.fixture
    def rule_kar032(self) -> dict[str, object]:
        return {
            "id": "KAR-032",
            "category": "weather",
            "severity": "hard",
            "check": {
                "type": "soil_condition",
                "worktypes": [5, 6, 7, 26, 28],
                "max_soil_moisture_pct_nfk": 90,
                "max_previous_day_precipitation_mm": 10,
            },
        }

    @pytest.fixture
    def rule_kar033(self) -> dict[str, object]:
        return {
            "id": "KAR-033",
            "category": "weather",
            "severity": "soft",
            "check": {
                "type": "soil_condition",
                "worktype": 26,
                "min_soil_temperature_c": 8,
            },
        }

    def test_kar032_no_violation_dry_soil(self, rule_kar032: dict[str, object]) -> None:
        """KAR-032: Bodenbearbeitung bei trockenem Boden → keine Verletzung."""
        d = datetime.date(2026, 4, 15)
        prev = d - datetime.timedelta(days=1)
        lookup = {
            d: _wd(d, moisture=50.0, precip=0.0),
            prev: _wd(prev, moisture=50.0, precip=0.0),
        }
        cycles = [[_event(6, d)]]
        result = check_rule(rule_kar032, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_kar032_violation_wet_soil(self, rule_kar032: dict[str, object]) -> None:
        """KAR-032: Bodenbearbeitung bei nFK >90% → harte Verletzung."""
        d = datetime.date(2026, 4, 15)
        lookup = {d: _wd(d, moisture=95.0, precip=0.0)}
        cycles = [[_event(6, d)]]
        result = check_rule(rule_kar032, cycles, weather_lookup=lookup)
        hard = hard_violations(result)
        assert len(hard) == 1
        assert "nFK" in hard[0].message or "moisture" in hard[0].message.lower()

    def test_kar032_violation_prev_day_precip(self, rule_kar032: dict[str, object]) -> None:
        """KAR-032: Bodenbearbeitung nach Vortagesniederschlag >10 mm → Verletzung."""
        d = datetime.date(2026, 4, 15)
        prev = d - datetime.timedelta(days=1)
        lookup = {
            d: _wd(d, moisture=50.0, precip=0.0),
            prev: _wd(prev, moisture=50.0, precip=12.0),
        }
        cycles = [[_event(7, d)]]
        result = check_rule(rule_kar032, cycles, weather_lookup=lookup)
        hard = hard_violations(result)
        assert len(hard) == 1
        assert "Vortag" in hard[0].message or "precip" in hard[0].message.lower()

    def test_kar032_ignores_other_worktype(self, rule_kar032: dict[str, object]) -> None:
        """KAR-032: Worktype nicht in Liste → ignoriert."""
        d = datetime.date(2026, 4, 15)
        lookup = {d: _wd(d, moisture=95.0, precip=20.0)}
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar032, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_kar033_violation_cold_soil(self, rule_kar033: dict[str, object]) -> None:
        """KAR-033: Legen bei Bodentemp <8°C → weiche Verletzung."""
        d = datetime.date(2026, 3, 1)
        # Bodentemp ≈ (t_max + t_min) / 2 = (6 + 0) / 2 = 3°C < 8°C
        lookup = {d: _wd(d, t_max=6.0, t_min=0.0)}
        cycles = [[_event(26, d)]]
        result = check_rule(rule_kar033, cycles, weather_lookup=lookup)
        soft = soft_violations(result)
        assert len(soft) == 1
        assert "Bodentemp" in soft[0].message or "temp" in soft[0].message.lower()

    def test_kar033_no_violation_warm_soil(self, rule_kar033: dict[str, object]) -> None:
        """KAR-033: Legen bei Bodentemp >=8°C → keine Verletzung."""
        d = datetime.date(2026, 4, 20)
        # Bodentemp ≈ (15 + 7) / 2 = 11°C >= 8°C
        lookup = {d: _wd(d, t_max=15.0, t_min=7.0)}
        cycles = [[_event(26, d)]]
        result = check_rule(rule_kar033, cycles, weather_lookup=lookup)
        assert result.violations == []


# ---------------------------------------------------------------------------
# forecast_condition (KAR-031)
# ---------------------------------------------------------------------------


class TestForecastCondition:
    """KAR-031: forecast_condition Checker."""

    @pytest.fixture
    def rule_kar031(self) -> dict[str, object]:
        return {
            "id": "KAR-031",
            "category": "weather",
            "severity": "hard",
            "check": {
                "type": "forecast_condition",
                "worktype": 15,
                "forecast_days": 4,
                "max_cumulative_precipitation_mm": 10,
            },
        }

    def test_no_violation_dry_forecast(self, rule_kar031: dict[str, object]) -> None:
        """KAR-031: Beregnung bei trockener Prognose → keine Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {
            d + datetime.timedelta(days=i): _wd(d + datetime.timedelta(days=i), precip=0.0)
            for i in range(5)
        }
        cycles = [[_event(15, d)]]
        result = check_rule(rule_kar031, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_violation_wet_forecast(self, rule_kar031: dict[str, object]) -> None:
        """KAR-031: Beregnung bei >10 mm kumuliert in 4 Tagen → Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {
            d: _wd(d, precip=0.0),
            d + datetime.timedelta(days=1): _wd(d + datetime.timedelta(days=1), precip=4.0),
            d + datetime.timedelta(days=2): _wd(d + datetime.timedelta(days=2), precip=4.0),
            d + datetime.timedelta(days=3): _wd(d + datetime.timedelta(days=3), precip=4.0),
            d + datetime.timedelta(days=4): _wd(d + datetime.timedelta(days=4), precip=0.0),
        }
        cycles = [[_event(15, d)]]
        result = check_rule(rule_kar031, cycles, weather_lookup=lookup)
        hard = hard_violations(result)
        assert len(hard) == 1
        assert "Prognose" in hard[0].message or "cumul" in hard[0].message.lower()

    def test_ignores_other_worktype(self, rule_kar031: dict[str, object]) -> None:
        """KAR-031: Nicht-Beregnung wird ignoriert."""
        d = datetime.date(2026, 6, 1)
        lookup = {
            d + datetime.timedelta(days=i): _wd(d + datetime.timedelta(days=i), precip=20.0)
            for i in range(5)
        }
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar031, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_partial_forecast_no_violation(self, rule_kar031: dict[str, object]) -> None:
        """KAR-031: Nur 2 von 4 Tagen im Lookup, Summe <10 → keine Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {
            d + datetime.timedelta(days=1): _wd(d + datetime.timedelta(days=1), precip=3.0),
            d + datetime.timedelta(days=2): _wd(d + datetime.timedelta(days=2), precip=3.0),
        }
        cycles = [[_event(15, d)]]
        result = check_rule(rule_kar031, cycles, weather_lookup=lookup)
        assert result.violations == []


# ---------------------------------------------------------------------------
# irrigation_trigger (KAR-034)
# ---------------------------------------------------------------------------


class TestIrrigationTrigger:
    """KAR-034: irrigation_trigger Checker."""

    @pytest.fixture
    def rule_kar034(self) -> dict[str, object]:
        return {
            "id": "KAR-034",
            "category": "weather",
            "severity": "hard",
            "check": {
                "type": "irrigation_trigger",
                "worktype": 15,
                "trigger_pct_nfk_early": 50,
                "trigger_pct_nfk_late": 40,
            },
        }

    def test_no_violation_dry_trigger(self, rule_kar034: dict[str, object]) -> None:
        """KAR-034: Beregnung bei nFK <50% → keine Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, moisture=35.0)}
        cycles = [[_event(15, d)]]
        result = check_rule(rule_kar034, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_violation_wet_trigger(self, rule_kar034: dict[str, object]) -> None:
        """KAR-034: Beregnung bei nFK >=50% → harte Verletzung."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, moisture=55.0)}
        cycles = [[_event(15, d)]]
        result = check_rule(rule_kar034, cycles, weather_lookup=lookup)
        hard = hard_violations(result)
        assert len(hard) == 1
        assert "nFK" in hard[0].message or "trigger" in hard[0].message.lower()

    def test_ignores_other_worktype(self, rule_kar034: dict[str, object]) -> None:
        """KAR-034: Nicht-Beregnung wird ignoriert."""
        d = datetime.date(2026, 6, 1)
        lookup = {d: _wd(d, moisture=80.0)}
        cycles = [[_event(14, d)]]
        result = check_rule(rule_kar034, cycles, weather_lookup=lookup)
        assert result.violations == []

    def test_missing_weather_no_violation(self, rule_kar034: dict[str, object]) -> None:
        """KAR-034: Kein Wetterdatum → keine Verletzung (graceful)."""
        d = datetime.date(2026, 6, 1)
        lookup: dict[datetime.date, WeatherData] = {}
        cycles = [[_event(15, d)]]
        result = check_rule(rule_kar034, cycles, weather_lookup=lookup)
        assert result.violations == []


# ---------------------------------------------------------------------------
# Abwärtskompatibilität: weather_lookup=None → skip
# ---------------------------------------------------------------------------


class TestWeatherSkipFallback:
    """Ohne weather_lookup müssen Wetterregeln weiterhin skippen."""

    @pytest.mark.parametrize(
        "rule_id",
        ["KAR-030", "KAR-031", "KAR-032", "KAR-033", "KAR-034", "KAR-035"],
    )
    def test_skip_without_lookup(self, rule_id: str) -> None:
        rule: dict[str, object] = {
            "id": rule_id,
            "category": "weather",
            "severity": "hard",
            "check": {"type": "weather_condition", "worktype": 14},
        }
        result = check_rule(rule, [[]], weather_lookup=None)
        assert result.weather_skip is True
        assert result.skip_reason is not None
