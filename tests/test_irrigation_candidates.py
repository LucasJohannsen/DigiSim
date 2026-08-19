"""
Tests for IrrigationSimulator candidate operations (Issue #38 / #59)

This test suite verifies:
1. Candidate generation without side-effects
2. Side-effect application via apply_irrigation()
3. Backward compatibility of trigger_irrigation()
4. Proper separation of concerns in the decision pipeline
5. Correct event date from the passed simulation date (Issue #59)
"""
import pytest
import numpy as np
import datetime
from models.sim_context import SimContext
from services.irrigation_service import IrrigationSimulator


@pytest.fixture
def sim_context():
    """Create a standard simulation context for testing"""
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2022, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )


@pytest.fixture
def moisture_data_dry():
    """Create moisture data that requires irrigation (dry conditions)"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    # Low moisture levels that trigger irrigation
    moisture_values = [30.0] * 365  # Below default threshold of 50

    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": moisture_values
    }


@pytest.fixture
def moisture_data_wet():
    """Create moisture data that does NOT require irrigation (wet conditions)"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    # High moisture levels, no irrigation needed
    moisture_values = [80.0] * 365  # Above threshold

    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": moisture_values
    }


class TestCandidateGeneration:
    """Test get_candidate_operations() method"""

    def test_returns_empty_list_when_no_irrigation_needed(self, sim_context, moisture_data_wet):
        """Candidate generation should return empty list when moisture is sufficient"""
        simulator = IrrigationSimulator(sim_context, moisture_data_wet)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))

        assert isinstance(candidates, list)
        assert len(candidates) == 0

    def test_returns_candidate_when_irrigation_needed(self, sim_context, moisture_data_dry):
        """Candidate generation should return event(s) when irrigation is needed"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))

        assert isinstance(candidates, list)
        assert len(candidates) >= 1

        event = candidates[0]
        assert event.worktype == 15
        assert event.worktype_text == 'Bewässerung'
        assert event.application_type == 'irrigation'
        assert event.application_amount > 0

    def test_candidate_has_correct_attributes(self, sim_context, moisture_data_dry):
        """Candidate event should have all required attributes"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))
        event = candidates[0]

        # Verify all required attributes
        assert hasattr(event, 'worktype')
        assert hasattr(event, 'start_date')
        assert hasattr(event, 'end_date')
        assert hasattr(event, 'area')
        assert hasattr(event, 'duration')
        assert hasattr(event, 'fuel')
        assert hasattr(event, 'application_amount')
        assert hasattr(event, 'application_unit')
        assert hasattr(event, 'field')

        # Verify values
        assert event.worktype == 15
        assert event.area == sim_context.field_size
        assert event.application_unit == 12  # Kubikmeter (DataUnit pk=12)
        assert event.field == sim_context.field_id

    def test_candidate_generation_does_not_apply_side_effects(self, sim_context, moisture_data_dry):
        """CRITICAL: Candidate generation must NOT modify moisture arrays"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        # Store original state
        original_irrigation = simulator.irrigation.copy()
        original_updated_moisture = simulator.updated_moisture.copy()

        # Generate candidate (must return at least one candidate for a meaningful test)
        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))
        assert len(candidates) >= 1

        # Verify arrays are unchanged
        np.testing.assert_array_equal(
            simulator.irrigation,
            original_irrigation,
            err_msg="Candidate generation should NOT modify irrigation array"
        )
        np.testing.assert_array_equal(
            simulator.updated_moisture,
            original_updated_moisture,
            err_msg="Candidate generation should NOT modify updated_moisture array"
        )

    def test_handles_out_of_range_day_gracefully(self, sim_context, moisture_data_dry):
        """Should return empty list for invalid day index"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        # Test day beyond range
        candidates = simulator.get_candidate_operations(datetime.date(2024, 12, 31))
        assert candidates == []


class TestApplyIrrigation:
    """Test apply_irrigation() side-effect method"""

    def test_applies_irrigation_to_arrays(self, sim_context, moisture_data_dry):
        """apply_irrigation() should update moisture arrays"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday
        irrigation_amount = 20.0

        # Get initial moisture
        initial_moisture = simulator.updated_moisture[day]

        # Apply irrigation
        simulator.apply_irrigation(date, irrigation_amount)

        # Verify irrigation was recorded
        assert simulator.irrigation[day] == irrigation_amount

        # Verify moisture was updated
        assert simulator.updated_moisture[day] == initial_moisture + irrigation_amount

    def test_propagates_moisture_to_future_days(self, sim_context, moisture_data_dry):
        """Moisture increase should propagate to future days"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday
        irrigation_amount = 20.0

        # Apply irrigation
        simulator.apply_irrigation(date, irrigation_amount)

        # Verify propagation to future days
        for future_day in range(day + 1, min(day + 10, len(simulator.updated_moisture))):
            assert simulator.updated_moisture[future_day] >= simulator.updated_moisture[day]

    def test_raises_error_for_invalid_day(self, sim_context, moisture_data_dry):
        """Should raise IndexError for out-of-range day"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        with pytest.raises(IndexError):
            simulator.apply_irrigation(datetime.date(2024, 12, 31), irrigation_amount=20.0)


class TestTriggerIrrigationBackwardCompatibility:
    """Test that trigger_irrigation() still works (backward compatibility)"""

    def test_trigger_irrigation_combines_candidate_and_side_effects(self, sim_context, moisture_data_dry):
        """trigger_irrigation() should create event AND apply side-effects"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday

        # Trigger irrigation (legacy method)
        event = simulator.trigger_irrigation(date)

        # Should return event
        assert event is not None
        assert event.worktype == 15

        # Should have applied side-effects
        assert simulator.irrigation[day] > 0
        assert simulator.updated_moisture[day] > moisture_data_dry["moisture_data"][day]

    def test_trigger_irrigation_with_explicit_amount(self, sim_context, moisture_data_dry):
        """trigger_irrigation() should accept explicit irrigation amount.

        P3-5 (Issue #83): Bei langen Dauern wird das Event aufgeteilt.
        trigger_irrigation gibt das erste Teil-Event zurück; die
        Seiteneffekte werden mit der Gesamtmenge angewendet.
        """
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday
        explicit_amount = 25.0

        event = simulator.trigger_irrigation(date, irrigation_amount=explicit_amount)

        assert event is not None
        assert event.worktype == 15
        # Side-effects use the full explicit amount
        assert simulator.irrigation[day] == explicit_amount

    def test_trigger_irrigation_returns_none_when_not_needed(self, sim_context, moisture_data_wet):
        """trigger_irrigation() should return None when irrigation not needed"""
        simulator = IrrigationSimulator(sim_context, moisture_data_wet)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday

        event = simulator.trigger_irrigation(date)

        assert event is None
        assert simulator.irrigation[day] == 0


class TestCandidateAndApplySeparation:
    """Test the separation of candidate generation and side-effect application"""

    def test_candidate_then_apply_produces_same_result_as_trigger(self, sim_context, moisture_data_dry):
        """Using get_candidate + apply should produce same result as trigger_irrigation"""
        # Simulator 1: Use new pattern (candidate + apply)
        sim1 = IrrigationSimulator(sim_context, moisture_data_dry)
        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday
        candidates = sim1.get_candidate_operations(date)
        if candidates:
            event1 = candidates[0]
            sim1.apply_irrigation(date=date, irrigation_amount=event1.application_amount)

        # Simulator 2: Use legacy pattern (trigger)
        sim2 = IrrigationSimulator(sim_context, moisture_data_dry)
        event2 = sim2.trigger_irrigation(date=date)
        assert event2 is not None

        # Both should have applied irrigation
        assert sim1.irrigation[day] > 0
        assert sim2.irrigation[day] > 0

        # Moisture should be updated in both
        assert sim1.updated_moisture[day] > moisture_data_dry["moisture_data"][day]
        assert sim2.updated_moisture[day] > moisture_data_dry["moisture_data"][day]

    def test_multiple_candidates_can_be_generated_before_applying(self, sim_context, moisture_data_dry):
        """Should be able to generate multiple candidates before applying any"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        # Generate candidates for multiple days
        date_100 = datetime.date(2022, 4, 10)
        date_101 = datetime.date(2022, 4, 11)
        date_102 = datetime.date(2022, 4, 12)
        day_100 = date_100.timetuple().tm_yday
        day_101 = date_101.timetuple().tm_yday
        day_102 = date_102.timetuple().tm_yday

        candidates_day_100 = simulator.get_candidate_operations(date_100)
        candidates_day_101 = simulator.get_candidate_operations(date_101)
        candidates_day_102 = simulator.get_candidate_operations(date_102)

        # All should return candidates (dry conditions)
        assert len(candidates_day_100) > 0
        assert len(candidates_day_101) > 0
        assert len(candidates_day_102) > 0

        # No side-effects should be applied yet
        assert simulator.irrigation[day_100] == 0
        assert simulator.irrigation[day_101] == 0
        assert simulator.irrigation[day_102] == 0

        # Now apply one
        if candidates_day_101:
            simulator.apply_irrigation(date=date_101, irrigation_amount=candidates_day_101[0].application_amount)

        # Only day 101 should have irrigation applied
        assert simulator.irrigation[day_100] == 0
        assert simulator.irrigation[day_101] > 0
        assert simulator.irrigation[day_102] == 0


class TestEventDateTimeline:
    """Test that irrigation events carry the correct simulation date (Issue #59)."""

    def test_candidate_event_uses_passed_date_not_start_year(self, sim_context, moisture_data_dry):
        """get_candidate_operations(date) must use the passed date for the event.

        P3-5 (Issue #83): Startzeit ist 05:00 (WORK_START_HOUR) statt 12:00.
        Bei langen Dauern wird auf mehrere Tage aufgeteilt; das erste
        Event startet am übergebenen Datum.
        """
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        candidate_date = datetime.date(2027, 6, 5)

        candidates = simulator.get_candidate_operations(candidate_date)

        assert len(candidates) >= 1
        event = candidates[0]
        # Erstes Event startet am übergebenen Datum um 05:00
        assert event.start_date == "2027-06-05 05:00:00"


class TestDecisionPipelineIntegration:
    """Test integration with decision pipeline pattern"""

    def test_candidate_can_be_rejected_without_side_effects(self, sim_context, moisture_data_dry):
        """DecisionManager can reject candidate without any side-effects"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday

        # Generate candidate
        candidates = simulator.get_candidate_operations(date)
        assert len(candidates) > 0

        # DecisionManager rejects it (we simply don't call apply_irrigation)
        # No side-effects should occur

        assert simulator.irrigation[day] == 0
        assert simulator.updated_moisture[day] == moisture_data_dry["moisture_data"][day]

    def test_candidate_can_be_confirmed_with_side_effects(self, sim_context, moisture_data_dry):
        """DecisionManager can confirm candidate and apply side-effects"""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        date = datetime.date(2022, 4, 10)
        day = date.timetuple().tm_yday

        # Generate candidate
        candidates = simulator.get_candidate_operations(date)
        assert len(candidates) > 0

        candidate = candidates[0]

        # DecisionManager confirms it
        simulator.apply_irrigation(date=date, irrigation_amount=candidate.application_amount)

        # Side-effects should be applied
        assert simulator.irrigation[day] > 0
        assert simulator.updated_moisture[day] > moisture_data_dry["moisture_data"][day]


# ---------------------------------------------------------------------------
# P3-3 (Issue #81): Beregnungsmengen fachlich korrigieren (Befund B3)
# ---------------------------------------------------------------------------


@pytest.fixture
def moisture_data_very_dry():
    """Moisture data so dry that irrigation is still needed after a 25 mm gift."""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    moisture_values = [10.0] * 365  # Well below threshold of 50

    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": moisture_values,
    }


class TestTargetApplicationAmount:
    """P3-3 AK 1-3: Feste Zielgabe 20-30 mm mit Clamping auf [10, 40] mm."""

    def test_typical_application_in_target_range(self, sim_context, moisture_data_dry):
        """AK 2: Typische Gabe liegt im Bereich [20, 30] mm (KAR-040 soft).

        P3-5 (Issue #83): Bei Aufteilung ist die Gesamtmenge (Summe aller
        Teil-Events) relevant, nicht die einzelne Teil-Gabe.
        """
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        np.random.seed(42)

        # Sample multiple candidates across different days
        amounts = []
        for offset in range(0, 200, 11):
            date = datetime.date(2022, 1, 1) + datetime.timedelta(days=offset)
            candidates = simulator.get_candidate_operations(date)
            if candidates:
                total = sum(c.application_amount for c in candidates)
                amounts.append(total)

        assert amounts, "Expected at least one irrigation candidate"
        for amt in amounts:
            assert 20.0 <= amt <= 30.0, (
                f"Typical application {amt} mm outside target range [20, 30] mm"
            )

    def test_no_application_below_min(self, sim_context, moisture_data_dry):
        """AK 3 / AK 1: Keine Gabe < 10 mm (Clamping auf min_application_mm).

        P3-5: Die Gesamtmenge (Summe aller Teil-Events) muss >= min sein.
        """
        # Use a tiny target so the raw amount would be below min → clamping kicks in
        simulator = IrrigationSimulator(
            sim_context,
            moisture_data_dry,
            target_application_mm=5.0,
            target_tolerance_pct=0.0,
        )
        np.random.seed(42)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))
        assert len(candidates) >= 1
        total = sum(c.application_amount for c in candidates)
        assert total >= 10.0, (
            f"Total application {total} mm below min 10 mm"
        )
        assert total == 10.0

    def test_no_application_above_max(self, sim_context, moisture_data_dry):
        """AK 1: Keine Gabe > 40 mm (Clamping auf max_application_mm).

        P3-5: Die Gesamtmenge (Summe aller Teil-Events) muss <= max sein.
        """
        # Use a huge target so the raw amount would exceed max → clamping kicks in
        simulator = IrrigationSimulator(
            sim_context,
            moisture_data_dry,
            target_application_mm=50.0,
            target_tolerance_pct=0.0,
        )
        np.random.seed(42)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 4, 10))
        assert len(candidates) >= 1
        total = sum(c.application_amount for c in candidates)
        assert total <= 40.0, (
            f"Total application {total} mm above max 40 mm"
        )
        assert total == 40.0

    def test_all_applications_within_hard_limits(self, sim_context, moisture_data_dry):
        """AK 1: Alle Gaben im harten Bereich [10, 40] mm (KAR-040 hart).

        P3-5: Gesamtmenge pro Beregnungs-Event-Gruppe muss in [10, 40] liegen.
        """
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        np.random.seed(123)

        for offset in range(0, 300, 7):
            date = datetime.date(2022, 1, 1) + datetime.timedelta(days=offset)
            candidates = simulator.get_candidate_operations(date)
            if candidates:
                total = sum(c.application_amount for c in candidates)
                assert 10.0 <= total <= 40.0


class TestPostIrrigationBlock:
    """P3-3 AK 5: Post-Irrigation-Block (10 Tage nach Beregnung)."""

    def test_no_candidates_for_10_days_after_irrigation(
        self, sim_context, moisture_data_very_dry
    ):
        """Nach apply_irrigation() werden für 10 Tage keine Kandidaten erzeugt."""
        simulator = IrrigationSimulator(sim_context, moisture_data_very_dry)
        np.random.seed(42)

        irrigation_date = datetime.date(2022, 4, 10)
        simulator.apply_irrigation(irrigation_date, irrigation_amount=25.0)

        # Days 1-9 after irrigation: blocked
        for delta in range(1, 10):
            check_date = irrigation_date + datetime.timedelta(days=delta)
            candidates = simulator.get_candidate_operations(check_date)
            assert candidates == [], (
                f"Day +{delta}: expected no candidates (post-irrigation block), "
                f"got {len(candidates)}"
            )

    def test_candidate_allowed_on_day_10_after_irrigation(
        self, sim_context, moisture_data_very_dry
    ):
        """Am 10. Tag nach Beregnung ist der Block aufgehoben."""
        simulator = IrrigationSimulator(sim_context, moisture_data_very_dry)
        np.random.seed(42)

        irrigation_date = datetime.date(2022, 4, 10)
        simulator.apply_irrigation(irrigation_date, irrigation_amount=25.0)

        # Day +10: block expired (block_until = irrigation_date + 10)
        check_date = irrigation_date + datetime.timedelta(days=10)
        candidates = simulator.get_candidate_operations(check_date)
        assert len(candidates) >= 1, (
            f"Day +10: expected candidate (block expired), got {len(candidates)}"
        )


class TestSeasonalLimit:
    """P3-3 AK 4: Saisonale Obergrenze 170 mm (hard-stop)."""

    def test_no_candidates_after_seasonal_max_reached(
        self, sim_context, moisture_data_very_dry
    ):
        """AK 4: Nach Erreichen von 170 mm keine weiteren Kandidaten."""
        simulator = IrrigationSimulator(sim_context, moisture_data_very_dry)
        simulator.seasonal_sum_mm = 170.0

        candidates = simulator.get_candidate_operations(datetime.date(2022, 6, 15))
        assert candidates == [], (
            "Expected no candidates after seasonal max (170 mm) reached"
        )

    def test_candidates_when_below_seasonal_max(
        self, sim_context, moisture_data_very_dry
    ):
        """Unter 170 mm werden noch Kandidaten erzeugt."""
        simulator = IrrigationSimulator(sim_context, moisture_data_very_dry)
        simulator.seasonal_sum_mm = 100.0
        np.random.seed(42)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 6, 15))
        assert len(candidates) >= 1

    def test_last_gift_capped_to_remaining_budget(
        self, sim_context, moisture_data_very_dry
    ):
        """AK 4/f: Letzte Gabe wird auf Restbudget begrenzt (>= min).

        P3-5: Die Gesamtmenge (Summe aller Teil-Events) muss dem Restbudget
        entsprechen.
        """
        simulator = IrrigationSimulator(sim_context, moisture_data_very_dry)
        # Remaining budget = 170 - 155 = 15 mm (>= min 10)
        simulator.seasonal_sum_mm = 155.0
        np.random.seed(42)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 6, 15))
        assert len(candidates) >= 1
        total = sum(c.application_amount for c in candidates)
        assert total == 15.0, (
            f"Expected last gift capped to remaining budget 15 mm, "
            f"got {total}"
        )

    def test_no_candidates_when_remaining_budget_below_min(
        self, sim_context, moisture_data_very_dry
    ):
        """Restbudget < min_application_mm → keine weitere Gabe."""
        simulator = IrrigationSimulator(sim_context, moisture_data_very_dry)
        # Remaining budget = 170 - 165 = 5 mm (< min 10)
        simulator.seasonal_sum_mm = 165.0
        np.random.seed(42)

        candidates = simulator.get_candidate_operations(datetime.date(2022, 6, 15))
        assert candidates == [], (
            "Expected no candidates when remaining budget (5 mm) < min (10 mm)"
        )


class TestSeasonalSumTracking:
    """P3-3: apply_irrigation trackt saisonale Summe und letzte Beregnung."""

    def test_apply_irrigation_updates_seasonal_sum(self, sim_context, moisture_data_dry):
        """apply_irrigation addiert zur saisonalen Summe."""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        assert simulator.seasonal_sum_mm == 0.0
        simulator.apply_irrigation(datetime.date(2022, 4, 10), irrigation_amount=25.0)
        assert simulator.seasonal_sum_mm == 25.0

        simulator.apply_irrigation(datetime.date(2022, 4, 25), irrigation_amount=20.0)
        assert simulator.seasonal_sum_mm == 45.0

    def test_apply_irrigation_records_last_date(self, sim_context, moisture_data_dry):
        """apply_irrigation speichert das Datum der letzten Beregnung."""
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)

        assert simulator._last_irrigation_date is None
        d1 = datetime.date(2022, 4, 10)
        simulator.apply_irrigation(d1, irrigation_amount=25.0)
        assert simulator._last_irrigation_date == d1

        d2 = datetime.date(2022, 4, 25)
        simulator.apply_irrigation(d2, irrigation_amount=20.0)
        assert simulator._last_irrigation_date == d2


class TestStatePersistenceP33:
    """P3-3 AK 7: State-Persistenz inkl. seasonal_sum_mm und _last_irrigation_date."""

    def test_get_state_includes_seasonal_fields(self, sim_context, moisture_data_dry):
        simulator = IrrigationSimulator(sim_context, moisture_data_dry)
        simulator.apply_irrigation(datetime.date(2022, 4, 10), irrigation_amount=25.0)

        state = simulator.get_state()
        assert state["seasonal_sum_mm"] == 25.0
        assert state["last_irrigation_date"] == "2022-04-10"

    def test_apply_state_restores_seasonal_fields(self, sim_context, moisture_data_dry):
        sim1 = IrrigationSimulator(sim_context, moisture_data_dry)
        sim1.apply_irrigation(datetime.date(2022, 4, 10), irrigation_amount=25.0)
        sim1.apply_irrigation(datetime.date(2022, 4, 25), irrigation_amount=20.0)

        state = sim1.get_state()

        sim2 = IrrigationSimulator(sim_context, moisture_data_dry)
        sim2.apply_state(state)

        assert sim2.seasonal_sum_mm == 45.0
        assert sim2._last_irrigation_date == datetime.date(2022, 4, 25)
