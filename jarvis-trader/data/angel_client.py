"""Angel One SmartAPI client: login (TOTP), candles, instrument lookup.

Credentials come from environment (.env): ANGEL_API_KEY, ANGEL_CLIENT_CODE,
ANGEL_PASSWORD, ANGEL_TOTP_SECRET.
"""
import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

INSTRUMENT_URL = ("https://margincalculator.angelone.in/OpenAPI_File/files/"
                  "OpenAPIScripMaster.json")
CACHE_FILE = Path(__file__).resolve().parent / ".scrip_master.json"


class AngelClient:
    def __init__(self, api_key=None, client_code=None, password=None,
                 totp_secret=None):
        self.api_key = api_key or os.environ["ANGEL_API_KEY"]
        self.client_code = client_code or os.environ["ANGEL_CLIENT_CODE"]
        self.password = password or os.environ["ANGEL_PASSWORD"]
        self.totp_secret = totp_secret or os.environ["ANGEL_TOTP_SECRET"]
        self._api = None

    # ---------------------------------------------------------------- login
    def login(self):
        """Returns True on success. Raises on failure."""
        from SmartApi import SmartConnect
        import pyotp
        api = SmartConnect(api_key=self.api_key)
        totp = pyotp.TOTP(self.totp_secret).now()
        resp = api.generateSession(self.client_code, self.password, totp)
        if not resp.get("status"):
            raise RuntimeError(f"Angel login failed: {resp.get('message')}")
        self._api = api
        return True

    def _ensure(self):
        if self._api is None:
            self.login()

    # ------------------------------------------------------------ candles
    def candles(self, symboltoken, exchange, interval, fromdate, todate):
        """
        One chunk of candles. fromdate/todate: "YYYY-MM-DD HH:MM".
        Returns a DataFrame indexed by timestamp (IST-naive).
        """
        self._ensure()
        params = {"exchange": exchange, "symboltoken": str(symboltoken),
                  "interval": interval,
                  "fromdate": fromdate, "todate": todate}
        resp = self._api.getCandleData(params)
        rows = resp.get("data") or []
        if not rows:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"])
        df = pd.DataFrame(rows,
                          columns=["timestamp", "open", "high", "low",
                                   "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.set_index("timestamp").sort_index()

    # ------------------------------------------------------- instrument map
    def _load_master(self, max_age_days=1):
        if (CACHE_FILE.exists() and
                time.time() - CACHE_FILE.stat().st_mtime
                < max_age_days * 86400):
            return json.loads(CACHE_FILE.read_text())
        r = requests.get(INSTRUMENT_URL, timeout=120)
        r.raise_for_status()
        data = r.json()
        CACHE_FILE.write_text(json.dumps(data))
        return data

    def token_for(self, symbol, exchange="NSE"):
        """Trading symbol -> symboltoken (e.g. RELIANCE -> 2885)."""
        for row in self._load_master():
            if (row.get("exch_seg") == exchange
                    and row.get("symbol", "").rstrip(" -EQ") == symbol
                    and row.get("instrumenttype") == ""):
                return str(row["token"])
        # fallback: first NSE match on symbol prefix
        for row in self._load_master():
            if (row.get("exch_seg") == exchange
                    and row.get("symbol", "").startswith(symbol)):
                return str(row["token"])
        raise KeyError(f"No token found for {symbol} on {exchange}")
