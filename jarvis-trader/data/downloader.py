"""Chunked historical downloader: 15-min candles -> Parquet.

Angel's candle API caps how much comes back per call, so long histories
are fetched in 60-day chunks and concatenated.
"""
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from .angel_client import AngelClient

CHUNK_DAYS = 60


def download(symbol, interval, start, end, outdir="data/parquet",
             exchange="NSE", client=None):
    """
    start/end: "YYYY-MM-DD". Returns the Path of the written Parquet file.
    """
    client = client or AngelClient()
    token = client.token_for(symbol, exchange)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)

    chunks = []
    cur = start_dt
    while cur < end_dt:
        nxt = min(cur + timedelta(days=CHUNK_DAYS), end_dt)
        df = client.candles(
            token, exchange, interval,
            cur.strftime("%Y-%m-%d %H:%M"), nxt.strftime("%Y-%m-%d %H:%M"))
        if not df.empty:
            chunks.append(df)
        print(f"  {cur.date()} -> {nxt.date()}: {len(df)} candles")
        cur = nxt

    if not chunks:
        raise RuntimeError(f"No data returned for {symbol}")
    full = pd.concat(chunks)
    full = full[~full.index.duplicated(keep="first")].sort_index()

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tag = {"FIFTEEN_MINUTE": "15m", "ONE_DAY": "1d",
           "ONE_HOUR": "1h"}.get(interval, interval.lower())
    path = outdir / f"{symbol}_{tag}.parquet"
    full.to_parquet(path)
    print(f"wrote {len(full)} candles -> {path}")
    return path
