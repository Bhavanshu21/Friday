"""Market structure: swings, support/resistance, breakouts. All causal."""
import numpy as np
import pandas as pd

from .indicators import donchian_high, donchian_low


def swing_high(high, order=5):
    """True where bar is the highest of [t-order, t+order].

    NOTE: uses order bars of *future* data — for live signals, the swing is
    only confirmed `order` bars later. Never trade the unconfirmed swing."""
    return high == high.rolling(2 * order + 1, center=True,
                                min_periods=1).max()


def swing_low(low, order=5):
    return low == low.rolling(2 * order + 1, center=True,
                              min_periods=1).min()


def support_resistance(df, lookback=120, order=5, tol_pct=0.003):
    """
    Cluster recent swing levels into zones. Returns (supports, resistances)
    as lists of prices, using only data up to each bar's close — call it on
    df.iloc[:i] in walk-forward use, not on the full frame.
    """
    win = df.iloc[-lookback:]
    highs = win["high"][swing_high(win["high"], order)]
    lows = win["low"][swing_low(win["low"], order)]
    levels = sorted(set(highs.tolist() + lows.tolist()))
    zones, cur = [], []
    for lv in levels:
        if cur and abs(lv - cur[-1]) / cur[-1] > tol_pct:
            zones.append(sum(cur) / len(cur))
            cur = []
        cur.append(lv)
    if cur:
        zones.append(sum(cur) / len(cur))
    last = df["close"].iloc[-1]
    return [z for z in zones if z < last], [z for z in zones if z > last]


def donchian_breakout(df, n=20):
    """True on a close above the prior n-bar high (causal: shifted)."""
    return df["close"] > donchian_high(df["high"], n).shift(1)


def donchian_breakdown(df, n=20):
    return df["close"] < donchian_low(df["low"], n).shift(1)
