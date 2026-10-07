"""Rule-based strategies. Each returns a 0/1 position Series.

The position at bar t is the position HELD DURING bar t. The backtest
engine enters/exits at the next bar's open, so there is no lookahead.
"""
import pandas as pd

from patterns.candles import bullish_engulfing, bearish_engulfing
from patterns.indicators import rsi, atr
from patterns.structure import donchian_breakout


def entries_to_positions(entries, exits=None, max_hold=20):
    """
    entries/exits: boolean Series. Long-only: position becomes 1 on entry,
    0 on exit signal or after max_hold bars, whichever comes first.
    """
    entries = entries.fillna(False)
    exits = exits.fillna(False) if exits is not None else pd.Series(
        False, index=entries.index)
    pos = pd.Series(0, index=entries.index, dtype=int)
    holding = 0
    for i in range(len(entries)):
        if holding:
            holding += 1
            if bool(exits.iloc[i]) or holding > max_hold:
                holding = 0
        elif bool(entries.iloc[i]):
            holding = 1
        pos.iloc[i] = 1 if holding else 0
    return pos


def engulfing_rsi(df, rsi_n=14, oversold=35, max_hold=10):
    """Bullish engulfing while RSI is washed out. Exit: 10 bars or reversal."""
    sig = (bullish_engulfing(df)
           & (rsi(df["close"], rsi_n) < oversold))
    return entries_to_positions(sig, exits=bearish_engulfing(df),
                                max_hold=max_hold)


def donchian_breakout_atr(df, n=20, atr_n=14, atr_mult=1.5, max_hold=15):
    """20-bar breakout, only when the breakout bar's range is decisive
    (>= 1.5x ATR — filters chop)."""
    brk = donchian_breakout(df, n)
    decisive = (df["high"] - df["low"]) >= atr_mult * atr(
        df["high"], df["low"], df["close"], atr_n)
    return entries_to_positions(brk & decisive.fillna(False),
                                max_hold=max_hold)


STRATEGIES = {
    "engulfing_rsi": engulfing_rsi,
    "donchian_breakout": donchian_breakout_atr,
}
