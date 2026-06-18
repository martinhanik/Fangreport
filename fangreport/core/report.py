import os
import requests
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages

import numpy as np
import scipy.stats as stats
from datetime import datetime, timedelta
from PIL import Image

from fangreport.data_loading.water_level import load_italian_station_data, load_german_station_data


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


def wind_direction_arrow(deg):
    if deg is None or deg == "Keine Daten":
        return ""

    try:
        deg = float(deg)
    except:
        return ""

    arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]

    # Drehe um 180° für Pfeil in Blasrichtung
    return arrows[((round(deg / 45) % 8) + 4) % 8]


def trend_arrow(slope, threshold):
    if slope is None:
        return ""

    try:
        slope = float(slope)
    except:
        return ""

    if slope > threshold:
        return "↗"
    elif slope < -threshold:
        return "↘"
    return "→"


def MetricTile(label, value, meta=None):
    """
    meta kann enthalten:
    - unit
    - trend (slope: float)
    - direction (degrees)
    - threshold
    - color_mode
    """

    meta = meta or {}

    # 1. Basiswert
    display_value = value

    # 2. Windrichtung
    if meta.get("direction") is not None:
        display_value = f"{value} {wind_direction_arrow(meta['direction'])}"

    # 3. Trend
    if "trend" in meta:
        slope = meta["trend"]
        threshold = meta.get("threshold")
        arrow = trend_arrow(slope, threshold)
        display_value = f"{value} {arrow}"

    # 4. Farbe optional
    color = "#111827"

    if "trend" in meta and meta["trend"] is not None:
        slope = float(meta["trend"])
        threshold = np.abs(meta.get("threshold"))
        if slope > threshold:
            color = "#16a34a"   # grün
        elif slope < -threshold:
            color = "#dc2626"   # rot
        else:
            color = "#6b7280"

    return label, display_value, color


def generate_catch_report(date: str,
                          time_of_catch: str,
                          station: str,
                          latitude: float,
                          longitude: float,
                          water_temperature_at_catch: float | None,
                          species: str,
                          fish_length: float | None,
                          fish_weight: float | None,
                          water_turbidity: str,
                          photo_path: str | None = None,
                          notes: str = "",
                          n_days_past: int = 3,
                          n_days_future: int = 1):
    # 1. KONFIGURATION

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

    italian_station_result = load_italian_station_data(
        station,
        start,
        end,
        water_temperature_at_catch
    )

    station_number = None
    pegel_url = None

    if italian_station_result is None:
        stations_dict = load_german_station_data()

        station_data = stations_dict.get(station.upper())
        if station_data is None:
            raise ValueError(
                f"Ungültige Pegelstelle: '{station}'. "
                "Bitte gib eine gültige PEGELONLINE-Pegelstelle oder eine unterstützte italienische Station an."
            )

        # Verifizierte PEGELONLINE-Pegelstation
        station_number = station_data["stationsnummer"]
        water = station_data["gewaesser"]
        station_display_name = station.title()
        station_source = "PEGELONLINE"
    else:
        water = italian_station_result["water"]
        station_display_name = italian_station_result["station_display_name"]
        station_source = italian_station_result["source"]
        water_temperature_at_catch = italian_station_result["water_temperature_at_catch"]

    print(f"--- GENERIERE GRAFISCHEN ANGEL-REPORT ---")
    print(f"Zeitraum: {start_date} bis {end_date}")
    print(f"Pegelquelle: {station_source}\n")

    # ==========================================
    # 2. DATENABRUF (Wetter & Pegel)
    # ==========================================
    # Wetterdaten abrufen
    weather_url = "https://archive-api.open-meteo.com/v1/era5"
    weather_params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": (
            "temperature_2m,"
            "surface_pressure,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "weather_code,"
            "precipitation,"
            "cloud_cover"
        ),
        "timezone": "Europe/Berlin"
    }

    # Pegeldaten abrufen
    pegel_start = start.isoformat()
    if italian_station_result is None:
        pegel_url = f"https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_number}/W/measurements.json"

    def load_json(url, params=None, description="Daten"):
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
        weather_json = load_json(weather_url, weather_params, "Wetterdaten")

        if "hourly" not in weather_json:
            raise RuntimeError(f"Wetterdaten enthalten keinen 'hourly'-Block: {weather_json}")

        weather_res = weather_json["hourly"]

        df_weather = pd.DataFrame({
            "Zeit": pd.to_datetime(weather_res["time"]),
            "Temperatur": weather_res["temperature_2m"],
            "Luftdruck": weather_res["surface_pressure"],
            "Wind": weather_res["wind_speed_10m"],
            "Windrichtung": weather_res["wind_direction_10m"],
            "Wettercode": weather_res["weather_code"],
            "Regen": weather_res["precipitation"],
            "Wolkenbedeckung": weather_res["cloud_cover"]
        }).set_index("Zeit")


        def remove_timezone(index):
            if index.tz is None:
                return index
            return index.tz_convert("Europe/Berlin").tz_localize(None)


        df_weather.index = remove_timezone(df_weather.index)
        df_weather = df_weather.loc[(df_weather.index >= plot_start) & (df_weather.index <= plot_end)]

        # 2b. Pegel abrufen & verarbeiten
        print(f"[2/2] Rufe Pegeldaten für Station {station_display_name} ab...")

        if italian_station_result is None:
            water_level_res = load_json(pegel_url, {"start": pegel_start}, "Pegeldaten")

            df_water_level = pd.DataFrame({
                "Zeit": pd.to_datetime([eintrag["timestamp"] for eintrag in water_level_res]),
                "Wasserstand": [eintrag["value"] for eintrag in water_level_res]
            }).set_index("Zeit")
            df_water_level.index = remove_timezone(df_water_level.index)
            df_water_level = df_water_level.loc[(df_water_level.index >= plot_start) & (df_water_level.index <= plot_end)]

        else:
            df_water_level = italian_station_result["df_water_level"]
            df_water_level = df_water_level.loc[
                (df_water_level.index >= plot_start)
                & (df_water_level.index <= plot_end)
            ]

        # Setze klar falsche Werte auf None
        df_water_level["Wasserstand"] = df_water_level["Wasserstand"].astype("Float64")

        cond = np.abs(df_water_level["Wasserstand"]) > 10 ** 5
        df_water_level["Wasserstand"] = df_water_level["Wasserstand"].mask(cond, pd.NA)

        air_temperature_at_catch = get_nearest_value(df_weather, catch_datetime, "Temperatur")
        air_pressure_at_catch = get_nearest_value(df_weather, catch_datetime, "Luftdruck")
        wind_speed_at_catch = get_nearest_value(df_weather, catch_datetime, "Wind")
        wind_direction_at_catch = get_nearest_value(df_weather, catch_datetime, "Windrichtung")
        weather_code_at_catch = get_nearest_value(df_weather, catch_datetime, "Wettercode")
        water_level_at_catch = get_nearest_value(df_water_level, catch_datetime, "Wasserstand")

        weather_type_at_catch = (
            describe_weather_code(weather_code_at_catch)
            if weather_code_at_catch is not None
            else "Keine Daten"
        )

        report_data = {
            "Fischart": species,
            "Länge": format_value(fish_length, "cm", 0),
            "Gewicht": format_value(fish_weight, "kg", 1),
            "Datum": catch_datetime.strftime("%d.%m.%Y"),
            "Fangzeit": catch_datetime.strftime("%H:%M Uhr"),
            "Fangort": f"{latitude:.5f}, {longitude:.5f}",
            "Fangort-Link": f"https://www.google.com/maps?q={latitude:.5f},{longitude:.5f}",
            "Gewässer": water,
            "Mondphase": calculate_moon_phase(catch_datetime),
            "Wettertyp": weather_type_at_catch,
            "Lufttemperatur": format_value(air_temperature_at_catch, "°C"),
            "Wassertemperatur": format_value(water_temperature_at_catch, "°C"),
            "Luftdruck": format_value(air_pressure_at_catch, "hPa", 0),
            "Wind": format_value(wind_speed_at_catch, "km/h", 0),
            "Pegelstelle": station_display_name,
            "Wasserstand": format_value(water_level_at_catch, "cm", 0),
            "Trübung": water_turbidity,
        }

        def slope_of_trend(df, keyword, timeframe_m: int = 360):
            # Berechne den Anstieg einer äquidistanten Zeitreihe in den letzten timeframe_m Minuten.
            time_delta_m = (df.index[1] - df.index[0]).to_numpy().astype("timedelta64[m]").astype(int)
            ind_timeframe_ago = timeframe_m // time_delta_m

            nearest_index = df.index.get_indexer([catch_datetime], method="nearest")[0]
            recent_level = df[keyword].to_numpy()[nearest_index - ind_timeframe_ago: nearest_index]

            # Berechne stündlichen Anstieg
            time_delta_h = time_delta_m / 60
            timeframe_h = int(timeframe_m / 60)
            slope = stats.linregress(np.arange(0, timeframe_h, time_delta_h), recent_level)[0]

            return slope

        water_slope = slope_of_trend(df_water_level, "Wasserstand")
        air_pressure_slope = slope_of_trend(df_weather, "Luftdruck")
        air_temperature_slope = slope_of_trend(df_weather, "Temperatur", 4320)  # 3 Tage

        summary_items = [
            MetricTile(
                "Wetter",
                report_data.get("Wettertyp", "Keine Daten")
            ),

            MetricTile(
                "Luft",
                report_data.get("Lufttemperatur", "Keine Daten"),
                meta={
                    "trend": (
                        air_temperature_slope
                    ),
                    "threshold": (
                        0.03
                    )
                }
            ),

            MetricTile(
                "Wasser",
                report_data.get("Wassertemperatur", "Keine Daten")
            ),

            MetricTile(
                f"Pegel ({station_display_name})",
                report_data.get("Wasserstand", "Keine Daten"),
                meta={
                    "trend": (
                        water_slope
                    ),
                    "threshold": (
                        0.1
                    )
                }
            ),

            MetricTile(
                "Wind",
                report_data.get("Wind", "Keine Daten"),
                meta={
                    "direction": wind_direction_at_catch
                }
            ),

            MetricTile(
                "Mondphase",
                report_data.get("Mondphase", "Keine Daten")
            ),

            MetricTile(
                "Luftdruck",
                report_data.get("Luftdruck", "Keine Daten"),
                meta={
                    "trend": (
                        air_pressure_slope
                    ),
                    "threshold": (
                        0.1
                    )
                }
            ),

            MetricTile(
                "Trübung",
                report_data.get("Trübung", "Keine Daten")
            ),
        ]

        print("-> Alle Daten erfolgreich geladen. Erstelle Diagramme...")

    except Exception as e:
        print(f"\n❌ Fehler beim Datenabruf: {e}")
        raise SystemExit(1)


    # ==========================================
    # 3. GRAFISCHE VISUALISIERUNG (Matplotlib)
    # ==========================================
    # Erstelle zwei Subplots untereinander mit geteilter X-Achse
    fig, (ax1, ax_rain, ax3) = plt.subplots(
        3,
        1,
        figsize=(12, 9),
        sharex=True,
        gridspec_kw={
            "height_ratios": [2.2, 1.0, 1.8],
            "hspace": 0.18
        }
    )
    fig.suptitle(
        f"Wetter- und Pegelverlauf: {start_date} - {end_date}",
        fontsize=14,
        fontweight='bold'
    )

    # Hilfsfunktion: Wolkenbedeckung im Regenplot als Hintergrund darstellen.
    # 0 % = hellblau, 100 % = grau.
    def draw_cloud_cover_background(axis):
        if "Wolkenbedeckung" not in df_weather.columns or df_weather.empty:
            return

        cloud_data = df_weather["Wolkenbedeckung"].fillna(0).clip(0, 100)

        clear_sky_color = np.array([0.78, 0.90, 1.00])  # hellblau
        cloudy_color = np.array([0.62, 0.62, 0.62])  # grau

        for timestamp, cloud_cover in cloud_data.items():
            cloud_fraction = cloud_cover / 100
            background_color = (
                    clear_sky_color * (1 - cloud_fraction)
                    + cloudy_color * cloud_fraction
            )

            axis.axvspan(
                timestamp,
                timestamp + timedelta(hours=1),
                color=background_color,
                alpha=0.45,
                linewidth=0,
                zorder=0
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

    # --- DIAGRAMM 2: REGEN & WOLKENBEDECKUNG ---
    draw_cloud_cover_background(ax_rain)

    color_rain = "#3498db"
    ax_rain.bar(
        df_weather.index,
        df_weather["Regen"],
        width=0.035,
        align="edge",
        color=color_rain,
        edgecolor=color_rain,
        alpha=0.85,
        label="Regen (mm/h)",
        zorder=2
    )
    ax_rain.set_ylabel("Regen\n(mm/h)", color=color_rain, fontweight="bold")
    ax_rain.tick_params(axis="y", labelcolor=color_rain)
    ax_rain.grid(True, linestyle=":", alpha=0.6, zorder=1)

    max_rain = df_weather["Regen"].max()
    if pd.isna(max_rain) or max_rain <= 0:
        ax_rain.set_ylim(0, 1)
    else:
        ax_rain.set_ylim(0, max_rain * 1.25)

    ax_rain.axvspan(
        catchtime_start,
        catchtime_ende,
        color='gold',
        alpha=0.18,
        zorder=3
    )

    if plot_start <= forecast_start <= plot_end:
        ax_rain.axvspan(
            forecast_start,
            plot_end,
            color='gray',
            alpha=0.12,
            hatch='//',
            zorder=3
        )

    cloud_cover_handle = Line2D(
        [],
        [],
        color="#9ea7ad",
        linewidth=8,
        alpha=0.45,
        label="Wolkenbedeckung: hellblau → grau"
    )

    rain_handles, rain_labels = ax_rain.get_legend_handles_labels()
    ax_rain.legend(
        rain_handles + [cloud_cover_handle],
        rain_labels + ["Wolkenbedeckung: hellblau → grau"],
        loc="upper left"
    )
    ax_rain.set_title(
        "Niederschlag und Wolkenbedeckung",
        fontsize=11,
        loc="left",
        pad=10
    )

    # --- DIAGRAMM 3: WASSERSTAND ---
    color_pegel = '#2980b9'
    ax3.plot(
        df_water_level.index, df_water_level['Wasserstand'],
        color=color_pegel,
        linewidth=2.5,
        label=f'Pegel {station_display_name} (cm)'
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
        f"{water}-Pegel {station_display_name}",
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
    fig.subplots_adjust(
        left=0.08,
        right=0.92,
        bottom=0.10,
        top=0.90,
        hspace=0.25
    )

    report_location = "./Fänge"
    if not os.path.exists(report_location):
        os.makedirs(report_location)

    pdf_path = f"{report_location}/fang_report_{date}_{station_display_name.lower().replace(' ', '_')}.pdf"
    create_pdf_report(
        pdf_path=pdf_path,
        plot_figure=fig,
        report_data=report_data,
        summary_items=summary_items,
        photo_path=photo_path,
        notes = notes
    )

    print(f"-> PDF wurde erstellt: {pdf_path}")
    print("-> Diagramm-Fenster wird geöffnet.")


def create_pdf_report(
    pdf_path,
    plot_figure,
    report_data,
    summary_items,
    photo_path=None,
    notes=""
):

    PAGE_TOP = 0.95
    PAGE_BOTTOM = 0.05

    HEADER_H = 0.07

    CARD_H = 0.06
    CARD_ROWS = 2
    CARD_GAP = 0.02

    GAP_SECTION = 0.04

    header_y = PAGE_TOP - HEADER_H

    cards_top = header_y - GAP_SECTION
    cards_height = CARD_ROWS * CARD_H + (CARD_ROWS - 1) * CARD_GAP
    cards_bottom = cards_top - cards_height

    content_top = cards_bottom - GAP_SECTION
    content_height = 0.34
    content_bottom = content_top - content_height

    photo_top = content_bottom - GAP_SECTION
    photo_bottom = PAGE_BOTTOM
    photo_height = photo_top - photo_bottom

    with PdfPages(pdf_path) as pdf:
        report_figure = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
        report_figure.patch.set_facecolor("#f7f9fb")

        # Kopfbereich
        header_axis = report_figure.add_axes((0.06, header_y, 0.88, HEADER_H))
        header_axis.set_facecolor("#1f4e79")
        header_axis.set_xticks([])
        header_axis.set_yticks([])

        for spine in header_axis.spines.values():
            spine.set_visible(False)

        header_axis.text(
            0.03,
            0.62,
            "Fangreport",
            color="white",
            fontsize=22,
            fontweight="bold",
            va="center"
        )
        header_axis.text(
            0.03,
            0.25,
            f"{report_data.get('Gewässer', '')} · {report_data.get('Datum', '')} · {report_data.get('Fangzeit', '')}",
            color="#dbe9f6",
            fontsize=10,
            va="center"
        )

        fish_details = []

        if report_data.get("Länge") != "Keine Daten":
            fish_details.append(report_data["Länge"])

        if report_data.get("Gewicht") != "Keine Daten":
            fish_details.append(report_data["Gewicht"])

        fish_measurements = " · ".join(fish_details)

        header_axis.text(
            0.97,
            0.62,
            report_data.get("Fischart", ""),
            fontsize=18,
            fontweight="bold",
            color="white",
            ha="right",
            va="center"
        )

        if fish_measurements != "":
            header_axis.text(
                0.97,
                0.25,
                fish_measurements,
                color="#dbe9f6",
                fontsize=10,
                ha="right",
                va="center"
            )

        card_width = 0.205
        card_gap = 0.02
        card_height = 0.06

        top_row_y = cards_top - CARD_H
        second_row_y = top_row_y - CARD_H - CARD_GAP

        for index, (label, value, color) in enumerate(summary_items):

            row = index // 4  # 0 oder 1
            col = index % 4  # 0 bis 3

            card_y = top_row_y if row == 0 else second_row_y

            card_axis = report_figure.add_axes((
                0.06 + col * (card_width + card_gap),
                card_y,
                card_width,
                card_height
            ))

            card_axis.set_facecolor("white")
            card_axis.set_xticks([])
            card_axis.set_yticks([])

            for spine in card_axis.spines.values():
                spine.set_edgecolor("#d8dee6")
                spine.set_linewidth(1)

            card_axis.text(
                0.06,
                0.68,
                label,
                fontsize=8,
                color="#6b7280",
                fontweight="bold",
                transform=card_axis.transAxes
            )

            card_axis.text(
                0.06,
                0.28,
                value,
                fontsize=10,
                color=color,
                transform=card_axis.transAxes
            )

        content_y = content_bottom

        # Notizen rechts
        notes_axis = report_figure.add_axes((0.52, content_y, 0.42, content_height))
        notes_axis.set_facecolor("white")
        notes_axis.set_title("Notizen", loc="left", fontsize=12, fontweight="bold", pad=10)
        notes_axis.set_xticks([])
        notes_axis.set_yticks([])

        for spine in notes_axis.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("#d8dee6")
            spine.set_linewidth(1)

        if notes.strip():
            import textwrap

            def fit_notes(text, max_chars=52, max_lines=12):
                lines = []

                for paragraph in text.split("\n"):
                    lines.extend(textwrap.wrap(paragraph, width=max_chars))

                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    lines[-1] += " ..."

                return "\n".join(lines)

            notes_text = fit_notes(notes.strip())

            notes_axis.text(
                0.05,
                0.92,
                notes_text,
                fontsize=9,
                color="#111827",
                va="top",
                transform=notes_axis.transAxes,
                clip_on=True
            )
        else:
            notes_axis.text(
                0.05,
                0.94,
                "Beobachtungen, Köder, Strömung, Bisse ...",
                fontsize=8,
                color="#9ca3af",
                transform=notes_axis.transAxes
            )

        # Freie Fläche für Skizze unterhalb der Fangdaten
        sketch_axis = report_figure.add_axes((0.06, content_y, 0.42, content_height))
        sketch_axis.set_facecolor("white")
        title_obj = sketch_axis.set_title(
            f"Angelplatz ({report_data.get('Fangort', 'Keine Daten')}) ↗",
            loc="left",
            fontsize=12,
            fontweight="bold",
            pad=10
        )
        title_obj.set_url(report_data.get("Fangort-Link"))
        sketch_axis.set_xticks([])
        sketch_axis.set_yticks([])

        for spine in sketch_axis.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("#d8dee6")
            spine.set_linewidth(1)

        sketch_axis.text(
            0.10,
            0.94,
            "Skizze ...",
            ha="center",
            va="center",
            color="#c0c4cc",
            fontsize=9,
            transform=sketch_axis.transAxes
        )

        # Foto-Bereich unten über die volle Breite
        photo_axis = report_figure.add_axes((0.06, photo_bottom, 0.88, photo_height))
        photo_axis.set_facecolor("white")
        photo_axis.set_title("Foto", loc="left", fontsize=12, fontweight="bold", pad=10)
        photo_axis.set_xticks([])
        photo_axis.set_yticks([])

        for spine in photo_axis.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("#d8dee6")
            spine.set_linewidth(1)

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
                    wrap=True,
                    color="#6b7280"
                )
        else:
            photo_axis.text(
                0.5,
                0.5,
                "Hier kann ein Foto eingefügt werden",
                ha="center",
                va="center",
                color="#9ca3af",
                fontsize=11
            )

        pdf.savefig(report_figure)
        plt.close(report_figure)

        plot_figure.set_size_inches(11.69, 8.27)
        plot_figure.subplots_adjust(
            left=0.08,
            right=0.92,
            bottom=0.10,
            top=0.90,
            hspace=0.25
        )
        pdf.savefig(plot_figure)
        plt.close(plot_figure)
