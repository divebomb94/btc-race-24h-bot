import { runBars, type Bar, type BarsState, type BuyInput, type SellInput } from './vendor/makefun-bars.ts';

const closes: number[] = [];
let emaFast: number | null = null;
let emaSlow: number | null = null;
const slowHist: number[] = [];
let peakEquity: bigint = 0n;
let peakClose = 0;
let cooldown = 0;
let halted = false;

const SYM = 'CBBTC';
const SLIP = 300;

function onBatch(state: BarsState, batch: { bars: Bar[] }): (BuyInput | SellInput)[] {
  const bar = batch.bars.find((b) => b.symbol === SYM);
  if (!bar) return [];
  const close = Number(bar.c);
  closes.push(close);
  emaFast = emaFast === null ? close : emaFast + (2 / 31) * (close - emaFast);
  emaSlow = emaSlow === null ? close : emaSlow + (2 / 181) * (close - emaSlow);
  slowHist.push(emaSlow);
  if (slowHist.length > 31) slowHist.shift();
  if (state.equity > peakEquity) peakEquity = state.equity;

  if (state.warmingUp) return [];

  const held = state.positions.get(SYM);
  if (held !== undefined && held.qty > 0n) {
    if (close > peakClose) peakClose = close;
    if (state.equity * 10n < peakEquity * 9n) {
      halted = true;
      return [{ side: 'sell', symbol: SYM, qty: held.qty, max_slippage_bps: SLIP }];
    }
    if (close * 1000 < peakClose * 982) {
      cooldown = 60;
      peakClose = 0;
      return [{ side: 'sell', symbol: SYM, qty: held.qty, max_slippage_bps: SLIP }];
    }
    if (emaSlow !== null && close * 1000 < emaSlow * 996) {
      cooldown = 60;
      peakClose = 0;
      return [{ side: 'sell', symbol: SYM, qty: held.qty, max_slippage_bps: SLIP }];
    }
    return [];
  }

  if (halted) return [];
  if (cooldown > 0) {
    cooldown -= 1;
    return [];
  }

  const n = closes.length;
  if (
    n >= 200 &&
    emaSlow !== null &&
    close > emaSlow &&
    slowHist.length === 31 &&
    slowHist[30] > slowHist[0] &&
    closes[n - 1] * 1000 > closes[n - 121] * 1002
  ) {
    peakClose = close;
    return [{ side: 'buy', symbol: SYM, notional_quote_units: (state.cash * 95n) / 100n, max_slippage_bps: SLIP }];
  }
  return [];
}

await runBars({ onBatch });
