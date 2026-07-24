# Data Limitations

This screener is built entirely on scraped public web pages — NEPSE has no official public
API. Please understand these limitations before acting on anything shown here.

## Historical price depth

Historical daily prices come from sharesansar.com's own charting data feed, which only goes
back to approximately **2025-02-27** (~320 trading sessions at the time this was written).
This is enough for the 200-day moving average the Trend Template needs, but stocks listed
or actively traded for less time than that will show as "insufficient history" rather than
being scored.

## Corporate actions are NOT price-adjusted

NEPSE listed companies frequently issue bonus shares and rights shares. Historical closing
prices on sharesansar (and everywhere else we could find) are **not retroactively adjusted**
for these events. A large bonus/rights issuance causes a mechanical, one-day price drop that
has nothing to do with the company's actual performance — but it looks identical to a real
crash in the raw price series.

This screener flags a `possible_corporate_action_gap` warning when a single-session price
move is larger than NEPSE's circuit-breaker bands would normally allow, since that's the
practical fingerprint of an unadjusted ex-date gap. **This is a heuristic warning, not a
correction** — moving averages, 52-week highs/lows, and relative strength for flagged stocks
may be distorted around the gap date. Always check a flagged stock's actual news/corporate
action history before trusting its scorecard.

## SMA vs. AMA tabs are scored independently

The dashboard has two tabs running the same 8-criterion Trend Template, but against
different moving averages:

- **SMA** — the classic Minervini Trend Template, using fixed 50/150/200-day simple
  moving averages.
- **AMA** — the same 8 criteria, but using Kaufman's Adaptive Moving Average (KAMA) in
  place of each SMA. AMA speeds up (tracks price closely) during efficient, one-directional
  moves and slows down during choppy/sideways stretches, so it can flag a genuine trend
  change faster than a backward-looking SMA — at the cost of being noisier in genuinely
  indecisive markets.

A stock's SMA and AMA candidacy are computed independently — it can pass one and fail the
other. Neither is "more correct"; they're different lenses on the same price data.

## Relative Strength is universe-relative, not index-relative

Minervini's RS Rating is normally computed against the broader market index. We don't yet
have a reliable scrapeable source for historical NEPSE index values, so relative strength
here is computed by ranking each stock's trailing return against every other scraped equity
in the universe instead. Directionally similar, but not identical to an index-relative
RS Rating.

## Universe

Only ordinary equity shares are screened. Mutual funds, corporate debentures/bonds,
preference shares, and promoter shares are excluded, based on each company's sector as
classified on sharesansar.com.

## Not investment advice

This is a mechanical screener over incomplete, unaudited, scraped data. It is a starting
point for further research, not a buy/sell signal.
