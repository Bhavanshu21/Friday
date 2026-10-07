"""Backtest engine: long-only, next-bar-open execution, full costs.

ANTI-LOOKAHEAD CONTRACT
- Signals are positions held DURING bar t (computed from data <= t).
- A 0->1 flip ENTERS at bar t+1's open; a 1->0 flip EXITS at t+1's open.
- Slippage is applied adversely on both sides.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Trade:
    entry_time: object
    exit_time: object
    entry_price: float
    exit_price: float
    qty: int
    pnl: float
    fees: float


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity: pd.Series = None
    metrics: dict = field(default_factory=dict)


def intraday_fees(buy_value, sell_value):
    """
    Approximate NSE equity-intraday costs (Angel One: Rs 20/order).
    buy_value/sell_value: turnover per side for ONE order.
    """
    brokerage = 20.0 + 20.0
    stt = 0.00025 * sell_value
    exchange = 0.0000297 * (buy_value + sell_value)
    sebi = 10 / 1e7 * (buy_value + sell_value)
    stamp = 0.00002 * buy_value
    gst = 0.18 * (brokerage + exchange + sebi)
    return brokerage + stt + exchange + sebi + stamp + gst


def run(df, position, capital=100000, qty=10, slippage=0.0005,
        fee_fn=intraday_fees):
    """
    df: OHLCV with DatetimeIndex. position: 0/1 Series aligned to df.
    Returns BacktestResult.
    """
    position = position.reindex(df.index).fillna(0).astype(int)
    opens = df["open"].values
    times = df.index
    trades, equity = [], []
    cash, holding, entry_px, entry_t = capital, 0, 0.0, None

    for t in range(len(df) - 1):  # need t+1 to exist for execution
        want = int(position.iloc[t])
        if want == 1 and not holding:
            px = opens[t + 1] * (1 + slippage)
            cost = px * qty
            if cost > cash:  # can't afford: skip, stay flat
                want = 0
            else:
                holding, entry_px, entry_t = qty, px, times[t + 1]
                cash -= cost
        elif want == 0 and holding:
            px = opens[t + 1] * (1 - slippage)
            proceeds = px * holding
            buy_val, sell_val = entry_px * holding, proceeds
            fees = fee_fn(buy_val, sell_val)
            pnl = proceeds - buy_val - fees
            trades.append(Trade(entry_t, times[t + 1], entry_px, px,
                                holding, pnl, fees))
            cash += proceeds - fees
            holding = 0
        equity.append(cash + (holding * df["close"].iloc[t] if holding else 0))

    # force-close any open position at the last close (no slippage fantasy)
    if holding:
        px = df["close"].iloc[-1] * (1 - slippage)
        proceeds = px * holding
        fees = fee_fn(entry_px * holding, proceeds)
        trades.append(Trade(entry_t, times[-1], entry_px, px,
                            holding, proceeds - entry_px * holding - fees,
                            fees))
        cash += proceeds - fees

    eq = pd.Series(equity, index=times[:len(equity)])
    return BacktestResult(trades, eq, _metrics(trades, eq, capital))


def _metrics(trades, equity, capital):
    n = len(trades)
    pnls = np.array([t.pnl for t in trades]) if n else np.array([0.0])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    net = float(pnls.sum())
    peak = equity.cummax()
    dd = ((equity - peak) / peak).min() if len(equity) else 0.0
    # Sharpe on daily bars, annualised
    daily = equity.resample("1D").last().pct_change().dropna()
    sharpe = (float(daily.mean() / daily.std() * np.sqrt(252))
              if len(daily) > 1 and daily.std() > 0 else 0.0)
    return {
        "net_pnl": round(net, 2),
        "return_pct": round(net / capital * 100, 2),
        "n_trades": n,
        "win_rate_pct": round(len(wins) / n * 100, 1) if n else 0.0,
        "avg_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
        "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0.0,
        "profit_factor": round(float(-wins.sum() / losses.sum()), 2)
        if losses.sum() < 0 else float("inf") if wins.sum() > 0 else 0.0,
        "max_drawdown_pct": round(float(dd * 100), 2),
        "sharpe": round(sharpe, 2),
    }
