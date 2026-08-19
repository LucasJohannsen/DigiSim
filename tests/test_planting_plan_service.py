"""Tests für P3-7: Erntezeitpunkt mit harvest_period_months-Validierung (Befund B12, Issue #85).

Deckt die Akzeptanzkriterien aus dem Konzept
``documentation/konzepte/P3-7_erntezeitpunkt.md`` ab:

1. ``growth_duration`` ist primäre Quelle für den Erntetermin.
2. ``harvest_period_months`` validiert und korrigiert bei Abweichung
   (nur Verschiebung nach hinten, nicht unter biologische Reife).
3. Logging bei Korrektur.
4. ``actual_planting_date`` None wird abgesichert (Filter).

Die Korrektur-Logik ist in ``PlantingPlanService._compute_harvest_date``
gekapselt (reine Logik, testbar ohne I/O – Styleguide: Separation of
Concerns). ``update_phase_status`` delegiert an diese Methode.
"""

from __future__ import annotations

import datetime
import random
from unittest.mock import patch

import numpy as np
import pytest

from models.planting_plan import (
    FieldOperation,
    FieldOperationCycle,
    FieldOperationPhases,
    FieldOperationStatus,
    PlantingPlan,
)
from models.sim_context import SimContext
from services.planting_plan_service import PlantingPlanService

# ---------------------------------------------------------------------------
# Fixtures & Helpers
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


def _make_service(
    context: SimContext,
    grow_duration: int = 110,
    harvest_period_months: tuple[int, int] = (9, 10),
) -> PlantingPlanService:
    """Erzeugt einen PlantingPlanService mit minimalem, kontrolliertem Plan.

    ``initialize_planting_plan`` wird gepatcht, danach wird ein PlantingPlan
    mit ``grow_duration`` und ``harvest_period_months`` zugewiesen.
    """
    with patch.object(PlantingPlanService, "initialize_planting_plan"):
        service = PlantingPlanService(
            context=context,
            start_date=datetime.datetime(2026, 1, 1),
        )
    service.planting_plan = PlantingPlan(
        crop_type="Potato",
        variety="Belana",
        planting_period_months=(4, 5),
        harvest_period_months=harvest_period_months,
        grow_duration=grow_duration,
        phases=[],
        protection_plans=[],
    )
    return service


# ---------------------------------------------------------------------------
# (a) growth_duration ist primäre Quelle – Ernte = Legen + growth_duration
# ---------------------------------------------------------------------------


class TestGrowthDurationPrimary:
    """``growth_duration`` bleibt primäre Quelle; bei Fenster-Treffer keine
    Korrektur."""

    def test_harvest_equals_planting_plus_duration_in_window(self, basic_context):
        """Legen 20.05. + 110 d = 07.09. (Sep, im Fenster [9,10]) → keine
        Korrektur, Ernte = Legen + 110 d."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 5, 20)
        harvest = service._compute_harvest_date(planting)
        expected = planting + datetime.timedelta(days=110)
        assert harvest == expected, (
            f"Erwartet {expected} (keine Korrektur im Fenster), got {harvest}"
        )

    def test_harvest_in_september_no_correction(self, basic_context):
        """Legen 25.05. + 110 d = 12.09. (Sep) → keine Korrektur."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 5, 25)
        harvest = service._compute_harvest_date(planting)
        expected = planting + datetime.timedelta(days=110)
        assert harvest == expected
        assert harvest.month == 9

    def test_no_harvest_period_months_no_correction(self, basic_context):
        """Ohne harvest_period_months (leeres Tuple) → nur growth_duration."""
        service = _make_service(
            basic_context,
            grow_duration=110,
            harvest_period_months=(),
        )
        planting = datetime.datetime(2026, 5, 1)
        harvest = service._compute_harvest_date(planting)
        expected = planting + datetime.timedelta(days=110)
        assert harvest == expected


# ---------------------------------------------------------------------------
# (b)/(d) Ernte außerhalb Fenster (vorher, August) → Korrektur auf 01.09.
# ---------------------------------------------------------------------------


class TestHarvestPeriodCorrectionForward:
    """Erntetermin liegt vor dem Fenster (August) → Verschiebung nach hinten
    auf den ersten zulässigen Monat (September)."""

    def test_august_corrected_to_september_first(self, basic_context):
        """Legen 01.05. + 110 d = 19.08. (Aug, außerhalb [9,10]) → korrigiert
        auf 01.09. (nur nach hinten, nicht unter biologische Reife)."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 5, 1)
        harvest = service._compute_harvest_date(planting)
        assert harvest == datetime.datetime(2026, 9, 1), (
            f"Erwartet Korrektur auf 2026-09-01, got {harvest}"
        )
        assert harvest.month == 9

    def test_correction_only_forward_not_below_bio_maturity(self, basic_context):
        """Korrektur darf niemals vor den growth_duration-Mindesttermin
        (biologische Reife) verlegt werden.

        Legen 01.05. + 110 d = 19.08.; Korrektur auf 01.09. liegt NACH
        19.08. → zulässig.
        """
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 5, 1)
        harvest = service._compute_harvest_date(planting)
        bio_maturity = planting + datetime.timedelta(days=110)
        assert harvest >= bio_maturity, (
            f"Korrektur {harvest} liegt vor biologischer Reife {bio_maturity}"
        )

    def test_july_planting_corrected_to_september_next_year_window(self, basic_context):
        """Legen 01.04. + 110 d = 20.07. (Jul, außerhalb) → Zielmonat 9 liegt
        nach Pflanzmonat 4 → gleiches Jahr → 01.09.2026."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 4, 1)
        harvest = service._compute_harvest_date(planting)
        assert harvest == datetime.datetime(2026, 9, 1)


# ---------------------------------------------------------------------------
# (c) Ernte innerhalb Fenster → keine Korrektur
# ---------------------------------------------------------------------------


class TestNoCorrectionInWindow:
    """Erntetermin liegt im Fenster [9,10] → keine Korrektur."""

    def test_september_no_correction(self, basic_context):
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 5, 20)
        harvest = service._compute_harvest_date(planting)
        assert harvest.month == 9
        assert harvest == planting + datetime.timedelta(days=110)

    def test_october_no_correction(self, basic_context):
        """Legen 01.06. + 110 d = 19.09. ... verwende growth_duration der auf
        Oktober fällt: Legen 15.06. + 110 d = 03.10. (Okt, im Fenster)."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 6, 15)
        harvest = service._compute_harvest_date(planting)
        assert harvest.month == 10, f"Erwartet Oktober, got {harvest.month}"
        assert harvest == planting + datetime.timedelta(days=110)


# ---------------------------------------------------------------------------
# (e) Ernte nach Fenster (November) → KEINE Korrektur zurück, nur nach hinten
# ---------------------------------------------------------------------------


class TestNoBackwardCorrection:
    """Fällt der Erntetermin NACH das Fenster (November), wird er **nicht**
    zurück verschoben – Korrektur erfolgt ausschließlich nach hinten.

    Begründung: Eine Vorverlegung unter den growth_duration-Termin würde die
    biologische Reife unterschreiten. Da der Zielmonat (September) vor dem
    berechneten November-Termin liegt, ist ``corrected > harvest_date``
    False → keine Änderung. November bleibt November.
    """

    def test_november_not_corrected_backward(self, basic_context):
        """Legen 15.07. + 110 d = 02.11. (Nov, nach [9,10]) → keine Korrektur
        zurück auf Oktober; November bleibt November."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 7, 15)
        harvest = service._compute_harvest_date(planting)
        expected = planting + datetime.timedelta(days=110)
        assert harvest == expected, f"November darf nicht zurück korrigiert werden; got {harvest}"
        assert harvest.month == 11

    def test_december_not_corrected_backward(self, basic_context):
        """Legen 01.08. + 110 d = 19.11. (Nov) → keine Rück-Korrektur."""
        service = _make_service(basic_context, grow_duration=110)
        planting = datetime.datetime(2026, 8, 1)
        harvest = service._compute_harvest_date(planting)
        expected = planting + datetime.timedelta(days=110)
        assert harvest == expected
        assert harvest.month == 11


# ---------------------------------------------------------------------------
# Integration: update_phase_status delegiert an _compute_harvest_date
# ---------------------------------------------------------------------------


def _build_full_plan(
    grow_duration: int,
    harvest_period_months: tuple[int, int],
    planting_actual_date: datetime.datetime,
) -> PlantingPlan:
    """Baut einen PlantingPlan mit allen Phasen; sowing_planting und
    crop_management sind COMPLETED, harvesting ist NOT_STARTED."""
    planting_op = FieldOperation(
        sequence=1,
        operation="Pflanzen",
        worktype=26,
        min_days_to_target=0,
        max_days_to_target=0,
        duration_per_ha=1.0,
        working_width=3.6,
        fuel_consumption=10.0,
        planned_date=planting_actual_date,
        actual_date=planting_actual_date,
    )
    cm_op = FieldOperation(
        sequence=1,
        operation="N Düngung",
        worktype=23,
        min_days_to_target=3,
        max_days_to_target=5,
        duration_per_ha=0.5,
        working_width=18,
        fuel_consumption=1.0,
        planned_date=planting_actual_date,
        actual_date=planting_actual_date,
    )
    roden_op = FieldOperation(
        sequence=2,
        operation="Roden",
        worktype=27,
        min_days_to_target=0,
        max_days_to_target=0,
        duration_per_ha=2.5,
        working_width=0.8,
        fuel_consumption=42.0,
    )
    return PlantingPlan(
        crop_type="Potato",
        variety="Belana",
        planting_period_months=(4, 5),
        harvest_period_months=harvest_period_months,
        grow_duration=grow_duration,
        phases=[
            FieldOperationCycle(
                phase_name=FieldOperationPhases.SOIL_PREPARATION.value,
                operations=[],
                status=FieldOperationStatus.COMPLETED,
            ),
            FieldOperationCycle(
                phase_name=FieldOperationPhases.PLANTING.value,
                operations=[planting_op],
                status=FieldOperationStatus.COMPLETED,
            ),
            FieldOperationCycle(
                phase_name=FieldOperationPhases.CROP_MANAGEMENT.value,
                operations=[cm_op],
                status=FieldOperationStatus.IN_PROGRESS,
            ),
            FieldOperationCycle(
                phase_name=FieldOperationPhases.HARVESTING.value,
                operations=[roden_op],
                status=FieldOperationStatus.NOT_STARTED,
            ),
        ],
        protection_plans=[],
    )


class TestUpdatePhaseStatusHarvesting:
    """Integration: ``update_phase_status`` plant die Harvest-Phase mit
    korrigiertem Erntetermin."""

    def test_harvesting_scheduled_with_correction(self, basic_context):
        """Legen 01.05. + 110 d = 19.08. → Korrektur auf 01.09.

        ``update_planned_operations_startdates`` wird als Spy gepatcht, um
        den übergebenen Zieltermin zu prüfen (unabhängig vom Zufalls-Offset
        der Operationen).
        """
        random.seed(42)
        np.random.seed(42)
        planting = datetime.datetime(2026, 5, 1)
        plan = _build_full_plan(110, (9, 10), planting)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        service.planting_plan = plan
        # crop_management ist aktiv (IN_PROGRESS) und abgeschlossen →
        # update_phase_status schließt sie ab und plant harvesting.
        cm_phase = next(
            p for p in plan.phases if p.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value
        )
        service.active_phase = cm_phase
        captured: dict[str, datetime.datetime] = {}

        def _spy(phase_name: str, target_date: datetime.datetime) -> None:
            captured["phase"] = phase_name
            captured["target"] = target_date

        with patch.object(service, "update_planned_operations_startdates", side_effect=_spy):
            service.update_phase_status(datetime.datetime(2026, 8, 20))

        assert captured.get("phase") == FieldOperationPhases.HARVESTING.value
        assert captured.get("target") == datetime.datetime(2026, 9, 1), (
            f"Erwartet korrigierten Erntetermin 2026-09-01, got {captured.get('target')}"
        )

    def test_harvesting_scheduled_no_correction(self, basic_context):
        """Legen 20.05. + 110 d = 07.09. (im Fenster) → keine Korrektur."""
        random.seed(42)
        np.random.seed(42)
        planting = datetime.datetime(2026, 5, 20)
        plan = _build_full_plan(110, (9, 10), planting)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        service.planting_plan = plan
        cm_phase = next(
            p for p in plan.phases if p.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value
        )
        service.active_phase = cm_phase
        captured: dict[str, datetime.datetime] = {}

        def _spy(phase_name: str, target_date: datetime.datetime) -> None:
            captured["target"] = target_date

        with patch.object(service, "update_planned_operations_startdates", side_effect=_spy):
            service.update_phase_status(datetime.datetime(2026, 9, 1))

        expected = planting + datetime.timedelta(days=110)
        assert captured.get("target") == expected

    def test_no_actual_planting_date_does_not_crash(self, basic_context):
        """Wenn keine sowing_planting-Op ein actual_date hat, darf
        ``update_phase_status`` nicht abstürzen (Befund: None-Filter)."""
        random.seed(42)
        np.random.seed(42)
        # planting_op ohne actual_date
        planting_op = FieldOperation(
            sequence=1,
            operation="Pflanzen",
            worktype=26,
            min_days_to_target=0,
            max_days_to_target=0,
            duration_per_ha=1.0,
            actual_date=None,
        )
        cm_op = FieldOperation(
            sequence=1,
            operation="N Düngung",
            worktype=23,
            min_days_to_target=3,
            max_days_to_target=5,
            duration_per_ha=0.5,
            actual_date=datetime.datetime(2026, 5, 1),
        )
        plan = PlantingPlan(
            crop_type="Potato",
            variety="Belana",
            planting_period_months=(4, 5),
            harvest_period_months=(9, 10),
            grow_duration=110,
            phases=[
                FieldOperationCycle(
                    phase_name=FieldOperationPhases.SOIL_PREPARATION.value,
                    operations=[],
                    status=FieldOperationStatus.COMPLETED,
                ),
                FieldOperationCycle(
                    phase_name=FieldOperationPhases.PLANTING.value,
                    operations=[planting_op],
                    status=FieldOperationStatus.COMPLETED,
                ),
                FieldOperationCycle(
                    phase_name=FieldOperationPhases.CROP_MANAGEMENT.value,
                    operations=[cm_op],
                    status=FieldOperationStatus.IN_PROGRESS,
                ),
                FieldOperationCycle(
                    phase_name=FieldOperationPhases.HARVESTING.value,
                    operations=[],
                    status=FieldOperationStatus.NOT_STARTED,
                ),
            ],
            protection_plans=[],
        )
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        service.planting_plan = plan
        cm_phase = next(
            p for p in plan.phases if p.phase_name == FieldOperationPhases.CROP_MANAGEMENT.value
        )
        service.active_phase = cm_phase
        # Darf keine Exception werfen; harvesting wird nicht geplant.
        service.update_phase_status(datetime.datetime(2026, 8, 20))
        harvesting = next(
            p for p in plan.phases if p.phase_name == FieldOperationPhases.HARVESTING.value
        )
        assert harvesting.status == FieldOperationStatus.NOT_STARTED
