from services.moisture_service import MoistureService
import datetime
from models.sim_context import SimContext

def test_min_moisture_level():
    
    # Wenn wir erst am 0 %nFK bewässern, ist das schlecht für die Kartoffeln aber der moisture_service sollte keine Bewässerung errechnen.
    MIN_MOISTURE_LEVEL = 0
    context  = SimContext(
        start_date=datetime.datetime(2023, 1, 1),
        field_size=10
    )

    moisture_service = MoistureService(context=context, min_moisture_level=MIN_MOISTURE_LEVEL)
    irrigation = moisture_service.planned_events['irrigation']


    print(f"Total irrigation needed: {irrigation.sum():.2f} mm")

    # get all non-zero irrigation values and print them. the index of the value is the doy, so print the date and the irrigtaion value
    for doy, value in enumerate(irrigation):
        if value > 0:
            print(f"Day {doy + 1}: {value:.2f} mm irrigation needed")
    
    assert irrigation.sum() == 0, "Expected no irrigation needed, but some irrigation was calculated."



def test_max_moisture_level():
    
    # Wenn wir 150%nFK im Boden halten wollen, müssen wir in jedem Jahr bewässern.
    MIN_MOISTURE_LEVEL = 150
    context  = SimContext(
        start_date=datetime.datetime(2023, 1, 1),
        field_size=10
    )

    moisture_service = MoistureService(context=context, min_moisture_level=MIN_MOISTURE_LEVEL)
     # simulate the moisture for the year
    irrigation = moisture_service.planned_events['irrigation']


    print(f"Total irrigation needed: {irrigation.sum():.2f} mm")

    # get all non-zero irrigation values and print them. the index of the value is the doy, so print the date and the irrigtaion value
    for doy, value in enumerate(irrigation):
        if value > 0:
            print(f"Day {doy + 1}: {value:.2f} mm irrigation needed")
    
    assert irrigation.sum() > 0, "Expected irrigation needed, but no irrigation was calculated."
    assert irrigation.sum() < 1000, "Expected irrigation to be less than 1000 mm, but got a different value."
    assert 365 <= len(irrigation) <= 366, "Expected irrigation array to have 365/366 days, but got a different length."
    

def test_extreme_moisture_level():
    
    # Wenn wir 150%nFK im Boden halten wollen, müssen wir in jedem Jahr bewässern.
    MIN_MOISTURE_LEVEL = 150000
    context  = SimContext(
        start_date=datetime.datetime(2023, 1, 1),
        field_size=10
    )

    moisture_service = MoistureService(context=context, min_moisture_level=MIN_MOISTURE_LEVEL)
     # simulate the moisture for the year
    irrigation = moisture_service.planned_events['irrigation']


    print(f"Total irrigation needed: {irrigation.sum():.2f} mm")

    # get all non-zero irrigation values and print them. the index of the value is the doy, so print the date and the irrigtaion value
    for doy, value in enumerate(irrigation):
        if value > 0:
            print(f"Day {doy + 1}: {value:.2f} mm irrigation needed")
    
    assert irrigation.sum() > 0, "Expected irrigation needed, but no irrigation was calculated."
    assert irrigation.sum() > 1000, "Expected irrigation to be less than 1000 mm, but got a different value."
    assert 365 <= len(irrigation) <= 366, "Expected irrigation array to have 365/366 days, but got a different length."
    

