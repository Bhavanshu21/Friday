"""Walk-forward validation: train on the past, test on the future, roll on.

For rule-based strategies there is nothing to fit — the point is to check
the rules hold on data they never saw. Each test window is strictly AFTER
its train window. Aggregate the OUT-OF-SAMPLE windows only.
"""
import pandas as pd

from .engine import run


def windows(index, train_days=180, test_days=60, step_days=60):
    """Yield (train_start, train_end, test_start, test_end) datetimes."""
    start, end = index[0], index[-1]
    t0 = start
    while True:
        tr_s, tr_e = t0, t0 + pd.Timedelta(days=train_days)
        te_s, te_e = tr_e, tr_e + pd.Timedelta(days=test_days)
        if te_e > end:
            break
        yield tr_s, tr_e, te_s, te_e
        t0 += pd.Timedelta(days=step_days)


def walkforward(df, signal_fn, train_days=180, test_days=60, step_days=60,
                **engine_kw):
    """
    signal_fn(df_slice) -> 0/1 position Series. Returns dict with per-window
    metrics plus the aggregated out-of-sample metrics.
    """
    results = []
    for tr_s, tr_e, te_s, te_e in windows(df.index, train_days, test_days,
                                         step_days):
        test = df[(df.index >= te_s) & (df.index < te_e)]
        if len(test) < 50:
            continue
        pos = signal_fn(test)
        res = run(test, pos, **engine_kw)
        results.append({"train": f"{tr_s.date()}->{tr_e.date()}",
                        "test": f"{te_s.date()}->{te_e.date()}",
                        **res.metrics})
    if not results:
        return {"windows": [], "oos": {}}
    oos = pd.DataFrame(results)
    agg = {"n_windows": len(results),
           "mean_return_pct": round(oos["return_pct"].mean(), 2),
           "median_return_pct": round(oos["return_pct"].median(), 2),
           "positive_windows_pct": round((oos["return_pct"] > 0).mean() * 100, 1),
           "mean_sharpe": round(oos["sharpe"].mean(), 2),
           "worst_window_pct": round(oos["return_pct"].min(), 2)}
    return {"windows": results, "oos": agg}
