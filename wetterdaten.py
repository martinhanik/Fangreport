import sys

import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from datetime import datetime, timedelta
from PIL import Image


def describe_weather_code(code):
    weather_codes = {
        0: "Klar",
        1: "Überwiegend klar",
        2: "Teilweise bewölkt",
        3: "Bewölkt",
        45: "Nebel",
        48: "Reifnebel",
        51: "Leichter Nieselregen",
        53: "Mäßiger Nieselregen",
        55: "Starker Nieselregen",
        56: "Leichter gefrierender Nieselregen",
        57: "Starker gefrierender Nieselregen",
        61: "Leichter Regen",
        63: "Mäßiger Regen",
        65: "Starker Regen",
        66: "Leichter gefrierender Regen",
        67: "Starker gefrierender Regen",
        71: "Leichter Schneefall",
        73: "Mäßiger Schneefall",
        75: "Starker Schneefall",
        77: "Schneekörner",
        80: "Leichte Regenschauer",
        81: "Mäßige Regenschauer",
        82: "Starke Regenschauer",
        85: "Leichte Schneeschauer",
        86: "Starke Schneeschauer",
        95: "Gewitter",
        96: "Gewitter mit leichtem Hagel",
        99: "Gewitter mit starkem Hagel",
    }
    return weather_codes.get(int(code), f"Unbekannt ({code})")


def calculate_moon_phase(date_time):
    reference_new_moon = datetime(2000, 1, 6, 18, 14)
    synodic_month = 29.53058867

    days_since_new_moon = (date_time - reference_new_moon).total_seconds() / 86400
    moon_age = days_since_new_moon % synodic_month

    if moon_age < 1.84566:
        return "Neumond"
    if moon_age < 5.53699:
        return "Zunehmende Sichel"
    if moon_age < 9.22831:
        return "Erstes Viertel"
    if moon_age < 12.91963:
        return "Zunehmender Mond"
    if moon_age < 16.61096:
        return "Vollmond"
    if moon_age < 20.30228:
        return "Abnehmender Mond"
    if moon_age < 23.99361:
        return "Letztes Viertel"
    if moon_age < 27.68493:
        return "Abnehmende Sichel"
    return "Neumond"


def get_nearest_value(data_frame, date_time, column):
    if data_frame is None or data_frame.empty or column not in data_frame.columns:
        return None

    nearest_index = data_frame.index.get_indexer([date_time], method="nearest")[0]
    return data_frame.iloc[nearest_index][column]


def format_value(value, unit="", decimals=1):
    if value is None or pd.isna(value):
        return "Keine Daten"

    if isinstance(value, str):
        return value

    return f"{value:.{decimals}f} {unit}".strip()


def describe_wind_direction(degrees):
    if degrees is None or pd.isna(degrees):
        return "Keine Daten"

    directions = [
        "Nord",
        "Nordnordost",
        "Nordost",
        "Ostnordost",
        "Ost",
        "Ostsüdost",
        "Südost",
        "Südsüdost",
        "Süd",
        "Südsüdwest",
        "Südwest",
        "Westsüdwest",
        "West",
        "Westnordwest",
        "Nordwest",
        "Nordnordwest",
    ]

    index = round(float(degrees) / 22.5) % 16
    return directions[index]


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


def generate_catch_report(date: str,
                               time_of_catch: str,
                               station: str,
                               latitude: float,
                               longitude: float,
                               water_temperature_at_catch: float,
                               fish_length: float,
                               photo_path: str | None = None,
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
    
    # Verifizierte Pegelstation
    station_number = station_data["stationsnummer"]
    water = station_data["gewaesser"]

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
        catch_datetime = datetime.strptime(f"{date} {time_of_catch}", "%Y-%m-%d %H:%M")
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
    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,surface_pressure,wind_speed_10m,wind_direction_10m,weather_code",
        "timezone": "Europe/Berlin"
    }

    # Pegeldaten abrufen (Vollständige URL über die funktionierende API)
    pegel_start = start.isoformat()
    pegel_url = f"https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_number}/W/measurements.json"

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
        weather_json = lade_json(weather_url, weather_params, "Wetterdaten")

        if "hourly" not in weather_json:
            raise RuntimeError(f"Wetterdaten enthalten keinen 'hourly'-Block: {weather_json}")

        weather_res = weather_json["hourly"]

        df_weather = pd.DataFrame({
            "Zeit": pd.to_datetime(weather_res["time"]),
            "Temperatur": weather_res["temperature_2m"],
            "Luftdruck": weather_res["surface_pressure"],
            "Wind": weather_res["wind_speed_10m"],
            "Windrichtung": weather_res["wind_direction_10m"],
            "Wettercode": weather_res["weather_code"]
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

        air_temperature_at_catch = get_nearest_value(df_weather, catch_datetime, "Temperatur")
        air_pressure_at_catch = get_nearest_value(df_weather, catch_datetime, "Luftdruck")
        wind_speed_at_catch = get_nearest_value(df_weather, catch_datetime, "Wind")
        wind_direction_at_catch = get_nearest_value(df_weather, catch_datetime, "Windrichtung")
        weather_code_at_catch = get_nearest_value(df_weather, catch_datetime, "Wettercode")
        water_level_at_catch = get_nearest_value(df_water_level, catch_datetime, "Wasserstand")
        # water_temperature_at_catch = get_nearest_value(
        #     df_water_temperature,
        #     catch_datetime,
        #     "Wassertemperatur"
        # )

        weather_type_at_catch = (
            describe_weather_code(weather_code_at_catch)
            if weather_code_at_catch is not None
            else "Keine Daten"
        )

        report_data = {
            "Länge": format_value(fish_length,  "cm", 0),
            "Datum": catch_datetime.strftime("%d.%m.%Y"),
            "Fangzeit": catch_datetime.strftime("%H:%M Uhr"),
            "Fangort": f"{latitude:.5f}, {longitude:.5f}",
            "Gewässer": water,
            "Mondphase": calculate_moon_phase(catch_datetime),
            "Wettertyp": weather_type_at_catch,
            "Lufttemperatur": format_value(air_temperature_at_catch, "°C"),
            "Wassertemperatur": format_value(water_temperature_at_catch, "°C"),
            "Luftdruck": format_value(air_pressure_at_catch, "hPa", 0),
            "Wind": format_value(wind_speed_at_catch, "km/h", 0),
            "Windrichtung": describe_wind_direction(wind_direction_at_catch),
            "Pegelstelle": station.title(),
            "Wasserstand": format_value(water_level_at_catch, "cm", 0),
        }

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
        f"Wetter- und Pegelverlauf: {start_date} - {end_date}",
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

    catchtime_start = catch_datetime - timedelta(minutes=30)
    catchtime_ende = catch_datetime + timedelta(minutes=30)

    ax1.axvspan(
        catchtime_start,
        catchtime_ende,
        color='gold',
        alpha=0.18
    )

    ax1.annotate(
        f"Fangzeit {time_of_catch}",
        xy=(catch_datetime, 1),
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
        f"{water}-Pegel {station.title()}",
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
    plt.tight_layout(rect=(0, 0, 1, 0.95))

    pdf_path = f"fang_report_{date}_{station.lower().replace(' ', '_')}.pdf"
    create_pdf_report(
        pdf_path=pdf_path,
        plot_figure=fig,
        report_data=report_data,
        photo_path=photo_path
    )

    print(f"-> PDF wurde erstellt: {pdf_path}")
    print("-> Diagramm-Fenster wird geöffnet.")
    plt.show()


def create_pdf_report(
    pdf_path,
    plot_figure,
    report_data,
    photo_path=None
):
    with PdfPages(pdf_path) as pdf:
        report_figure = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
        report_figure.suptitle("Fangreport", fontsize=18, fontweight="bold", y=0.97)

        table_axis = report_figure.add_axes((0.08, 0.50, 0.84, 0.38))
        table_axis.axis("off")

        table_data = [[key, value] for key, value in report_data.items()]
        table = table_axis.table(
            cellText=table_data,
            colLabels=["Feld", "Wert"],
            loc="center",
            cellLoc="left",
            colLoc="left"
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.4)

        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_text_props(fontweight="bold")
                cell.set_facecolor("#dddddd")
            elif col == 0:
                cell.set_text_props(fontweight="bold")
                cell.set_facecolor("#f2f2f2")

        notes_axis = report_figure.add_axes((0.08, 0.18, 0.40, 0.24))
        notes_axis.set_title("Notizen", loc="left", fontsize=11, fontweight="bold")
        notes_axis.set_xticks([])
        notes_axis.set_yticks([])
        for spine in notes_axis.spines.values():
            spine.set_visible(True)

        for y_position in np.linspace(0.85, 0.15, 6):
            notes_axis.axhline(y_position, color="lightgray", linewidth=0.8)

        photo_axis = report_figure.add_axes((0.55, 0.18, 0.34, 0.24))
        photo_axis.set_title("Foto", loc="left", fontsize=11, fontweight="bold")
        photo_axis.set_xticks([])
        photo_axis.set_yticks([])

        if photo_path:
            try:
                image = Image.open(photo_path)
                photo_axis.imshow(image)
                photo_axis.set_aspect("equal", adjustable="box")
                photo_axis.set_anchor("C")
            except Exception as e:
                photo_axis.text(
                    0.5,
                    0.5,
                    f"Foto konnte nicht geladen werden:\n{e}",
                    ha="center",
                    va="center",
                    wrap=True
                )
        else:
            photo_axis.text(
                0.5,
                0.5,
                "Hier kann ein Foto eingefügt werden",
                ha="center",
                va="center",
                color="gray"
            )

        pdf.savefig(report_figure)
        plt.close(report_figure)

        plot_figure.set_size_inches(11.69, 8.27)
        plot_figure.tight_layout(rect=(0, 0, 1, 0.95))
        pdf.savefig(plot_figure)


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

    fish_length = int(sys.argv[6])
    water_temperature = float(sys.argv[7])
    photo_path = sys.argv[8] if len(sys.argv) > 8 else None

    try:
        generate_catch_report(station, date, catchtime, latitude, longitude, water_temperature, fish_length, photo_path)
    except ValueError as e:
        print(f"❌ Eingabefehler: {e}")
        raise SystemExit(1)