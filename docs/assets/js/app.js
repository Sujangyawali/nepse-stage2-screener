(function () {
  const METHOD_BLURBS = {
    sma: "Classic Minervini Trend Template: 50/150/200-day simple moving averages.",
    ama: "Same 8 criteria, but using Kaufman's Adaptive Moving Average (AMA) instead of a " +
      "fixed-window SMA — reacts faster to genuinely efficient trends and slower to choppy " +
      "ones. Scored independently of the SMA tab; a stock can pass one and not the other.",
  };

  const state = { candidates: null, method: "sma", sortKey: "score", sortDir: -1 };

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toFixed(digits === undefined ? 2 : digits);
  }

  function badge(pass, warn) {
    const cls = warn ? "warn" : pass ? "pass" : "fail";
    const label = warn ? "warn" : pass ? "yes" : "no";
    return `<span class="badge ${cls}">${label}</span>`;
  }

  function currentBlock() {
    return state.candidates[state.method];
  }

  function renderMeta() {
    const block = currentBlock();
    const bar = document.getElementById("metaBar");
    bar.innerHTML = `
      <span>As of: <strong>${state.candidates.as_of_trading_date || "n/a"}</strong></span>
      <span>Universe: <strong>${block.universe_size}</strong> equities</span>
      <span>Stage 2 candidates (${state.method.toUpperCase()}): <strong>${block.candidates_count}</strong></span>
      <span>Generated: ${new Date(state.candidates.generated_at).toLocaleString()}</span>
    `;
    document.getElementById("methodBlurb").textContent = METHOD_BLURBS[state.method];
  }

  function sortedStocks() {
    const { sortKey, sortDir } = state;
    const stocks = currentBlock().stocks.slice();
    stocks.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (av < bv) return -1 * sortDir;
      if (av > bv) return 1 * sortDir;
      return 0;
    });
    return stocks;
  }

  function renderTable() {
    const body = document.getElementById("stocksBody");
    body.innerHTML = sortedStocks().map((s) => `
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
        window.location.href =
          `stock.html?symbol=${encodeURIComponent(row.dataset.symbol)}&method=${state.method}`;
      });
    });
  }

  function renderAll() {
    renderMeta();
    renderTable();
  }

  document.querySelectorAll("#stocksTable th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      state.sortDir = state.sortKey === key ? -state.sortDir : -1;
      state.sortKey = key;
      renderTable();
    });
  });

  document.querySelectorAll("#methodTabs .tab-btn").forEach((btn) => {
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

  fetch("data/candidates.json")
    .then((r) => r.json())
    .then((candidates) => {
      state.candidates = candidates;
      renderAll();
    })
    .catch((err) => {
      document.getElementById("metaBar").textContent =
        "No data yet — the daily scrape/screen pipeline hasn't published results.";
      console.error(err);
    });
})();
