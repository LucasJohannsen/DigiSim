"""Tests für P2-2: Intra-Tages-Sequenz bei Event-Erzeugung (Befund B7, Issue #66).

Deckt die Akzeptanzkriterien aus dem Konzept
``documentation/konzepte/P2-2_intra_tages_sequenz.md`` ab:

1. ``assign_sequential_time`` — Hilfsfunktion für strikt monotone
   Uhrzeitvergabe pro Kalendertag.
2. ``PlantingPlanService.get_events_for_ops`` — Cursor-basierte
   sequenzkonforme Uhrzeitvergabe bei Einzel-Calls (realistisches
   Aufrufmuster aus ``CalendarDrivenRunner.tick()``).
3. ``ProtectionPlanService.get_events_for_ops`` — analog, eigener Cursor.
4. Edge-Cases: 1 Operation, Cursor-Erschöpfung, Tagesgrenze.
5. Regressionstest: ``CalendarDrivenRunner.tick()`` übergibt Operationen
   in sequenz-/kandidatenerhaltender Reihenfolge an ``get_events_for_ops``.
6. Integration: FF-Lauf Seed 42 — Pflanzguttransport (wt=18) startet vor
   dem Legen (wt=26) am selben Tag (KAR-003).
"""

from __future__ import annotations

import contextlib
import datetime
import io
import random
from unittest.mock import Mock, patch

import numpy as np
import pytest

from models.planting_plan import FieldOperation, FieldOperationEvent
from models.sim_context import SimContext
from models.worktypes import WorkType
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from scheduler.fast_forward_runner import FastForwardRunner
from services.planting_plan_service import PlantingPlanService
from services.protection_plan_service import ProtectionPlanService
from utils.sim_helper import assign_sequential_time


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_DATE = datetime.datetime(2026, 5, 10, 0, 0)


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


@pytest.fixture
def mock_planting_plan_service():
    """Mock-PlantingPlanService für CalendarDrivenRunner-Regressionstests."""
    service = Mock()
    service.get_next_operations = Mock(return_value=[])
    service.get_events_for_ops = Mock(return_value=[])
    service.active_phase = None
    return service


def _make_op(
    sequence: int,
    worktype: int = WorkType.KARTOFFELN_LEGEN,
    operation: str = "Legen",
    planned_date: datetime.datetime = _TEST_DATE,
) -> FieldOperation:
    """Erzeuge eine minimale FieldOperation für Tests."""
    return FieldOperation(
        sequence=sequence,
        operation=operation,
        worktype=worktype,
        duration_per_ha=0.5,
        working_width=3.0,
        fuel_consumption=10.0,
        planned_date=planned_date,
        actual_date=None,
    )


# ---------------------------------------------------------------------------
# 1. Unit-Tests: assign_sequential_time
# ---------------------------------------------------------------------------


class TestAssignSequentialTime:
    """Unit-Tests für die Hilfsfunktion ``assign_sequential_time``."""

    def test_first_call_full_window(self):
        """Erster Call ohne Cursor -> Zeit im vollen Fenster [06:00, 17:00]."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        result = assign_sequential_time(d)
        assert result.date() == d.date()
        assert result.time() >= datetime.time(6, 0)
        assert result.time() <= datetime.time(17, 0)

    def test_second_call_strictly_later(self):
        """Folge-Call mit min_start = Ergebnis des ersten -> strikt später."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        t1 = assign_sequential_time(d)
        t2 = assign_sequential_time(d, min_start=t1.time())
        assert t2 > t1, f"t2 ({t2}) muss strikt nach t1 ({t1}) liegen"

    def test_within_window(self):
        """Alle Zeitpunkte liegen im Fenster [min_start, max_end]."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        for _ in range(20):
            t = assign_sequential_time(d)
            assert datetime.time(6, 0) <= t.time() <= datetime.time(17, 0)

    def test_custom_window(self):
        """Custom-Fenster wird respektiert."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        t = assign_sequential_time(d, min_start=datetime.time(8, 0), max_end=datetime.time(10, 0))
        assert t.time() >= datetime.time(8, 0)
        assert t.time() <= datetime.time(10, 0)

    def test_window_exhausted_clamp(self):
        """Fenster < 1 Minute -> deterministischer Fallback min_start + 1 Min."""
        d = datetime.datetime(2026, 5, 10)
        t = assign_sequential_time(
            d,
            min_start=datetime.time(16, 59, 30),
            max_end=datetime.time(17, 0),
        )
        # Fenster = 30 Sekunden < 60 -> Clamp: 16:59:30 + 1 Min = 17:00:30
        expected = datetime.datetime(2026, 5, 10, 17, 0, 30)
        assert t == expected

    def test_window_exactly_one_minute(self):
        """Fenster = exakt 1 Minute -> normaler Zufall (offset in [1, 60])."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        t = assign_sequential_time(
            d,
            min_start=datetime.time(16, 59, 0),
            max_end=datetime.time(17, 0, 0),
        )
        assert t.time() > datetime.time(16, 59, 0)
        assert t.time() <= datetime.time(17, 0, 0)

    def test_monotonicity_over_many_calls(self):
        """10 aufeinanderfolgende Calls -> strikt monoton steigend."""
        random.seed(42)
        d = datetime.datetime(2026, 5, 10)
        times: list[datetime.datetime] = []
        min_start = datetime.time(6, 0)
        for _ in range(10):
            t = assign_sequential_time(d, min_start=min_start)
            times.append(t)
            min_start = t.time()
        for i in range(1, len(times)):
            assert times[i] > times[i - 1], (
                f"Verletzung der Monotonie an Position {i}: "
                f"{times[i]} <= {times[i-1]}"
            )


# ---------------------------------------------------------------------------
# 2. Unit-Tests: PlantingPlanService.get_events_for_ops
# ---------------------------------------------------------------------------


class TestPlantingPlanServiceIntradaySequence:
    """Tests für die sequenzkonforme Uhrzeitvergabe im PlantingPlanService."""

    def test_single_op_full_window(self, basic_context):
        """AK3: 1 Operation -> Uhrzeit im Fenster [05:00, 20:00].

        P3-5 (Issue #83): PlantingPlanService übergibt explizit [05:00, 20:00].
        """
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        op = _make_op(sequence=1)
        events = service.get_events_for_ops([op], _TEST_DATE)
        assert len(events) == 1
        start = datetime.datetime.strptime(events[0].start_date, "%Y-%m-%d %H:%M:%S")
        assert start.time() >= datetime.time(5, 0)
        assert start.time() <= datetime.time(20, 0)

    def test_two_single_calls_same_day_monotonic(self, basic_context):
        """AK1: Zwei EINZEL-Calls [op1], [op2] mit seq1<seq2 -> event1 < event2.

        Bildet exakt das reale Aufrufmuster aus CalendarDrivenRunner.tick()
        ab (kein Batch-Call mit [op1, op2]).
        """
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        op1 = _make_op(sequence=1, worktype=WorkType.TRANSPORTIEREN, operation="Pflanzguttransport")
        op2 = _make_op(sequence=2, worktype=WorkType.KARTOFFELN_LEGEN, operation="Legen")

        events1 = service.get_events_for_ops([op1], _TEST_DATE)
        events2 = service.get_events_for_ops([op2], _TEST_DATE)

        t1 = datetime.datetime.strptime(events1[0].start_date, "%Y-%m-%d %H:%M:%S")
        t2 = datetime.datetime.strptime(events2[0].start_date, "%Y-%m-%d %H:%M:%S")
        assert t1 < t2, (
            f"Pflanzguttransport (seq1) muss VOR Legen (seq2) starten: "
            f"{t1} >= {t2}"
        )

    def test_cursor_does_not_leak_across_days(self, basic_context):
        """AK5: Cursor gilt nicht über Tagesgrenzen (neues Datum -> volles Fenster)."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        date_a = datetime.datetime(2026, 5, 10)
        date_b = datetime.datetime(2026, 5, 11)

        # Erste Op an Tag A -> setzt Cursor
        op_a = _make_op(sequence=1)
        service.get_events_for_ops([op_a], date_a)

        # Erste Op an Tag B -> muss volles Fenster haben (Cursor nicht geerbt)
        op_b = _make_op(sequence=1)
        events_b = service.get_events_for_ops([op_b], date_b)
        t_b = datetime.datetime.strptime(events_b[0].start_date, "%Y-%m-%d %H:%M:%S")
        # Wenn der Cursor von Tag A geerbt wuerde, waere min_start > 06:00.
        # Mit vollem Fenster kann die Uhrzeit ab 06:00:01 liegen.
        # Wir pruefen, dass der Cursor fuer Tag B leer ist:
        assert date_b.date() not in service._last_assigned_time or \
            service._last_assigned_time[date_b.date()] == op_b.actual_datetime
        # Die Uhrzeit muss im vollen Fenster liegen:
        assert t_b.time() >= datetime.time(6, 0)
        assert t_b.time() <= datetime.time(17, 0)

    def test_batch_call_preserves_order(self, basic_context):
        """Batch-Call [op1, op2] -> event1 < event2 (innerhalb eines Calls)."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        op1 = _make_op(sequence=1, worktype=WorkType.TRANSPORTIEREN, operation="Pflanzguttransport")
        op2 = _make_op(sequence=2, worktype=WorkType.KARTOFFELN_LEGEN, operation="Legen")

        events = service.get_events_for_ops([op1, op2], _TEST_DATE)
        assert len(events) == 2
        t1 = datetime.datetime.strptime(events[0].start_date, "%Y-%m-%d %H:%M:%S")
        t2 = datetime.datetime.strptime(events[1].start_date, "%Y-%m-%d %H:%M:%S")
        assert t1 < t2

    def test_all_times_within_window(self, basic_context):
        """AK4: Alle Uhrzeiten bleiben im Fenster [05:00, 20:00].

        P3-5 (Issue #83): PlantingPlanService übergibt explizit [05:00, 20:00].
        """
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            service = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        ops = [_make_op(sequence=i) for i in range(1, 6)]
        for op in ops:
            events = service.get_events_for_ops([op], _TEST_DATE)
            t = datetime.datetime.strptime(events[0].start_date, "%Y-%m-%d %H:%M:%S")
            assert datetime.time(5, 0) <= t.time() <= datetime.time(20, 0), (
                f"Uhrzeit {t.time()} ausserhalb [05:00, 20:00]"
            )


# ---------------------------------------------------------------------------
# 3. Unit-Tests: ProtectionPlanService.get_events_for_ops
# ---------------------------------------------------------------------------


class TestProtectionPlanServiceIntradaySequence:
    """Tests für die sequenzkonforme Uhrzeitvergabe im ProtectionPlanService."""

    def test_two_single_calls_same_day_monotonic(self, basic_context):
        """Zwei Einzel-Calls am selben Tag -> strikt monoton steigend."""
        random.seed(42)
        with patch.object(ProtectionPlanService, "plan_protections"):
            service = ProtectionPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 5, 1),
            )
        op1 = _make_op(sequence=1, worktype=WorkType.SPRITZEN, operation="Spritzen")
        op2 = _make_op(sequence=2, worktype=WorkType.SPRITZEN, operation="Spritzen")

        events1 = service.get_events_for_ops([op1], _TEST_DATE)
        events2 = service.get_events_for_ops([op2], _TEST_DATE)

        t1 = datetime.datetime.strptime(events1[0].start_date, "%Y-%m-%d %H:%M:%S")
        t2 = datetime.datetime.strptime(events2[0].start_date, "%Y-%m-%d %H:%M:%S")
        assert t1 < t2

    def test_single_op_full_window(self, basic_context):
        """1 Operation -> Uhrzeit im vollen Fenster [06:00, 17:00].

        P3-5: ProtectionPlanService behält Default-Fenster (keine Verschiebung).
        """
        random.seed(42)
        with patch.object(ProtectionPlanService, "plan_protections"):
            service = ProtectionPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 5, 1),
            )
        op = _make_op(sequence=1, worktype=WorkType.SPRITZEN, operation="Spritzen")
        events = service.get_events_for_ops([op], _TEST_DATE)
        t = datetime.datetime.strptime(events[0].start_date, "%Y-%m-%d %H:%M:%S")
        assert datetime.time(6, 0) <= t.time() <= datetime.time(17, 0)

    def test_cursor_separate_from_planting_service(self, basic_context):
        """Protection- und Planting-Service haben getrennte Cursor."""
        random.seed(42)
        with patch.object(PlantingPlanService, "initialize_planting_plan"):
            planting = PlantingPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 1, 1),
            )
        with patch.object(ProtectionPlanService, "plan_protections"):
            protection = ProtectionPlanService(
                context=basic_context,
                start_date=datetime.datetime(2026, 5, 1),
            )
        # Setze Planting-Cursor
        planting.get_events_for_ops([_make_op(sequence=1)], _TEST_DATE)
        # Protection-Cursor muss unberührt sein
        assert protection._last_assigned_time == {}
        # Protection kann frei im vollen Fenster starten
        op = _make_op(sequence=1, worktype=WorkType.SPRITZEN, operation="Spritzen")
        events = protection.get_events_for_ops([op], _TEST_DATE)
        t = datetime.datetime.strptime(events[0].start_date, "%Y-%m-%d %H:%M:%S")
        assert t.time() >= datetime.time(6, 0)


# ---------------------------------------------------------------------------
# 4. Regressionstest: CalendarDrivenRunner.tick() Aufrufreihenfolge
# ---------------------------------------------------------------------------


class TestCalendarDrivenRunnerOrderRegression:
    """AK6: tick() übergibt Operationen in sequenz-/kandidatenerhaltender Reihenfolge.

    Die Cursor-basierte Uhrzeitvergabe setzt voraus, dass die Execute-Schleife
    in ``tick()`` die Operationen in der Reihenfolge an ``get_events_for_ops``
    übergibt, in der sie aus ``selected_ops`` kommen - und dass diese
    Reihenfolge die Sequenz-/Kandidaten-Ordnung erhält. Dieser Test sichert
    diese Design-Annahme ab.
    """

    def test_tick_passes_ops_in_selected_order(
        self, basic_context, mock_planting_plan_service
    ):
        """tick() ruft get_events_for_ops pro Op in selected_ops-Reihenfolge auf."""
        test_date = datetime.date(2026, 5, 10)

        op1 = FieldOperation(
            sequence=1, operation="Pflanzguttransport",
            worktype=WorkType.TRANSPORTIEREN,
            duration_per_ha=0.5, working_width=3.0, fuel_consumption=10.0,
            planned_date=test_date, actual_date=None,
        )
        op2 = FieldOperation(
            sequence=2, operation="Legen",
            worktype=WorkType.KARTOFFELN_LEGEN,
            duration_per_ha=0.5, working_width=3.0, fuel_consumption=10.0,
            planned_date=test_date, actual_date=None,
        )

        # get_next_operations gibt sequenzsortiert zurueck (wie real).
        mock_planting_plan_service.get_next_operations.return_value = [op1, op2]
        # Protokolliere die Aufrufreihenfolge.
        call_order: list[list[FieldOperation]] = []
        def _record(ops, date):
            call_order.append(list(ops))
            return [FieldOperationEvent(worktype=op.worktype, worktype_text=op.operation) for op in ops]
        mock_planting_plan_service.get_events_for_ops.side_effect = _record
        mock_planting_plan_service.active_phase = None

        with patch(
            "scheduler.calendar_driven_runner.PlantingPlanService",
            return_value=mock_planting_plan_service,
        ):
            runner = CalendarDrivenRunner(basic_context)
            runner.tick(test_date)

        # Jede Operation wird einzeln uebergeben (Single-Op-Aufrufmuster).
        assert len(call_order) == 2
        assert call_order[0] == [op1]
        assert call_order[1] == [op2]
        # Reihenfolge entspricht der Sequenz: op1 (seq1) vor op2 (seq2).
        assert call_order[0][0].sequence < call_order[1][0].sequence


# ---------------------------------------------------------------------------
# 5. Integration: FF-Lauf Seed 42 - KAR-003 (Pflanzguttransport vor Legen)
# ---------------------------------------------------------------------------


_SEED = 42
_FIELD_ID = 990001
_FIELD_SIZE = 20.0
_N_DAYS = 760
_START_DATE = datetime.datetime(2026, 1, 1)


@pytest.fixture(scope="module")
def ff_simulation() -> dict:
    """Module-scoped FF-Lauf (Seed 42, 760 Tage) fuer Integrationstests."""
    random.seed(_SEED)
    np.random.seed(_SEED)
    ctx = SimContext(
        field_size=_FIELD_SIZE,
        soil_type="sandy_loam",
        start_date=_START_DATE,
        crop_type="Potato",
        variety="Belana",
        field_id=_FIELD_ID,
        field_name="Audit Field",
        fuel_variation=0.1,
    )
    runner = FastForwardRunner(
        context=ctx, n_days=_N_DAYS, output_target="stdout",
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        events = runner.run()
    return {"events": events}


class TestIntegrationKAR003:
    """Integrationstest: KAR-003 - Pflanzguttransport (wt=18) vor Legen (wt=26)."""

    def test_transport_before_planting_same_day(self, ff_simulation):
        """AK2: An jedem Tag mit beiden Ops gilt start(wt=18) < start(wt=26)."""
        events = ff_simulation["events"]
        transport_events = [e for e in events if e.worktype == WorkType.TRANSPORTIEREN]
        planting_events = [e for e in events if e.worktype == WorkType.KARTOFFELN_LEGEN]

        # Finde Tage, an denen beide Operationen ausgefuehrt wurden.
        transport_by_date: dict[datetime.date, list] = {}
        for e in transport_events:
            start = datetime.datetime.strptime(e.start_date, "%Y-%m-%d %H:%M:%S")
            transport_by_date.setdefault(start.date(), []).append(start)

        violations: list[str] = []
        for e in planting_events:
            p_start = datetime.datetime.strptime(e.start_date, "%Y-%m-%d %H:%M:%S")
            p_date = p_start.date()
            if p_date in transport_by_date:
                for t_start in transport_by_date[p_date]:
                    if t_start >= p_start:
                        violations.append(
                            f"wt=18 ({t_start}) >= wt=26 ({p_start}) am {p_date}"
                        )

        assert not violations, (
            f"KAR-003 verletzt: {len(violations)} Intra-Tages-Inversion(en): "
            + "; ".join(violations[:5])
        )

    def test_at_least_one_day_with_both_ops(self, ff_simulation):
        """Es gibt mindestens einen Tag mit beiden Ops (sonst ist der Test trivial)."""
        events = ff_simulation["events"]
        transport_dates = {
            datetime.datetime.strptime(e.start_date, "%Y-%m-%d %H:%M:%S").date()
            for e in events if e.worktype == WorkType.TRANSPORTIEREN
        }
        planting_dates = {
            datetime.datetime.strptime(e.start_date, "%Y-%m-%d %H:%M:%S").date()
            for e in events if e.worktype == WorkType.KARTOFFELN_LEGEN
        }
        common = transport_dates & planting_dates
        assert common, (
            "Erwartet mindestens einen Tag mit Pflanzguttransport UND Legen "
            "fuer einen aussagekraeftigen KAR-003-Test."
        )
