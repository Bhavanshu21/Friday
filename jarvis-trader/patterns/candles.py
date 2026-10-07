"""Candlestick patterns as boolean Series. All use only past bars.

Conventions: body = |close-open|; upper_wick = high-max(open,close);
lower_wick = min(open,close)-low. Thresholds are fractions of the full range.
"""
import pandas as pd

_EPS = 1e-9


def _parts(df):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = (c - o).abs()
    rng = (h - l).replace(0, _EPS)
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    return body, rng, upper, lower


def bullish_engulfing(df):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    prev_red = pc < po
    return (prev_red & (c > o) & (c >= po) & (o <= pc)
            & ((c - o) > (po - pc) * 0.8))


def bearish_engulfing(df):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    prev_green = pc > po
    return (prev_green & (c < o) & (c <= po) & (o >= pc)
            & ((o - c) > (pc - po) * 0.8))


def hammer(df, wick_ratio=2.0, body_max=0.35):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body, rng, upper, lower = _parts(df)
    return ((lower >= wick_ratio * body) & (upper <= body)
            & (body / rng <= body_max))


def shooting_star(df, wick_ratio=2.0, body_max=0.35):
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body, rng, upper, lower = _parts(df)
    return ((upper >= wick_ratio * body) & (lower <= body)
            & (body / rng <= body_max))


def doji(df, body_max=0.1):
    body, rng, _, _ = _parts(df)
    return body / rng <= body_max
