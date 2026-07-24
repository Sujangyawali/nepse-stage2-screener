(function () {
  function criteriaLabels(method) {
    const M = method.toUpperCase();
    return {
      price_above_150_200: `Price above 150-day & 200-day ${M}`,
      sma150_above_sma200: `150-day ${M} above 200-day ${M}`,
      sma200_trending_up: `200-day ${M} trending up (~1 month)`,
      sma50_above_150_200: `50-day ${M} above 150-day & 200-day ${M}`,
      price_above_sma50: `Price above 50-day ${M}`,
      above_52w_low_25pct: "At least 25% above 52-week low",
      within_25pct_52w_high: "Within 25% of 52-week high",
      rs_top_30pct: "Relative strength in top 30% of universe",
    };
  }

  const MA_COLORS = {
    50: "#60a5fa",
    150: "#f59e0b",
    200: "#f87171",
  };

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toFixed(digits === undefined ? 2 : digits);
  }

  const params = new URLSearchParams(window.location.search);
  const symbol = params.get("symbol");
  const initialMethod = params.get("method") === "ama" ? "ama" : "sma";

  if (!symbol) {
    document.getElementById("stockTitle").textContent = "No symbol specified";
    return;
  }

  const state = { method: initialMethod, candidates: null, history: null, chart: null };

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

  function renderScorecard(stock, method) {
    const labels = criteriaLabels(method);
    const M = method.toUpperCase();
    const rows = Object.entries(labels).map(([key, label]) => `
      <tr>
        <td>${label}</td>
        <td><span class="badge ${stock.criteria[key] ? "pass" : "fail"}">
          ${stock.criteria[key] ? "pass" : "fail"}</span></td>
      </tr>
    `).join("");
    document.getElementById("scorecardBody").innerHTML = rows + `
      <tr><td><strong>Score</strong></td><td><strong>${stock.score} / 8</strong></td></tr>
      <tr><td>Close</td><td>${fmt(stock.close)}</td></tr>
      <tr><td>50-day ${M}</td><td>${fmt(stock.ma50)}</td></tr>
      <tr><td>150-day ${M}</td><td>${fmt(stock.ma150)}</td></tr>
      <tr><td>200-day ${M}</td><td>${fmt(stock.ma200)}</td></tr>
      <tr><td>52-week high / low</td><td>${fmt(stock.week52_high)} / ${fmt(stock.week52_low)}</td></tr>
      <tr><td>RS percentile</td><td>${stock.rs_percentile === null ? "—" : fmt(stock.rs_percentile, 0)}</td></tr>
    `;
  }

  function chartDatasets(method) {
    const series = state.history.series;
    const M = method.toUpperCase();
    return [
      { label: "Close", data: series.map((p) => p.close), borderColor: "#4ade80", pointRadius: 0, borderWidth: 2 },
      ...[50, 150, 200].map((window) => ({
        label: `${M} ${window}`,
        data: series.map((p) => p[`${method}${window}`]),
        borderColor: MA_COLORS[window],
        pointRadius: 0,
        borderWidth: 1,
      })),
    ];
  }

  function renderChart(method) {
    const labels = state.history.series.map((p) => p.date);
    if (state.chart) {
      state.chart.data.labels = labels;
      state.chart.data.datasets = chartDatasets(method);
      state.chart.update();
      return;
    }
    state.chart = new Chart(document.getElementById("priceChart"), {
      type: "line",
      data: { labels, datasets: chartDatasets(method) },
      options: {
        responsive: true,
        interaction: { mode: "index", intersect: false },
        scales: { x: { ticks: { maxTicksLimit: 12 } } },
      },
    });
  }

  function renderAll() {
    const method = state.method;
    const block = state.candidates[method];
    const stock = block.stocks.find((s) => s.symbol === symbol);
    if (!stock) {
      document.getElementById("stockTitle").textContent = `${symbol}: not found in latest run`;
      return;
    }
    document.getElementById("stockTitle").textContent =
      `${stock.symbol} — ${stock.name || ""} (${stock.sector || "n/a"})`;
    renderWarnings(stock);
    renderScorecard(stock, method);
    if (state.history) renderChart(method);
  }

  document.querySelectorAll("#methodTabs .tab-btn").forEach((btn) => {
    if (btn.dataset.method === initialMethod) {
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
    } else {
      btn.classList.remove("active");
      btn.setAttribute("aria-selected", "false");
    }
    btn.addEventListener("click", () => {
      if (btn.dataset.method === state.method) return;
      state.method = btn.dataset.method;
      document.querySelectorAll("#methodTabs .tab-btn").forEach((b) => {
        b.classList.toggle("active", b === btn);
        b.setAttribute("aria-selected", b === btn ? "true" : "false");
      });
      renderAll();
    });
  });

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
