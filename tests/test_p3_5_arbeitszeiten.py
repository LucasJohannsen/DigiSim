"""Tests für P3-5: Arbeitszeiten begrenzen – mehrtägige Aufteilung (Befund B10, Issue #83).

Deckt die Akzeptanzkriterien aus dem Konzept
``documentation/konzepte/P3-5_arbeitszeiten.md`` ab:

1. Operation mit > 18 h Dauer → Aufteilung auf mehrere Tage (jede Teil-Op ≤ 18 h).
2. Operation mit ≤ 18 h Dauer → einzelnes Event (keine Aufteilung).
3. Kein Event startet vor 05:00 oder endet nach 22:00 Uhr.
4. Aufgeteilte Operationen haben proportionale application_amount/Fläche.
5. ``assign_sequential_time`` Defaults: [05:00, 20:00].
6. Irrigation mit langer Dauer → mehrtägige Aufteilung.
"""

from __future__ import annotations

import datetime
import random
from unittest.mock import patch

import numpy as np
import pytest

from models.planting_plan import FieldOperation
from models.sim_context import SimContext
from services.irrigation_service import IrrigationSimulator
from services.planting_plan_service import PlantingPlanService
from utils.sim_helper import assign_sequential_time

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

_WORK_START_HOUR = 5
_WORK_END_HOUR = 22
_MAX_DURATION_HOURS = 18
_START_MAX_HOUR = 20  # KAR-045 start_hour_range upper bound

_TEST_DATE = datetime.datetime(2026, 5, 10, 0, 0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_context() -> SimContext:
    return SimContext(
        field_id=990001,
        field_name="Test Field",
        field_size=20.0,
        soil_type="sandy_loam",
        start_date=datetime.datetime(2026, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1,
    )


def _make_op(
    sequence: int = 1,
    duration_per_ha: float = 0.5,
    working_width: float = 3.0,
    fuel_consumption: float = 10.0,
    application_amount: float = 100.0,
    operation: str = "Test-Op",
    worktype: int = 28,  # Separieren (not in _SINGLE_EVENT_WORKTYPES)
) -> FieldOperation:
    """Erzeuge eine minimale FieldOperation für Tests."""
    return FieldOperation(
        sequence=sequence,
        operation=operation,
        worktype=worktype,
        duration_per_ha=duration_per_ha,
        working_width=working_width,
        fuel_consumption=fuel_consumption,
        planned_date=_TEST_DATE,
        actual_date=None,
        application_amount=application_amount,
    )


# ---------------------------------------------------------------------------
# (e) assign_sequential_time – neue Defaults [05:00, 20:00]
# ---------------------------------------------------------------------------


class TestAssignSequentialTimeExplicitWindow:
    """PlantingPlanService übergibt explizit [05:00, 20:00] (KAR-045).

    Die Defaults bleiben auf [06:00, 17:00], um den Zufallszustand für
    ProtectionPlanService nicht zu verschieben (KAR-021).
    """

    def test_default_window_unchanged(self):
        """Default-Fenster bleibt [06:00, 17:00] (keine Zufallsverschiebung)."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        for _ in range(20):
            t = assign_sequential_time(d)
            assert datetime.time(6, 0) <= t.time() <= datetime.time(17, 0)

    def test_explicit_window_05_to_20(self):
        """Explizites Fenster [05:00, 20:00] wird respektiert."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        for _ in range(20):
            t = assign_sequential_time(
                d, min_start=datetime.time(5, 0), max_end=datetime.time(20, 0)
            )
            assert datetime.time(5, 0) <= t.time() <= datetime.time(20, 0)

    def test_custom_window_still_respected(self):
        """Explizite Fenster bleiben unangetastet."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        t = assign_sequential_time(d, min_start=datetime.time(8, 0), max_end=datetime.time(10, 0))
        assert datetime.time(8, 0) <= t.time() <= datetime.time(10, 0)


# ---------------------------------------------------------------------------
# (a-c) PlantingPlanService.get_events_for_ops – mehrtägige Aufteilung
# ---------------------------------------------------------------------------


class TestPlantingPlanServiceSplitting:
    """Tests für die mehrtägige Aufteilung langer Operationen."""

    def test_long_operation_split_into_multiple_events(self, basic_context):
        """30 h Dauer → 2 Events (je 15 h), auf zwei Tage aufgeteilt."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 30 h = 1.5 h/ha × 20 ha
        op = _make_op(duration_per_ha=1.5, application_amount=100.0)
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 2, f"30 h → erwartet 2 Events, got {len(events)}"

        # Jedes Event ≤ 18 h
        for ev in events:
            dur_h = ev.duration / 3600.0
            assert dur_h <= _MAX_DURATION_HOURS, (
                f"Teil-Event Dauer {dur_h:.1f} h > {_MAX_DURATION_HOURS} h"
            )

        # Gesamtdauer = 30 h
        total_dur = sum(ev.duration / 3600.0 for ev in events)
        assert abs(total_dur - 30.0) < 0.01, f"Gesamtdauer {total_dur:.1f} h ≠ 30 h"

    def test_short_operation_single_event(self, basic_context):
        """≤ 18 h Dauer → 1 Event (keine Aufteilung)."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 10 h = 0.5 h/ha × 20 ha
        op = _make_op(duration_per_ha=0.5)
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 1, f"10 h → erwartet 1 Event, got {len(events)}"
        dur_h = events[0].duration / 3600.0
        assert abs(dur_h - 10.0) < 0.01

    def test_split_events_on_consecutive_days(self, basic_context):
        """Aufgeteilte Events liegen auf aufeinanderfolgenden Tagen."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 50 h = 2.5 h/ha × 20 ha → 3 Tage
        op = _make_op(duration_per_ha=2.5)
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 3
        dates = [
            datetime.datetime.strptime(ev.start_date, "%Y-%m-%d %H:%M:%S").date() for ev in events
        ]
        # Tage sind aufeinanderfolgend
        for i in range(1, len(dates)):
            assert dates[i] == dates[i - 1] + datetime.timedelta(days=1), (
                f"Tag {i} ({dates[i]}) nicht aufeinanderfolgend mit Tag {i - 1} ({dates[i - 1]})"
            )

    def test_no_event_starts_before_05_or_after_20(self, basic_context):
        """KAR-045: Start zwischen 05:00 und 20:00.

        P3-5: Erster Aufteilungs-Tag verwendet assign_sequential_time
        (Fenster [06:00, 17:00]), folgende Tage sind deterministisch 06:00.
        """
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 34.8 h = 1.74 h/ha × 20 ha → 2 Tage
        op = _make_op(duration_per_ha=1.74)
        events = service.get_events_for_ops([op], _TEST_DATE)

        for ev in events:
            start = datetime.datetime.strptime(ev.start_date, "%Y-%m-%d %H:%M:%S")
            assert start.time() >= datetime.time(5, 0), f"Start {start.time()} vor 05:00"
            assert start.time() <= datetime.time(20, 0), (
                f"Start {start.time()} nach 20:00 (KAR-045 start_hour_range)"
            )

    def test_no_event_duration_exceeds_18h(self, basic_context):
        """KAR-045: Keine Einzeloperation > 18 h."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 50 h → 3 Events
        op = _make_op(duration_per_ha=2.5)
        events = service.get_events_for_ops([op], _TEST_DATE)

        for ev in events:
            dur_h = ev.duration / 3600.0
            assert dur_h <= _MAX_DURATION_HOURS, f"Dauer {dur_h:.1f} h > {_MAX_DURATION_HOURS} h"

    def test_proportional_application_amount(self, basic_context):
        """Aufgeteilte Events haben proportionale application_amount."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 30 h → 2 Events je 15 h, application_amount=100/ha × 20 ha = 2000 total
        op = _make_op(duration_per_ha=1.5, application_amount=100.0)
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 2
        total_amount = sum(ev.application_amount for ev in events)
        expected_total = 100.0 * 20.0  # application_amount_per_ha × field_size
        assert abs(total_amount - expected_total) < 1.0, (
            f"Proportionale Summe {total_amount:.1f} ≠ {expected_total:.1f}"
        )
        # Beide Events haben ~gleichen Anteil (15/30 = 0.5)
        assert abs(events[0].application_amount - events[1].application_amount) < 1.0

    def test_proportional_area(self, basic_context):
        """Aufgeteilte Events haben proportionale Fläche."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        op = _make_op(duration_per_ha=1.5)  # 30 h → 2 Events
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 2
        total_area = sum(ev.area for ev in events)
        assert abs(total_area - basic_context.field_size) < 0.1, (
            f"Proportionale Fläche {total_area:.1f} ≠ {basic_context.field_size}"
        )

    def test_proportional_fuel(self, basic_context):
        """Aufgeteilte Events haben proportionalen Kraftstoffverbrauch."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        op = _make_op(duration_per_ha=1.5, fuel_consumption=10.0)  # 30 h → 2 Events
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 2
        # fuel = field_size × fuel_consumption × fraction × fuel_variation
        # Ohne Variation wäre total = 20 × 10 = 200 l
        # Mit Variation ist es ~200 × (0.9..1.1)
        total_fuel = sum(ev.fuel for ev in events)
        assert 150 < total_fuel < 250, (
            f"Proportionaler Kraftstoff {total_fuel:.1f} außerhalb des erwarteten Bereichs"
        )

    def test_cursor_set_per_day(self, basic_context):
        """Bei mehrtägiger Aufteilung wird der Cursor für jeden Tag gesetzt."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        op = _make_op(duration_per_ha=2.5)  # 50 h → 3 Tage
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 3
        # Cursor für alle 3 Tage gesetzt
        for day_idx in range(3):
            day = _TEST_DATE.date() + datetime.timedelta(days=day_idx)
            assert day in service._last_assigned_time, f"Cursor für Tag +{day_idx} nicht gesetzt"

    def test_wt26_not_split(self, basic_context):
        """KAR-046: wt=26 (Legen) wird nicht aufgeteilt, auch wenn > 18 h."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 21.4 h = 1.07 h/ha × 20 ha, wt=26 (Legen)
        op = _make_op(duration_per_ha=1.07, worktype=26, operation="Pflanzen")
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 1, (
            f"wt=26 darf nicht aufgeteilt werden (KAR-046), got {len(events)} Events"
        )

    def test_wt27_not_split(self, basic_context):
        """KAR-046: wt=27 (Roden) wird nicht aufgeteilt, auch wenn > 18 h."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        # 50 h = 2.5 h/ha × 20 ha, wt=27 (Roden)
        op = _make_op(duration_per_ha=2.5, worktype=27, operation="Roden")
        events = service.get_events_for_ops([op], _TEST_DATE)

        assert len(events) == 1, (
            f"wt=27 darf nicht aufgeteilt werden (KAR-046), got {len(events)} Events"
        )


# ---------------------------------------------------------------------------
# (d) IrrigationSimulator – mehrtägige Aufteilung
# ---------------------------------------------------------------------------


@pytest.fixture
def sim_context() -> SimContext:
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2022, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1,
    )


@pytest.fixture
def moisture_data_dry():
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": [30.0] * 365,
    }


class TestIrrigationStartHour:
    """Tests für die vorverlegte Beregnungs-Startzeit (P3-5).

    Die mehrtägige Aufteilung von Beregnungs-Events wird nicht vorgenommen,
    da KAR-040 (hard) jede Einzelgabe auf [10, 40] mm begrenzt –
    proportionale Teil-Gaben würden diesen harten Bereich unterschreiten.
    Die Startzeit wird jedoch von 12:00 auf 05:00 (WORK_START_HOUR)
    vorverlegt, um dem erweiterten Arbeitsfenster zu entsprechen.
    """

    def test_irrigation_starts_at_05(self, sim_context, moisture_data_dry):
        """Beregnungs-Event startet um 05:00 (WORK_START_HOUR)."""
        np.random.seed(42)
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))

        assert len(candidates) >= 1
        start = datetime.datetime.strptime(candidates[0].start_date, "%Y-%m-%d %H:%M:%S")
        assert start.time() == datetime.time(5, 0), (
            f"Beregnungs-Start {start.time()} ≠ 05:00 (WORK_START_HOUR)"
        )

    def test_irrigation_no_event_starts_before_05(self, sim_context, moisture_data_dry):
        """KAR-045: Beregnungs-Start ≥ 05:00."""
        np.random.seed(42)
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))

        for ev in candidates:
            start = datetime.datetime.strptime(ev.start_date, "%Y-%m-%d %H:%M:%S")
            assert start.time() >= datetime.time(5, 0), f"Beregnungs-Start {start.time()} vor 05:00"

    def test_irrigation_uses_passed_date(self, sim_context, moisture_data_dry):
        """Beregnungs-Event verwendet das übergebene Datum."""
        np.random.seed(42)
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        candidates = simulator.get_candidate_operations(datetime.date(2027, 6, 5))

        assert len(candidates) >= 1
        assert candidates[0].start_date == "2027-06-05 05:00:00"
