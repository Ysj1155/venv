document.addEventListener("DOMContentLoaded", function () {
    window.showTab = showTab;
    initApp();
});

function initApp() {
    loadPortfolioTable();
    loadPieChart();
    loadAccountChart();
    loadExchangeRateChart();
    loadTreemaps();
    loadWatchlist();
    setupWatchlistForm();
}

function showTab(tabId) {
    document.querySelectorAll(".tab-content").forEach(tab => tab.style.display = "none");
    document.getElementById(tabId).style.display = "block";
    document.querySelectorAll(".nav-link").forEach(link => link.classList.remove("active"));
    document.getElementById(`tab-${tabId}`).classList.add("active");
}

function formatMarketCap(value) {
    if (!value) return "N/A";
    const billion = 1_000_000_000;
    const million = 1_000_000;
    if (value >= billion) return (value / billion).toFixed(1) + "B";
    if (value >= million) return (value / million).toFixed(1) + "M";
    return value.toLocaleString();
}

function interpretRSI(rsi) {
    if (rsi > 70) return "과매수 📈";
    if (rsi < 30) return "과매도 📉";
    return "보통 ⚖️";
}

function loadJsonAndRender(url, onSuccess, onError) {
    fetch(url)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.error(`❌ Error from ${url}:`, data.error);
                if (onError) onError(data.error);
            } else {
                onSuccess(data);
            }
        })
        .catch(error => {
            console.error(`❌ Fetch failed from ${url}:`, error);
            if (onError) onError(error);
        });
}

function loadPortfolioTable() {
    loadJsonAndRender("/get_portfolio_data", data => {
        const tableBody = document.getElementById("portfolio-table-body");
        tableBody.innerHTML = "";
        data.forEach(row => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${row.account_number}</td>
                <td>${row.ticker}</td>
                <td>${row.quantity}</td>
                <td>${row.purchase_amount.toLocaleString()} KRW</td>
                <td>${row.evaluation_amount.toLocaleString()} KRW</td>
                <td>${row.profit_loss.toLocaleString()} KRW</td>
                <td style="color: ${row.profit_rate >= 0 ? 'red' : 'blue'}; font-weight: bold;">
                ${row.profit_rate.toFixed(2)}%</td>`;
            tableBody.appendChild(tr);
        });
    });
}

function loadPieChart() {
    loadJsonAndRender("/get_pie_chart_data", data => {
        Plotly.newPlot("pie-chart", [{
            labels: data.labels,
            values: data.values,
            type: "pie"
        }]);

        let totalValueElement = document.getElementById("total-value");
        if (totalValueElement) {
            totalValueElement.innerText = `Total Value: ${data.total_value}`;
        }
    });
}

function loadAccountChart() {
    loadJsonAndRender("/get_account_value_data", data => {
        let totalValueElement = document.getElementById("total-value");
        let latestValue = data.latest_value.toLocaleString();
        let latestProfit = data.latest_profit.toFixed(2);
        let profitColor = latestProfit >= 0 ? "red" : "blue";
        if (totalValueElement) {
            totalValueElement.innerHTML = `
                Total Value: ${latestValue} KRW
                <span style="color: ${profitColor}; font-weight: bold;">
                    (${latestProfit}%)
                </span>
            `;
        }
        let totalValueTrace = {
            x: data.dates,
            y: data.total_values,
            type: "scatter",
            mode: "lines+markers",
            name: "Total Account Value",
            yaxis: "y1"
        };

        let profitTrace = {
            x: data.dates,
            y: data.profits,
            type: "scatter",
            mode: "lines",
            name: "Account Profit (%)",
            yaxis: "y2",
            line: { color: "red", dash: "dot" }
        };

        let layout = {
            title: "Portfolio Total Value & Profit",
            xaxis: { title: "Date" },
            yaxis: { title: "Total Value (KRW)", side: "left", showgrid: false },
            yaxis2: {
                title: "Profit (%)",
                overlaying: "y",
                side: "right",
                showgrid: false
            }
        };

        Plotly.newPlot("profit-chart", [totalValueTrace, profitTrace], layout);
    });
}

function loadExchangeRateChart() {
    loadJsonAndRender("/get_exchange_rate_data", data => {
        Plotly.newPlot("exchange-rate-chart", [{
            x: data.dates,
            y: data.rates,
            type: "scatter",
            mode: "lines",
            name: "USD/KRW Exchange Rate",
            connectgaps: false
        }]);
    });
}
function loadTreemaps() {
    loadJsonAndRender("/get_treemap_data", data => {
        let fig_sp500 = {
            type: "treemap",
            labels: data.sectors,
            parents: Array(data.sectors.length).fill(""),
            values: data.changes.map(change => Math.abs(change)),
            textinfo: "label+value",
            marker: {
                colors: data.changes,
                colorscale: "RdYlGn",
                cmin: -3, cmax: 3
            }
        };
        Plotly.newPlot("sp500-treemap", [fig_sp500], {
            title: "S&P 500 섹터별 변동률",
            height: 600, width: 600
        });
    });
    loadJsonAndRender("/get_portfolio_sector_data", data => {
        let sectors = Object.keys(data);
        let values = sectors.map(sector => data[sector].total_value);
        let hover_texts = sectors.map(sector => {
            let stocks = data[sector].stocks.map(s => {
                let ticker = s.ticker ? s.ticker : "Unknown";
                return `${ticker}: $${s.price.toLocaleString()}`;
            }).join("<br>");
            return `${stocks}`;
        });
        let treemapData = [{
            type: "treemap",
            labels: sectors,
            parents: Array(sectors.length).fill(""),
            values: values,
            text: hover_texts,
            hoverinfo: "text"
        }];
        Plotly.newPlot("portfolio-treemap", treemapData, {
            title: "내 포트폴리오 섹터 분포"
        });
    });
}
function loadWatchlist() {
    loadJsonAndRender("/get_watchlist", data => {
        const watchlistItems = document.getElementById("watchlist-items");
        watchlistItems.innerHTML = "";
        data.watchlist.forEach(ticker => {
            const li = createWatchlistItem(ticker);
            watchlistItems.appendChild(li);
        });
    });
}

function setupWatchlistForm() {
    document.getElementById("watchlist-form").addEventListener("submit", function(event) {
        event.preventDefault();
        const ticker = document.getElementById("ticker").value.trim().toUpperCase();
        if (!ticker) return;
        fetch("/add_watchlist", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticker: ticker })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
            } else {
                const listItem = createWatchlistItem(ticker);
                document.getElementById("watchlist-items").appendChild(listItem);
                document.getElementById("ticker").value = "";
            }
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
    span.addEventListener("click", () => {
        const panel = document.getElementById("stock-detail-panel");
        const content = document.getElementById("detail-content");
        content.innerHTML = `<p>🔄 데이터 로딩중...</p>`;
        fetch(`/get_stock_detail_finnhub?ticker=${ticker}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    content.innerHTML = `<p style=\"color:red;\">❌ ${data.error}</p>`;
                    return;
                }
                const price = data.price?.c || 'N/A';
                const marketCap = data.profile?.marketCapitalization || 'N/A';
                const per = data.metrics?.metric?.peTTM || 'N/A';
                const dividendYield = data.metrics?.metric?.currentDividendYieldTTM || 0;
                content.innerHTML = `
                    <h5>${data.profile?.name} (${ticker})</h5>
                    <p><strong>📈 현재가:</strong> $${price}</p>
                    <p><strong>💰 시가총액:</strong> ${formatMarketCap(marketCap)}</p>
                    <p><strong>📊 PER:</strong> ${per}</p>
                    <p><strong>📤 배당률:</strong> ${(dividendYield * 100).toFixed(2)}%</p>
                `;

                const kisChartDiv = document.createElement("div");
                kisChartDiv.id = "kis-candle-chart";
                kisChartDiv.style.height = "500px";
                kisChartDiv.style.marginTop = "20px";
                kisChartDiv.innerHTML = "🔄 KIS 캔들차트 로딩중...";
                content.appendChild(kisChartDiv);

                fetch(`/get_stock_chart_kis?ticker=${ticker}&exchange=NAS`)
                    .then(res => res.json())
                    .then(kisData => {
                        if (kisData.error) {
                            console.error("KIS 데이터 불러오기 실패", kisData.error);
                            kisChartDiv.innerHTML = `<p style=\"color:red;\">KIS 데이터 불러오기 실패: ${kisData.error}</p>`;
                            return;
                        }

                        const ohlc = kisData.ohlc;
                        const dates = ohlc.map(x => x.date);
                        const opens = ohlc.map(x => x.open);
                        const highs = ohlc.map(x => x.high);
                        const lows = ohlc.map(x => x.low);
                        const closes = ohlc.map(x => x.close);
                        const volumes = ohlc.map(x => x.volume);

                        Plotly.newPlot("kis-candle-chart", [
                            {
                                x: dates,
                                open: opens,
                                high: highs,
                                low: lows,
                                close: closes,
                                type: 'candlestick',
                                name: 'Price',
                                xaxis: 'x',
                                yaxis: 'y'
                            },
                            {
                                x: dates,
                                y: volumes,
                                type: 'bar',
                                name: 'Volume',
                                xaxis: 'x',
                                yaxis: 'y2',
                                marker: { color: "rgba(128,128,128,0.4)" }
                            }
                        ], {
                            title: `${ticker} 캔들차트 (KIS API)`,
                            xaxis: {
                                title: '날짜',
                                rangeslider: { visible: false }
                            },
                            yaxis: {
                                title: '가격',
                                domain: [0.3, 1]
                            },
                            yaxis2: {
                                title: '거래량',
                                domain: [0, 0.2],
                                showticklabels: true
                            },
                            height: 500,
                            margin: { t: 40, b: 50 },
                            showlegend: false
                        }).then(() => {
                            //kisChartDiv.innerHTML = "";
                        });
                    })
                    .catch(err => {
                        console.error("KIS fetch error:", err);
                        kisChartDiv.innerHTML = `<p style=\"color:red;\">KIS 캔들차트 로드 실패</p>`;
                    });
            })
            .catch(error => {
                console.error("Finnhub fetch error:", error);
                content.innerHTML = `<p style=\"color:red;\">❌ Finnhub 데이터 요청 실패</p>`;
            });
        panel.style.display = "block";
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "❌";
    deleteBtn.style.border = "none";
    deleteBtn.style.background = "none";
    deleteBtn.style.cursor = "pointer";
    deleteBtn.style.color = "red";
    deleteBtn.title = "관심 목록에서 제거";

    deleteBtn.addEventListener("click", () => {
        if (confirm(`${ticker} 티커를 관심 목록에서 삭제할까요?`)) {
            fetch("/remove_watchlist", {
                method: "DELETE",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ticker: ticker})
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        li.remove();
                    }
                });
        }
    });
    li.appendChild(span);
    li.appendChild(deleteBtn);
    return li;
}