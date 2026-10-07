"""Supervised model: learn which setups actually work.

Label (tradable): 1 if price rises >= target_pct within `horizon` bars.
Features: causal (strategy/features.py). Validation: walk-forward — train
on the past, test on the future. A model is PROMOTED only if its
out-of-sample precision and net P&L (after costs) beat the baseline.

This is Phase 2. It does not place orders.
"""
import numpy as np
import pandas as pd

from backtest.walkforward import windows
from strategy.features import make_features, FEATURE_COLS

TARGET_PCT = 0.015
STOP_PCT = 0.010
HORIZON = 10
PROBA_THRESHOLD = 0.60
MIN_PRECISION = 0.55


def make_labels(df, target_pct=TARGET_PCT, stop_pct=STOP_PCT,
                horizon=HORIZON):
    """
    1 if +target_pct is touched BEFORE -stop_pct within `horizon` bars.
    The label IS the trade outcome: precision = trade win rate.
    A bar touching both counts as a loss (conservative).
    """
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)
    labels = np.zeros(n, dtype=int)
    for t in range(n - horizon):
        tgt, stp = closes[t] * (1 + target_pct), closes[t] * (1 - stop_pct)
        for j in range(t + 1, t + 1 + horizon):
            hit_stop, hit_tgt = lows[j] <= stp, highs[j] >= tgt
            if hit_stop:      # stop first, or both: loss
                break
            if hit_tgt:
                labels[t] = 1
                break
    return pd.Series(labels, index=df.index)


def build_dataset(df, target_pct=TARGET_PCT, horizon=HORIZON):
    X = make_features(df)
    y = make_labels(df, target_pct, horizon)
    data = pd.concat([X, y.rename("label")], axis=1).dropna()
    return data[FEATURE_COLS], data["label"]


def train_model(X_train, y_train, X_val=None, y_val=None):
    import xgboost as xgb
    neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
    clf = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=neg / max(1, pos),
        eval_metric="logloss", tree_method="hist", random_state=7,
        n_jobs=-1,
    )
    if X_val is not None and len(X_val) > 50:
        clf.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    else:
        clf.fit(X_train, y_train, verbose=False)
    return clf


def simulate_trades(df, signals, qty=100, capital=500000, slippage=0.0005,
                    target_pct=TARGET_PCT, stop_pct=STOP_PCT,
                    max_hold=HORIZON):
    """
    Trade a binary signal like the label promises: enter at the next open,
    exit at +target, -stop, or max_hold bars — whichever comes first.
    Intrabar: if a bar hits both stop and target, the stop is assumed
    (conservative). Returns a list of dicts with pnl/fees.
    """
    from backtest.engine import intraday_fees
    trades = []
    idx = df.index
    opens, highs, lows = df["open"].values, df["high"].values, df["low"].values
    sig = signals.reindex(idx).fillna(False).values
    i, cash = 0, capital
    n = len(df)
    while i < n - 1:
        if not sig[i]:
            i += 1
            continue
        entry_px = opens[i + 1] * (1 + slippage)
        if entry_px * qty > cash:
            i += 1
            continue
        tgt, stp = entry_px * (1 + target_pct), entry_px * (1 - stop_pct)
        exit_px, j = None, i + 1
        last = min(i + 1 + max_hold, n - 1)
        while j <= last:
            hit_stop, hit_tgt = lows[j] <= stp, highs[j] >= tgt
            if hit_stop:  # stop first when both hit: conservative
                exit_px = stp * (1 - slippage)
                break
            if hit_tgt:
                exit_px = tgt * (1 - slippage)
                break
            j += 1
        if exit_px is None:  # time stop at the open
            j = last
            exit_px = opens[j] * (1 - slippage)
        fees = intraday_fees(entry_px * qty, exit_px * qty)
        pnl = (exit_px - entry_px) * qty - fees
        cash += pnl
        trades.append({"entry": idx[i + 1], "exit": idx[j], "pnl": pnl,
                       "fees": fees})
        i = j + 1  # no overlapping positions
    return trades


def evaluate_window(df_test, clf, threshold=PROBA_THRESHOLD, **engine_kw):
    """Signals -> target/stop simulator. Returns precision/recall/P&L."""
    Xte, yte = build_dataset(df_test)
    if len(Xte) < 50:
        return None
    proba = clf.predict_proba(Xte)[:, 1]
    pred = (proba >= threshold).astype(int)
    tp = int(((pred == 1) & (yte == 1)).sum())
    fp = int(((pred == 1) & (yte == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / int((yte == 1).sum()) if (yte == 1).sum() else 0.0
    sub = df_test.loc[Xte.index]
    signals = pd.Series(pred.astype(bool), index=Xte.index)
    trades = simulate_trades(sub, signals, **engine_kw)
    net = sum(t["pnl"] for t in trades)
    return {"n_signals": int(pred.sum()), "precision": round(precision, 3),
            "recall": round(recall, 3), "net_pnl": round(net, 2),
            "n_trades": len(trades)}


def walkforward_ml(df, train_days=180, test_days=60, step_days=60,
                   **engine_kw):
    """Train on each train window, evaluate on the following test window."""
    results = []
    for tr_s, tr_e, te_s, te_e in windows(df.index, train_days, test_days,
                                         step_days):
        train = df[(df.index >= tr_s) & (df.index < tr_e)]
        test = df[(df.index >= te_s) & (df.index < te_e)]
        if len(train) < 1000 or len(test) < 200:
            continue
        Xtr, ytr = build_dataset(train)
        if len(Xtr) < 500 or ytr.sum() < 20:
            continue
        cut = int(len(Xtr) * 0.8)  # time-ordered validation split
        clf = train_model(Xtr.iloc[:cut], ytr.iloc[:cut],
                          Xtr.iloc[cut:], ytr.iloc[cut:])
        ev = evaluate_window(test, clf, **engine_kw)
        if ev:
            ev["test"] = f"{te_s.date()}->{te_e.date()}"
            results.append(ev)
            print(f"  {ev['test']}: prec {ev['precision']} "
                  f"rec {ev['recall']} pnl {ev['net_pnl']}")
    return results


def verdict(results):
    """Promote only on out-of-sample evidence."""
    if not results:
        return {"promote": False, "reason": "no test windows"}
    prec = np.mean([r["precision"] for r in results])
    pnl = sum(r["net_pnl"] for r in results)
    wins = sum(1 for r in results if r["net_pnl"] > 0)
    ok = prec >= MIN_PRECISION and pnl > 0
    return {"promote": bool(ok),
            "mean_precision": round(float(prec), 3),
            "total_pnl": round(float(pnl), 2),
            "profitable_windows": f"{wins}/{len(results)}",
            "reason": ("OOS precision and P&L clear the bar" if ok
                       else "does not beat the bar on unseen data")}
