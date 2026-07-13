from datetime import datetime
import json
from pathlib import Path

import pandas as pd
import requests


class AipoClient:
    """
    Client for accessing measurement data from the AIPo / Agenzia Interregionale Po platform.

    ## Authentication

    The AIPo web application uses OAuth2/OpenID Connect with access and
    refresh tokens. The required authentication credentials are stored by
    the website in the browser's local storage:

    ```
    Aegis/refreshToken
    Aegis/clientInstance
    ```

    These values must be copied from the browser once. The client
    then uses the refresh token to automatically obtain new access tokens
    via the endpoint

    ```
    https://idrometri.agenziapo.it/datascapeA/connect/token
    ```

    The platform uses refresh token rotation. Therefore, a new refresh token
    is returned after every successful token refresh. The client should
    persistently store this token and use it for future requests.

    ## Usage

    ```
    client = AipoClient.from_file("aipo_auth.json")

    df = client.load_sensor_values(
        element_id=43395,
        start=start_datetime,
        end=end_datetime,
    )
    ```

    The `load_sensor_values()` method returns a pandas.DataFrame with the
    following columns:

    ```
    time           Timestamp of the measurement
    water_level    Measured sensor value
    ```

    ## Measurement Data

    Measurement values are retrieved via the endpoint

    ```
    /datascapeA/v3/data-combo/{element_id}
    ```

    The API delivers the time series in the `plausibleData` field as a list of

    ```
    [epoch_timestamp_ms, water_level]
    ```

    which is automatically converted into a DataFrame by the client.

    ## Notes

    * Access tokens expire after a limited time (currently 86,400 seconds).
    * Renewal happens automatically using the refresh token.
    * The current refresh token should be persistently saved after every successful refresh.
    * When not used for some time, the refresh token also expires and a new one must be copied from the browser.
    * The `clientInstance` is typically stable over the long term and normally does not need to be updated.
"""


    def __init__(self, refresh_token: str, client_instance: str):
        self.refresh_token = refresh_token
        self.client_instance = client_instance


    @classmethod
    def from_file(cls, filename: str | Path) -> "AipoClient":
        """
        Creates a client from a JSON-Datei.

        Expected format:

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
        Provides access_token
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

        # Save tokens
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
        Loads AIPo-measurements and returns a DataFrame
        with columns 'time' and 'water_level'.
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
                    "Der AIPo refresh token ist nicht mehr gültig. "
                    "Bitte erneuern Sie ihn über den Browser."
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

        # Want water level in cm
        df["water_level"] = df["water_level"] * 100

        df = df.drop(columns=["EpochTime"])
        df = df.set_index("time")

        df = df.sort_index()

        return df
