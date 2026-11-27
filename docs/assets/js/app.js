(function () {
  // Columns that read naturally ascending on first click; everything else starts descending.
  const ASCENDING_FIRST = new Set([
    "rank", "order", "symbol", "sector", "pct_from_52w_high", "screener_rank",
    "status_order", "dist_to_pivot_pct", "tightness_pct", "volume_dry_up_ratio", "stop",
  ]);

  const SETUP_STATUS = {
    breakout: { label: "Breakout", cls: "pass", title: "Closed above the pivot on strong volume" },
    breakout_low_volume: { label: "Breakout · low vol", cls: "warn", title: "Closed above the pivot, but volume < 1.5x average" },
    ready: { label: "Ready", cls: "ready", title: "Valid VCP within 5% below the pivot" },
    forming: { label: "Forming", cls: "neutral", title: "Valid VCP, more than 5% below the pivot" },
  };
  const SETUP_STATUS_ORDER = ["breakout", "breakout_low_volume", "ready", "forming"];
  const CRITERIA_SHORT = {
    price_above_150_200: "price > AMA 150/200",
    price_above_ma20: "price > AMA 20",
    ma200_trending_up: "AMA 200 rising",
    price_above_all_ma: "price > all AMAs",
    price_above_ma50: "price > AMA 50",
    above_52w_low_25pct: "25% above 52w low",
    within_25pct_52w_high: "within 25% of 52w high",
    rs_top_30pct: "RS top 30%",
  };

  const CATEGORY_LABELS = { volume: "Vol", transactions: "Txn", turnover: "T/O" };
  const CATEGORY_TITLES = { volume: "Top 10 by volume", transactions: "Top 10 by transactions", turnover: "Top 10 by turnover" };

  function fmt(value, digits) {
    if (value === null || value === undefined || Number.isNaN(value)) return "—";
    return Number(value).toFixed(digits === undefined ? 2 : digits);
  }

  function fmtInt(value) {
    if (value === null || value === undefined) return "—";
    return Math.round(value).toLocaleString("en-IN");
  }

  // NEPSE convention: turnover in crore (1 Cr = 10,000,000) or lakh (1 L = 100,000) rupees.
  function fmtRupees(value) {
    if (value === null || value === undefined) return "—";
    if (value >= 1e7) return `Rs ${(value / 1e7).toFixed(2)} Cr`;
    if (value >= 1e5) return `Rs ${(value / 1e5).toFixed(2)} L`;
    return `Rs ${fmtInt(value)}`;
  }

  function badge(pass, warn) {
    const cls = warn ? "warn" : pass ? "pass" : "fail";
    const label = warn ? "warn" : pass ? "yes" : "no";
    return `<span class="badge ${cls}">${label}</span>`;
  }

  function sortRows(rows, key, dir) {
    return rows.slice().sort((a, b) => {
      const av = a[key];
      const bv = b[key];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }

  function linkRowsToStockPage(body) {
    body.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        window.location.href = `stock.html?symbol=${encodeURIComponent(row.dataset.symbol)}`;
      });
    });
  }

  // Wires sortable headers; `table.sortKey/sortDir` hold the current order.
  function makeSortable(tableId, table) {
    document.querySelectorAll(`#${tableId} th[data-key]`).forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        table.sortDir = table.sortKey === key ? -table.sortDir : (ASCENDING_FIRST.has(key) ? 1 : -1);
        table.sortKey = key;
        table.render();
      });
    });
  }

  // ---- Stage 2 screener tab -------------------------------------------------------

  const screener = { data: null, sortKey: "rank", sortDir: 1 };

  screener.render = function () {
    const data = screener.data;
    if (!data) return;
    document.getElementById("metaBar").innerHTML = `
      <span>As of: <strong>${data.as_of_trading_date || "n/a"}</strong></span>
      <span>Universe: <strong>${data.universe_size}</strong> equities</span>
      <span>Stage 2 candidates: <strong>${data.candidates_count}</strong></span>
      <span>Generated: ${new Date(data.generated_at).toLocaleString()}</span>
    `;
    const body = document.getElementById("stocksBody");
    body.innerHTML = sortRows(data.stocks, screener.sortKey, screener.sortDir).map((s) => `
      <tr data-symbol="${s.symbol}">
        <td class="rank">${s.rank ?? "—"}</td>
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
    linkRowsToStockPage(body);
  };

  // ---- Setups & breakouts tab -------------------------------------------------------

  const setups = { data: null, rows: [], sortKey: "order", sortDir: 1 };

  setups.render = function () {
    const data = setups.data;
    const meta = document.getElementById("setupsMeta");
    if (!data) {
      meta.textContent = "No setup data published yet.";
      return;
    }
    const c = data.counts;
    meta.innerHTML = `
      <span>Session: <strong>${data.as_of_trading_date || "n/a"}</strong></span>
      <span>Breakouts: <strong>${c.breakout}</strong>${c.breakout_low_volume ? ` (+${c.breakout_low_volume} low volume)` : ""}</span>
      <span>Ready: <strong>${c.ready}</strong></span>
      <span>Forming: <strong>${c.forming}</strong></span>
    `;
    const body = document.getElementById("setupsBody");
    if (!setups.rows.length) {
      body.innerHTML = `<tr class="empty"><td colspan="13">No VCP setups or breakouts among Trend Template stocks this session.</td></tr>`;
      return;
    }
    body.innerHTML = sortRows(setups.rows, setups.sortKey, setups.sortDir).map((s) => {
      const st = SETUP_STATUS[s.status];
      const footprint = s.contractions_pct && s.contractions_pct.length
        ? `${s.t_count}T · ${s.contractions_pct.map((d) => fmt(d, 1)).join(" → ")}%`
        : (s.breakout_type === "52w_high" ? "new 52w high" : "—");
      const missing = (s.missing_criteria || []).map((k) => CRITERIA_SHORT[k] || k).join(", ");
      const stage2 = `<span class="${s.is_candidate ? "candidate" : ""}" title="${missing ? "Fails: " + missing : "Passes all 8"}">#${s.screener_rank} · ${s.score}/8</span>`;
      const volToday = s.breakout_volume_ratio === null ? "—" : `${fmt(s.breakout_volume_ratio)}×`;
      const dry = s.volume_dry_up_ratio === null || s.volume_dry_up_ratio === undefined ? "—"
        : `<span class="${s.volume_dry_up_ratio <= 0.8 ? "good" : ""}">${fmt(s.volume_dry_up_ratio)}×</span>`;
      return `
        <tr data-symbol="${s.symbol}">
          <td class="rank">${s.order}</td>
          <td>${s.symbol}</td>
          <td><span class="badge ${st.cls}" title="${st.title}">${st.label}</span></td>
          <td>${fmt(s.close)}</td>
          <td><strong>${fmt(s.pivot)}</strong></td>
          <td class="${s.dist_to_pivot_pct <= 0 ? "up" : ""}">${s.dist_to_pivot_pct > 0 ? "−" : "+"}${fmt(Math.abs(s.dist_to_pivot_pct))}%</td>
          <td class="footprint">${footprint}</td>
          <td>${s.base_length ? `${s.base_length}d` : "—"}</td>
          <td>${s.tightness_pct === null || s.tightness_pct === undefined ? "—" : fmt(s.tightness_pct, 1) + "%"}</td>
          <td>${dry}</td>
          <td>${volToday}</td>
          <td>${fmt(s.stop)} <span class="muted">(${fmt(s.risk_pct, 1)}%)</span></td>
          <td>${stage2}</td>
        </tr>`;
    }).join("");
    linkRowsToStockPage(body);
  };

  // ---- Market activity tab --------------------------------------------------------

  const activity = { data: null, rows: [], sortKey: "order", sortDir: 1 };

  function withRank(value, rank) {
    return rank ? `${value} <span class="top-rank" title="Rank in this top 10">#${rank}</span>` : value;
  }

  activity.render = function () {
    const data = activity.data;
    const meta = document.getElementById("activityMeta");
    if (!data) {
      meta.textContent = "No market activity data published yet.";
      return;
    }
    const inAll = activity.rows.filter((r) => r.list_count === data.categories.length).length;
    meta.innerHTML = `
      <span>Session: <strong>${data.as_of_trading_date || "n/a"}</strong></span>
      <span>Unique stocks: <strong>${data.stocks.length}</strong> (from ${data.categories.length} × top ${data.top_n})</span>
      <span>In all ${data.categories.length} lists: <strong>${inAll}</strong></span>
    `;
    const body = document.getElementById("activityBody");
    body.innerHTML = sortRows(activity.rows, activity.sortKey, activity.sortDir).map((s) => {
      const changeCls = s.change_pct > 0 ? "up" : s.change_pct < 0 ? "down" : "";
      const chips = data.categories
        .filter((c) => s.ranks[c])
        .map((c) => `<span class="chip chip-${c}" title="${CATEGORY_TITLES[c]}">${CATEGORY_LABELS[c]}</span>`)
        .join("");
      const stage2 = s.screener_rank
        ? `<span class="${s.is_candidate ? "candidate" : ""}" title="Screener rank · Trend Template score">#${s.screener_rank} · ${s.score}/8</span>`
        : "—";
      return `
        <tr data-symbol="${s.symbol}">
          <td class="rank">${s.order}</td>
          <td>${s.symbol}</td>
          <td>${s.sector || "—"}</td>
          <td>${fmt(s.close)}</td>
          <td class="${changeCls}">${s.change_pct === null ? "—" : `${s.change_pct > 0 ? "+" : ""}${fmt(s.change_pct)}%`}</td>
          <td>${withRank(fmtInt(s.volume), s.ranks.volume)}</td>
          <td>${withRank(fmtInt(s.transactions), s.ranks.transactions)}</td>
          <td>${withRank(fmtRupees(s.turnover), s.ranks.turnover)}</td>
          <td class="chips">${chips}</td>
          <td>${stage2}</td>
        </tr>`;
    }).join("");
    linkRowsToStockPage(body);
  };

  // ---- Tabs (hash-based, so links and the browser Back button keep the tab) -----

  const TABS = ["screener", "setups", "activity"];

  function showTab(name) {
    const tab = TABS.includes(name) ? name : "screener";
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      const active = btn.dataset.tab === tab;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
    TABS.forEach((t) => { document.getElementById(`tab-${t}`).hidden = t !== tab; });
  }

  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      history.replaceState(null, "", btn.dataset.tab === "screener" ? "#" : `#${btn.dataset.tab}`);
      showTab(btn.dataset.tab);
    });
  });
  window.addEventListener("hashchange", () => showTab(location.hash.slice(1)));
  showTab(location.hash.slice(1));

  makeSortable("stocksTable", screener);
  makeSortable("activityTable", activity);
  makeSortable("setupsTable", setups);

  fetch("data/setups.json")
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      setups.data = data;
      setups.rows = data
        ? data.stocks.map((s, i) => ({ ...s, order: i + 1, status_order: SETUP_STATUS_ORDER.indexOf(s.status) }))
        : [];
      setups.render();
    })
    .catch((err) => {
      setups.render();
      console.error(err);
    });

  fetch("data/candidates.json")
    .then((r) => r.json())
    .then((data) => {
      screener.data = data;
      screener.render();
    })
    .catch((err) => {
      document.getElementById("metaBar").textContent =
        "No data yet — the daily scrape/screen pipeline hasn't published results.";
      console.error(err);
    });

  fetch("data/market_activity.json")
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      activity.data = data;
      activity.rows = data
        ? data.stocks.map((s, i) => ({ ...s, order: i + 1, list_count: s.categories.length }))
        : [];
      activity.render();
    })
    .catch((err) => {
      activity.render();
      console.error(err);
    });
})();
