"""Tests für die Wetter-Guard-Regeln (MS6 P3-2, Issue #80).

Unit-Tests für die drei neuen Guard-Klassen:
- ``WeatherConditionGuard`` (KAR-030, KAR-035): Niederschlag/Wind/Temperatur
- ``SoilConditionGuard`` (KAR-032): Bodenfeuchte + Vortagesniederschlag
- ``ForecastConditionGuard`` (KAR-031): kumulativer Prognose-Niederschlag

Die Guards sind datengetrieben (``from_config``) und folgen dem
``GuardRule``-Protocol. Sie sind deaktiviert, wenn
``cycle_context.current_weather``/``weather_forecast`` None ist
(Abwärtskompatibilität ohne P3-1).
"""

from __future__ import annotations

import datetime

import pytest

from scheduler.decision_manager import (
    CycleContext,
    ForecastConditionGuard,
    RuleGuard,
    SoilConditionGuard,
    WeatherConditionGuard,
)
from scheduler.guard_rule_loader import GuardRuleLoader
from services.weather_service import WeatherData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockOperation:
    """Minimal Mock für eine Operation mit worktype/application_category."""

    def __init__(
        self,
        worktype: int,
        application_category: int | None = None,
        name: str = "MockOp",
    ) -> None:
        self.worktype = worktype
        self.application_category = application_category
        self.worktype_text = name
        self.operation = name


def _weather(
    precipitation_mm: float = 0.0,
    wind_speed_ms: float = 0.0,
    temperature_max_c: float = 20.0,
    temperature_min_c: float = 10.0,
    soil_moisture_pct_nfk: float = 50.0,
    date: datetime.date | None = None,
) -> WeatherData:
    return WeatherData(
        date=date or datetime.date(2027, 6, 15),
        precipitation_mm=precipitation_mm,
        wind_speed_ms=wind_speed_ms,
        temperature_max_c=temperature_max_c,
        temperature_min_c=temperature_min_c,
        soil_moisture_pct_nfk=soil_moisture_pct_nfk,
    )


def _ctx(
    current_weather: WeatherData | None = None,
    weather_forecast: list[WeatherData] | None = None,
) -> CycleContext:
    return CycleContext(
        current_weather=current_weather,
        weather_forecast=weather_forecast,
    )


_DATE = datetime.datetime(2027, 6, 15)


# ---------------------------------------------------------------------------
# WeatherConditionGuard (KAR-030, KAR-035)
# ---------------------------------------------------------------------------


class TestWeatherConditionGuard:
    """KAR-030: kein Spritzen bei Regen/Wind; KAR-035: Sikkation bei Hitze."""

    def test_from_config_reads_all_fields(self) -> None:
        entry = {
            "rule_id": "KAR-030",
            "description": "Kein Spritzen bei Regen oder Wind",
            "worktype": 14,
            "max_precipitation_mm_day": 5,
            "max_wind_ms": 5,
        }
        guard = WeatherConditionGuard.from_config(entry)
        assert guard.rule_id == "KAR-030"
        assert guard.worktype == 14
        assert guard.application_category is None
        assert guard.max_precipitation_mm_day == 5.0
        assert guard.max_wind_ms == 5.0
        assert guard.max_temperature_c is None

    def test_from_config_with_category_and_temperature(self) -> None:
        entry = {
            "rule_id": "KAR-035",
            "description": "Keine Sikkation bei Hitze",
            "worktype": 14,
            "application_category": 26,
            "max_temperature_c": 30,
            "max_precipitation_mm_day": 1,
        }
        guard = WeatherConditionGuard.from_config(entry)
        assert guard.application_category == 26
        assert guard.max_temperature_c == 30.0
        assert guard.max_precipitation_mm_day == 1.0

    def test_from_config_defaults(self) -> None:
        entry = {
            "rule_id": "KAR-030",
            "description": "x",
            "worktype": 14,
        }
        guard = WeatherConditionGuard.from_config(entry)
        assert guard.max_precipitation_mm_day == 5.0
        assert guard.max_wind_ms == 5.0
        assert guard.max_temperature_c is None

    def test_rejects_spraying_with_heavy_rain(self) -> None:
        guard = WeatherConditionGuard(
            rule_id="KAR-030",
            description="Kein Spritzen bei Regen",
            worktype=14,
            max_precipitation_mm_day=5.0,
            max_wind_ms=5.0,
        )
        op = MockOperation(worktype=14)
        ctx = _ctx(current_weather=_weather(precipitation_mm=6.0))
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-030:")
        assert "Niederschlag" in reason

    def test_rejects_spraying_with_strong_wind(self) -> None:
        guard = WeatherConditionGuard(
            rule_id="KAR-030",
            description="Kein Spritzen bei Wind",
            worktype=14,
            max_precipitation_mm_day=5.0,
            max_wind_ms=5.0,
        )
        op = MockOperation(worktype=14)
        ctx = _ctx(current_weather=_weather(wind_speed_ms=6.0))
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-030:")
        assert "Wind" in reason

    def test_passes_spraying_in_good_weather(self) -> None:
        guard = WeatherConditionGuard(
            rule_id="KAR-030",
            description="Kein Spritzen bei Regen",
            worktype=14,
            max_precipitation_mm_day=5.0,
            max_wind_ms=5.0,
        )
        op = MockOperation(worktype=14)
        ctx = _ctx(current_weather=_weather(precipitation_mm=2.0, wind_speed_ms=3.0))
        assert guard.check(op, ctx, _DATE) is None

    def test_passes_at_exact_limit(self) -> None:
        """Grenzwert 5.0 mm / 5.0 m/s → nicht abgelehnt (strikt >)."""
        guard = WeatherConditionGuard(
            rule_id="KAR-030",
            description="x",
            worktype=14,
            max_precipitation_mm_day=5.0,
            max_wind_ms=5.0,
        )
        op = MockOperation(worktype=14)
        ctx = _ctx(current_weather=_weather(precipitation_mm=5.0, wind_speed_ms=5.0))
        assert guard.check(op, ctx, _DATE) is None

    def test_rejects_sikkation_with_heat(self) -> None:
        guard = WeatherConditionGuard(
            rule_id="KAR-035",
            description="Keine Sikkation bei Hitze",
            worktype=14,
            application_category=26,
            max_precipitation_mm_day=1.0,
            max_wind_ms=5.0,
            max_temperature_c=30.0,
        )
        op = MockOperation(worktype=14, application_category=26)
        ctx = _ctx(current_weather=_weather(temperature_max_c=31.0))
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-035:")
        assert "Temperatur" in reason

    def test_sikkation_category_filter(self) -> None:
        """KAR-035 mit cat=26 lehnt nur Sikkation ab, nicht Fungizid (cat=27)."""
        guard = WeatherConditionGuard(
            rule_id="KAR-035",
            description="Keine Sikkation bei Hitze",
            worktype=14,
            application_category=26,
            max_precipitation_mm_day=1.0,
            max_wind_ms=5.0,
            max_temperature_c=30.0,
        )
        op_fungicide = MockOperation(worktype=14, application_category=27)
        ctx = _ctx(current_weather=_weather(temperature_max_c=35.0))
        # cat != 26 → Guard nicht anwendbar → None
        assert guard.check(op_fungicide, ctx, _DATE) is None

    def test_other_worktype_not_checked(self) -> None:
        """wt=15 (Beregnung) wird von wt=14-Guard nicht geprüft."""
        guard = WeatherConditionGuard(
            rule_id="KAR-030",
            description="x",
            worktype=14,
            max_precipitation_mm_day=5.0,
            max_wind_ms=5.0,
        )
        op = MockOperation(worktype=15)
        ctx = _ctx(current_weather=_weather(precipitation_mm=20.0))
        assert guard.check(op, ctx, _DATE) is None

    def test_disabled_without_weather(self) -> None:
        """current_weather=None → Guard deaktiviert (Abwärtskompatibilität)."""
        guard = WeatherConditionGuard(
            rule_id="KAR-030",
            description="x",
            worktype=14,
            max_precipitation_mm_day=5.0,
            max_wind_ms=5.0,
        )
        op = MockOperation(worktype=14)
        assert guard.check(op, _ctx(current_weather=None), _DATE) is None
        assert guard.check(op, None, _DATE) is None


# ---------------------------------------------------------------------------
# SoilConditionGuard (KAR-032)
# ---------------------------------------------------------------------------


class TestSoilConditionGuard:
    """KAR-032: keine Bodenbearbeitung auf nassem Boden."""

    def test_from_config_reads_all_fields(self) -> None:
        entry = {
            "rule_id": "KAR-032",
            "description": "nasser Boden",
            "worktypes": [5, 6, 7, 26, 28],
            "max_soil_moisture_pct_nfk": 90,
            "max_previous_day_precipitation_mm": 10,
        }
        guard = SoilConditionGuard.from_config(entry)
        assert guard.rule_id == "KAR-032"
        assert guard.worktypes == [5, 6, 7, 26, 28]
        assert guard.max_soil_moisture_pct_nfk == 90.0
        assert guard.max_previous_day_precipitation_mm == 10.0

    def test_from_config_defaults(self) -> None:
        entry = {
            "rule_id": "KAR-032",
            "description": "x",
            "worktypes": [5],
        }
        guard = SoilConditionGuard.from_config(entry)
        assert guard.max_soil_moisture_pct_nfk == 90.0
        assert guard.max_previous_day_precipitation_mm == 10.0

    def test_rejects_tillage_on_wet_soil(self) -> None:
        guard = SoilConditionGuard(
            rule_id="KAR-032",
            description="nasser Boden",
            worktypes=[5, 6, 7, 26, 28],
            max_soil_moisture_pct_nfk=90.0,
            max_previous_day_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=6)
        ctx = _ctx(current_weather=_weather(soil_moisture_pct_nfk=95.0))
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-032:")
        assert "Bodenfeuchte" in reason

    def test_rejects_tillage_after_heavy_rain(self) -> None:
        """Vortagesniederschlag-Vereinfachung: nutzt current_weather.precipitation_mm."""
        guard = SoilConditionGuard(
            rule_id="KAR-032",
            description="nasser Boden",
            worktypes=[5, 6, 7, 26, 28],
            max_soil_moisture_pct_nfk=90.0,
            max_previous_day_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=7)
        ctx = _ctx(current_weather=_weather(soil_moisture_pct_nfk=50.0, precipitation_mm=12.0))
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-032:")
        assert "Niederschlag" in reason

    def test_passes_tillage_on_dry_soil(self) -> None:
        guard = SoilConditionGuard(
            rule_id="KAR-032",
            description="x",
            worktypes=[5, 6, 7, 26, 28],
            max_soil_moisture_pct_nfk=90.0,
            max_previous_day_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=6)
        ctx = _ctx(current_weather=_weather(soil_moisture_pct_nfk=50.0, precipitation_mm=2.0))
        assert guard.check(op, ctx, _DATE) is None

    def test_passes_at_exact_limit(self) -> None:
        """Grenzwert 90 % nFK / 10 mm → nicht abgelehnt (strikt >)."""
        guard = SoilConditionGuard(
            rule_id="KAR-032",
            description="x",
            worktypes=[5, 6, 7, 26, 28],
            max_soil_moisture_pct_nfk=90.0,
            max_previous_day_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=6)
        ctx = _ctx(current_weather=_weather(soil_moisture_pct_nfk=90.0, precipitation_mm=10.0))
        assert guard.check(op, ctx, _DATE) is None

    def test_other_worktype_not_checked(self) -> None:
        """wt=14 (Spritzen) wird von Boden-Guard nicht geprüft."""
        guard = SoilConditionGuard(
            rule_id="KAR-032",
            description="x",
            worktypes=[5, 6, 7, 26, 28],
            max_soil_moisture_pct_nfk=90.0,
            max_previous_day_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=14)
        ctx = _ctx(current_weather=_weather(soil_moisture_pct_nfk=99.0))
        assert guard.check(op, ctx, _DATE) is None

    def test_disabled_without_weather(self) -> None:
        guard = SoilConditionGuard(
            rule_id="KAR-032",
            description="x",
            worktypes=[5, 6, 7, 26, 28],
            max_soil_moisture_pct_nfk=90.0,
            max_previous_day_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=6)
        assert guard.check(op, _ctx(current_weather=None), _DATE) is None
        assert guard.check(op, None, _DATE) is None


# ---------------------------------------------------------------------------
# ForecastConditionGuard (KAR-031)
# ---------------------------------------------------------------------------


class TestForecastConditionGuard:
    """KAR-031: keine Beregnung bei prognostiziertem Niederschlag."""

    def test_from_config_reads_all_fields(self) -> None:
        entry = {
            "rule_id": "KAR-031",
            "description": "keine Beregnung bei Regenprognose",
            "worktype": 15,
            "forecast_days": 4,
            "max_cumulative_precipitation_mm": 10,
        }
        guard = ForecastConditionGuard.from_config(entry)
        assert guard.rule_id == "KAR-031"
        assert guard.worktype == 15
        assert guard.forecast_days == 4
        assert guard.max_cumulative_precipitation_mm == 10.0

    def test_from_config_defaults(self) -> None:
        entry = {
            "rule_id": "KAR-031",
            "description": "x",
            "worktype": 15,
        }
        guard = ForecastConditionGuard.from_config(entry)
        assert guard.forecast_days == 4
        assert guard.max_cumulative_precipitation_mm == 10.0

    def test_rejects_irrigation_with_rain_forecast(self) -> None:
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="keine Beregnung bei Regenprognose",
            worktype=15,
            forecast_days=4,
            max_cumulative_precipitation_mm=10.0,
        )
        forecast = [
            _weather(precipitation_mm=3.0, date=datetime.date(2027, 6, 15)),
            _weather(precipitation_mm=4.0, date=datetime.date(2027, 6, 16)),
            _weather(precipitation_mm=2.0, date=datetime.date(2027, 6, 17)),
            _weather(precipitation_mm=3.0, date=datetime.date(2027, 6, 18)),
        ]
        op = MockOperation(worktype=15)
        ctx = _ctx(weather_forecast=forecast)
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-031:")
        assert "Prognose-Niederschlag" in reason

    def test_passes_irrigation_with_dry_forecast(self) -> None:
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="x",
            worktype=15,
            forecast_days=4,
            max_cumulative_precipitation_mm=10.0,
        )
        forecast = [
            _weather(precipitation_mm=2.0, date=datetime.date(2027, 6, 15)),
            _weather(precipitation_mm=2.0, date=datetime.date(2027, 6, 16)),
            _weather(precipitation_mm=2.0, date=datetime.date(2027, 6, 17)),
            _weather(precipitation_mm=2.0, date=datetime.date(2027, 6, 18)),
        ]
        op = MockOperation(worktype=15)
        ctx = _ctx(weather_forecast=forecast)
        assert guard.check(op, ctx, _DATE) is None

    def test_uses_only_forecast_days_entries(self) -> None:
        """forecast_days=2 → nur erste 2 Tage zählen, Rest ignoriert."""
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="x",
            worktype=15,
            forecast_days=2,
            max_cumulative_precipitation_mm=5.0,
        )
        forecast = [
            _weather(precipitation_mm=3.0, date=datetime.date(2027, 6, 15)),
            _weather(precipitation_mm=3.0, date=datetime.date(2027, 6, 16)),
            _weather(precipitation_mm=20.0, date=datetime.date(2027, 6, 17)),
        ]
        op = MockOperation(worktype=15)
        ctx = _ctx(weather_forecast=forecast)
        # 3+3=6 > 5 → reject (Tag 3 mit 20 mm wird ignoriert)
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-031:")

    def test_passes_at_exact_limit(self) -> None:
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="x",
            worktype=15,
            forecast_days=4,
            max_cumulative_precipitation_mm=10.0,
        )
        forecast = [
            _weather(precipitation_mm=2.5, date=datetime.date(2027, 6, 15)),
            _weather(precipitation_mm=2.5, date=datetime.date(2027, 6, 16)),
            _weather(precipitation_mm=2.5, date=datetime.date(2027, 6, 17)),
            _weather(precipitation_mm=2.5, date=datetime.date(2027, 6, 18)),
        ]
        op = MockOperation(worktype=15)
        ctx = _ctx(weather_forecast=forecast)
        assert guard.check(op, ctx, _DATE) is None

    def test_other_worktype_not_checked(self) -> None:
        """wt=14 wird von wt=15-Guard nicht geprüft."""
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="x",
            worktype=15,
            forecast_days=4,
            max_cumulative_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=14)
        forecast = [
            _weather(precipitation_mm=20.0, date=datetime.date(2027, 6, 15)),
        ]
        ctx = _ctx(weather_forecast=forecast)
        assert guard.check(op, ctx, _DATE) is None

    def test_disabled_without_forecast(self) -> None:
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="x",
            worktype=15,
            forecast_days=4,
            max_cumulative_precipitation_mm=10.0,
        )
        op = MockOperation(worktype=15)
        assert guard.check(op, _ctx(weather_forecast=None), _DATE) is None
        assert guard.check(op, None, _DATE) is None

    def test_short_forecast_handled(self) -> None:
        """Forecast kürzer als forecast_days → nur verfügbare Tage summieren."""
        guard = ForecastConditionGuard(
            rule_id="KAR-031",
            description="x",
            worktype=15,
            forecast_days=4,
            max_cumulative_precipitation_mm=5.0,
        )
        forecast = [
            _weather(precipitation_mm=6.0, date=datetime.date(2027, 6, 15)),
        ]
        op = MockOperation(worktype=15)
        ctx = _ctx(weather_forecast=forecast)
        reason = guard.check(op, ctx, _DATE)
        assert reason is not None
        assert reason.startswith("KAR-031:")


# ---------------------------------------------------------------------------
# Konfigurations-Integration (GuardRuleLoader)
# ---------------------------------------------------------------------------


class TestWeatherGuardConfigLoading:
    """Die 4 neuen Wetter-Guards werden aus der Konfiguration geladen."""

    @pytest.fixture
    def guard(self) -> RuleGuard:
        return GuardRuleLoader.load_default()

    def test_loads_seven_guard_rules(self, guard: RuleGuard) -> None:
        """3 bestehende + 4 neue Wetter-Guards = 7 Regeln."""
        assert len(guard.rules) == 7

    @pytest.mark.parametrize("rule_id", ["KAR-030", "KAR-031", "KAR-032", "KAR-035"])
    def test_weather_guard_loaded(self, guard: RuleGuard, rule_id: str) -> None:
        rule_ids = [r.rule_id for r in guard.rules]
        assert rule_id in rule_ids

    def test_existing_guards_still_loaded(self, guard: RuleGuard) -> None:
        """Bestehende Guards (KAR-005, KAR-020, KAR-024) bleiben erhalten."""
        rule_ids = [r.rule_id for r in guard.rules]
        assert "KAR-005" in rule_ids
        assert "KAR-020" in rule_ids
        assert "KAR-024" in rule_ids

    def test_weather_guards_disabled_in_baseline_context(self, guard: RuleGuard) -> None:
        """Ohne Wetterdaten (current_weather=None) lehnen Wetter-Guards
        nichts ab – Baseline-Fixture ohne WeatherService bleibt unangetastet."""
        op = MockOperation(worktype=14, application_category=26)
        ctx = _ctx(current_weather=None, weather_forecast=None)
        # KAR-024 (no_siccation_after_harvest) greift nur bei
        # harvest_completed=True; hier False → alle Guards pass.
        reason = guard.check(op, ctx, _DATE)
        assert reason is None
