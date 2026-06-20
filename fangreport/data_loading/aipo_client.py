from datetime import datetime
import json
from pathlib import Path

import pandas as pd
import requests


class AipoClient:
    """
    Client für den Zugriff auf Messdaten der AIPo-/Agenzia-Interregionale-Po-Plattform.

    ## Authentifizierung

    Die AIPo-Webanwendung verwendet OAuth2/OpenID Connect mit Access- und
    Refresh-Tokens. Die benötigten Authentifizierungsinformationen werden von
    der Webseite im Browser-Local-Storage abgelegt:

    ```
    Aegis/refreshToken
    Aegis/clientInstance
    ```

    Diese Werte müssen einmalig aus dem Browser übernommen werden. Der Client
    verwendet anschließend den Refresh-Token, um automatisch neue Access-Tokens
    über den Endpoint

    ```
    https://idrometri.agenziapo.it/datascapeA/connect/token
    ```

    zu beziehen.

    Die Plattform verwendet Refresh-Token-Rotation. Nach jedem erfolgreichen
    Token-Refresh wird daher ein neuer Refresh-Token zurückgegeben. Der Client
    sollte diesen dauerhaft speichern und bei zukünftigen Aufrufen verwenden.

    ## Verwendung

    ```
    client = AipoClient.from_file("aipo_auth.json")

    df = client.load_sensor_values(
        element_id=43395,
        start=start_datetime,
        end=end_datetime,
    )
    ```

    Die Methode `load_sensor_values()` liefert ein pandas.DataFrame mit den
    Spalten:

    ```
    time           Zeitstempel der Messung
    water_level    Gemessener Sensorwert
    ```

    ## Messdaten

    Messwerte werden über den Endpoint

    ```
    /datascapeA/v3/data-combo/{element_id}
    ```

    abgerufen.

    Die API liefert die Zeitreihe im Feld `plausibleData` als Liste von

    ```
    [epoch_timestamp_ms, water_level]
    ```

    welche vom Client automatisch in ein DataFrame umgewandelt wird.

    ## Hinweise

    * Access-Tokens sind zeitlich begrenzt (aktuell 86400 Sekunden).
    * Die Erneuerung erfolgt automatisch über den Refresh-Token.
    * Der aktuelle Refresh-Token sollte nach jedem erfolgreichen Refresh
      persistent gespeichert werden.
    * Die `clientInstance` ist typischerweise langfristig stabil und muss
      normalerweise nicht aktualisiert werden.
      """

    def __init__(self, refresh_token: str, client_instance: str):
        self.refresh_token = refresh_token
        self.client_instance = client_instance


    @classmethod
    def from_file(cls, filename: str | Path) -> "AipoClient":
        """
        Erstellt einen Client aus einer JSON-Datei.

        Erwartetes Format:

        {
            "refresh_token": "...",
            "client_instance": "..."
        }
        """

        with open(filename, encoding="utf-8") as f:
            auth = json.load(f)

        return cls(
            refresh_token=auth["refresh_token"],
            client_instance=auth["client_instance"],
        )


    def refresh_access_token(self) -> dict:
        """
        Liefert access_token
        """

        url = "https://idrometri.agenziapo.it/datascapeA/connect/token"

        payload = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "client_id": "Aegis",
            "client_instance": self.client_instance,
        }

        r = requests.post(
            url,
            data=payload,
            verify=True,
            timeout=30,
        )

        r.raise_for_status()

        r = r.json()
        self.refresh_token = r["refresh_token"]

        # Speichern des Tokens
        with open("fangreport/data/aipo_auth.json", "w") as f:
            json.dump(
                {
                    "refresh_token": self.refresh_token,
                    "client_instance": self.client_instance,
                },
                f,
            )

        return r

    def load_sensor_values(
        self,
        element_id: int,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """
        Lädt AIPo-Messwerte und gibt ein DataFrame mit den
        Spalten 'time' und 'water_level' zurück.
        """

        url = f"https://idrometri.agenziapo.it/datascapeA/v3/data-combo/{element_id}"

        params = {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "basicType": "Plausible",
            "part": ["EpochTime", "ValueWithInvalid"],
            "timing": "SmartEquispaced",
            "loadAlsoExtemp": "true",
            "ui_culture": "en",
        }

        try:
            token = self.refresh_access_token()["access_token"]
        except requests.HTTPError as e:
            if e.response is not None and "invalid_grant" in e.response.text:
                raise RuntimeError(
                    "AIPo refresh token is no longer valid. "
                    "Please update aipo_auth.json from the browser."
                ) from e
            raise

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
        }

        r = requests.get(
            url,
            params=params,
            headers=headers,
            verify=True,
            timeout=30,
        )

        r.raise_for_status()

        raw = r.json()

        if "plausibleData" not in raw:
            raise ValueError(
                f"Unerwartete Antwortstruktur: {raw.keys()}"
            )

        data = raw["plausibleData"]

        df = pd.DataFrame(
            data,
            columns=["EpochTime", "water_level"]
        )

        df["time"] = pd.to_datetime(df["EpochTime"], unit="ms", utc=True).dt.tz_convert(None)

        # wollen Pegelstand in cm
        df["water_level"] = df["water_level"] * 100

        df = df.drop(columns=["EpochTime"])
        df = df.set_index("time")

        df = df.sort_index()

        return df
