"""Risk manager: position sizing + hard guards.

The user sets every limit in config/risk.yaml. Breach = halt, never a
silent resize. Nothing here invents limits on its own.
"""
import yaml
from pathlib import Path


def load_risk(path="config/risk.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def position_size(capital, risk_pct, entry, stop):
    """Shares such that a stop-out loses risk_pct of capital."""
    risk_amt = capital * risk_pct / 100
    per_share = abs(entry - stop)
    if per_share <= 0:
        return 0
    return int(risk_amt // per_share)


def within_trading_hours(ts, start="09:20", end="15:15"):
    t = ts.time()
    lo = (int(start[:2]), int(start[3:]))
    hi = (int(end[:2]), int(end[3:]))
    return lo <= (t.hour, t.minute) <= hi


class DailyGuard:
    """Halt for the day once the daily loss cap is breached."""

    def __init__(self, max_daily_loss_pct=2.0):
        self.cap = max_daily_loss_pct
        self.day_start_equity = None
        self._day = None
        self.halted = False

    def update(self, equity, day):
        if self.day_start_equity is None or self._day != day:
            self._day, self.day_start_equity, self.halted = day, equity, False
        dd = (equity - self.day_start_equity) / self.day_start_equity * 100
        if dd <= -self.cap:
            self.halted = True
        return self.halted
