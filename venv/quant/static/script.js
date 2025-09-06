document.addEventListener("DOMContentLoaded", function () {
  window.showTab = showTab;
  initApp();
});

let dataTabLoaded = false

function forceRelayout(id) {
  const el = document.getElementById(id);
  if (!el) return;

  // 카드 내부 '콘텐츠 폭' 계산 (padding 제외)
  const parent = el.closest(".chart-card") || el.parentElement || el;
  const cs = getComputedStyle(parent);
  const padX = (parseFloat(cs.paddingLeft) || 0) + (parseFloat(cs.paddingRight) || 0);
  const contentW = Math.max(320, Math.floor(parent.clientWidth - padX));

  // 비율 결정: square-plot → 1:1, data-aspect → 사용자 지정, 기본 0.56(≈16:9)
  const isSquare = el.classList.contains("square-plot");
  const aspectAttr = el.dataset.aspect ? parseFloat(el.dataset.aspect) : null;
  const aspect = isSquare ? 1 : (aspectAttr || 0.56);

  const h = Math.max(240, Math.round(contentW * aspect));

  // ✅ 차트별 margin 커스터마이즈 (특히 x축 라벨 확보)
  const mTop = parseInt(el.dataset.marginT || 10);
  const mRight = parseInt(el.dataset.marginR || 10);
  const mLeft = parseInt(el.dataset.marginL || 40);
  const mBottom = parseInt(el.dataset.marginB || 60);

  Plotly.relayout(el, {
    width: contentW,
    height: h,
    margin: { t: mTop, r: mRight, l: mLeft, b: mBottom },
    xaxis: { automargin: true },   // 라벨 길면 자동 여백 확보
    yaxis: { automargin: true }
  });
}


function initApp() {
  loadPortfolioTable();
  loadPieChart();
  loadAccountChart();
  loadWatchlist();
  setupWatchlistForm();
  setupPrivacyToggle();
}

// -------------------- UI Helpers --------------------
function showTab(tabId) {
  document.querySelectorAll(".tab-content").forEach(tab => (tab.style.display = "none"));
  document.getElementById(tabId).style.display = "block";
  document.querySelectorAll(".nav-link").forEach(link => link.classList.remove("active"));
  document.getElementById(`tab-${tabId}`).classList.add("active");

  if (tabId === "data") {
    if (!dataTabLoaded) {
      loadTreemaps();
      loadExchangeRateChart();
      dataTabLoaded = true;
      setTimeout(() => {
        ["sp500-treemap", "portfolio-treemap", "exchange-rate-chart"].forEach(forceRelayout);
      }, 0);
    } else {
      ["sp500-treemap", "portfolio-treemap", "exchange-rate-chart"].forEach(id => {
        Plotly.Plots.resize(document.getElementById(id));
        forceRelayout(id);
      });
    }
  }
}

window.addEventListener("resize", () => {
  ["sp500-treemap","portfolio-treemap","exchange-rate-chart","profit-chart","pie-chart"]
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) Plotly.Plots.resize(el);
    });
});

function formatMarketCap(value) {
  if (!value) return "N/A";
  const billion = 1_000_000_000;
  const million = 1_000_000;
  if (value >= billion) return (value / billion).toFixed(1) + "B";
  if (value >= million) return (value / million).toFixed(1) + "M";
  return Number(value).toLocaleString();
}

// 공통 fetch 래퍼
function loadJsonAndRender(url, onSuccess, onError) {
  fetch(url)
    .then(res => res.json())
    .then(data => {
      if (data?.error) {
        console.error(`❌ Error from ${url}:`, data.error);
        onError && onError(data.error);
      } else {
        onSuccess(data);
      }
    })
    .catch(err => {
      console.error(`❌ Fetch failed from ${url}:`, err);
      onError && onError(err);
    });
}

// -------------------- Data: Portfolio table --------------------
function loadPortfolioTable() {
  loadJsonAndRender("/get_portfolio_data", data => {
    const tbody = document.getElementById("portfolio-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    data.forEach(row => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.account_number}</td>
        <td>${row.ticker}</td>
        <td>${row.quantity}</td>
        <td>${Number(row.purchase_amount).toLocaleString()} KRW</td>
        <td>${Number(row.evaluation_amount).toLocaleString()} KRW</td>
        <td>${Number(row.profit_loss).toLocaleString()} KRW</td>
        <td style="color:${row.profit_rate >= 0 ? 'red' : 'blue'}; font-weight:bold;">
          ${Number(row.profit_rate).toFixed(2)}%
        </td>`;
      tbody.appendChild(tr);
    });
  });
}

// -------------------- Charts: Pie --------------------
function loadPieChart() {
  loadJsonAndRender("/get_pie_chart_data", data => {
    Plotly.newPlot("pie-chart", [{
      labels: data.labels,
      values: data.values,
      type: "pie"
    }], {margin: {t: 10}}, {responsive: true});

    const totalEl = document.getElementById("total-value");
    if (totalEl) totalEl.innerText = `Total Value: ${data.total_value}`;
  });
}

// -------------------- Charts: Account value & profit --------------------
function loadAccountChart() {
  loadJsonAndRender("/get_account_value_data", data => {
    const latestValue = Number(data.latest_value).toLocaleString();
    const latestProfit = Number(data.latest_profit).toFixed(2);
    const profitColor = data.latest_profit >= 0 ? "red" : "blue";

    const headEl = document.getElementById("total-value");
    if (headEl) {
      headEl.innerHTML = `
        Total Value: ${latestValue} KRW
        <span style="color:${profitColor}; font-weight:bold;">(${latestProfit}%)</span>
      `;
    }

    const totalValueTrace = {
      x: data.dates,
      y: data.total_values,
      type: "scatter",
      mode: "lines+markers",
      name: "Total Account Value",
      yaxis: "y1"
    };
    const profitTrace = {
      x: data.dates,
      y: data.profits,
      type: "scatter",
      mode: "lines",
      name: "Account Profit (%)",
      yaxis: "y2",
      line: { dash: "dot" }
    };
    const layout = {
      title: "Portfolio Total Value & Profit",
      xaxis: { title: "Date" },
      yaxis: { title: "Total Value (KRW)", side: "left", showgrid: false },
      yaxis2: { title: "Profit (%)", overlaying: "y", side: "right", showgrid: false },
      margin: { t: 40, r: 10, l: 50, b: 40 }
    };

    Plotly.newPlot("profit-chart", [totalValueTrace, profitTrace], layout, {responsive: true});
  });
}

// -------------------- Charts: Treemaps (SP500 & Portfolio) --------------------
function loadTreemaps() {
  loadJsonAndRender("/get_treemap_data", data => {
    const fig = {
      type: "treemap",
      labels: data.sectors,
      parents: Array(data.sectors.length).fill(""),
      values: data.changes.map(v => Math.abs(v)),
      textinfo: "label+value",
      marker: { colors: data.changes, colorscale: "RdYlGn", cmin: -3, cmax: 3 }
    };
    Plotly.newPlot("sp500-treemap", [fig], {
      margin: { t: 10, l: 10, r: 10, b: 10 },
      height: 440,
      autosize: true
    }, { responsive: true }).then(() => forceRelayout("sp500-treemap"));
  });

  // 내 포트폴리오 섹터 분포(ETF look-through 반영)
  loadJsonAndRender("/get_portfolio_sector_data", data => {
    const sectors = Object.keys(data);
    const values  = sectors.map(s => data[s].total_value);
    const hover   = sectors.map(s => {
      const stocks = (data[s].stocks || []).map(x => {
        const t = x.ticker || "Unknown";
        return `${t}: $${Number(x.price).toLocaleString()}`;
      }).join("<br>");
      return `${s}<br>${stocks}`;
    });

    Plotly.newPlot("portfolio-treemap", [{
      type: "treemap",
      labels: sectors,
      parents: Array(sectors.length).fill(""),
      values: values,
      text: hover,
      hoverinfo: "text"
    }], {
      margin: { t: 10, l: 10, r: 10, b: 10 },
      height: 440,
      autosize: true
    }, { responsive: true }).then(() => forceRelayout("portfolio-treemap"));
  });
}

function loadExchangeRateChart() {
  loadJsonAndRender("/get_exchange_rate_data", data => {
    Plotly.newPlot("exchange-rate-chart", [{
      x: data.dates,
      y: data.rates,
      type: "scatter",
      mode: "lines",
      name: "USD/KRW",
      connectgaps: false
    }], {
      margin: { t: 10, r: 10, l: 40, b: 40 },
      height: 440,
      autosize: true
    }, { responsive: true }).then(() => forceRelayout("exchange-rate-chart"));
  });
}

// 반응형 리사이즈(보강)
window.addEventListener("resize", () => {
  ["sp500-treemap", "portfolio-treemap", "exchange-rate-chart", "profit-chart", "pie-chart"]
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) Plotly.Plots.resize(el);
    });
});

// -------------------- Watchlist --------------------
function loadWatchlist() {
  loadJsonAndRender("/get_watchlist", data => {
    const ul = document.getElementById("watchlist-items");
    if (!ul) return;
    ul.innerHTML = "";
    (data.watchlist || []).forEach(t => ul.appendChild(createWatchlistItem(t)));
  });
}

function setupWatchlistForm() {
  const form = document.getElementById("watchlist-form");
  if (!form) return;
  form.addEventListener("submit", e => {
    e.preventDefault();
    const input = document.getElementById("ticker");
    const ticker = (input.value || "").trim().toUpperCase();
    if (!ticker) return;
    fetch("/add_watchlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker })
    })
      .then(r => r.json())
      .then(res => {
        if (res.error) return alert(res.error);
        document.getElementById("watchlist-items").appendChild(createWatchlistItem(ticker));
        input.value = "";
      });
  });
}

function createWatchlistItem(ticker) {
  const li = document.createElement("li");
  li.style.display = "flex";
  li.style.justifyContent = "space-between";
  li.style.alignItems = "center";
  li.style.padding = "4px 8px";

  const span = document.createElement("span");
  span.textContent = ticker;
  span.style.cursor = "pointer";
  span.title = "클릭하면 분석 정보를 확인합니다";
  span.addEventListener("click", () => openStockDetail(ticker));

  const del = document.createElement("button");
  del.textContent = "❌";
  del.style.border = "none";
  del.style.background = "none";
  del.style.cursor = "pointer";
  del.style.color = "red";
  del.title = "관심 목록에서 제거";
  del.addEventListener("click", () => {
    if (!confirm(`${ticker} 티커를 관심 목록에서 삭제할까요?`)) return;
    fetch("/remove_watchlist", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker })
    })
      .then(r => r.json())
      .then(res => {
        if (res.error) return alert(res.error);
        li.remove();
      });
  });

  li.appendChild(span);
  li.appendChild(del);
  return li;
}

function openStockDetail(ticker) {
  const panel = document.getElementById("stock-detail-panel");
  const content = document.getElementById("detail-content");
  if (!panel || !content) return;

  content.innerHTML = `<p>🔄 데이터 로딩중...</p>`;
  fetch(`/get_stock_detail_finnhub?ticker=${ticker}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        content.innerHTML = `<p style="color:red;">❌ ${data.error}</p>`;
        return;
      }
      const price = data.price?.c ?? "N/A";
      const marketCap = data.profile?.marketCapitalization ?? "N/A";
      const per = data.metrics?.metric?.peTTM ?? "N/A";
      const dividendYield = (data.metrics?.metric?.currentDividendYieldTTM ?? 0) * 100;

      content.innerHTML = `
        <h5>${data.profile?.name ?? ""} (${ticker})</h5>
        <p><strong>📈 현재가:</strong> $${price}</p>
        <p><strong>💰 시가총액:</strong> ${formatMarketCap(marketCap)}</p>
        <p><strong>📊 PER:</strong> ${per}</p>
        <p><strong>📤 배당률:</strong> ${dividendYield.toFixed(2)}%</p>
      `;

      // KIS 캔들 차트
      const chartDiv = document.createElement("div");
      chartDiv.id = "kis-candle-chart";
      chartDiv.style.height = "500px";
      chartDiv.style.marginTop = "20px";
      chartDiv.innerHTML = `<span id="kis-loading-text">🔄 KIS 캔들차트 로딩중...</span>`;
      content.appendChild(chartDiv);

      fetch(`/get_stock_chart_kis?ticker=${ticker}&exchange=NAS`)
        .then(r => r.json())
        .then(kis => {
          if (kis.error) {
            chartDiv.innerHTML = `<p style="color:red;">KIS 데이터 불러오기 실패: ${kis.error}</p>`;
            return;
          }
          const ohlc = kis.ohlc || [];
          const dates  = ohlc.map(x => `${x.date.slice(0,4)}-${x.date.slice(4,6)}-${x.date.slice(6,8)}`);
          const opens  = ohlc.map(x => x.open);
          const highs  = ohlc.map(x => x.high);
          const lows   = ohlc.map(x => x.low);
          const closes = ohlc.map(x => x.close);
          const vols   = ohlc.map(x => x.volume);

          Plotly.newPlot("kis-candle-chart", [
            { x: dates, open: opens, high: highs, low: lows, close: closes, type: "candlestick", name: "Price", xaxis: "x", yaxis: "y" },
            { x: dates, y: vols, type: "bar", name: "Volume", xaxis: "x", yaxis: "y2", marker: { color: "rgba(128,128,128,0.4)" } }
          ], {
            title: `${ticker} 캔들차트 (KIS API)`,
            xaxis: { title: "날짜", rangeslider: { visible: false } },
            yaxis:  { title: "가격",   domain: [0.3, 1] },
            yaxis2: { title: "거래량", domain: [0, 0.2], showticklabels: true },
            height: 500,
            margin: { t: 40, b: 50 },
            showlegend: false
          }, {responsive: true}).then(() => {
            const loading = document.getElementById("kis-loading-text");
            loading && loading.remove();
          });
        })
        .catch(err => {
          console.error("KIS fetch error:", err);
          chartDiv.innerHTML = `<p style="color:red;">KIS 캔들차트 로드 실패</p>`;
        });
    })
    .catch(err => {
      console.error("Finnhub fetch error:", err);
      content.innerHTML = `<p style="color:red;">❌ Finnhub 데이터 요청 실패</p>`;
    });

  panel.style.display = "block";
}

// -------------------- Privacy toggle --------------------
function setupPrivacyToggle() {
  const btn = document.getElementById("toggle-privacy-btn");
  if (!btn) return;
  let hidden = false;
  btn.addEventListener("click", () => {
    document.querySelectorAll(".privacy-sensitive").forEach(el => {
      el.style.visibility = hidden ? "visible" : "hidden";
    });
    btn.textContent = hidden ? "🔒 정보 숨기기" : "🔓 정보 보이기";
    hidden = !hidden;
  });
}