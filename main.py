"""cbBTC trend bot for the make.fun BTC race (agent-fun/bars-replay/v1).

Run as: python3 -P -s /bot/main.py

Deterministic: orders are a pure function of the CBBTC bars seen so far —
no wall clock, no randomness, no environment reads.
"""

import os
import sys

# -P keeps the script's directory off sys.path; add the vendored shim next to main.py.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

FAST_SPAN = 30                 # fast EMA span
SLOW_SPAN = 180                # slow EMA span
SLOW_SLOPE_BARS = 30           # slope of the slow EMA over the last 30 bars
SLOW_SLOPE_KEEP = SLOW_SLOPE_BARS + 1  # keep the last 31 slow-EMA values
MOMENTUM_BARS = 120            # entry momentum window
MIN_BARS = 200                 # minimum CBBTC bars seen before entering
DRAWDOWN_BRAKE = 0.90          # halt if equity < 90% of peak equity
TRAIL_STOP = 0.982             # exit if close < 98.2% of peak close since entry
TREND_BREAK = 0.996            # exit if close < 99.6% of the slow EMA
MOMENTUM_MIN = 0.002           # entry needs > 0.2% return over the last 120 bars
COOLDOWN_BARS = 60             # bars to wait after a stop/trend-break exit
BUY_CASH_PCT = 95              # buy with 95% of cash (integer floor)
SLIPPAGE_BPS = 300             # max slippage on every order


class TrendBot:
    """Holds all indicator and position-tracking state across batches."""

    def __init__(self):
        self.closes = []          # every CBBTC close seen, as ints
        self.ema_fast = None      # EMA(30) over closes, seeded with the first close
        self.ema_slow = None      # EMA(180) over closes, seeded with the first close
        self.slow_history = []    # the last 31 slow-EMA values (slope look-back)
        self.peak_equity = 0      # max state.equity seen so far
        self.peak_close = None    # peak close since entry
        self.cooldown = 0         # bars since an exit
        self.halted = False       # set by the drawdown brake; no orders ever after

    def _update_indicators(self, close):
        self.closes.append(close)
        if self.ema_fast is None:
            self.ema_fast = float(close)
            self.ema_slow = float(close)
        else:
            alpha_fast = 2.0 / (FAST_SPAN + 1)
            alpha_slow = 2.0 / (SLOW_SPAN + 1)
            self.ema_fast += alpha_fast * (close - self.ema_fast)
            self.ema_slow += alpha_slow * (close - self.ema_slow)
        self.slow_history.append(self.ema_slow)
        if len(self.slow_history) > SLOW_SLOPE_KEEP:
            del self.slow_history[0]

    def _sell_all(self, holding):
        return {"side": "sell", "symbol": SYMBOL, "qty": holding.qty, "max_slippage_bps": SLIPPAGE_BPS}

    def _buy(self, state):
        return {
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash * BUY_CASH_PCT // 100,
            "max_slippage_bps": SLIPPAGE_BPS,
        }

    def on_batch(self, state, batch):
        # Indicators move only on a batch that carries a CBBTC bar.
        bar = None
        for b in batch["bars"]:
            if b["symbol"] == SYMBOL:
                bar = b
                break
        if bar is None:
            return []

        close = int(bar["c"])
        self._update_indicators(close)

        if state.equity > self.peak_equity:
            self.peak_equity = state.equity

        if state.warming_up:
            return []

        if self.halted:
            return []

        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            # Holding: track the peak close since entry, then check the exits.
            if self.peak_close is None or close > self.peak_close:
                self.peak_close = close
            # Drawdown brake: equity below 90% of peak equity -> sell all, halt forever.
            if state.equity < DRAWDOWN_BRAKE * self.peak_equity:
                self.halted = True
                return [self._sell_all(holding)]
            # Trailing stop: close below 98.2% of the peak close since entry.
            if close < TRAIL_STOP * self.peak_close:
                self.cooldown = COOLDOWN_BARS
                return [self._sell_all(holding)]
            # Trend break: close below 99.6% of the slow EMA.
            if close < TREND_BREAK * self.ema_slow:
                self.cooldown = COOLDOWN_BARS
                return [self._sell_all(holding)]
            return []

        # Flat: cool down, then look for a confirmed uptrend entry.
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.cooldown != 0 or len(self.closes) < MIN_BARS:
            return []
        slow_ema_30_bars_ago = self.slow_history[-SLOW_SLOPE_KEEP]
        close_120_bars_ago = self.closes[-1 - MOMENTUM_BARS]
        momentum = (close - close_120_bars_ago) / close_120_bars_ago
        if (
            close > self.ema_slow
            and self.ema_slow > slow_ema_30_bars_ago
            and momentum > MOMENTUM_MIN
        ):
            self.peak_close = close
            return [self._buy(state)]
        return []


_bot = TrendBot()


def on_batch(state, batch):
    return _bot.on_batch(state, batch)


if __name__ == "__main__":
    makefun_bars.run(on_batch)
