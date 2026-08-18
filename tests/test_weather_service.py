"""Tests für den Wetterdaten-Service (P3-1, Issue #79).

Test-Reihenfolge (test-first):
1. SyntheticWeatherDataProvider – deterministisch, 365/366 Tage, plausible Werte
2. WeatherDataService – Caching, get_weather_for_date, get_forecast
3. CalendarDrivenRunner mit weather_service_factory + CycleContext.current_weather
"""

from __future__ import annotations

import datetime
from unittest.mock import Mock, patch

import pytest

from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from services.weather_service import WeatherData, WeatherDataProvider, WeatherDataService
from services.providers.synthetic_weather_provider import SyntheticWeatherDataProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_context() -> SimContext:
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2026, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1,
    )


@pytest.fixture
def synthetic_provider() -> SyntheticWeatherDataProvider:
    return SyntheticWeatherDataProvider(seed=42)


@pytest.fixture
def weather_service(
    basic_context: SimContext,
    synthetic_provider: SyntheticWeatherDataProvider,
) -> WeatherDataService:
    return WeatherDataService(
        context=basic_context,
        provider=synthetic_provider,
    )


# ---------------------------------------------------------------------------
# 1. SyntheticWeatherDataProvider
# ---------------------------------------------------------------------------


class TestSyntheticWeatherDataProvider:
    """Unit-Tests für den synthetischen Wetter-Provider."""

    def test_provides_365_days_for_normal_year(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        assert len(data) == 365

    def test_provides_366_days_for_leap_year(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2024, (52.5, 9.9))
        assert len(data) == 366

    def test_dates_cover_full_year(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        assert data[0].date == datetime.date(2023, 1, 1)
        assert data[-1].date == datetime.date(2023, 12, 31)

    def test_deterministic_same_seed_same_output(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data1 = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        data2 = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        assert len(data1) == len(data2)
        for d1, d2 in zip(data1, data2):
            assert d1 == d2

    def test_different_seed_different_output(self) -> None:
        p1 = SyntheticWeatherDataProvider(seed=42)
        p2 = SyntheticWeatherDataProvider(seed=99)
        data1 = p1.get_weather_data(2023, (52.5, 9.9))
        data2 = p2.get_weather_data(2023, (52.5, 9.9))
        # Wenigstens ein Tag muss unterschiedlich sein
        diffs = [d1 != d2 for d1, d2 in zip(data1, data2)]
        assert any(diffs)

    def test_precipitation_non_negative(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        for d in data:
            assert d.precipitation_mm >= 0.0

    def test_wind_speed_non_negative(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        for d in data:
            assert d.wind_speed_ms >= 0.0

    def test_temperature_max_geq_min(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        for d in data:
            assert d.temperature_max_c >= d.temperature_min_c

    def test_soil_moisture_in_valid_range(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        for d in data:
            assert 0.0 <= d.soil_moisture_pct_nfk <= 100.0

    def test_summer_warmer_than_winter(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        """Saisonales Muster: Sommer (Jul/Aug) sollte wärmer sein als Winter (Jan/Dez)."""
        data = synthetic_provider.get_weather_data(2023, (52.5, 9.9))
        summer_temps = [
            d.temperature_max_c
            for d in data
            if d.date.month in (7, 8)
        ]
        winter_temps = [
            d.temperature_max_c
            for d in data
            if d.date.month in (1, 12)
        ]
        avg_summer = sum(summer_temps) / len(summer_temps)
        avg_winter = sum(winter_temps) / len(winter_temps)
        assert avg_summer > avg_winter

    def test_implements_weather_data_provider_protocol(
        self, synthetic_provider: SyntheticWeatherDataProvider
    ) -> None:
        assert isinstance(synthetic_provider, WeatherDataProvider)


# ---------------------------------------------------------------------------
# 2. WeatherDataService
# ---------------------------------------------------------------------------


class TestWeatherDataService:
    """Unit-Tests für den WeatherDataService."""

    def test_get_weather_for_date_returns_correct_date(
        self, weather_service: WeatherDataService
    ) -> None:
        date = datetime.date(2026, 6, 15)
        wd = weather_service.get_weather_for_date(date)
        assert isinstance(wd, WeatherData)
        assert wd.date == date

    def test_get_weather_for_date_jan1(
        self, weather_service: WeatherDataService
    ) -> None:
        wd = weather_service.get_weather_for_date(datetime.date(2026, 1, 1))
        assert wd.date == datetime.date(2026, 1, 1)

    def test_get_weather_for_date_dec31(
        self, weather_service: WeatherDataService
    ) -> None:
        wd = weather_service.get_weather_for_date(datetime.date(2026, 12, 31))
        assert wd.date == datetime.date(2026, 12, 31)

    def test_caching_does_not_call_provider_twice(
        self, basic_context: SimContext
    ) -> None:
        mock_provider = Mock(spec=WeatherDataProvider)
        mock_provider.get_weather_data.return_value = [
            WeatherData(
                date=datetime.date(2026, 1, 1) + datetime.timedelta(days=i),
                precipitation_mm=0.0,
                wind_speed_ms=1.0,
                temperature_max_c=10.0,
                temperature_min_c=5.0,
                soil_moisture_pct_nfk=60.0,
            )
            for i in range(365)
        ]
        service = WeatherDataService(
            context=basic_context, provider=mock_provider
        )
        service.get_weather_for_date(datetime.date(2026, 3, 1))
        service.get_weather_for_date(datetime.date(2026, 6, 15))
        service.get_weather_for_date(datetime.date(2026, 9, 30))
        # Provider should only be called once for the same year
        assert mock_provider.get_weather_data.call_count == 1

    def test_different_years_separate_cache(
        self, basic_context: SimContext
    ) -> None:
        mock_provider = Mock(spec=WeatherDataProvider)
        mock_provider.get_weather_data.return_value = [
            WeatherData(
                date=datetime.date(2026, 1, 1) + datetime.timedelta(days=i),
                precipitation_mm=0.0,
                wind_speed_ms=1.0,
                temperature_max_c=10.0,
                temperature_min_c=5.0,
                soil_moisture_pct_nfk=60.0,
            )
            for i in range(365)
        ]
        service = WeatherDataService(
            context=basic_context, provider=mock_provider
        )
        service.get_weather_for_date(datetime.date(2026, 6, 15))
        service.get_weather_for_date(datetime.date(2027, 6, 15))
        assert mock_provider.get_weather_data.call_count == 2

    def test_get_forecast_returns_n_days(
        self, weather_service: WeatherDataService
    ) -> None:
        date = datetime.date(2026, 6, 15)
        forecast = weather_service.get_forecast(date, 7)
        assert len(forecast) == 7
        assert forecast[0].date == date
        for i, wd in enumerate(forecast):
            assert wd.date == date + datetime.timedelta(days=i)

    def test_get_forecast_at_year_boundary(
        self, weather_service: WeatherDataService
    ) -> None:
        """Forecast über Jahreswechsel: 30.12. → 7 Tage Forecast reicht ins Folgejahr."""
        date = datetime.date(2026, 12, 30)
        forecast = weather_service.get_forecast(date, 7)
        # 30.12, 31.12 (2026) + 1.1–5.1 (2027) = 7 Tage
        # Wenn das Folgejahr noch nicht gecacht ist, wird es nachgeladen
        assert len(forecast) == 7

    def test_field_coords_from_context(self) -> None:
        ctx = SimContext(
            field_id=1,
            field_name="Test",
            field_size=10.0,
            soil_type="sand",
            start_date=datetime.datetime(2026, 1, 1),
            crop_type="Potato",
            variety="Belana",
            fuel_variation=0.1,
            field_coords=(48.1, 11.5),
        )
        mock_provider = Mock(spec=WeatherDataProvider)
        mock_provider.get_weather_data.return_value = [
            WeatherData(
                date=datetime.date(2026, 1, 1) + datetime.timedelta(days=i),
                precipitation_mm=0.0,
                wind_speed_ms=1.0,
                temperature_max_c=10.0,
                temperature_min_c=5.0,
                soil_moisture_pct_nfk=60.0,
            )
            for i in range(365)
        ]
        service = WeatherDataService(context=ctx, provider=mock_provider)
        service.get_weather_for_date(datetime.date(2026, 6, 15))
        mock_provider.get_weather_data.assert_called_once_with(
            2026, (48.1, 11.5)
        )

    def test_field_coords_default_when_none(
        self, basic_context: SimContext
    ) -> None:
        mock_provider = Mock(spec=WeatherDataProvider)
        mock_provider.get_weather_data.return_value = [
            WeatherData(
                date=datetime.date(2026, 1, 1) + datetime.timedelta(days=i),
                precipitation_mm=0.0,
                wind_speed_ms=1.0,
                temperature_max_c=10.0,
                temperature_min_c=5.0,
                soil_moisture_pct_nfk=60.0,
            )
            for i in range(365)
        ]
        service = WeatherDataService(
            context=basic_context, provider=mock_provider
        )
        service.get_weather_for_date(datetime.date(2026, 6, 15))
        args, _ = mock_provider.get_weather_data.call_args
        assert args[1] == (52.5, 9.9)


# ---------------------------------------------------------------------------
# 3. CalendarDrivenRunner Integration
# ---------------------------------------------------------------------------


class TestCalendarDrivenRunnerWeatherIntegration:
    """Integration: CalendarDrivenRunner mit weather_service_factory."""

    @pytest.fixture
    def mock_planting_plan_service(self) -> Mock:
        service = Mock()
        service.get_next_operations = Mock(return_value=[])
        service.get_events_for_ops = Mock(return_value=[])
        service.active_phase = None
        service.planned_planting_date = datetime.datetime(2026, 3, 15)
        service.planting_plan = Mock()
        service.planting_plan.grow_duration = 120
        service.planting_plan.phases = []
        service.update_phase_status = Mock()
        service.get_phase_status = Mock(return_value=None)
        service.set_planned_planting_date = Mock()
        return service

    @pytest.fixture
    def mock_protection_plan_service(self) -> Mock:
        service = Mock()
        service.operations = []
        return service

    def test_runner_accepts_weather_service_factory(
        self, basic_context: SimContext, mock_planting_plan_service: Mock
    ) -> None:
        """Runner kann mit weather_service_factory konstruiert werden."""
        ws = WeatherDataService(
            context=basic_context,
            provider=SyntheticWeatherDataProvider(seed=42),
        )
        factory = Mock(return_value=ws)

        with patch(
            "scheduler.calendar_driven_runner.PlantingPlanService",
            return_value=mock_planting_plan_service,
        ):
            runner = CalendarDrivenRunner(
                basic_context,
                weather_service_factory=factory,
            )
        assert runner._weather_service_factory is factory

    def test_cycle_context_contains_current_weather(
        self, basic_context: SimContext, mock_planting_plan_service: Mock,
        mock_protection_plan_service: Mock,
    ) -> None:
        """Nach _initialize_services enthält CycleContext current_weather."""
        ws = WeatherDataService(
            context=basic_context,
            provider=SyntheticWeatherDataProvider(seed=42),
        )
        factory = Mock(return_value=ws)

        with patch(
            "scheduler.calendar_driven_runner.PlantingPlanService",
            return_value=mock_planting_plan_service,
        ), patch(
            "scheduler.calendar_driven_runner.ProtectionPlanService",
            return_value=mock_protection_plan_service,
        ):
            runner = CalendarDrivenRunner(
                basic_context,
                weather_service_factory=factory,
            )
            # Simulate service initialization
            runner._initialize_services(datetime.date(2026, 6, 15))
            ctx = runner._build_cycle_context(datetime.date(2026, 6, 15))

        assert ctx.current_weather is not None
        assert ctx.current_weather.date == datetime.date(2026, 6, 15)
        assert isinstance(ctx.current_weather, WeatherData)

    def test_cycle_context_contains_weather_forecast(
        self, basic_context: SimContext, mock_planting_plan_service: Mock,
        mock_protection_plan_service: Mock,
    ) -> None:
        """Nach _initialize_services enthält CycleContext weather_forecast."""
        ws = WeatherDataService(
            context=basic_context,
            provider=SyntheticWeatherDataProvider(seed=42),
        )
        factory = Mock(return_value=ws)

        with patch(
            "scheduler.calendar_driven_runner.PlantingPlanService",
            return_value=mock_planting_plan_service,
        ), patch(
            "scheduler.calendar_driven_runner.ProtectionPlanService",
            return_value=mock_protection_plan_service,
        ):
            runner = CalendarDrivenRunner(
                basic_context,
                weather_service_factory=factory,
            )
            runner._initialize_services(datetime.date(2026, 6, 15))
            ctx = runner._build_cycle_context(datetime.date(2026, 6, 15))

        assert ctx.weather_forecast is not None
        assert len(ctx.weather_forecast) > 0

    def test_cycle_context_weather_none_without_factory(
        self, basic_context: SimContext, mock_planting_plan_service: Mock
    ) -> None:
        """Ohne weather_service_factory sind current_weather/forecast None."""
        with patch(
            "scheduler.calendar_driven_runner.PlantingPlanService",
            return_value=mock_planting_plan_service,
        ):
            runner = CalendarDrivenRunner(basic_context)
            ctx = runner._build_cycle_context(datetime.date(2026, 6, 15))

        assert ctx.current_weather is None
        assert ctx.weather_forecast is None
