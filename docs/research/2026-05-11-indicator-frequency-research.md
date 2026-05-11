# QTrend_v2 — Indicator & Frequency Research

**Date:** 2026-05-11
**Author:** Research synthesis for Simon
**Scope:** Long-only trend confirmation, pullback overlay, timeframe architecture, and discrete-lot sizing for a single-instrument HC (热卷 / hot-rolled coil) futures engine. Holding period 1 week to 1 quarter, average ~22 trading days. Direction comes from a human fundamental view; the engine only handles when/how to enter, lighten, reload, and exit.

---

## 0. Executive summary

For this exact problem — long-only, ~1-month average hold on a single Chinese ferrous contract, with active inventory management in {0..5} lots — the literature converges on a narrow, opinionated set of choices:

- **Trend confirmation (top 3):** (1) **Donchian channel breakout** at ~20-day length, (2) **EMA crossover (EWMAC)** with span pair ~16/64 (Carver's medium-term variant), (3) **time-series momentum (TSMOM)** using sign of past 1–3 month return. The first two are the proven CTA-grade workhorses; TSMOM is the academic backbone and is essentially a smoother version of #2. **ADX is not a primary signal but a useful "is trend strong enough" gate.**
- **Pullback overlay (top 2):** (1) **Distance-from-MA in ATR units (z-score-style)** for "how stretched are we" and (2) **short-term RSI (2–5 day) or Bollinger %B** for tactical re-load timing — both used only when the trend signal is already long and only as a sizing modulator, never as a direction signal.
- **Timeframe architecture:** **Multi-timeframe is worth the complexity here, but lightly.** Use **weekly bias gate + daily entry/exit + ATR-based pullback timing on daily**. Don't go intraday — for a 22-day hold, intraday signals are noise relative to the holding horizon. Empirically, ensemble of short + long horizons beats either alone (Sharpe efficiency +75% in the Bayesian-CTA study below).
- **Lookback ranges:** Pardo's rule (lookback ≈ holding period) plus CTA practice suggests **breakout 20–55 days, EMA spans 16/64 to 32/128, ATR 14–20 days**. Avoid <10 day lookbacks (too noisy for monthly hold) and >120 day (you'll miss the entire trade).
- **Sizing:** **Carver-style scaled forecast with thresholding + ATR vol target** is the cleanest fit for the 0–5 lot integer constraint. Pyramiding (Turtle-style, +1 unit every 0.5 ATR favourable) is the natural way to drive the {0..5} inventory ladder, but with a smoother forecast on top so you don't bang against the cap on every micro-move.

The rest of this report defends each of these.

---

## 1. Trend confirmation: ranking and rationale

### Recommendation order

| Rank | Indicator | Why for HC, ~22d hold |
|------|-----------|----------------------|
| 1 | **Donchian (20–55d)** | Simplest, most robust, hardest to overfit. Decade-stable. Native fit for "enter when price confirms the human's bias." |
| 2 | **EWMAC 16/64 (medium-term)** | Smoother than breakout; produces a continuous forecast that maps naturally onto integer-lot sizing. Carver's canonical medium-horizon span. |
| 3 | **TSMOM (sign of 1–3M return)** | Academic gold standard, very robust, very few parameters. Best as a *confirmation* layer on top of #1/#2 rather than a standalone trigger. |
| - | ADX | Useful as a **gate** (only act when ADX>20–25), not as a direction signal. Linda Raschke's pattern. |
| - | MACD | A specific case of EWMAC. No additional information vs #2. |
| - | RSI on weekly | Slow RSI is a momentum proxy, but adds noise and reversal bias unsuitable for a long-only trend engine. |
| - | Supertrend | Pretty on charts, but Liberated Stock Trader's 4,052-trade backtest reports only a 43% win rate on daily — not a robust trend confirmer on its own. |
| - | Kalman / regression slope | More theoretically appealing but more degrees of freedom → overfit risk. Reserve for a v2 research item, not the day-1 stack. |
| - | KAMA | Adapts well in theory; in practice the efficiency ratio adds a parameter without clear evidence of beating fixed-span EWMAC for ~22d holds. |

### Why these three and not the others

**Why Donchian wins for robustness.** Donchian channels are the original Richard Donchian / Richard Dennis (Turtle) breakout system. They have one parameter (lookback), the breakout rule is mechanical, and they survived 70+ years of out-of-sample evidence on commodities specifically — the asset class they were designed for ([Donchian Trading Guidelines, StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/overview/donchian-trading-guidelines); [Quantified Strategies trend following overview](https://www.quantifiedstrategies.com/trend-following-trading-strategy/)). The "trend following is robust because the signals are simple" thesis is explicitly supported by AHL's own published white paper ([AHL, *Trend-Following: What's Not to Like?*](https://americanbeaconfunds.com/wp-content/uploads/2025/08/Trend-Following-Whats-Not-to-Like_AHL-TREND-WP-1.pdf)) and by the Hedge Fund Journal's [CTAs Under Threat](https://thehedgefundjournal.com/ctas-under-threat/) piece. Curve-fit risk is minimal.

**Why EWMAC for the continuous signal.** Donchian gives a binary "in / out" view; the engine needs a continuous trend strength to drive inventory between 0 and 5 lots. Rob Carver's *Systematic Trading* (Harriman House, 2015) builds the canonical mapping: EWMAC(n_fast, n_slow) → scaled forecast → integer position size, with thresholding to handle small accounts ([Carver, "Diversification and small account size", qoppac.blogspot.com 2016](https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html); [Carver, "Some more trading rules", qoppac.blogspot.com 2017](https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html)). The 16/64 span pair targets a ~6–8 week holding period — almost exactly Simon's average.

**Why TSMOM as the cross-check.** Moskowitz, Ooi, Pedersen (2012), [*Time Series Momentum*, JFE](https://www.sciencedirect.com/science/article/pii/S0304405X11002613) found that **every single one of 58 liquid futures contracts** exhibited positive predictability from past 12-month returns, with 52/58 significant at 5%. A diversified portfolio achieves Sharpe >1. The 1-, 3-, and 12-month variants are highly correlated but the 1–3 month versions match Simon's holding horizon better. Use as a confirmation layer: only enter when sign(past 1M return) agrees with the Donchian/EWMAC signal. ([Quantpedia TSMOM page](https://quantpedia.com/strategies/time-series-momentum-effect); [AQR original-paper dataset](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data).)

**Specific Chinese-rebar evidence.** The Springer paper [*Technical Trading Behaviour: Evidence from Chinese Rebar Futures Market* (Computational Economics, 2019)](https://link.springer.com/article/10.1007/s10614-018-9851-4) used tick-by-tick data to identify three dominant practitioner signal classes in RB: **Momentum, Moving Average, and Trading-Range Breakout** — i.e. the three families recommended above. This is direct evidence that the actual traders working RB are running variants of these systems, which has both crowding-risk (signals are "common knowledge") and validation-of-edge implications. Crowding is less of an issue for a single-trader-discretionary-overlay use case like Simon's.

The 2025 Zheng paper [*Evaluating Trend-Based Strategies in Chinese Commodity Futures Markets*, J. Futures Markets](https://onlinelibrary.wiley.com/doi/10.1002/fut.70033) tested 64 Chinese commodities 2003–2023 — paywalled, but the published abstract confirms trend strategies remain profitable, with sector heterogeneity (ferrous is one of the more trend-friendly sectors per related work). **Flag: I could not read the full paper, only the abstract and the search-summary**. Worth a one-off purchase if Simon wants the parameter sweeps.

---

## 2. Timeframe architecture

### Recommendation: weekly bias gate + daily entry + daily-bar pullback overlay. No intraday.

### Evidence

**Practitioner side.** [Aspect Capital](https://thehedgefundjournal.com/aspect-stays-true-to-trend/) explicitly runs "medium-term (multi-month) trend models, still ~80% of risk budget" — i.e. mostly a single, multi-week horizon. AHL/Winton diversified across many horizons but the *Trend-Following: What's Not to Like?* paper makes clear that medium-term (weeks-to-months) is the load-bearing part; fast signals have decayed over time and slow signals only kick in for the strongest moves.

**Academic side.** The 2025 arXiv paper [*Re-evaluating Short- and Long-Term Trend Factors in CTA Replication: A Bayesian Graphical Approach*](https://arxiv.org/html/2507.15876v1) is the cleanest direct evidence: combining short-term (10/20/40/60 day) and long-term (~500 day) signals lifted Sharpe-to-MaxDD efficiency from 1.34 (STT alone) and 2.09 (LTT alone) to **2.37 (combined)** — a meaningful diversification win. Standalone Sharpes: STT 0.40, LTT 0.39, combined with market beta MKT+STT 0.49. **The combined-horizon edge is real, but it is mostly a drawdown-mitigation edge, not a Sharpe edge.**

**What this means for QTrend_v2.** Simon already has the directional bias from his fundamental view — so the role of the longer horizon (weekly) is essentially the same as the human view: confirm that we are in a regime where being long HC is sensible. The engine's job is then daily tactical implementation. This argues for a **weekly trend filter that mostly agrees with Simon's view** (sanity check + auto-disable when fundamentals and price action disagree), and the **daily layer doing the work**.

**Don't go intraday.** [Yang & Göncü, "Momentum and reversal strategies in Chinese commodity futures markets", *International Review of Financial Analysis* 2018](https://www.sciencedirect.com/science/article/abs/pii/S1057521918305696) found explicitly that "intra-day strategies cannot generate sufficiently high excess returns to cover the excessive costs due to the higher frequency of trading." For a 22-day average hold, intraday signal noise dominates.

**Night-session caveat for HC specifically.** SHFE introduced night sessions for ferrous in 2014. Multiple papers ([He et al., "What the Night Tells the Day", *JFM* 2025](https://onlinelibrary.wiley.com/doi/10.1002/fut.70042); [Jiang et al. *JFM* 2020](https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22147)) show night-session volatility carries genuine signal for next-day realised vol — but this is a vol-forecasting / sizing input, not a direction signal. The practical implication: **compute ATR using night+day combined bars (continuous session), don't split.** Pricing the first half-hour after open on the night session can also signal next-period direction, but exploiting it pushes the engine into intraday territory which we said we'd avoid.

---

## 3. Pullback / re-entry overlay

### Recommendation: ATR-distance-from-MA as the *measure*, short-period RSI or %B as the *trigger*.

### The two indicators

1. **Distance-from-MA in ATR units** — formula: `(close - SMA(close, 20)) / ATR(20)`. This is essentially a z-score and works as a "stretchedness" gauge. Empirically used in trend-trading guides (e.g., [Trade That Swing's ATR-based trend trading framework](https://tradethatswing.com/trend-trading-strategy-for-high-momentum-stocks-atr-based/)) for both entry timing on pullbacks and exit timing on extension. Best property: it auto-adapts to changing volatility regimes, unlike fixed-percentage thresholds.

2. **Short-period RSI (2–5 day) or Bollinger %B** — used as a tactical re-load trigger only when the trend signal is already long. Larry Connors' *Connors%B* and short-period RSI are the documented small-time-frame mean-revert triggers ([StockCharts %B page](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/b-indicator); [Quantified Strategies, *Bollinger Bands trading strategy*](https://www.quantifiedstrategies.com/bollinger-bands-trading-strategy/)). When RSI(2) drops below ~10 *while* the trend is still up (i.e. distance-from-MA was just very positive and is contracting), reload. The Connors/Alvarez ETF research (2006–2012 backtests cited by [Quantified Strategies](https://www.quantifiedstrategies.com/bollinger-bands-trading-strategy/)) reported >75% win rate on this exact "pullback in uptrend" pattern.

### Why not just RSI everywhere

RSI as a standalone signal in trending markets has high false-signal rate ([blog.opofinance.com](https://blog.opofinance.com/en/bollinger-bands-and-rsi-strategy/)). The key is RSI **only fires conditional on a trend filter** — Simon's bias + the trend confirmation signal both being long. Then RSI(2) <10 = "load a unit", RSI(2) >90 = "lighten a unit." This matches the lighten-before-pullback/reload-after spec exactly.

**Flag: evidence here is mostly anecdotal blog backtests, not refereed papers.** The Han 2023 paper [*Commodity momentum and reversal: do they exist, and if so, why?* J. Futures Markets](https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22424) confirms that short-horizon reversal coexists with longer-horizon momentum in commodity futures, which is the theoretical justification for a pullback overlay — but the paper doesn't prescribe a specific overlay indicator.

---

## 4. Lookback parameter ranges

Pardo's rule (signal half-life ≈ holding period) plus CTA practice gives:

| Component | Lookback | Justification |
|-----------|----------|---------------|
| Donchian breakout entry | **20 days** | Classic Turtle short-term; matches ~22d avg hold. Turtles also used 55-day for re-entry filter — same logic applies here. |
| Donchian exit | **10 days** (asymmetric, faster) | Turtle convention — exit faster than you enter, locks profit on pullback. |
| EWMAC span (fast, slow) | **(16, 64)** | Carver's medium-term. Half-life ≈ 4 weeks (fast) and 16 weeks (slow). |
| TSMOM lookback | **1 month and 3 month** (both, agreement-gate) | MOP 2012 finds 1–12M all work; 1–3M is closest to Simon's hold. |
| ATR | **14 or 20 days** | Standard. Use the same window as Donchian for coherence. |
| Weekly trend filter | **20-week MA** (or 10/30 week MA cross) | Roughly the same effective half-life as a 100-day daily MA. Used by Donchian himself for long-term confirmation. |
| RSI overlay | **2-day** (Connors-style), gated on trend | Larry Connors' research. Avoid the default 14-day RSI as a trigger — too slow for the overlay role. |
| Distance-from-MA | **20-day SMA, divided by ATR(20)** | Self-consistent vol normalisation. |

Carver's *Systematic Trading* publishes three EWMAC variants used together — (8,32), (16,64), (32,128) — to span fast/medium/slow. For a *single* horizon to keep the system simple, **(16,64) is the medium choice and matches Simon's holding period**. ([Carver blog, qoppac.blogspot.com](https://qoppac.blogspot.com/p/systematic-trading-start-here.html); also see [pysystemtrade GitHub](https://qoppac.blogspot.com/2016/01/pysystemtrader-estimated-forecast.html).)

**Flag: I could not find published parameter sweep studies specifically on HC.** Closest available is the 2025 Zheng paper on 64 Chinese commodities; the Springer rebar paper used "popular" lookbacks without sweeping them. The parameter ranges above are imported from global CTA literature and validated against general Chinese commodity findings, not specifically optimised for HC. **Simon should run his own parameter robustness sweep on HC data and check whether the global-CTA convention generalises.**

---

## 5. Position sizing in the 0–5 lot world

This is the part where the literature is most directly useful.

### The two coherent frameworks

**Framework A: Pyramiding (Turtle-style, discrete-by-construction).**
- 1 unit = the position whose 1×ATR move equals X% of equity (Turtles used 1%).
- Add +1 unit every time price moves 0.5×ATR in your favour past the last add ([Turtle Trading rules canon, multiple sources including QuantifiedStrategies](https://www.quantifiedstrategies.com/position-sizing-in-a-turtle-trading-system/)).
- Cap at 4 units (original Turtles) or 5 (Simon's spec).
- Stop = 2×ATR below the most recent add.
- **Pros:** native fit to integer lots; the "scale back up after pullback" emerges automatically as price moves favourably again after a stop-flush; Concretum Group's [40-futures backtest](https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/) found pyramiding (VP+P) delivered **~100bps higher peak profit per trade** than volatility targeting on strong trends.
- **Cons:** big drawdowns when reversal hits at max size — same Concretum study notes "swift drawdown as stops are triggered" after pyramid peak. Simon's "lighten before pullback" instinct is the human discretion adding value over pure mechanical pyramiding.

**Framework B: Continuous forecast → rounded integer (Carver-style).**
- Compute scaled forecast in [-20, +20] from EWMAC.
- Map forecast to ideal position size via vol target.
- Round to nearest integer.
- Apply **thresholding** to avoid churn when the forecast hovers near rounding boundaries: if |forecast|<10, hold 0; if |forecast|>20, cap at max; in between, scale linearly ([Carver's small-account post, qoppac.blogspot.com 2016](https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html)).
- **Pros:** handles the integer-lot constraint cleanly; thresholding prevents the 0↔1 churn that destroys small-account trend systems; mathematically continuous "trend strength → size" mapping.
- **Cons:** less aggressive on strong trends than pyramiding; doesn't naturally produce "lighten on pullback then reload."

### Recommendation: hybrid, with Carver as the spine

Use **Framework B as the base layer** (Carver-style forecast → integer with thresholding) because it gives clean continuous control. Then **overlay a pullback modulator**: when the ATR-distance-from-MA + RSI(2) overlay says "stretched," cap the engine's allowed position one lot below the forecast's request; when it says "pulled back inside trend," release the cap. This way the engine implements Simon's "lighten before pullback, reload after" pattern without abandoning the Carver discipline.

Set the vol target such that a forecast of +20 maps to ~5 lots (i.e., the cap), and a forecast of +10 maps to ~2–3 lots. Use thresholding to make sure forecasts <8 round to 0 — otherwise the engine will hold 1 lot indefinitely.

**On Kelly:** integer-lot constraints make Kelly basically inapplicable directly. The right framing is fractional-Kelly via vol target (Carver typically uses 20%/yr account vol target → fractional-Kelly ≈ 0.25× full-Kelly assuming Sharpe ~0.7). Don't over-think this.

---

## 6. Where evidence is thin (honest flags)

1. **HC-specific parameter sweeps**: not published openly. Closest is the Zheng 2025 paper, paywalled, sector-aggregated. Run your own.
2. **Pullback overlay edge sizing**: most evidence is blog-grade backtests (Quantified Strategies, Concretum). Connors/Alvarez did rigorous ETF work in 2006–2012 but I did not find peer-reviewed evidence specifically on Chinese commodity futures. Treat the pullback layer as a hypothesis to be validated, not a proven edge.
3. **Multi-timeframe Sharpe lift on a *single* instrument**: the arXiv Bayesian-graphical paper measures portfolio-level efficiency, not single-instrument. For a 1-instrument system the diversification benefit will be smaller. The argument for multi-timeframe here is mostly "weekly = sanity check against the human bias," not "weekly = independent alpha source."
4. **Crowding risk in RB/HC technical signals**: the 2019 Springer rebar paper showed practitioners cluster around MA/momentum/breakout. If everyone runs the same signals, the edge degrades. Simon's edge here is the *fundamental directional view*; the engine's job is execution, not alpha generation — so crowding matters less.
5. **Night-session adjustment for HC**: confirmed material on copper/gold/silver papers; ferrous-specific (HC/RB/I/JM/J) night-session direction-predictability is under-studied compared to precious metals. Use night data for vol estimation, be cautious about night-only direction signals.

---

## 7. The shortest possible recipe

If Simon wants to ship v1 fast, here's the indicator/frequency stack:

1. **Bias gate (weekly):** human discretionary fundamental view, sanity-checked against 20-week MA slope on HC. Engine refuses to be long if both disagree.
2. **Trend confirmation (daily):** Donchian 20-day breakout high *AND* EWMAC(16,64) > 0 *AND* sign(20-day return) > 0. All three must agree.
3. **Sizing (daily close):** Carver-style scaled forecast → ATR-vol-targeted integer position in {0..5}, with thresholding such that |forecast|<8 ⇒ 0 lots.
4. **Pullback modulator (daily):** if `(close - SMA20) / ATR20 > +1.5σ` AND RSI(2) > 85, cap one lot below forecast (lighten); if `< -0.5σ` AND RSI(2) < 15, release cap (reload).
5. **Exit:** Donchian 10-day low breakout (asymmetric exit), OR fundamental bias revoked, OR stop = entry - 2×ATR(20) at the lowest-priced unit.
6. **Holding period drift:** if a trade is open for > 1 quarter (~66 trading days), force a re-evaluation gate even if signals still say long — prevents the "should have closed it last month" tail.

Everything in this recipe is supported by at least one citation above. The pullback modulator (step 4) is the most speculative piece and should be the first thing Simon evaluates in his own backtest.

---

## Sources

- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, JFE — [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304405X11002613), [AQR dataset](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data), [Quantpedia summary](https://quantpedia.com/strategies/time-series-momentum-effect).
- Hurst, Ooi & Pedersen (2013), *Demystifying Managed Futures*, AQR — [AQR PDF](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2333776).
- Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following Investing* — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026).
- Baltas & Kosowski, *Momentum Strategies in Futures Markets and Trend-Following Funds* — [NAAIM PDF](https://www.naaim.org/wp-content/uploads/2013/10/00S_Momentum_Strategies_in_Futures_Markets_Nick_Baltas.pdf).
- Re-evaluating Short- and Long-Term Trend Factors in CTA Replication (2025 arXiv) — [arXiv 2507.15876](https://arxiv.org/html/2507.15876v1).
- Yang & Göncü (2018), *Momentum and reversal strategies in Chinese commodity futures markets*, IRFA — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1057521918305696), [RePEc](https://ideas.repec.org/a/eee/finana/v60y2018icp177-196.html).
- Bianchi, Fan & Zhang (2021), *Investable commodity premia in China*, JBF — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3525612), [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378426621000856), [GCARD summary](https://www.jpmcc-gcard.com/digest-uploads/2020-spring/issue-pages/Page%2078_81%20GCARD%20Summer%202020%20Fuertes_Investability%20050820.pdf).
- Zheng & Yu (2025), *Evaluating Trend-Based Strategies in Chinese Commodity Futures Markets*, J. Futures Markets — [Wiley](https://onlinelibrary.wiley.com/doi/10.1002/fut.70033). **(paywalled — abstract only available)**
- Han (2023), *Commodity momentum and reversal: do they exist, and if so, why?*, J. Futures Markets — [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22424).
- He et al. (2025), *What the Night Tells the Day: Forecasting Realized Volatility in Chinese Commodity Markets*, J. Futures Markets — [Wiley](https://onlinelibrary.wiley.com/doi/10.1002/fut.70042).
- Jiang et al. (2020), *Night trading and market quality: Evidence from Chinese and US precious metal futures markets*, J. Futures Markets — [Wiley](https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22147).
- *Technical Trading Behaviour: Evidence from Chinese Rebar Futures Market* (2019), Computational Economics — [Springer](https://link.springer.com/article/10.1007/s10614-018-9851-4).
- Volatility spillover effects of Chinese ferrous metal futures (2022) — [arXiv 2206.15039](https://arxiv.org/pdf/2206.15039).
- Carver, *Systematic Trading*, Harriman House 2015 — book; supplementary blog posts: ["Diversification and small account size"](https://qoppac.blogspot.com/2016/03/diversification-and-small-account-size.html), ["Some more trading rules"](https://qoppac.blogspot.com/2017/06/some-more-trading-rules.html), ["pysystemtrader Estimated forecast scalars"](https://qoppac.blogspot.com/2016/01/pysystemtrader-estimated-forecast.html), ["Vol Targeting and Trend Following"](https://qoppac.blogspot.com/2018/07/vol-targeting-and-trend-following.html).
- Concretum Group, *Position Sizing in Trend-Following: VT vs VP vs VP+Pyramiding* — [Concretum](https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/), [LinkedIn long-form](https://www.linkedin.com/pulse/position-sizing-trend-following-comparing-volatility-parity-carlo-2ucve).
- Hood & Raughtigan (2024), *Volatility Targeting Is Trendy*, SSRN — [SSRN PDF](https://papers.ssrn.com/sol3/Delivery.cfm/4773781.pdf?abstractid=4773781&mirid=1).
- Turtle Trading rules — [QuantifiedStrategies position sizing](https://www.quantifiedstrategies.com/position-sizing-in-a-turtle-trading-system/), [MarketClutch original rules summary](https://marketclutch.com/quantitative-precision-original-turtle-trading-rules-for-position-sizing/).
- Donchian channels & history — [StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/overview/donchian-trading-guidelines), [Hedge Fund Journal "CTAs Under Threat"](https://thehedgefundjournal.com/ctas-under-threat/), [Aspect Capital profile](https://thehedgefundjournal.com/aspect-stays-true-to-trend/), [AHL trend-following white paper](https://americanbeaconfunds.com/wp-content/uploads/2025/08/Trend-Following-Whats-Not-to-Like_AHL-TREND-WP-1.pdf).
- Larry Connors %B and short-period RSI — [StockCharts %B page](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/b-indicator), [Quantified Strategies Bollinger backtest](https://www.quantifiedstrategies.com/bollinger-bands-trading-strategy/), [Quantified Strategies RSI guide](https://www.quantifiedstrategies.com/rsi-trading-strategy/).
- ADX as trend-strength gate (Linda Raschke) — [Interactive Brokers ADX/DMI lesson](https://www.interactivebrokers.com/campus/trading-lessons/adx-dmi/), [StatOasis ADX guide](https://statoasis.com/post/how-to-use-the-adx-indicator-like-a-pro-step-by-step-guide).
- Pardo, *The Evaluation and Optimization of Trading Strategies* (2nd ed., Wiley 2008) — book reference for lookback ≈ holding period rule.

---

*End of report.*
