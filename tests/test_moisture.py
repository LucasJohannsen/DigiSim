import datetime
from models.sim_context import SimContext
from services.moisture_service import MoistureDataService


def test_min_moisture_level():
    """
    Test case for minimum moisture level where no irrigation is expected.
    """
    MIN_MOISTURE_LEVEL = 0
    context = SimContext(
        field_id=1,
        field_name="Test",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2023, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )

    moisture_service = MoistureDataService(context=context, min_moisture_level=MIN_MOISTURE_LEVEL)
    moisture_data = moisture_service.get_moisture_data()

    moisture_data = moisture_data['moisture_data']
    moisture_data = moisture_data.astype(float)  # Ensure proper scalar extraction
  

    assert moisture_data.sum() > 0, "Expected some moisture data, but got none."
    assert 365 <= len(moisture_data) <= 366, "Expected moisture data for 365/366 days, but got a different length."


def test_extreme_moisture_level():
    """
    Test case for extreme moisture level where excessive irrigation is expected.
    """
    MIN_MOISTURE_LEVEL = 150000
    context = SimContext(
        field_id=1,
        field_name="Test",
        field_size=10.0,
        soil_type="sand",
        start_date=datetime.datetime(2023, 1, 1),
        crop_type="Potato",
        variety="Belana",
        fuel_variation=0.1
    )

    moisture_service = MoistureDataService(context=context, min_moisture_level=MIN_MOISTURE_LEVEL)
    moisture_data = moisture_service.get_moisture_data()

    irrigation = moisture_data['moisture_data']

    print(f"Total irrigation needed: {irrigation.sum():.2f} mm")

    for doy, value in enumerate(irrigation):
        if value > 0:
            print(f"Day {doy + 1}: {value:.2f} mm irrigation needed")

    assert irrigation.sum() > 0, "Expected irrigation needed, but no irrigation was calculated."
    assert irrigation.sum() > 1000, "Expected irrigation to be greater than 1000 mm, but got a different value."
    assert 365 <= len(irrigation) <= 366, "Expected irrigation array to have 365/366 days, but got a different length."
