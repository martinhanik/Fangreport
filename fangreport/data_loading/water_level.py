import requests
import pandas as pd
from datetime import timedelta
import json
import unicodedata

from fangreport.data_loading import AipoClient

def load_german_station_data():
    """
    Ruft Daten von der Pegel Online API ab und gibt ein Dictionary mit Stationsinformationen zurück.

    Die Funktion ruft eine Liste von Wasserstandsstationen im JSON-Format von der Pegel Online API ab.
    Sie verarbeitet die Daten, um ein Dictionary zu erstellen, bei dem die Schlüssel die Langnamen
    der Stationen sind und die entsprechenden Werte Dictionaries enthalten, die Stationsdetails wie
    Stationsnummer, Breitengrad, Längengrad und den Namen des zugehörigen Gewässers enthalten.

    :raises RuntimeError: Wenn ein Fehler bei der HTTP-Anfrage an die Pegel Online API auftritt.

    :return: Ein Dictionary, bei dem die Schlüssel die Langnamen der Stationen (str) sind und die
             Werte Dictionaries sind, die Details wie Stationsnummer (int), Breitengrad (float),
             Längengrad (float) und Gewässername (str) enthalten.
    :rtype: dict
    """


    url = "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json"

    try:
        response = requests.get(url)
        response.raise_for_status()
        raw_data = response.json()

        # Erstellt das gewünschte Dictionary
        pegel_dict = {}
        for station in raw_data:
            name = station.get("longname")

            # Nur Stationen mit gültigem Namen aufnehmen
            if name:
                pegel_dict[name] = {
                    "stationsnummer": station.get("number"),
                    "breitengrad": station.get("latitude"),
                    "laengengrad": station.get("longitude"),
                    "gewaesser": station.get("water")["longname"].title()
                }

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Fehler beim Abrufen der Daten: {e}")

    return pegel_dict


def load_italian_station_data(station, start, end, water_temperature_at_catch):
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
        df_water_level_raw = load_arpa_lombardia_sensor_values(
            level_sensor_id,
            start,
            end + timedelta(days=1)
        )
    else:
        source = "AIPO"
        client = AipoClient.from_file("fangreport/data/aipo_auth.json")
        df_water_level_raw = client.load_sensor_values(
            level_sensor_id,
            start,
            end + timedelta(days=1)
        )

    if df_water_level_raw.empty:
        raise ValueError(
            f"Für die italienische Station '{station_data['display_name']}' "
            f"wurden im gewählten Zeitraum keine Pegeldaten für Sensor {level_sensor_id} gefunden."
        )

    df_water_level = df_water_level_raw.rename(columns={"Wert": "Wasserstand"})

    return {
        "station_display_name": station_data["display_name"],
        "water": station_data["water"],
        "df_water_level": df_water_level,
        "water_temperature_at_catch": water_temperature_at_catch,
        "source": source,
    }


def normalize_station_name(value):
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.replace("-", " ").replace("_", " ").split())


def italian_stations_dict():
    stations = {}

    with open("fangreport/data/italian_stations.json", "r", encoding="utf-8") as f:
        italian_stations = json.load(f)

    for canonical_name, station_data in italian_stations.items():
        stations[normalize_station_name(canonical_name)] = station_data

        for alias in station_data.get("aliases", []):
            stations[normalize_station_name(alias)] = station_data

    return stations


def find_italian_station(station):
    return italian_stations_dict().get(normalize_station_name(station))


def load_arpa_lombardia_sensor_values(sensor_id, start, end):
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
        return pd.DataFrame(columns=["Zeit", "Wert"]).set_index("Zeit")

    data_frame = pd.DataFrame(raw_data)

    if "data" not in data_frame.columns or "valore" not in data_frame.columns:
        raise ValueError(
            "Die ARPA-Lombardia-Daten enthalten nicht die erwarteten Spalten "
            "'data' und 'valore'."
        )

    data_frame = data_frame.rename(
        columns={
            "data": "Zeit",
            "valore": "Wert",
        }
    )

    data_frame["Zeit"] = pd.to_datetime(data_frame["Zeit"], errors="coerce")
    data_frame["Wert"] = pd.to_numeric(data_frame["Wert"], errors="coerce")
    data_frame = data_frame.dropna(subset=["Zeit", "Wert"])
    data_frame = data_frame.set_index("Zeit").sort_index()

    if data_frame.index.tz is not None:
        data_frame.index = data_frame.index.tz_convert("Europe/Rome").tz_localize(None)

    return data_frame