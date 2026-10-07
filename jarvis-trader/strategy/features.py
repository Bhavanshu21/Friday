"""Feature engineering for the ML model.

Every feature at bar t uses only data up to bar t (causal). NaNs from
warmup are dropped by the dataset builder, never filled forward.
"""
import pandas as pd

from patterns.candles import (bullish_engulfing, bearish_engulfing, hammer,
                              shooting_star, doji)
from patterns.indicators import rsi, atr, macd, bollinger


def make_features(df):
    close, high, low = df["close"], df["high"], df["low"]
    f = pd.DataFrame(index=df.index)
    # momentum
    f["ret_1"] = close.pct_change(1)
    f["ret_5"] = close.pct_change(5)
    f["ret_20"] = close.pct_change(20)
    # oscillators / volatility
    f["rsi_14"] = rsi(close)
    _atr = atr(high, low, close)
    f["atr_pct"] = _atr / close
    _, _, m_hist = macd(close)
    f["macd_hist"] = m_hist / close
    mid, upper, lower = bollinger(close)
    f["bb_pos"] = (close - lower) / (upper - lower).replace(0, float("nan"))
    # structure (shifted: breakout levels use prior bars only)
    f["dist_don_high"] = (close - high.rolling(20).max().shift(1)) / close
    f["dist_don_low"] = (close - low.rolling(20).min().shift(1)) / close
    # volume
    vol_ma = df["volume"].rolling(20).mean()
    vol_sd = df["volume"].rolling(20).std().replace(0, float("nan"))
    f["vol_z"] = (df["volume"] - vol_ma) / vol_sd
    # candle patterns as flags
    f["bull_engulf"] = bullish_engulfing(df).astype(int)
    f["bear_engulf"] = bearish_engulfing(df).astype(int)
    f["hammer"] = hammer(df).astype(int)
    f["star"] = shooting_star(df).astype(int)
    f["doji"] = doji(df).astype(int)
    return f


FEATURE_COLS = ["ret_1", "ret_5", "ret_20", "rsi_14", "atr_pct", "macd_hist",
                "bb_pos", "dist_don_high", "dist_don_low", "vol_z",
                "bull_engulf", "bear_engulf", "hammer", "star", "doji"]
