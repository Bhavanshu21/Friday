"""CLI: download | backtest | walkforward."""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))


def load_settings():
    with open("config/settings.yaml") as f:
        return yaml.safe_load(f)


def synthetic_ohlcv(n=5000, seed=7):
    """Random-walk 15-min bars. No edge by construction — a strategy that
    'wins' here is curve-fit or has lookahead."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.004, n)
    close = 100 * np.exp(np.cumsum(rets))
    idx = pd.date_range("2024-01-01 09:15", periods=n, freq="15min")
    df = pd.DataFrame(index=idx)
    df["close"] = close
    df["open"] = np.concatenate([[100], close[:-1]])
    spread = np.abs(rng.normal(0, 0.003, n))
    df["high"] = np.maximum(df["open"], df["close"]) * (1 + spread)
    df["low"] = np.minimum(df["open"], df["close"]) * (1 - spread)
    df["volume"] = rng.integers(1000, 100000, n)
    return df[["open", "high", "low", "close", "volume"]]


def cmd_download(a):
    from data.downloader import download
    from dotenv import load_dotenv  # optional
    try:
        import dotenv
        dotenv.load_dotenv()
    except ImportError:
        pass
    download(a.symbol, a.interval, a.from_, a.to)


def _load_df(a, cfg):
    if a.synthetic:
        print("using synthetic random-walk data (no edge by construction)")
        return synthetic_ohlcv()
    if a.file:
        print(f"loading {a.file}")
        return pd.read_parquet(a.file)
    from pathlib import Path as P
    tag = {"FIFTEEN_MINUTE": "15m"}.get(cfg["interval"], "15m")
    p = P(cfg["data_dir"]) / f"{a.symbol}_{tag}.parquet"
    print(f"loading {p}")
    return pd.read_parquet(p)


def cmd_backtest(a):
    from strategy.rules import STRATEGIES
    from backtest.engine import run
    cfg = load_settings()
    df = _load_df(a, cfg)
    fn = STRATEGIES[a.strategy]
    pos = fn(df)
    res = run(df, pos, capital=cfg["starting_capital"],
              qty=cfg["qty_per_trade"], slippage=cfg["slippage"])
    print(f"\n{a.strategy} on {len(df)} bars, {res.metrics['n_trades']} trades")
    for k, v in res.metrics.items():
        print(f"  {k:18s} {v}")
    if a.journal:
        from journal.logger import Journal
        Journal().log_backtest(a.symbol or "SYNTH", a.strategy, res.trades)
        print("  logged to journal/trades.db")


def cmd_walkforward(a):
    from strategy.rules import STRATEGIES
    from backtest.walkforward import walkforward
    cfg = load_settings()
    df = _load_df(a, cfg)
    out = walkforward(df, STRATEGIES[a.strategy],
                      capital=cfg["starting_capital"],
                      qty=cfg["qty_per_trade"], slippage=cfg["slippage"])
    print(f"\n{a.strategy}: {out['oos'].get('n_windows', 0)} OOS windows")
    for w in out["windows"]:
        print(f"  {w['test']}: {w['return_pct']}%  sharpe {w['sharpe']}")
    print("aggregate OOS:", out["oos"])


def main():
    ap = argparse.ArgumentParser(description="jarvis-trader")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("download")
    d.add_argument("--symbol", required=True)
    d.add_argument("--interval", default="FIFTEEN_MINUTE")
    d.add_argument("--from", dest="from_", required=True)
    d.add_argument("--to", required=True)

    b = sub.add_parser("backtest")
    b.add_argument("--strategy", required=True,
                   choices=["engulfing_rsi", "donchian_breakout"])
    b.add_argument("--symbol", default=None)
    b.add_argument("--file", default=None)
    b.add_argument("--synthetic", action="store_true")
    b.add_argument("--journal", action="store_true")

    w = sub.add_parser("walkforward")
    w.add_argument("--strategy", required=True,
                   choices=["engulfing_rsi", "donchian_breakout"])
    w.add_argument("--symbol", default=None)
    w.add_argument("--file", default=None)
    w.add_argument("--synthetic", action="store_true")

    a = ap.parse_args()
    {"download": cmd_download, "backtest": cmd_backtest,
     "walkforward": cmd_walkforward}[a.cmd](a)


if __name__ == "__main__":
    main()
