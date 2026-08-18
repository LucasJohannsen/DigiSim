"""Unit-Tests für DeadlineAwarePriorityStrategy (P3-4, Issue #82).

Verifies the deadline-aware priority logic for terminkritische Operationen
(Fungizide). Die Strategie erweitert ``WorkTypePriorityStrategy`` um
Fälligkeitsberücksichtigung:

- Überfällige kritische Ops werden auch bei High-Prio-Konkurrenz ausgeführt.
- Im-Fenster-kritische Ops werden mit High-Prio zusammen ausgeführt.
- Nicht-kritische Low-Prio-Ops werden bei High-Prio-Konkurrenz unterdrückt
  (Bestandsschutz).
- Nur Low-Prio-Ops → alle werden ausgeführt.
- Leere Liste → None.
- Operation ohne is_critical/due_date → wird als "andere" behandelt.

Konzept: ``documentation/konzepte/P3-4_pflanzenschutz_prio.md``
"""

from __future__ import annotations

import datetime

import pytest

from scheduler.decision_manager import DeadlineAwarePriorityStrategy
from models.worktypes import WorkType


_TEST_DATE = datetime.datetime(2027, 6, 15)


def _make_op(
    worktype: int,
    planned_date: datetime.datetime | None = _TEST_DATE,
    is_critical: bool = False,
    due_date: datetime.datetime | None = None,
    name: str = "Op",
) -> object:
    """Erzeuge eine minimale Mock-Operation für Strategie-Tests."""

    class _Op:
        def __init__(self) -> None:
            self.worktype = worktype
            self.planned_date = planned_date
            self.is_critical = is_critical
            self.due_date = due_date
            self.operation = name
            self.worktype_text = name

    return _Op()


@pytest.fixture
def strategy() -> DeadlineAwarePriorityStrategy:
    """DeadlineAwarePriorityStrategy-Instanz."""
    return DeadlineAwarePriorityStrategy()


class TestDeadlineAwarePriorityStrategy:
    """Unit-Tests für die Fälligkeits-Prioritätsstrategie."""

    def test_empty_operations_returns_none(self, strategy):
        """(e) Leere Liste → None."""
        assert strategy.select_operation([]) is None

    def test_overdue_critical_executed_despite_high_prio(self, strategy):
        """(a) Überfällige kritische Op wird trotz High-Prio-Konkurrenz ausgeführt.

        Fungizid (wt=14, is_critical=True) ist überfällig (planned_date >
        due_date). High-Prio-Op (wt=23 Düngung) existiert. Die kritische
        Op MUSS ausgeführt werden, die High-Prio-Op ebenfalls, aber keine
        Low-Prio-Op.
        """
        overdue_fungicide = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 10),
            name="Fungizid überfällig",
        )
        high_prio = _make_op(
            worktype=WorkType.MINERALISCHE_DUENGUNG,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Düngung",
        )
        low_prio = _make_op(
            worktype=WorkType.BEREGNEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Beregnung",
        )

        result = strategy.select_operation([overdue_fungicide, high_prio, low_prio])

        assert result is not None
        assert overdue_fungicide in result
        assert high_prio in result
        # Low-Prio wird unterdrückt (Stauung vermeiden).
        assert low_prio not in result

    def test_in_window_critical_executed_with_high_prio(self, strategy):
        """(b) Im-Fenster-kritische Op wird mit High-Prio zusammen ausgeführt.

        Fungizid (wt=14, is_critical=True) ist noch im Fenster
        (planned_date <= due_date). High-Prio-Op existiert. Beide werden
        ausgeführt, Low-Prio unterdrückt.
        """
        in_window_fungicide = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 20),
            name="Fungizid im Fenster",
        )
        high_prio = _make_op(
            worktype=WorkType.MINERALISCHE_DUENGUNG,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Düngung",
        )
        low_prio = _make_op(
            worktype=WorkType.BEREGNEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Beregnung",
        )

        result = strategy.select_operation(
            [in_window_fungicide, high_prio, low_prio]
        )

        assert result is not None
        assert in_window_fungicide in result
        assert high_prio in result
        # Low-Prio wird unterdrückt.
        assert low_prio not in result

    def test_non_critical_low_prio_suppressed_by_high_prio(self, strategy):
        """(c) Nicht-kritische Low-Prio-Op wird bei High-Prio unterdrückt (Bestandsschutz).

        Spritzung (wt=14) ohne is_critical + High-Prio-Op → Spritzung
        unterdrückt (Standard-Logik wie WorkTypePriorityStrategy).
        """
        non_critical_spray = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=False,
            name="Sikkation (nicht kritisch)",
        )
        high_prio = _make_op(
            worktype=WorkType.PFLANZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Pflanzen",
        )

        result = strategy.select_operation([non_critical_spray, high_prio])

        assert result is not None
        assert high_prio in result
        assert non_critical_spray not in result

    def test_only_low_prio_all_executed(self, strategy):
        """(d) Nur Low-Prio-Ops → alle werden ausgeführt."""
        spray = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Spritzen",
        )
        irrigate = _make_op(
            worktype=WorkType.BEREGNEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Beregnung",
        )

        result = strategy.select_operation([spray, irrigate])

        assert result is not None
        assert len(result) == 2
        assert spray in result
        assert irrigate in result

    def test_op_without_is_critical_treated_as_other(self, strategy):
        """(f) Operation ohne is_critical/due_date → wird als "andere" behandelt.

        Eine Op ohne is_critical-Attribut (getattr-Default False) und ohne
        due_date wird wie eine Standard-Operation behandelt.
        """
        spray_no_critical = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=False,
            due_date=None,
            name="Spritzen ohne Fälligkeit",
        )
        high_prio = _make_op(
            worktype=WorkType.PFLUEGEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Pflügen",
        )

        result = strategy.select_operation([spray_no_critical, high_prio])

        assert result is not None
        assert high_prio in result
        # Low-Prio ohne is_critical wird bei High-Prio unterdrückt.
        assert spray_no_critical not in result

    def test_overdue_critical_alone_executed(self, strategy):
        """Überfällige kritische Op allein → wird ausgeführt."""
        overdue = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 10),
            name="Fungizid überfällig",
        )

        result = strategy.select_operation([overdue])

        assert result is not None
        assert overdue in result

    def test_overdue_critical_with_low_prio_only(self, strategy):
        """Überfällige kritische Op + nur Low-Prio → kritische + Low-Prio unterdrückt?

        Nein: Bei überfällig-kritisch werden Low-Prio-Ops unterdrückt
        (Stauung vermeiden), nur kritische + High-Prio ausgeführt. Da hier
        keine High-Prio existiert, wird nur die kritische Op ausgeführt.
        """
        overdue = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 10),
            name="Fungizid überfällig",
        )
        low_prio = _make_op(
            worktype=WorkType.BEREGNEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Beregnung",
        )

        result = strategy.select_operation([overdue, low_prio])

        assert result is not None
        assert overdue in result
        # Low-Prio wird unterdrückt (kein High-Prio, aber überfällig-kritisch
        # unterdrückt Low-Prio).
        assert low_prio not in result

    def test_planned_date_none_treated_as_in_window(self, strategy):
        """planned_date=None → Op wird als nicht-überfällig behandelt (Fallback).

        Eine kritische Op ohne planned_date kann nicht als überfällig
        erkannt werden → wird als im-Fenster-kritisch behandelt.
        """
        critical_no_date = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=None,
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 10),
            name="Fungizid ohne planned_date",
        )
        high_prio = _make_op(
            worktype=WorkType.PFLANZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Pflanzen",
        )

        result = strategy.select_operation([critical_no_date, high_prio])

        assert result is not None
        # Im-Fenster-kritisch + High-Prio werden ausgeführt.
        assert critical_no_date in result
        assert high_prio in result

    def test_multiple_overdue_critical_all_executed(self, strategy):
        """Mehrere überfällige kritische Ops → alle werden ausgeführt."""
        overdue1 = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 10),
            name="Fungizid 1",
        )
        overdue2 = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 12),
            name="Fungizid 2",
        )

        result = strategy.select_operation([overdue1, overdue2])

        assert result is not None
        assert overdue1 in result
        assert overdue2 in result

    def test_in_window_critical_suppresses_low_prio(self, strategy):
        """Im-Fenster-kritische Op unterdrückt Low-Prio (wie High-Prio)."""
        in_window = _make_op(
            worktype=WorkType.SPRITZEN,
            planned_date=datetime.datetime(2027, 6, 15),
            is_critical=True,
            due_date=datetime.datetime(2027, 6, 20),
            name="Fungizid im Fenster",
        )
        low_prio = _make_op(
            worktype=WorkType.BEREGNEN,
            planned_date=datetime.datetime(2027, 6, 15),
            name="Beregnung",
        )

        result = strategy.select_operation([in_window, low_prio])

        assert result is not None
        assert in_window in result
        # Low-Prio wird durch im-Fenster-kritische unterdrückt.
        assert low_prio not in result
