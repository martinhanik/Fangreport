# Copyright (c) 2026 Martin Hanik
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional, Any
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

from fangreport.data_loading.water_level import load_italian_station_data, load_german_station_data, clean_water_level


def describe_weather_code(code: int | str) -> str:
    """
    Provides a mapping from weather codes to their corresponding weather descriptions
    in German. If a code is not recognized, a default message including the unknown code
    is returned.

    :param code: Weather code corresponding to a specific weather description
                 (e.g., 0 for "Klar"). The code is expected to be convertible to an integer.
    :type code: int or str
    :return: The German description of the weather condition matching the provided
             weather code. If the code is unrecognized, it returns a default string
             in the format "Unbekannt (<code>)".
    :rtype: str
    """
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


def calculate_moon_phase(date_time: datetime):
    """
    Calculate the phase of the moon for a given date and time.

    This function determines the current phase of the moon based on the number
    of days elapsed since a reference new moon and compares it to the synodic
    month (the mean duration between new moons). The moon phase is returned
    as one of numerous descriptive states (e.g., "Neumond" or "Vollmond").

    :param date_time: The date and time for which to calculate the moon phase.
    :type date_time: datetime.datetime
    :return: The moon phase corresponding to the provided date and time.
    :rtype: str
    """
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


def get_nearest_value(
        data_frame: pd.DataFrame,
        date_time: datetime | pd.Timestamp,
        column: str
) -> Any:
    """
    Retrieves the value from a specific column in a DataFrame that corresponds
    to the row with the nearest index to the given datetime.

    The function checks if the DataFrame is valid, non-empty, and contains the
    specified column. If any of these conditions are not met, it returns None.
    Otherwise, it identifies the row index closest to the provided datetime
    and retrieves the value in the specified column.

    :param data_frame: Pandas DataFrame from which the value will be retrieved.
                       It must contain the specified column and a properly
                       formatted index for comparison with the given datetime.
    :type data_frame: pandas.DataFrame
    :param date_time: The datetime object to find the nearest row index for.
    :type date_time: pandas.Timestamp or datetime.datetime
    :param column: The name of the column to retrieve the value from.
    :type column: str
    :return: The value in the specified column corresponding to the row with
             the nearest index to the given datetime. Returns None if the
             DataFrame is invalid, empty, or the column does not exist.
    :rtype: Any
    """
    if data_frame is None or data_frame.empty or column not in data_frame.columns:
        return None

    nearest_index = data_frame.index.get_indexer([date_time], method="nearest")[0]
    return data_frame.iloc[nearest_index][column]


def format_value(value, unit="", decimals=1):
    """
    Formats a given numerical value into a string representation, including optional unit and
    decimals for precision. Handles missing or invalid data by returning a predefined string.

    :param value: The numerical or string value to be formatted. It can also be None or NaN.
    :param unit: Optional. A string representing the unit to append to the formatted value.
    :param decimals: An integer specifying the number of decimal places to include
        when formatting numerical values.
    :return: A formatted string with the numerical value, optional unit, and specified precision.
        If the value is None or NaN, returns "Keine Daten".
    """
    if value is None or pd.isna(value):
        return "Keine Daten"

    if isinstance(value, str):
        return value

    return f"{value:.{decimals}f} {unit}".strip()


def wind_direction_arrow(deg: float | str | None) -> str:
    """
    Converts a wind direction in degrees into a corresponding arrow symbol that indicates
    the blowing direction. If the input is invalid or no data is provided,
    an empty string is returned.

    :param deg: The wind direction in degrees as a numeric value or a string.
                Possible invalid values include `None` or the string "Keine Daten".
    :type deg: float | str | None
    :return: A string representing the arrow symbol in the blowing direction
             corresponding to the provided wind direction. If the input is invalid,
             returns an empty string.
    :rtype: str
    """
    if deg is None or deg == "Keine Daten":
        return ""

    try:
        deg = float(deg)
    except:
        return ""

    arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]

    # Rotate by 180° for an arrow that points into the direction in which the wind blows (and not where it comes from)
    return arrows[((round(deg / 45) % 8) + 4) % 8]


def trend_arrow(slope: float | None, threshold: float) -> str:
    """
    Determines the appropriate arrow symbol to represent a trend based on the slope value
    and a specified threshold. The function returns an upward arrow if the slope exceeds
    the threshold, a downward arrow if the slope is less than the negative of the
    threshold, and a rightward arrow if the slope lies within the threshold range.

    :param slope: The slope value used to determine the trend. Can be None or convertible
        to a float.
    :type slope: float or None
    :param threshold: The threshold value against which the slope is compared. Should be
        a positive float.
    :type threshold: float
    :return: A string representing the trend arrow corresponding to the slope. Returns
        an empty string if the slope is None or invalid. The possible return values are:
        - "↗" (upward arrow) for a positive trend exceeding the threshold.
        - "↘" (downward arrow) for a negative trend below the negative threshold.
        - "→" (rightward arrow) for a neutral trend within the threshold range.
        - "" (empty string) for invalid or None slope.
    :rtype: str
    """
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


def MetricTile(label: str, value: str | float, meta: Optional = None) -> tuple[str, str, str]:
    """
    Creates and formats a metric tile for display.

    The function takes a label, a value, and optional metadata to generate a
    metric tile, including conditional modifications to the display based on
    the metadata, such as visual indicators for trends, directions, and colors.

    :param label:
        A string representing the title or name of the metric.

    :param value:
        A numeric or string value representing the metric value to be displayed.

    :param meta:
        Optional. A dictionary containing additional metadata. This can include:
        - "direction": A value for describing a directional indication (e.g., wind direction).
        - "trend": A numeric slope value for describing trends.
        - "threshold": A numeric value used as a threshold to determine trend-based color.

    :return:
        A tuple of three items:
        - The provided label (str).
        - A formatted display value (str) including directional or trend arrows if applicable.
        - A color (str), represented as a hexadecimal string, determined by the trend threshold.
    """

    meta = meta or {}

    # 1. Base value
    display_value = value

    # 2. Wind direction
    if meta.get("direction") is not None:
        display_value = f"{value} {wind_direction_arrow(meta["direction"])}"

    # 3. Trend
    if "trend" in meta:
        slope = meta["trend"]
        threshold = meta.get("threshold")
        arrow = trend_arrow(slope, threshold)
        display_value = f"{value} {arrow}"

    # 4. Optional color
    color = "#111827"

    if "trend" in meta and meta["trend"] is not None:
        slope = float(meta["trend"])
        threshold = np.abs(meta.get("threshold"))
        if slope > threshold:
            color = "#16a34a"   # green
        elif slope < -threshold:
            color = "#dc2626"   # red
        else:
            color = "#6b7280"

    return label, display_value, color


def generate_catch_report(
        date: str,
        time_of_catch: str,
        station: str,
        latitude: float,
        longitude: float,
        water_temperature_at_catch: float | None,
        species: str,
        fish_length: float | None,
        fish_weight: float | None,
        water_clarity: str,
        photo_path: str | None = None,
        notes: str = "",
        n_days_past: int = 3,
        n_days_future: int = 1,
        report_location: str | None = "./fänge"
) -> None:
    """
    Generate a detailed report related to a fishing catch event, including weather data, water levels, and catch details.
    The function gathers weather and hydrological data for a specified time period and location,
    validates input parameters, processes the relevant data, and generates a comprehensive fishing report.

    :param date: Date of the fishing event in the format YYYY-MM-DD (e.g., 2026-05-17).
    :type date: str
    :param time_of_catch: Time of the catch in the format HH:MM (e.g., 18:30).
    :type time_of_catch: str
    :param station: Identifier of the water observation station (e.g., PEGELONLINE or supported Italian station).
    :type station: str
    :param latitude: Latitude of the fishing location.
    :type latitude: float
    :param longitude: Longitude of the fishing location.
    :type longitude: float
    :param water_temperature_at_catch: Water temperature at the catch time, if available.
    :type water_temperature_at_catch: float | None
    :param species: Species of the fish caught (e.g., Wels, Hecht).
    :type species: str
    :param fish_length: Length of the fish caught in centimeters, if known.
    :type fish_length: float | None
    :param fish_weight: Weight of the fish caught in kilograms, if known.
    :type fish_weight: float | None
    :param water_clarity: Clarity of the water at the fishing location, described qualitatively (e.g., Klar, Trüb).
    :type water_clarity: str
    :param photo_path: File path or URL for the photo of the fish caught, if available.
    :type photo_path: str | None
    :param notes: Additional notes or remarks about the fishing event.
    :type notes: str
    :param n_days_past: Number of days before the catch date to include in the data report. Default is 3.
    :type n_days_past: int
    :param n_days_future: Number of days after the catch date to include in the data report. Default is 1.
    :type n_days_future: int
    :param report_location: Directory path where the generated report will be saved.
        Default is "./fänge".
    :type report_location: str | None
    :return: None. The function creates a graphical fishing report but does not return any value.
    :rtype: None
    """
    # 1. CONFIGURATION

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
        end
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

        # Verified PEGELONLINE-Pegelstation
        station_number = station_data["number"]
        water = station_data["water"]
        station_display_name = station.title()
        station_source = "PEGELONLINE"
    else:
        water = italian_station_result["water"]
        station_display_name = italian_station_result["station_display_name"]
        station_source = italian_station_result["source"]

    print(f"--- GENERIERE GRAFISCHEN ANGEL-REPORT ---")
    print(f"Zeitraum: {start_date} bis {end_date}")
    print(f"Pegelquelle: {station_source}\n")

    # ==========================================
    # 2. Collecting Data (Weather & Water Level)
    # ==========================================
    # Obtain weather data
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

    # Obtain water level
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

    # 2a. Weather
    try:
        print("[1/2] Rufe Wetterdaten von Open-Meteo ab...")
        weather_json = load_json(weather_url, weather_params, "Wetterdaten")

        if "hourly" not in weather_json:
            raise RuntimeError(f"Wetterdaten enthalten keinen 'hourly'-Block: {weather_json}")

        weather_res = weather_json["hourly"]

        df_weather = pd.DataFrame({
            "time": pd.to_datetime(weather_res["time"]),
            "temperature": weather_res["temperature_2m"],
            "air_pressure": weather_res["surface_pressure"],
            "wind": weather_res["wind_speed_10m"],
            "wind_direction": weather_res["wind_direction_10m"],
            "weather_code": weather_res["weather_code"],
            "Regen": weather_res["precipitation"],
            "cloud_cover": weather_res["cloud_cover"]
        }).set_index("time")


        def remove_timezone(index):
            if index.tz is None:
                return index
            return index.tz_convert("Europe/Berlin").tz_localize(None)


        df_weather.index = remove_timezone(df_weather.index)
        df_weather = df_weather.loc[(df_weather.index >= plot_start) & (df_weather.index <= plot_end)]

        # 2b. Water level
        print(f"[2/2] Rufe Pegeldaten für Station {station_display_name} ab...")

        if italian_station_result is None:
            water_level_res = load_json(pegel_url, {"start": pegel_start}, "Pegeldaten")

            df_water_level = pd.DataFrame({
                "time": pd.to_datetime([entry["timestamp"] for entry in water_level_res]),
                "water_level": [entry["value"] for entry in water_level_res]
            }).set_index("time")
            df_water_level.index = remove_timezone(df_water_level.index)
            df_water_level = df_water_level.loc[(df_water_level.index >= plot_start) & (df_water_level.index <= plot_end)]

        else:
            df_water_level = italian_station_result["df_water_level"]
            df_water_level = df_water_level.loc[
                (df_water_level.index >= plot_start)
                & (df_water_level.index <= plot_end)
            ]

        # Set wrong values to None
        df_water_level["water_level"] = df_water_level["water_level"].astype("Float64")

        df_water_level = clean_water_level(df_water_level)

        air_temperature_at_catch = get_nearest_value(df_weather, catch_datetime, "temperature")
        air_pressure_at_catch = get_nearest_value(df_weather, catch_datetime, "air_pressure")
        wind_speed_at_catch = get_nearest_value(df_weather, catch_datetime, "wind")
        wind_direction_at_catch = get_nearest_value(df_weather, catch_datetime, "wind_direction")
        weather_code_at_catch = get_nearest_value(df_weather, catch_datetime, "weather_code")
        water_level_at_catch = get_nearest_value(df_water_level, catch_datetime, "water_level")

        weather_type_at_catch = (
            describe_weather_code(weather_code_at_catch)
            if weather_code_at_catch is not None
            else "Keine Daten"
        )

        report_data = {
            "species": species,
            "fish_length": format_value(fish_length, "cm", 0),
            "fish_weight": format_value(fish_weight, "kg", 1),
            "catch_date": catch_datetime.strftime("%d.%m.%Y"),
            "catch_time": catch_datetime.strftime("%H:%M Uhr"),
            "catch_location": f"{latitude:.5f}, {longitude:.5f}",
            "catch_link": f"https://www.google.com/maps?q={latitude:.5f},{longitude:.5f}",
            "water": water,
            "moon_phase": calculate_moon_phase(catch_datetime),
            "weather_type": weather_type_at_catch,
            "air_temperature": format_value(air_temperature_at_catch, "°C"),
            "water_temperature": format_value(water_temperature_at_catch, "°C"),
            "air_pressure": format_value(air_pressure_at_catch, "hPa", 0),
            "wind": format_value(wind_speed_at_catch, "km/h", 0),
            "station_name": station_display_name,
            "water_level": format_value(water_level_at_catch, "cm", 0),
            "water_clarity": water_clarity,
        }

        def slope_of_trend(df, keyword, timeframe_m: int = 360):
            # Calculate tagent to equidistant time series in the last timeframe_m minutes.
            time_delta_m = (df.index[1] - df.index[0]).to_numpy().astype("timedelta64[m]").astype(int)
            ind_timeframe_ago = timeframe_m // time_delta_m

            nearest_index = df.index.get_indexer([catch_datetime], method="nearest")[0]
            recent_level = df[keyword].to_numpy()[nearest_index - ind_timeframe_ago: nearest_index]

            # Calculate hourly tangent
            time_delta_h = time_delta_m / 60
            timeframe_h = int(timeframe_m / 60)
            slope = stats.linregress(np.arange(0, timeframe_h, time_delta_h), recent_level)[0]

            return slope

        water_slope = slope_of_trend(df_water_level, "water_level")
        air_pressure_slope = slope_of_trend(df_weather, "air_pressure")
        air_temperature_slope = slope_of_trend(df_weather, "temperature", 4320)  # 3 Tage

        summary_items = [
            MetricTile(
                "Wetter",
                report_data.get("weather_type", "Keine Daten")
            ),

            MetricTile(
                "Luft",
                report_data.get("air_temperature", "Keine Daten"),
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
                report_data.get("water_temperature", "Keine Daten")
            ),

            MetricTile(
                f"Pegel ({station_display_name})",
                report_data.get("water_level", "Keine Daten"),
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
                report_data.get("wind", "Keine Daten"),
                meta={
                    "direction": wind_direction_at_catch
                }
            ),

            MetricTile(
                "Mondphase",
                report_data.get("moon_phase", "Keine Daten")
            ),

            MetricTile(
                "Luftdruck",
                report_data.get("air_pressure", "Keine Daten"),
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
                report_data.get("water_clarity", "Keine Daten")
            ),
        ]

        print("-> Alle Daten erfolgreich geladen. Erstelle Diagramme...")

    except Exception as e:
        print(f"\n❌ Fehler beim Datenabruf: {e}")
        raise SystemExit(1)


    # ==========================================
    # 3. Visualization (Matplotlib)
    # ==========================================
    # Create two Subplots with shared X-Achse
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
        fontweight="bold"
    )

    def draw_cloud_cover_background(axis):
        if "cloud_cover" not in df_weather.columns or df_weather.empty:
            return

        cloud_data = df_weather["cloud_cover"].fillna(0).clip(0, 100)

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

    # --- DIAGRAM 1: WEATHER ---
    color_temp = "#e74c3c"
    ax1.plot(df_weather.index, df_weather["temperature"], color=color_temp, linewidth=2, label="Temperatur (°C)")
    ax1.set_ylabel("Temperatur / Wind", color=color_temp, fontweight="bold")
    ax1.set_ylim(0, 40)
    ax1.tick_params(axis="y", labelcolor=color_temp)
    ax1.grid(True, linestyle=":", alpha=0.6)

    if plot_start <= forecast_start <= plot_end:
        ax1.axvspan(
            forecast_start,
            plot_end,
            color="gray",
            alpha=0.12,
            hatch="//",
            # label="Vorhersage"
        )

        ax1.annotate(
            "Vorhersage",
            xy=(forecast_start, 1),
            xycoords=("data", "axes fraction"),
            xytext=(8, 8),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="dimgray",
            bbox={
                "boxstyle": "round,pad=0.3",
                "facecolor": "white",
                "edgecolor": "gray",
                "alpha": 0.85
            }
        )

    catchtime_start = catch_datetime - timedelta(minutes=30)
    catchtime_ende = catch_datetime + timedelta(minutes=30)

    ax1.axvspan(
        catchtime_start,
        catchtime_ende,
        color="gold",
        alpha=0.18
    )

    ax1.annotate(
        f"Fangzeit {time_of_catch}",
        xy=(catch_datetime, 1),
        xycoords=("data", "axes fraction"),
        xytext=(8, 8),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=9,
        fontweight="bold",
        color="black",
        bbox={
            "boxstyle": "round,pad=0.3",
            "facecolor": "white",
            "edgecolor": "goldenrod",
            "alpha": 0.85
        }
    )

    # Second Y-axis for the air pressure
    ax2 = ax1.twinx()
    color_press = "#2980b9"
    ax2.plot(df_weather.index, df_weather["air_pressure"], color=color_press, linewidth=2, linestyle="--",
             label="Luftdruck (hPa)")
    ax2.set_ylabel("Luftdruck (hPa)", color=color_press, fontweight="bold")
    ax2.set_ylim(970, 1045)
    ax2.tick_params(axis="y", labelcolor=color_press)

    # Wind speed in the background
    color_wind = "#2ecc71"
    ax1.fill_between(df_weather.index, df_weather["wind"], alpha=0.15, color=color_wind, label="Wind (km/h)")

    # Wind direction
    wind_sample = df_weather.iloc[::6].copy()  # every 6 hours an arrow
    wind_rad = np.deg2rad(wind_sample["wind_direction"])

    # Must rotate the arrows by 180°
    u = np.sin(wind_rad + np.pi)
    v = np.cos(wind_rad + np.pi)

    y_min, y_max = ax1.get_ylim()
    arrow_y = y_min + 0.08 * (y_max - y_min)

    ax1.quiver(
        wind_sample.index,
        [arrow_y] * len(wind_sample),
        u,
        v,
        angles="uv",
        scale_units="xy",
        scale=7,
        width=0.002,
        color=color_wind,
        alpha=0.8,
    )

    # Entry in legend for wind direction
    wind_direction_handle = Line2D(
        [],
        [],
        color=color_wind,
        marker=r"$\rightarrow$",
        linestyle="None",
        markersize=14,
        label="Windrichtung"
    )

    # Combine legends of upper plots
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(
        lines1 + lines2 + [wind_direction_handle],
        labels1 + labels2 + ["Windrichtung"],
        loc="upper left"
    )
    ax1.set_title(
        f"Wetter am Fangort ({latitude:.5f}, {longitude:.5f})",
        fontsize=11,
        loc="left",
        pad=10
    )

    # --- DIAGRAM 2: RAIN & CLOUD COVER ---
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
        color="gold",
        alpha=0.18,
        zorder=3
    )

    if plot_start <= forecast_start <= plot_end:
        ax_rain.axvspan(
            forecast_start,
            plot_end,
            color="gray",
            alpha=0.12,
            hatch="//",
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

    # --- DIAGRAM 3: WATER LEVEL ---
    color_pegel = "#2980b9"
    ax3.plot(
        df_water_level.index, df_water_level["water_level"],
        color=color_pegel,
        linewidth=2.5,
        label=f"Pegel {station_display_name} (cm)"
    )
    ax3.set_ylabel("Wasserstand (cm)", color=color_pegel, fontweight="bold")
    ax3.tick_params(axis="y", labelcolor=color_pegel)
    ax3.grid(True, linestyle=":", alpha=0.6)

    ax3.axvspan(
        catchtime_start,
        catchtime_ende,
        color="gold",
        alpha=0.18
    )

    if plot_start <= forecast_start <= plot_end:
        ax3.axvspan(
            forecast_start,
            plot_end,
            color="gray",
            alpha=0.12,
            hatch="//"
        )

    ax3.set_title(
        f"{water}-Pegel {station_display_name}",
        fontsize=11,
        loc="left",
        pad=10
    )
    ax3.legend(loc="upper left")

    ax3.set_xlabel("Datum / Uhrzeit", fontweight="bold", labelpad=10)
    ax3.set_xlim(plot_start, plot_end)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.\n%H:%M"))
    ax3.xaxis.set_major_locator(mdates.HourLocator(interval=12))  # Alle 12 Stunden ein Marker
    plt.xticks(rotation=0)

    fig.subplots_adjust(
        left=0.08,
        right=0.92,
        bottom=0.10,
        top=0.90,
        hspace=0.25
    )

    if report_location:
        if not os.path.exists(report_location):
            os.makedirs(report_location)

        pdf_path = f"{report_location}/fang_report_{date}_{station_display_name.lower().replace(" ", "_")}.pdf"
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

    else:
        print("Kein Speicherort gegeben. PDF kann nicht erstellt werden.")


def create_pdf_report(
    pdf_path,
    plot_figure,
    report_data,
    summary_items,
    photo_path=None,
    notes=""
):
    """
    Generates a PDF report that includes details about a fishing catch, summary items,
    a sketch section, and a photo section. This function uses matplotlib to render
    various components of the report, such as headers, cards, notes, and images.

    :param pdf_path: The file path where the output PDF report will be saved.
    :type pdf_path: str
    :param plot_figure: An existing matplotlib figure that will be included in the report.
    :type plot_figure: matplotlib.figure.Figure
    :param report_data: A dictionary containing details about the catch (species,
        measurements, location, date, and time) required to customize the report.
    :type report_data: dict
    :param summary_items: A list of tuples, where each tuple contains a summary label,
        corresponding value, and a color for rendering the summary cards.
    :type summary_items: list[tuple]
    :param photo_path: The file path to an optional photo that will be embedded in the
        photo section of the report. Default is None.
    :type photo_path: str, optional
    :param notes: Optional text to be included in the notes section of the report.
        Default is an empty string.
    :type notes: str, optional
    :return: None. The function generates a PDF file at the specified location.
    :rtype: None
    """

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
            f"{report_data.get("water", "")} · {report_data.get("catch_date", "")} · {report_data.get("catch_time", "")}",
            color="#dbe9f6",
            fontsize=10,
            va="center"
        )

        fish_details = []

        if report_data.get("fish_length") != "Keine Daten":
            fish_details.append(report_data["fish_length"])

        if report_data.get("fish_weight") != "Keine Daten":
            fish_details.append(report_data["fish_weight"])

        fish_measurements = " · ".join(fish_details)

        header_axis.text(
            0.97,
            0.62,
            report_data.get("species", ""),
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

        # Notes on the right
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

        # Empty space for a drawing
        sketch_axis = report_figure.add_axes((0.06, content_y, 0.42, content_height))
        sketch_axis.set_facecolor("white")
        title_obj = sketch_axis.set_title(
            f"Angelplatz ({report_data.get("catch_location", "Keine Daten")}) ↗",
            loc="left",
            fontsize=12,
            fontweight="bold",
            pad=10
        )
        title_obj.set_url(report_data.get("catch_link"))
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

        # Foto space
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
