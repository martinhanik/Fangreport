from datetime import datetime
import sys

sys.path.insert(0, './')

from fangreport.core import generate_catch_report

def test_function():
    """
    Test
    """
    date = datetime.today().strftime('%Y-%m-%d')
    time_of_catch = "20:00"
    latitude = 49.357599616156776
    longitude = 8.494281048199765
    water_temperature_at_catch = 10.
    species = "Wels"
    fish_length = 130
    fish_weight = 18
    water_clarity = "trüb"

    def test_station(station):
        return generate_catch_report(
            date=date,
            time_of_catch=time_of_catch,
            station=station,
            latitude=latitude,
            longitude=longitude,
            water_temperature_at_catch=water_temperature_at_catch,
            species=species,
            fish_length=fish_length,
            fish_weight=fish_weight,
            water_clarity=water_clarity,
            report_location=None
        )

    # Test all loading procedures
    stations = ["speyer", "borgoforte", "polesella"]
    for station in stations:
        test_station(station)

