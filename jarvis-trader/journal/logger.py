"""SQLite trade journal: every trade, its reason, and its result."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY,
  symbol TEXT, strategy TEXT,
  entry_time TEXT, exit_time TEXT,
  entry_price REAL, exit_price REAL, qty INTEGER,
  pnl REAL, fees REAL, reason TEXT, mode TEXT DEFAULT 'backtest'
)"""


class Journal:
    def __init__(self, path="journal/trades.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        self.db.commit()

    def log_backtest(self, symbol, strategy, trades):
        for t in trades:
            self.db.execute(
                "INSERT INTO trades(symbol,strategy,entry_time,exit_time,"
                "entry_price,exit_price,qty,pnl,fees,reason,mode)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,'backtest')",
                (symbol, strategy, str(t.entry_time), str(t.exit_time),
                 t.entry_price, t.exit_price, t.qty, t.pnl, t.fees, ""))
        self.db.commit()

    def summary(self, strategy=None):
        q = ("SELECT COUNT(*), ROUND(SUM(pnl),2), "
             "ROUND(AVG(CASE WHEN pnl>0 THEN 1.0 ELSE 0 END)*100,1) "
             "FROM trades WHERE mode='backtest'")
        args = ()
        if strategy:
            q += " AND strategy=?"; args = (strategy,)
        return self.db.execute(q, args).fetchone()
