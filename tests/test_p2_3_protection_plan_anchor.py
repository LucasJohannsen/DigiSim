"""Tests for Issue #67 (P2-3): ProtectionPlanService anchor + pruning (B6)."""

from __future__ import annotations

import contextlib
import datetime
import io
import random
from unittest.mock import patch

import numpy as np
import pytest

from events.domain_event_bus import DomainEventBus
from models.planting_plan import PlantingPlan, Protection, ProtectionPlan
from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner
from scheduler.fast_forward_runner import FastForwardRunner
from services.protection_plan_service import (
    SIKKATION_CATEGORY,
    SIKKATION_MIN_DAYS_BEFORE_HARVEST,
    ProtectionPlanService,
)


def _make_context() -> SimContext:
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


def _make_planting_plan(protections, days_to_target=0, grow_duration=90):
    return PlantingPlan(
        crop_type="Potato",
        variety="Belana",
        planting_period_months=(4, 5),
        harvest_period_months=(9, 10),
        grow_duration=grow_duration,
        phases=[],
        protection_plans=[
            ProtectionPlan(
                name="Test",
                description="Test",
                days_to_target=days_to_target,
                protections=protections,
            )
        ],
    )


class TestProtectionPlanServiceAnchor:
    def test_anchor_is_planting_date(self):
        planting_date = datetime.datetime(2026, 5, 11)
        harvest_date = planting_date + datetime.timedelta(days=90)
        plan = _make_planting_plan([Protection(day=0, type=27, name="Op", amount="1.0")])
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": 27, "category": "F", "name": "F"}],
        ):
            svc = ProtectionPlanService(_make_context(), planting_date, plan, harvest_date)
        assert len(svc.operations) == 1
        assert svc.operations[0].planned_date.date() == planting_date.date()


class TestProtectionPlanServicePruning:
    def test_operations_after_harvest_are_pruned(self):
        pd = datetime.datetime(2026, 5, 11)
        hd = pd + datetime.timedelta(days=90)
        prots = [
            Protection(day=0, type=27, name="Early", amount="1.0"),
            Protection(day=89, type=27, name="Before", amount="1.0"),
            Protection(day=90, type=27, name="At", amount="1.0"),
            Protection(day=100, type=27, name="After", amount="1.0"),
        ]
        plan = _make_planting_plan(prots)
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": 27, "category": "F", "name": "F"}],
        ):
            svc = ProtectionPlanService(_make_context(), pd, plan, hd)
        names = [op.application_name for op in svc.operations]
        assert len(svc.operations) == 2
        assert "Early (1.0)" in names and "Before (1.0)" in names
        assert "At (1.0)" not in names and "After (1.0)" not in names

    def test_sikkation_too_close_to_harvest_is_pruned(self):
        pd = datetime.datetime(2026, 5, 11)
        hd = pd + datetime.timedelta(days=90)
        prots = [
            Protection(day=76, type=SIKKATION_CATEGORY, name="OK", amount="1.0"),
            Protection(day=80, type=SIKKATION_CATEGORY, name="Late", amount="1.0"),
        ]
        plan = _make_planting_plan(prots)
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": SIKKATION_CATEGORY, "category": "H", "name": "H"}],
        ):
            svc = ProtectionPlanService(_make_context(), pd, plan, hd)
        names = [op.application_name for op in svc.operations]
        assert "OK (1.0)" in names and "Late (1.0)" not in names

    def test_sikkation_exactly_14_days_kept(self):
        pd = datetime.datetime(2026, 5, 11)
        hd = pd + datetime.timedelta(days=90)
        prots = [Protection(day=76, type=SIKKATION_CATEGORY, name="S14", amount="1.0")]
        plan = _make_planting_plan(prots)
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": SIKKATION_CATEGORY, "category": "H", "name": "H"}],
        ):
            svc = ProtectionPlanService(_make_context(), pd, plan, hd)
        assert len(svc.operations) == 1
        delta = (hd.date() - svc.operations[0].planned_date.date()).days
        assert delta == SIKKATION_MIN_DAYS_BEFORE_HARVEST

    def test_no_pruning_when_harvest_date_none(self):
        pd = datetime.datetime(2026, 5, 11)
        prots = [
            Protection(day=0, type=27, name="E", amount="1.0"),
            Protection(day=200, type=27, name="L", amount="1.0"),
        ]
        plan = _make_planting_plan(prots)
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": 27, "category": "F", "name": "F"}],
        ):
            svc = ProtectionPlanService(_make_context(), pd, plan, None)
        assert len(svc.operations) == 2


class TestProtectionOperationsPrunedEvent:
    def test_event_emitted_with_correct_counts(self):
        pd = datetime.datetime(2026, 5, 11)
        hd = pd + datetime.timedelta(days=90)
        prots = [
            Protection(day=0, type=27, name="Kept", amount="1.0"),
            Protection(day=100, type=27, name="After", amount="1.0"),
            Protection(day=80, type=SIKKATION_CATEGORY, name="Sikk", amount="1.0"),
        ]
        plan = _make_planting_plan(prots)
        bus = DomainEventBus()
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[
                {"id": 27, "category": "F", "name": "F"},
                {"id": SIKKATION_CATEGORY, "category": "H", "name": "H"},
            ],
        ):
            ProtectionPlanService(_make_context(), pd, plan, hd, bus)
        pruned = [e for e in bus.get_history() if e.event_type == "ProtectionOperationsPruned"]
        assert len(pruned) == 1
        p = pruned[0].payload
        assert p["planned_count"] == 3 and p["pruned_count"] == 2
        assert p["pruned_after_harvest"] == 1 and p["pruned_sikkation_too_late"] == 1

    def test_no_event_when_pruned_count_zero(self):
        pd = datetime.datetime(2026, 5, 11)
        hd = pd + datetime.timedelta(days=90)
        prots = [
            Protection(day=0, type=27, name="K1", amount="1.0"),
            Protection(day=50, type=27, name="K2", amount="1.0"),
        ]
        plan = _make_planting_plan(prots)
        bus = DomainEventBus()
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": 27, "category": "F", "name": "F"}],
        ):
            ProtectionPlanService(_make_context(), pd, plan, hd, bus)
        assert not [e for e in bus.get_history() if e.event_type == "ProtectionOperationsPruned"]

    def test_no_event_when_bus_none(self):
        pd = datetime.datetime(2026, 5, 11)
        hd = pd + datetime.timedelta(days=90)
        prots = [
            Protection(day=0, type=27, name="K", amount="1.0"),
            Protection(day=100, type=27, name="P", amount="1.0"),
        ]
        plan = _make_planting_plan(prots)
        with patch(
            "services.protection_plan_service.sim_helper.get_protection_categories",
            return_value=[{"id": 27, "category": "F", "name": "F"}],
        ):
            svc = ProtectionPlanService(_make_context(), pd, plan, hd, None)
        assert len(svc.operations) == 1


class TestCalendarDrivenRunnerHarvestDate:
    def test_compute_harvest_date(self):
        runner = CalendarDrivenRunner(_make_context())
        expected = runner.planting_plan_service.planned_planting_date + datetime.timedelta(
            days=runner.planting_plan_service.planting_plan.grow_duration
        )
        assert runner._compute_harvest_date() == expected

    def test_initialize_services_uses_planting_date(self):
        runner = CalendarDrivenRunner(_make_context())
        runner._initialize_services(datetime.datetime(2026, 5, 20))
        assert (
            runner.protection_plan_service.start_date
            == runner.planting_plan_service.planned_planting_date
        )
        assert runner.protection_plan_service.harvest_date == runner._compute_harvest_date()


_SEED = 42
_N_DAYS = 760


@pytest.fixture(scope="module")
def ff_sim():
    random.seed(_SEED)
    np.random.seed(_SEED)
    ctx = SimContext(
        field_size=20.0,
        soil_type="sandy_loam",
        start_date=datetime.datetime(2026, 1, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=990001,
        field_name="Audit Field",
        fuel_variation=0.1,
    )
    bus = DomainEventBus()
    runner = FastForwardRunner(context=ctx, n_days=_N_DAYS, output_target="stdout", event_bus=bus)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        events = runner.run()
    return {"events": events, "domain_events": bus.get_history()}


def _pd(v):
    return (
        v
        if isinstance(v, datetime.datetime)
        else datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
    )


class TestFastForwardIntegration:
    def test_no_spritzen_after_roden(self, ff_sim):
        events = ff_sim["events"]
        roden = [_pd(e.start_date) for e in events if int(getattr(e, "worktype", 0)) == 27]
        spritzen = [_pd(e.start_date) for e in events if int(getattr(e, "worktype", 0)) == 14]
        r = min(roden)
        assert not [s for s in spritzen if s > r]

    def test_pruned_emitted_once(self, ff_sim):
        pruned = [
            e for e in ff_sim["domain_events"] if e.event_type == "ProtectionOperationsPruned"
        ]
        assert len(pruned) == 1
        assert pruned[0].payload["pruned_count"] > 0

    def test_last_sikkation_14d_before_roden(self, ff_sim):
        events = ff_sim["events"]
        roden = min(_pd(e.start_date) for e in events if int(getattr(e, "worktype", 0)) == 27)
        sikk = [
            _pd(e.start_date)
            for e in events
            if int(getattr(e, "worktype", 0)) == 14
            and int(getattr(e, "application_category", 0)) == SIKKATION_CATEGORY
        ]
        before = [s for s in sikk if s < roden]
        assert before
        assert (roden.date() - max(before).date()).days >= SIKKATION_MIN_DAYS_BEFORE_HARVEST
