(function () {
  const state = { stocks: [], sortKey: "score", sortDir: -1 };

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toFixed(digits === undefined ? 2 : digits);
  }

  function badge(pass, warn) {
    const cls = warn ? "warn" : pass ? "pass" : "fail";
    const label = warn ? "warn" : pass ? "yes" : "no";
    return `<span class="badge ${cls}">${label}</span>`;
  }

  function renderMeta(meta) {
    const bar = document.getElementById("metaBar");
    bar.innerHTML = `
      <span>As of: <strong>${meta.as_of_trading_date || "n/a"}</strong></span>
      <span>Universe: <strong>${meta.universe_size}</strong> equities</span>
      <span>Stage 2 candidates: <strong>${meta.candidates_count}</strong></span>
      <span>Generated: ${new Date(meta.generated_at).toLocaleString()}</span>
    `;
  }

  function sortStocks() {
    const { sortKey, sortDir } = state;
    state.stocks.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (av < bv) return -1 * sortDir;
      if (av > bv) return 1 * sortDir;
      return 0;
    });
  }

  function renderTable() {
    sortStocks();
    const body = document.getElementById("stocksBody");
    body.innerHTML = state.stocks.map((s) => `
      <tr data-symbol="${s.symbol}">
        <td>${s.symbol}</td>
        <td>${s.sector || "—"}</td>
        <td>${fmt(s.close)}</td>
        <td>${fmt(s.pct_from_52w_high, 1)}%</td>
        <td>${fmt(s.pct_above_52w_low, 1)}%</td>
        <td>${s.rs_percentile === null ? "—" : fmt(s.rs_percentile, 0)}</td>
        <td>${s.score}/8</td>
        <td>${badge(s.is_candidate, !s.data_quality.sufficient_history)}</td>
      </tr>
    `).join("");

    body.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `stock.html?symbol=${encodeURIComponent(row.dataset.symbol)}`;
      });
    });
  }

  document.querySelectorAll("#stocksTable th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      state.sortDir = state.sortKey === key ? -state.sortDir : -1;
      state.sortKey = key;
      renderTable();
    });
  });

  Promise.all([
    fetch("data/candidates.json").then((r) => r.json()),
  ])
    .then(([candidates]) => {
      state.stocks = candidates.stocks;
      renderMeta(candidates);
      renderTable();
    })
    .catch((err) => {
      document.getElementById("metaBar").textContent =
        "No data yet — the daily scrape/screen pipeline hasn't published results.";
      console.error(err);
    });
})();
