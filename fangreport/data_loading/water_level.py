import requests
import pandas as pd
from datetime import timedelta
import json
import unicodedata

from fangreport.data_loading import AipoClient

def load_german_station_data() -> dict:
    """
    Loads and processes data from the German water levels API into a structured dictionary format.
    This utility retrieves station information available through a REST API endpoint, specifically
    tailored for water level monitoring. The resulting data only includes stations with valid names.

    :param None

    :return: A dictionary containing station data. Each station's name acts as a key corresponding
             to a dictionary with details such as station number, latitude, longitude, and water
             body name.
    :rtype: dict

    :raises RuntimeError: If there is an issue with the network request or fetching data from the API.
    """

    url = "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json"

    try:
        response = requests.get(url)
        response.raise_for_status()
        raw_data = response.json()

        pegel_dict = {}
        for station in raw_data:
            name = station.get("longname")

            # Only stations with valid names are included
            if name:
                pegel_dict[name] = {
                    "number": station.get("number"),
                    "latitude": station.get("latitude"),
                    "longitude": station.get("longitude"),
                    "water": station.get("water")["longname"].title()
                }

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Fehler beim Abrufen der Daten: {e}")

    return pegel_dict


def load_italian_station_data(station: str, start:  datetime.datetime, end: datetime.datetime) -> dict or None:
    """
    Loads water level data for an Italian station within a specific time range.

    The function retrieves data for a provided station from its corresponding provider
    (either "ARPA Lombardia" or "AIPO").

    :param station: The station identifier for which data is to be retrieved.
    :type station: str
    :param start: The start datetime for the data query range.
    :type start: datetime.datetime
    :param end: The end datetime for the data query range (inclusive).
    :type end: datetime.datetime
    :return: A dictionary containing the station's display name, water body,
        water level data, and data source.
    :rtype: dict or None
    :raises ValueError: If station data retrieval is not supported for the provider,
        if no level sensor is found for the station, or if no water level data is
        available for the given time range.
    """
    station_data = find_italian_station(station)

    if station_data is None:
        return None

    if station_data["provider"] != "arpa_lombardia" and station_data["provider"] != "aipo":
        raise ValueError(
            f"Die Station '{station_data['display_name']}' ist bereits angelegt, "
            "aber die automatische Datenabfrage für diese regionale Quelle ist noch nicht konfiguriert."
        )

    level_sensor_id = station_data.get("level_sensor_id")

    if level_sensor_id is None:
        raise ValueError(
            f"Für die italienische Station '{station_data['display_name']}' "
            "wurde kein Pegelsensor gefunden."
        )

    if station_data["provider"] == "arpa_lombardia":
        source = "ARPA Lombardia"
        df_water_level = load_arpa_lombardia_sensor_values(
            level_sensor_id,
            start,
            end + timedelta(days=1)
        )
    else:
        source = "AIPO"
        client = AipoClient.from_file("fangreport/data/aipo_auth.json")
        df_water_level = client.load_sensor_values(
            level_sensor_id,
            start,
            end + timedelta(days=1)
        )

    if df_water_level.empty:
        raise ValueError(
            f"Für die italienische Station '{station_data['display_name']}' "
            f"wurden im gewählten Zeitraum keine Pegeldaten für Sensor {level_sensor_id} gefunden."
        )

    return {
        "station_display_name": station_data["display_name"],
        "water": station_data["water"],
        "df_water_level": df_water_level,
        "source": source,
    }


def normalize_station_name(value: str) -> str:
    """
    Normalize a station name by removing extraneous characters, normalizing
    Unicode characters, and ensuring consistent formatting. This function
    removes leading and trailing spaces, converts text to lowercase, replaces
    hyphens and underscores with spaces, and collapses multiple spaces into a
    single space. Furthermore, it removes any characters with Unicode
    combining marks.

    :param value: The station name to be normalized.
    :type value: str
    :return: A normalized version of the station name.
    :rtype: str
    """
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.replace("-", " ").replace("_", " ").split())


def italian_stations_dict() -> dict:
    """
    Builds and returns a dictionary of normalized Italian station names and their associated
    station data. The function processes data from a JSON file, where each station may have
    multiple aliases. Aliases are also normalized and mapped to the corresponding station
    data in the resulting dictionary.

    :return: A dictionary where the keys are normalized names of Italian stations and their
        aliases, and the values are the associated station data loaded from the JSON file.
    :rtype: dict
    """
    stations = {}

    with open("fangreport/data/italian_stations.json", "r", encoding="utf-8") as f:
        italian_stations = json.load(f)

    for canonical_name, station_data in italian_stations.items():
        stations[normalize_station_name(canonical_name)] = station_data

        for alias in station_data.get("aliases", []):
            stations[normalize_station_name(alias)] = station_data

    return stations


def find_italian_station(station: str) -> dict or None:
    """
    Find the corresponding Italian station for the given station name.

    This function attempts to find the matching Italian station from a pre-defined
    dictionary, using a normalized version of the provided station name.

    :param station: The name of the station to be searched for.
    :type station: str
    :return: The corresponding Italian station if found, otherwise None.
    :rtype: str or None
    """
    return italian_stations_dict().get(normalize_station_name(station))


def load_arpa_lombardia_sensor_values(
        sensor_id: int,
        start: datetime.datetime,
        end: datetime.datetime
) -> pd.DataFrame:
    """
    Loads and processes water level sensor data from the ARPA Lombardia dataset for a
    specified sensor and time range. The function retrieves the data from a public
    API endpoint, performs validation, and formats the data for further use.

    :param sensor_id: The unique identifier of the sensor whose data is to be retrieved.
    :type sensor_id: int

    :param start: The start datetime for the time range of sensor data to be fetched.
                  Must be a timezone-aware datetime object.
    :type start: datetime.datetime

    :param end: The end datetime for the time range of sensor data to be fetched.
                Must be a timezone-aware datetime object.
    :type end: datetime.datetime

    :return: A pandas DataFrame containing the processed water level data. The DataFrame
             includes columns for time (as the index) and water level.
    :rtype: pandas.DataFrame

    :raises requests.exceptions.RequestException: If the HTTP request to the data API
                                                  fails or encounters timeout issues.
    :raises ValueError: If the data retrieved does not contain the expected columns
                        ('data' and 'valore') for processing.
    """
    url = "https://www.dati.lombardia.it/resource/647i-nhxk.json"
    params = {
        "$limit": 50000,
        "$order": "data ASC",
        "idsensore": str(sensor_id),
        "$where": (
            f"data between '{start.strftime('%Y-%m-%dT%H:%M:%S')}' "
            f"and '{end.strftime('%Y-%m-%dT%H:%M:%S')}'"
        ),
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    raw_data = response.json()

    if not raw_data:
        return pd.DataFrame(columns=["time", "water_level"]).set_index("time")

    data_frame = pd.DataFrame(raw_data)

    if "data" not in data_frame.columns or "valore" not in data_frame.columns:
        raise ValueError(
            "Die ARPA-Lombardia-Daten enthalten nicht die erwarteten Spalten "
            "'data' und 'valore'."
        )

    data_frame = data_frame.rename(
        columns={
            "data": "time",
            "valore": "water_level",
        }
    )

    data_frame["time"] = pd.to_datetime(data_frame["time"], errors="coerce")
    data_frame["water_level"] = pd.to_numeric(data_frame["water_level"], errors="coerce")
    data_frame = data_frame.dropna(subset=["time", "water_level"])
    data_frame = data_frame.set_index("time").sort_index()

    if data_frame.index.tz is not None:
        data_frame.index = data_frame.index.tz_convert("Europe/Rome").tz_localize(None)

    return data_frame