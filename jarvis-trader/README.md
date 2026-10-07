# jarvis-trader — FRIDAY's autonomous trading system (Phase 0+1)

Data → patterns → backtest. No live orders in this phase.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your Angel One SmartAPI credentials
```

Angel One: create the app at smartapi.angelone.in → get API key, enable TOTP.

## Use

```bash
# 1. Download 15-min candles (needs .env)
python main.py download --symbol RELIANCE --from 2024-01-01 --to 2024-12-31

# 2. Backtest a strategy on the file
python main.py backtest --file data/parquet/RELIANCE_15m.parquet --strategy engulfing_rsi

# 3. No credentials? Synthetic random-walk demo
python main.py backtest --synthetic --strategy donchian_breakout

# 4. Walk-forward validation (out-of-sample honesty check)
python main.py walkforward --file data/parquet/RELIANCE_15m.parquet --strategy engulfing_rsi
```

## Layout

- `data/` — Angel One client (login + TOTP), chunked candle downloader
- `patterns/` — indicators (pandas-only), candlestick patterns, market structure
- `strategy/` — rule-based strategies (emit 0/1 positions)
- `backtest/` — engine (fees + slippage, next-bar execution, no lookahead)
- `risk/` — position sizing, daily loss guard
- `journal/` — SQLite trade log
- `execution/` — Phase 3+ (paper/live broker stubs)

## Standing rules

- Signals execute at the NEXT bar's open. Never the signal bar. No lookahead, ever.
- Every backtest includes brokerage + taxes + slippage.
- Walk-forward before trusting any result.
