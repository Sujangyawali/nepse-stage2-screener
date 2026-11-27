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

  const params = new URLSearchParams(window.location.search);
  const symbol = params.get("symbol");

  if (!symbol) {
    document.getElementById("stockTitle").textContent = "No symbol specified";
    return;
  }

  const state = { candidates: null, history: null, chart: null };

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
      <tr><td>Close</td><td>${fmt(stock.close)}</td></tr>
      <tr><td>AMA 20</td><td>${fmt(stock.ma20)}</td></tr>
      <tr><td>AMA 50</td><td>${fmt(stock.ma50)}</td></tr>
      <tr><td>AMA 150</td><td>${fmt(stock.ma150)}</td></tr>
      <tr><td>AMA 200</td><td>${fmt(stock.ma200)}</td></tr>
      <tr><td>52-week high / low</td><td>${fmt(stock.week52_high)} / ${fmt(stock.week52_low)}</td></tr>
      <tr><td>RS percentile</td><td>${stock.rs_percentile === null ? "—" : fmt(stock.rs_percentile, 0)}</td></tr>
    `;
  }

  function chartDatasets() {
    const series = state.history.series;
    return [
      { label: "Close", data: series.map((p) => p.close), borderColor: "#4ade80", pointRadius: 0, borderWidth: 2 },
      ...MA_PERIODS.map((period) => ({
        label: `AMA ${period}`,
        data: series.map((p) => p[`ama${period}`]),
        borderColor: MA_COLORS[period],
        pointRadius: 0,
        borderWidth: 1,
      })),
    ];
  }

  function renderChart() {
    const labels = state.history.series.map((p) => p.date);
    state.chart = new Chart(document.getElementById("priceChart"), {
      type: "line",
      data: { labels, datasets: chartDatasets() },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        scales: { x: { ticks: { maxTicksLimit: 12 } } },
      },
    });
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

  Promise.all([
    fetch("data/candidates.json").then((r) => r.json()),
    fetch(`data/history/${encodeURIComponent(symbol)}.json`).then((r) => {
      if (!r.ok) throw new Error("no chart history for this symbol");
      return r.json();
    }),
  ])
    .then(([candidates, history]) => {
      state.candidates = candidates;
      state.history = history;
      renderAll();
    })
    .catch((err) => {
      document.getElementById("stockTitle").textContent = `${symbol}`;
      document.getElementById("warningBanner").textContent =
        "Chart data unavailable for this symbol.";
      console.error(err);
    });
})();
