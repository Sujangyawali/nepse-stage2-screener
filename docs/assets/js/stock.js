(function () {
  const CRITERIA_LABELS = {
    price_above_150_200: "Price above 150-day & 200-day SMA",
    sma150_above_sma200: "150-day SMA above 200-day SMA",
    sma200_trending_up: "200-day SMA trending up (~1 month)",
    sma50_above_150_200: "50-day SMA above 150-day & 200-day SMA",
    price_above_sma50: "Price above 50-day SMA",
    above_52w_low_25pct: "At least 25% above 52-week low",
    within_25pct_52w_high: "Within 25% of 52-week high",
    rs_top_30pct: "Relative strength in top 30% of universe",
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

  Promise.all([
    fetch("data/candidates.json").then((r) => r.json()),
    fetch(`data/history/${encodeURIComponent(symbol)}.json`).then((r) => {
      if (!r.ok) throw new Error("no chart history for this symbol");
      return r.json();
    }),
  ])
    .then(([candidates, history]) => {
      const stock = candidates.stocks.find((s) => s.symbol === symbol);
      if (!stock) {
        document.getElementById("stockTitle").textContent = `${symbol}: not found in latest run`;
        return;
      }

      document.getElementById("stockTitle").textContent =
        `${stock.symbol} — ${stock.name || ""} (${stock.sector || "n/a"})`;

      if (stock.data_quality && stock.data_quality.possible_corporate_action_gap) {
        document.getElementById("warningBanner").innerHTML =
          '<p class="badge warn">Warning: a large single-day price jump was detected — ' +
          "possibly an unadjusted bonus/rights share issuance. Moving averages and 52-week " +
          'range may be distorted. See <a href="DATA_LIMITATIONS.md">data limitations</a>.</p>';
      }
      if (stock.data_quality && !stock.data_quality.sufficient_history) {
        document.getElementById("warningBanner").innerHTML +=
          '<p class="badge warn">Insufficient history (' + stock.history_days_available +
          " sessions) — Trend Template criteria are not yet evaluable for this stock.</p>";
      }

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
        <tr><td>50-day SMA</td><td>${fmt(stock.sma50)}</td></tr>
        <tr><td>150-day SMA</td><td>${fmt(stock.sma150)}</td></tr>
        <tr><td>200-day SMA</td><td>${fmt(stock.sma200)}</td></tr>
        <tr><td>52-week high / low</td><td>${fmt(stock.week52_high)} / ${fmt(stock.week52_low)}</td></tr>
        <tr><td>RS percentile</td><td>${stock.rs_percentile === null ? "—" : fmt(stock.rs_percentile, 0)}</td></tr>
      `;

      const labels = history.series.map((p) => p.date);
      const datasets = [
        { label: "Close", data: history.series.map((p) => p.close), borderColor: "#4ade80", pointRadius: 0, borderWidth: 2 },
        { label: "SMA 50", data: history.series.map((p) => p.sma50), borderColor: "#60a5fa", pointRadius: 0, borderWidth: 1 },
        { label: "SMA 150", data: history.series.map((p) => p.sma150), borderColor: "#f59e0b", pointRadius: 0, borderWidth: 1 },
        { label: "SMA 200", data: history.series.map((p) => p.sma200), borderColor: "#f87171", pointRadius: 0, borderWidth: 1 },
      ];

      new Chart(document.getElementById("priceChart"), {
        type: "line",
        data: { labels, datasets },
        options: {
          responsive: true,
          interaction: { mode: "index", intersect: false },
          scales: { x: { ticks: { maxTicksLimit: 12 } } },
        },
      });
    })
    .catch((err) => {
      document.getElementById("stockTitle").textContent = `${symbol}`;
      document.getElementById("warningBanner").textContent =
        "Chart data unavailable for this symbol.";
      console.error(err);
    });
})();
