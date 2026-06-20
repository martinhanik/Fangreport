import typer
from datetime import datetime
from fangreport.core import generate_catch_report

app = typer.Typer()

"""
Client zum Erstellen eines Fangreports über die Konsole.
"""

@app.command()
def main(
    date: str = typer.Option(
        None,
        "--Datum",
        help="Datum des Fangs (YYYY-MM-DD)"
    ),
    catch_time: str = typer.Option(
        None,
        "--Zeit",
        help="Zeitpunkt des Fangs (HH:MM)"
    ),
    species: str = typer.Option(
        "Wels",
        "--Fischart",
        help="Gefangene Fischart (z. B. 'Hecht', 'Wels', 'Zander')"
    ),
    station: str = typer.Option(
        None,
        "--Pegelstation",
        help="Pegelmessstation verfügbar in pegelonline.wsv.de"
    ),
    longitude: float = typer.Option(
        None,
        "--Längengrad",
        help="Längengrad des Fangorts (-90 <= Längengrad <= 90)"
    ),
    latitude: float = typer.Option(
        None,
        "--Breitengrad",
        help="Breitengrad des Fangorts (-180 <= Breitengrad <= 180)"
    ),
    fish_length: int = typer.Option(
        None,
        "--Länge",
        help="Länge des Fangs in Zentimetern"
    ),
    fish_weight: float = typer.Option(
        None,
        "--Gewicht",
        help="Gewicht des Fangs in Kilogramm"
    ),
    water_temperature: float = typer.Option(
        None,
        "--Wassertemperatur",
        help=(
            "Wassertemperatur in Grad Celsius. "
            "Wenn nicht angegeben, wird versucht, sie über PEGELONLINE abzurufen."
        )
    ),
    water_clarity: str = typer.Option(
        "Keine Daten",
        "--Trübung",
        help="Beschreibung der Trübung, z. B. 'klar' oder 'leicht eingetrübt'"
    ),
    photo_path: str = typer.Option(
        None,
        "--Fotopfad",
        help="Speicherort des Fangfotos"
    ),
    notes: str = typer.Option(
        "",
        "--Notizen",
        help="Notizen für den Fangreport"
    ),
):
    try:
        if datetime.now() < datetime(int(date[:4]), int(date[5:7]), int(date[8:]), int(catch_time[:2]),
                                     int(catch_time[3:5])):
            raise ValueError(
                f"Das Fangdatum liegt in der Zukunft."
            )
        if not -90 <= latitude <= 90:
            raise ValueError(
                f"Ungültiger Breitengrad: {latitude}. Erwartet wird ein Wert zwischen -90 und 90."
            )

        if not -180 <= longitude <= 180:
            raise ValueError(
                f"Ungültiger Längengrad: {longitude}. Erwartet wird ein Wert zwischen -180 und 180."
            )

        generate_catch_report(
            date,
            catch_time,
            station,
            latitude,
            longitude,
            water_temperature,
            species,
            fish_length,
            fish_weight,
            water_clarity,
            photo_path,
            notes
        )
    except ValueError as e:
        print(f"❌ Eingabefehler: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    app()