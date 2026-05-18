import sys

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
import numpy as np
from datetime import datetime, timedelta


def pegelonline_stations_dict():
    """
    Fetches data from the Pegel Online API and returns a dictionary containing station information.

    The function retrieves a list of water level stations in JSON format from the Pegel Online API. It
    processes the data to create a dictionary where the keys are the long names of the stations and
    the corresponding values are dictionaries containing station details such as station number,
    latitude, longitude, and the related water body's name.

    :raises RuntimeError: If there is an error in making the HTTP request to the Pegel Online API.

    :return: A dictionary where keys are the stations' long names (str), and values are dictionaries
             containing details such as station number (int), latitude (float), longitude (float),
             and water body name (str).
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


def visualize_catch_conditions(date: str, 
                               time_of_catch: str, 
                               station: str,
                               latitude: float,
                               longitude: float,
                               n_days_past: int = 3, 
                               n_days_future: int = 1):
    # Datum im YYYY-MM-TT Format
    stations_dict = pegelonline_stations_dict()

    station_data = stations_dict.get(station.upper())
    if station_data is None:
        raise ValueError(
            f"Ungültige Pegelstelle: '{station}'. "
            "Bitte gib eine gültige Pegelstelle an."
        )

    # 1. KONFIGURATION
    # Koordinaten des Fangorts für Wetterdaten
    LAT = latitude
    LON = longitude
    
    # Verifizierte Pegelstation
    STATION_NUMBER = station_data["stationsnummer"]
    WATER = station_data["gewaesser"]

    # Zeitraum um das Fangdatum herum
    today = datetime.now()

    try:
        catch_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Ungültiges Datum: '{date}'. Erwartetes Format: YYYY-MM-DD, z. B. 2026-05-17."
        ) from e

    start = catch_date - timedelta(days=n_days_past)
    if catch_date.date() < today.date():
        end = catch_date + timedelta(days=n_days_future)
    else:
        end = catch_date
        
    plot_start = start
    plot_end = end + timedelta(days=1)
    forecast_start = today

    start_date = plot_start.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")

    try:
        tof = datetime.strptime(f"{date} {time_of_catch}", "%Y-%m-%d %H:%M")
    except ValueError as e:
        raise ValueError(
            f"Ungültige Fangzeit: '{time_of_catch}'. Erwartetes Format: HH:MM, z. B. 18:30."
        ) from e

    print(f"--- GENERIERE GRAFISCHEN ANGEL-REPORT ---")
    print(f"Zeitraum: {start_date} bis {end_date}\n")

    # ==========================================
    # 2. DATENABRUF (Wetter & Pegel)
    # ==========================================
    # Wetterdaten abrufen
    wetter_url = "https://api.open-meteo.com/v1/forecast"
    wetter_params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,surface_pressure,wind_speed_10m,wind_direction_10m",
        "timezone": "Europe/Berlin"
    }

    # Pegeldaten abrufen (Vollständige URL über die funktionierende API)
    pegel_start = start.isoformat()
    pegel_url = f"https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/{STATION_NUMBER}/W/measurements.json"

    def lade_json(url, params=None, description="Daten"):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=20,
                headers={"Accept": "application/json"}
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type.lower():
                raise ValueError(
                    f"{description}: Server hat kein JSON geliefert. "
                    f"Content-Type: {content_type}. Antwort-Anfang: {response.text[:300]}"
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"{description}: Netzwerk- oder HTTP-Fehler: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"{description}: Ungültige JSON-Antwort: {e}") from e


    # 2a. Wetter abrufen & verarbeiten
    try:
        print("[1/2] Rufe Wetterdaten von Open-Meteo ab...")
        weather_json = lade_json(wetter_url, wetter_params, "Wetterdaten")

        if "hourly" not in weather_json:
            raise RuntimeError(f"Wetterdaten enthalten keinen 'hourly'-Block: {weather_json}")

        weather_res = weather_json["hourly"]

        df_weather = pd.DataFrame({
            "Zeit": pd.to_datetime(weather_res["time"]),
            "Temperatur": weather_res["temperature_2m"],
            "Luftdruck": weather_res["surface_pressure"],
            "Wind": weather_res["wind_speed_10m"],
            "Windrichtung": weather_res["wind_direction_10m"]
        }).set_index("Zeit")


        def remove_timezone(index):
            if index.tz is None:
                return index
            return index.tz_convert("Europe/Berlin").tz_localize(None)


        df_weather.index = remove_timezone(df_weather.index)
        df_weather = df_weather.loc[(df_weather.index >= plot_start) & (df_weather.index <= plot_end)]

        # 2b. Pegel abrufen & verarbeiten
        print(f"[2/2] Rufe Pegeldaten für Station {station.title()} ab...")
        water_level_res = lade_json(pegel_url, {"start": pegel_start}, "Pegeldaten")

        df_water_level = pd.DataFrame({
            "Zeit": pd.to_datetime([eintrag["timestamp"] for eintrag in water_level_res]),
            "Wasserstand": [eintrag["value"] for eintrag in water_level_res]
        }).set_index("Zeit")
        df_water_level.index = remove_timezone(df_water_level.index)
        df_water_level = df_water_level.loc[(df_water_level.index >= plot_start) & (df_water_level.index <= plot_end)]

        print("-> Alle Daten erfolgreich geladen. Erstelle Diagramme...")

    except Exception as e:
        print(f"\n❌ Fehler beim Datenabruf: {e}")
        raise SystemExit(1)


    # ==========================================
    # 3. GRAFISCHE VISUALISIERUNG (Matplotlib)
    # ==========================================
    # Erstelle zwei Subplots untereinander mit geteilter X-Achse
    fig, (ax1, ax3) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(
        f"Angel-Report: {date}",
        fontsize=14,
        fontweight='bold'
    )

    # --- DIAGRAMM 1: WETTER (Temperatur & Luftdruck & Wind) ---
    color_temp = '#e74c3c'
    ax1.plot(df_weather.index, df_weather['Temperatur'], color=color_temp, linewidth=2, label='Temperatur (°C)')
    ax1.set_ylabel('Temperatur / Wind', color=color_temp, fontweight='bold')
    ax1.set_ylim(0, 35)
    ax1.tick_params(axis='y', labelcolor=color_temp)
    ax1.grid(True, linestyle=':', alpha=0.6)

    if plot_start <= forecast_start <= plot_end:
        ax1.axvspan(
            forecast_start,
            plot_end,
            color='gray',
            alpha=0.12,
            hatch='//',
            # label='Vorhersage'
        )

        ax1.annotate(
            "Vorhersage",
            xy=(forecast_start, 1),
            xycoords=('data', 'axes fraction'),
            xytext=(8, 8),
            textcoords='offset points',
            ha='left',
            va='bottom',
            fontsize=9,
            fontweight='bold',
            color='dimgray',
            bbox={
                'boxstyle': 'round,pad=0.3',
                'facecolor': 'white',
                'edgecolor': 'gray',
                'alpha': 0.85
            }
        )

    catchtime_start = tof - timedelta(minutes=30)
    catchtime_ende = tof + timedelta(minutes=30)

    ax1.axvspan(
        catchtime_start,
        catchtime_ende,
        color='gold',
        alpha=0.18
    )

    ax1.annotate(
        f"Fangzeit {time_of_catch}",
        xy=(tof, 1),
        xycoords=('data', 'axes fraction'),
        xytext=(8, 8),
        textcoords='offset points',
        ha='left',
        va='bottom',
        fontsize=9,
        fontweight='bold',
        color='black',
        bbox={
            'boxstyle': 'round,pad=0.3',
            'facecolor': 'white',
            'edgecolor': 'goldenrod',
            'alpha': 0.85
        }
    )

    # Zweite Y-Achse für den Luftdruck
    ax2 = ax1.twinx()
    color_press = '#2980b9'
    ax2.plot(df_weather.index, df_weather['Luftdruck'], color=color_press, linewidth=2, linestyle='--',
             label='Luftdruck (hPa)')
    ax2.set_ylabel('Luftdruck (hPa)', color=color_press, fontweight='bold')
    ax2.set_ylim(970, 1045)
    ax2.tick_params(axis='y', labelcolor=color_press)

    # Windstärke flächig im Hintergrund
    color_wind = '#2ecc71'
    ax1.fill_between(df_weather.index, df_weather['Wind'], alpha=0.15, color=color_wind, label='Wind (km/h)')

    # Windrichtung als Pfeile anzeigen
    wind_sample = df_weather.iloc[::6].copy()  # alle 6 Stunden ein Pfeil
    wind_rad = np.deg2rad(wind_sample["Windrichtung"])

    # Meteorologische Windrichtung: Richtung, aus der der Wind kommt.
    # Für die Pfeile drehen wir sie um 180°, damit sie in die Blasrichtung zeigen.
    u = np.sin(wind_rad + np.pi)
    v = np.cos(wind_rad + np.pi)

    y_min, y_max = ax1.get_ylim()
    arrow_y = y_min + 0.08 * (y_max - y_min)

    ax1.quiver(
        wind_sample.index,
        [arrow_y] * len(wind_sample),
        u,
        v,
        angles='uv',
        scale_units='xy',
        scale=7,
        width=0.002,
        color=color_wind,
        alpha=0.8,
    )

    # Eigener Legendeneintrag für Windrichtung als Pfeil
    wind_direction_handle = Line2D(
        [],
        [],
        color=color_wind,
        marker=r'$\rightarrow$',
        linestyle='None',
        markersize=14,
        label='Windrichtung'
    )

    # Legenden des oberen Plots zusammenführen
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(
        lines1 + lines2 + [wind_direction_handle],
        labels1 + labels2 + ['Windrichtung'],
        loc='upper left'
    )
    ax1.set_title(
        f"Wetter am Fangort ({latitude:.5f}, {longitude:.5f})",
        fontsize=11,
        loc='left',
        pad=10
    )

    # --- DIAGRAMM 2: WASSERSTAND ---
    color_pegel = '#2980b9'
    ax3.plot(
        df_water_level.index, df_water_level['Wasserstand'],
        color=color_pegel,
        linewidth=2.5,
        label=f'Pegel {station.title()} (cm)'
    )
    ax3.set_ylabel('Wasserstand (cm)', color=color_pegel, fontweight='bold')
    ax3.tick_params(axis='y', labelcolor=color_pegel)
    ax3.grid(True, linestyle=':', alpha=0.6)

    ax3.axvspan(
        catchtime_start,
        catchtime_ende,
        color='gold',
        alpha=0.18
    )

    if plot_start <= forecast_start <= plot_end:
        ax3.axvspan(
            forecast_start,
            plot_end,
            color='gray',
            alpha=0.12,
            hatch='//'
        )

    ax3.set_title(
        f"{WATER}-Pegel {station.title()}",
        fontsize=11,
        loc='left',
        pad=10
    )
    ax3.legend(loc='upper left')

    # Formatiere die gemeinsame X-Achse (Zeitachse)
    ax3.set_xlabel('Datum / Uhrzeit', fontweight='bold', labelpad=10)
    ax3.set_xlim(plot_start, plot_end)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m.\n%H:%M'))
    ax3.xaxis.set_major_locator(mdates.HourLocator(interval=12))  # Alle 12 Stunden ein Marker
    plt.xticks(rotation=0)

    # Layout optimieren und Diagramm anzeigen
    plt.tight_layout()
    print("-> Diagramm-Fenster wird geöffnet.")
    plt.show()


if __name__ == "__main__":
    station = sys.argv[1]
    date = sys.argv[2]
    catchtime = sys.argv[3]

    try:
        latitude = float(sys.argv[4])
        longitude = float(sys.argv[5])
    except IndexError as e:
        raise ValueError(
            "Latitude und Longitude müssen angegeben werden. "
            "Beispiel: python wetterdaten.py \"TWIELENFLETH SIEL\" 2026-05-17 18:30 53.60 9.55"
        ) from e
    except ValueError as e:
        raise ValueError(
            "Latitude und Longitude müssen Zahlen sein, z. B. 53.60 9.55."
        ) from e

    if not -90 <= latitude <= 90:
        raise ValueError(
            f"Ungültiger Breitengrad: {latitude}. Erwartet wird ein Wert zwischen -90 und 90."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            f"Ungültiger Längengrad: {longitude}. Erwartet wird ein Wert zwischen -180 und 180."
        )

    try:
        visualize_catch_conditions(station, date, catchtime, latitude, longitude)
    except ValueError as e:
        print(f"❌ Eingabefehler: {e}")
        raise SystemExit(1)