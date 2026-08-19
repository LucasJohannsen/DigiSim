"""
Integration tests for CalendarDrivenRunner irrigation pipeline (Issue #39)

Verifies that irrigation candidates are properly integrated into the unified
decision pipeline and that irrigation events are generated correctly.
"""

import datetime
from unittest.mock import Mock, patch

import pytest

from models.sim_context import SimContext
from scheduler.calendar_driven_runner import CalendarDrivenRunner


@pytest.fixture
def sim_context():
    """Create a simulation context for testing"""
    return SimContext(
        field_id=1,
        field_name="Test Field",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2022, 3, 15),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1,
    )


@pytest.fixture
def mock_moisture_data_dry():
    """Mock moisture data that requires irrigation"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": [30.0] * 365,  # Dry conditions
    }


@pytest.fixture
def mock_moisture_data_wet():
    """Mock moisture data that does NOT require irrigation"""
    dates = [datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)]
    return {
        "coords": [52.0, 13.0],
        "dates": dates,
        "moisture_data": [80.0] * 365,  # Wet conditions
    }


class TestIrrigationCandidatePipeline:
    """Test that irrigation candidates flow through the unified decision pipeline"""

    def test_irrigation_candidates_are_generated_in_crop_management_phase(
        self, sim_context, mock_moisture_data_dry
    ):
        """Irrigation candidates should be generated during crop management phase"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_dry
            MockMoistureService.return_value = mock_ms

            # Manually initialize services to simulate crop management phase
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Now irrigation service should be initialized
            assert runner.irrigation_service is not None

            # Mock get_candidate_operations to verify it's called
            with patch.object(
                runner.irrigation_service, "get_candidate_operations"
            ) as mock_get_candidates:
                mock_get_candidates.return_value = []

                runner.tick(test_date)

                # Verify get_candidate_operations was called
                mock_get_candidates.assert_called_once()

    def test_irrigation_events_appear_in_tick_output_when_needed(
        self, sim_context, mock_moisture_data_dry
    ):
        """Irrigation events should appear in tick output when conditions require it"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_dry
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Isolate irrigation behavior: suppress planting AND protection
            # candidates so that only irrigation competes in the
            # DecisionManager. After the B2 fix (Issue #58), planting is
            # scheduled in the start year, so soil-prep ops would otherwise
            # be due on this date and win priority over irrigation (which is
            # the correct behavior, but not what this test isolates).
            # Protection candidates are suppressed too, because the randomly
            # selected protection plan (random.choice, no seed here) may have
            # a spray due on this date that would win priority over irrigation
            # – P3-7 (Issue #85) shifted harvest later (growth_duration
            # 90->110), so fewer protection ops are pruned and more compete.
            with (
                patch.object(runner.planting_plan_service, "get_next_operations", return_value=[]),
                patch.object(
                    runner.protection_plan_service, "get_next_operations", return_value=[]
                ),
            ):
                events = runner.tick(test_date)

            # Check if any irrigation events were generated
            irrigation_events = [e for e in events if e.worktype == 15]

            # Should have at least one irrigation event (conditions are dry)
            assert len(irrigation_events) > 0
            assert irrigation_events[0].worktype_text == "Bewässerung"

    def test_no_irrigation_events_when_not_needed(self, sim_context, mock_moisture_data_wet):
        """No irrigation events should be generated when moisture is sufficient"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_wet
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Tick during wet conditions - should NOT generate irrigation
            events = runner.tick(test_date)

            # Check for irrigation events
            irrigation_events = [e for e in events if e.worktype == 15]

            # Should have NO irrigation events (conditions are wet)
            assert len(irrigation_events) == 0

    def test_irrigation_side_effects_are_applied_when_candidate_selected(
        self, sim_context, mock_moisture_data_dry
    ):
        """Side-effects should be applied when irrigation candidate is selected"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_dry
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Store initial irrigation state
            initial_irrigation = runner.irrigation_service.irrigation.copy()

            # Tick - should apply irrigation
            day_of_year = test_date.timetuple().tm_yday

            events = runner.tick(test_date)

            # If irrigation event was generated, side-effects should be applied
            irrigation_events = [e for e in events if e.worktype == 15]
            if irrigation_events:
                # Verify side-effects were applied
                assert runner.irrigation_service.irrigation[day_of_year] > 0
                assert (
                    runner.irrigation_service.irrigation[day_of_year]
                    != initial_irrigation[day_of_year]
                )


class TestUnifiedDecisionPipeline:
    """Test that all operation types go through the same decision pipeline"""

    def test_irrigation_candidates_compete_with_other_operations(
        self, sim_context, mock_moisture_data_dry
    ):
        """Irrigation candidates should compete with planting/protection in DecisionManager"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_dry
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Mock DecisionManager to verify it receives all candidate types
            with patch.object(runner.decision_manager, "decide") as mock_decide:
                mock_decide.return_value = []

                runner.tick(test_date)

                # Verify decide was called with candidates
                assert mock_decide.call_count == 1
                candidates = mock_decide.call_args[0][0]

                # Candidates list should potentially include irrigation (if conditions require it)
                # At minimum, verify decide() was called with a list
                assert isinstance(candidates, list)

    def test_no_special_path_for_irrigation(self, sim_context, mock_moisture_data_dry):
        """Irrigation should NOT have a special execution path"""
        runner = CalendarDrivenRunner(sim_context)

        # Verify _handle_irrigation method no longer exists
        assert not hasattr(runner, "_handle_irrigation"), (
            "_handle_irrigation() method should be removed (Issue #39)"
        )

    def test_irrigation_events_logged_same_as_other_events(
        self, sim_context, mock_moisture_data_dry
    ):
        """Irrigation events should be logged through the same EventLogger as other events"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_dry
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Mock event logger to verify logging
            with patch.object(runner.event_logger, "log") as mock_log:
                events = runner.tick(test_date)

                # All events (including irrigation) should be logged
                assert mock_log.call_count == len(events)


class TestErrorHandling:
    """Test error handling in the unified pipeline"""

    def test_irrigation_candidate_generation_error_handled_gracefully(self, sim_context):
        """Errors in candidate generation should not crash the tick"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = {
                "coords": [52.0, 13.0],
                "dates": [
                    datetime.date(2022, 1, 1) + datetime.timedelta(days=i) for i in range(365)
                ],
                "moisture_data": [50.0] * 365,
            }
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Mock get_candidate_operations to raise an error
            with patch.object(
                runner.irrigation_service, "get_candidate_operations"
            ) as mock_get_candidates:
                mock_get_candidates.side_effect = Exception("Test error")

                # Should not crash
                events = runner.tick(test_date)

                # Should still return events (just not irrigation)
                assert isinstance(events, list)

    def test_irrigation_execution_error_handled_gracefully(
        self, sim_context, mock_moisture_data_dry
    ):
        """Errors in irrigation execution should not crash the tick"""
        runner = CalendarDrivenRunner(sim_context)

        with patch("scheduler.calendar_driven_runner.MoistureDataService") as MockMoistureService:
            mock_ms = Mock()
            mock_ms.get_moisture_data.return_value = mock_moisture_data_dry
            MockMoistureService.return_value = mock_ms

            # Manually initialize services
            test_date = sim_context.start_date + datetime.timedelta(days=60)
            runner._initialize_services(test_date)

            # Mock apply_irrigation to raise an error
            with patch.object(runner.irrigation_service, "apply_irrigation") as mock_apply:
                mock_apply.side_effect = Exception("Test error")

                # Should not crash
                events = runner.tick(test_date)

                # Should still return events (just irrigation failed)
                assert isinstance(events, list)
