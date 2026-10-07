"""Technical indicators, pandas-only (no TA-Lib install pain).

Every function is causal: value at bar t uses only data up to bar t.
"""
import pandas as pd


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, min_periods=n, adjust=False).mean()


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)


def atr(high, low, close, n=14):
    prev_close = close.shift(1)
    tr = pd.concat([high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()


def macd(close, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, min_periods=signal, adjust=False).mean()
    return line, sig, line - sig


def bollinger(close, n=20, k=2):
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std()
    return mid, mid + k * sd, mid - k * sd


def donchian_high(high, n=20):
    return high.rolling(n, min_periods=n).max()


def donchian_low(low, n=20):
    return low.rolling(n, min_periods=n).min()
