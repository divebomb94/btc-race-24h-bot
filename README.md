# cbBTC Trend Bot — make.fun BTC Race

![bounty](https://make.fun/badge/btc-race-24h-20261123-0511.svg)
![rank](https://make.fun/badge/btc-race-24h-20261123-0511/divebomb94/btc-race-24h-bot/rank.svg)
![reward](https://make.fun/badge/btc-race-24h-20261123-0511/divebomb94/btc-race-24h-bot/reward.svg)

A deterministic trend-following bot that trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute bars in the make.fun paper-trading race: [the bounty page](https://make.fun/bounty/btc-race-24h-20261123-0511).

It speaks the agent-fun/bars-replay/v1 protocol: a hello message, then one batch per bar, and it answers each batch with its orders. It buys only a confirmed uptrend, holds while the trend is intact, and exits on a trend break, a trailing stop, or an equity drawdown brake. No network, no wall clock, no randomness: the same bars always produce the same orders.
