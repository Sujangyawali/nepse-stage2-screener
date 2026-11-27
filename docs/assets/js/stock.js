(function () {
  const CRITERIA_LABELS = {
    price_above_150_200: "Price above AMA 150 & AMA 200",
    price_above_ma20: "Price above AMA 20",
    ma200_trending_up: "AMA 200 trending up (~1 month)",
    price_above_all_ma: "Price above all four AMAs (20/50/150/200)",
    price_above_ma50: "Price above AMA 50",
    above_52w_low_25pct: "At least 25% above 52-week low",
    within_25pct_52w_high: "Within 25% of 52-week high",
    rs_top_30pct: "Relative strength in top 30% of universe",
  };

  // Same colors NepseAlpha uses for these four "Moving Average Adaptive" lines.
  const MA_PERIODS = [20, 50, 150, 200];
  const MA_COLORS = {
    20: "#ec407a",
    50: "#ffa726",
    150: "#26c6da",
    200: "#ab47bc",
  };

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toFixed(digits === undefined ? 2 : digits);
  }

  // Return to the dashboard tab the user came from (e.g. index.html#activity).
  try {
    const ref = new URL(document.referrer);
    if (ref.origin === location.origin && /(\/|index\.html)$/.test(ref.pathname)) {
      document.getElementById("backLink").href = ref.pathname + ref.hash;
    }
  } catch (e) { /* no or foreign referrer: keep the default link */ }

  const params = new URLSearchParams(window.location.search);
  const symbol = params.get("symbol");

  if (!symbol) {
    document.getElementById("stockTitle").textContent = "No symbol specified";
    return;
  }

  const state = { candidates: null, history: null, chart: null, bars: [], pointByDate: new Map() };

  function renderWarnings(stock) {
    const banner = document.getElementById("warningBanner");
    let html = "";
    if (stock.data_quality && stock.data_quality.possible_corporate_action_gap) {
      html +=
        '<p class="badge warn">Warning: a large single-day price jump was detected — ' +
        "possibly an unadjusted bonus/rights share issuance. Moving averages and 52-week " +
        'range may be distorted. See <a href="DATA_LIMITATIONS.md">data limitations</a>.</p>';
    }
    if (stock.data_quality && !stock.data_quality.sufficient_history) {
      html +=
        '<p class="badge warn">Insufficient history (' + stock.history_days_available +
        " sessions) — Trend Template criteria are not yet evaluable for this stock.</p>";
    }
    banner.innerHTML = html;
  }

  function renderScorecard(stock) {
    const rows = Object.entries(CRITERIA_LABELS).map(([key, label]) => `
      <tr>
        <td>${label}</td>
        <td><span class="badge ${stock.criteria[key] ? "pass" : "fail"}">
          ${stock.criteria[key] ? "pass" : "fail"}</span></td>
      </tr>
    `).join("");
    document.getElementById("scorecardBody").innerHTML = rows + `
      <tr><td><strong>Score</strong></td><td><strong>${stock.score} / 8</strong></td></tr>
      <tr><td>Rank</td><td>#${stock.rank ?? "—"} of ${state.candidates.universe_size}</td></tr>
      <tr><td>Close</td><td>${fmt(stock.close)}</td></tr>
      <tr><td>AMA 20</td><td>${fmt(stock.ma20)}</td></tr>
      <tr><td>AMA 50</td><td>${fmt(stock.ma50)}</td></tr>
      <tr><td>AMA 150</td><td>${fmt(stock.ma150)}</td></tr>
      <tr><td>AMA 200</td><td>${fmt(stock.ma200)}</td></tr>
      <tr><td>52-week high / low</td><td>${fmt(stock.week52_high)} / ${fmt(stock.week52_low)}</td></tr>
      <tr><td>RS percentile</td><td>${stock.rs_percentile === null ? "—" : fmt(stock.rs_percentile, 0)}</td></tr>
    `;
  }

  // ---- Chart (TradingView Lightweight Charts, NepseAlpha-style) -------------------

  const UP = "#26a69a";
  const DOWN = "#ef5350";
  const INITIAL_BARS = 130; // ~6 months of NEPSE sessions; scroll/zoom for the rest

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function themeOptions() {
    const border = cssVar("--border");
    return {
      layout: { background: { type: "solid", color: cssVar("--bg") }, textColor: cssVar("--muted"), fontSize: 12 },
      grid: { vertLines: { color: border }, horzLines: { color: border } },
      rightPriceScale: { borderColor: border },
      timeScale: { borderColor: border },
    };
  }

  function fmtVolume(v) {
    if (v === null || v === undefined) return "—";
    if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
    if (v >= 1e3) return (v / 1e3).toFixed(2) + "K";
    return String(Math.round(v));
  }

  function buildBars(series) {
    // Older history files only carried `close`; fall back to a flat bar so they still draw.
    return series.map((p) => {
      const close = p.close;
      return {
        time: p.date,
        open: p.open ?? close,
        high: p.high ?? close,
        low: p.low ?? close,
        close,
        volume: p.volume ?? null,
      };
    }).filter((b) => b.close !== null && b.close !== undefined);
  }

  function renderLegend(idx) {
    const legend = document.getElementById("chartLegend");
    const bar = state.bars[idx];
    if (!bar) { legend.innerHTML = ""; return; }
    const prev = state.bars[idx - 1];
    const change = prev ? (bar.close / prev.close - 1) * 100 : null;
    const color = bar.close >= bar.open ? UP : DOWN;
    const point = state.pointByDate.get(bar.time) || {};
    const amas = MA_PERIODS.map((p) => `
      <span class="lg-item"><span class="lg-dot" style="background:${MA_COLORS[p]}"></span>AMA ${p}
        <b style="color:${MA_COLORS[p]}">${fmt(point[`ama${p}`])}</b></span>`).join("");
    legend.innerHTML = `
      <div class="lg-row">
        <span class="lg-date">${bar.time}</span>
        <span>O <b style="color:${color}">${fmt(bar.open)}</b></span>
        <span>H <b style="color:${color}">${fmt(bar.high)}</b></span>
        <span>L <b style="color:${color}">${fmt(bar.low)}</b></span>
        <span>C <b style="color:${color}">${fmt(bar.close)}</b></span>
        ${change === null ? "" : `<b style="color:${change >= 0 ? UP : DOWN}">${change >= 0 ? "+" : ""}${fmt(change)}%</b>`}
        <span>Vol <b>${fmtVolume(bar.volume)}</b></span>
      </div>
      <div class="lg-row">${amas}</div>`;
  }

  function renderChart() {
    const container = document.getElementById("priceChart");
    const bars = buildBars(state.history.series);
    state.bars = bars;
    state.pointByDate = new Map(state.history.series.map((p) => [p.date, p]));
    if (!bars.length) {
      container.textContent = "No price history available for this symbol.";
      return;
    }
    const indexByTime = new Map(bars.map((b, i) => [b.time, i]));

    const chart = LightweightCharts.createChart(container, {
      autoSize: true,
      ...themeOptions(),
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      timeScale: { ...themeOptions().timeScale, rightOffset: 4 },
      localization: { priceFormatter: (p) => p.toFixed(2) },
    });
    state.chart = chart;

    const candles = chart.addCandlestickSeries({
      upColor: UP, downColor: DOWN, wickUpColor: UP, wickDownColor: DOWN, borderVisible: false,
      priceLineVisible: false,
    });
    candles.priceScale().applyOptions({ scaleMargins: { top: 0.14, bottom: 0.24 } });
    candles.setData(bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));

    if (bars.some((b) => b.volume !== null)) {
      const volume = chart.addHistogramSeries({
        priceScaleId: "",
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: false,
      });
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      volume.setData(bars.map((b) => ({
        time: b.time,
        value: b.volume ?? 0,
        color: (b.close >= b.open ? UP : DOWN) + "80",
      })));
    }

    MA_PERIODS.forEach((period) => {
      const line = chart.addLineSeries({
        color: MA_COLORS[period],
        lineWidth: 2,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      });
      line.setData(state.history.series
        .filter((p) => indexByTime.has(p.date))
        .map((p) => {
          const v = p[`ama${period}`];
          return v === null || v === undefined ? { time: p.date } : { time: p.date, value: v };
        }));
    });

    const last = bars.length - 1;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, last - INITIAL_BARS), to: last + 4 });
    renderLegend(last);
    chart.subscribeCrosshairMove((param) => {
      const idx = param.time !== undefined ? indexByTime.get(param.time) : undefined;
      renderLegend(idx === undefined ? last : idx);
    });

    document.getElementById("chartReset").addEventListener("click", () => {
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, last - INITIAL_BARS), to: last + 4 });
      chart.priceScale("right").applyOptions({ autoScale: true });
    });

    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    const retheme = () => chart.applyOptions(themeOptions());
    if (scheme.addEventListener) scheme.addEventListener("change", retheme);
  }

  function renderAll() {
    const stock = state.candidates.stocks.find((s) => s.symbol === symbol);
    if (!stock) {
      document.getElementById("stockTitle").textContent = `${symbol}: not found in latest run`;
      return;
    }
    document.getElementById("stockTitle").textContent =
      `${stock.symbol} — ${stock.name || ""} (${stock.sector || "n/a"})`;
    renderWarnings(stock);
    renderScorecard(stock);
    if (state.history) renderChart();
  }

  const loadHistory = fetch(`data/history/${encodeURIComponent(symbol)}.json`)
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);

  Promise.all([fetch("data/candidates.json").then((r) => r.json()), loadHistory])
    .then(([candidates, history]) => {
      state.candidates = candidates;
      state.history = history;
      if (!history) {
        document.getElementById("chartCard").hidden = true;
        document.getElementById("chartMissing").hidden = false;
      }
      renderAll();
    })
    .catch((err) => {
      document.getElementById("stockTitle").textContent = `${symbol}`;
      document.getElementById("warningBanner").textContent =
        "Data unavailable for this symbol.";
      console.error(err);
    });
})();
