document.addEventListener("DOMContentLoaded", function () {
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

function createWatchlistItem(ticker) {
    const li = document.createElement("li");
    li.style.display = "flex";
    li.style.justifyContent = "space-between";
    li.style.alignItems = "center";
    li.style.padding = "4px 8px";
    // 티커 텍스트
    const span = document.createElement("span");
    span.textContent = ticker;
        span.style.cursor = "pointer";
    span.title = "클릭하면 분석 정보를 확인합니다";

    // ✅ 클릭 시 분석 정보 로드
    span.addEventListener("click", () => {
        fetch(`/get_stock_detail_yf?ticker=${ticker}`)
            .then(response => response.json())
            .then(data => {
                const panel = document.getElementById("stock-detail-panel");
                const content = document.getElementById("detail-content");

                if (data.error) {
                    content.innerHTML = `<p style="color:red;">❌ ${data.error}</p>`;
                } else {
                    content.innerHTML = `
                        <h5>${data.name} (${data.ticker})</h5>
                        <p><strong>📈 현재가:</strong> $${data.price}</p>
                        <p><strong>💰 시가총액:</strong> ${formatMarketCap(data.marketCap)}</p>
                        <p><strong>📊 PER:</strong> ${data.per || 'N/A'}</p>
                        <p><strong>📤 배당률:</strong> ${(data.dividendYield * 100 || 0).toFixed(2)}%</p>
                        <p><strong>📍 RSI:</strong> ${data.RSI} → ${interpretRSI(data.RSI)}</p>
                        <p><strong>📉 골든크로스:</strong> ${data.golden_cross ? "✅ 있음" : "❌ 없음"}</p>
                    `;
                    const chartDiv = document.createElement("div");
                    chartDiv.id = "stock-price-chart";
                    chartDiv.style.height = "400px";
                    chartDiv.style.marginTop = "20px";
                    content.appendChild(chartDiv);

                    const traceClose = {
                        x: data.chart_data.dates,
                        y: data.chart_data.close,
                        name: "종가",
                        mode: "lines",
                        line: { color: "black" }
                    };
                    const traceMA5 = {
                        x: data.chart_data.dates,
                        y: data.chart_data.MA5,
                        name: "MA5",
                        mode: "lines",
                        line: { color: "blue", dash: "dot" }
                    };
                    const traceMA20 = {
                        x: data.chart_data.dates,
                        y: data.chart_data.MA20,
                        name: "MA20",
                        mode: "lines",
                        line: { color: "red", dash: "dash" }
                    };

                    Plotly.newPlot("stock-price-chart", [traceClose, traceMA5, traceMA20], {
                        title: `${data.ticker} 주가 차트 (최근 3개월)`,
                        xaxis: { title: "날짜" },
                        yaxis: { title: "가격 (USD)" }
                    });
                    panel.style.display = "block";
                }
            });
    });
    // ❌ 삭제 버튼
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
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticker: ticker })
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
    window.showTab = showTab; // 글로벌 함수 등록
    // portfolio_data.csv 테이블
    fetch("/get_portfolio_data")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error fetching portfolio data:", data.error);
                return;
            }

            const tableBody = document.getElementById("portfolio-table-body");
            tableBody.innerHTML = ""; // 기존 데이터 초기화
            data.forEach(row => {
                    let tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${row.account_number}</td>
                    <td>${row.ticker}</td>
                    <td>${row.quantity}</td>
                    <td>${row.purchase_amount.toLocaleString()} KRW</td>
                    <td>${row.evaluation_amount.toLocaleString()} KRW</td>
                    <td>${row.profit_loss.toLocaleString()} KRW</td>
                    <td style="color: ${row.profit_rate >= 0 ? 'red' : 'blue'}; font-weight: bold;">
                    ${row.profit_rate.toFixed(2)}%
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        })
        .catch(error => console.error("Error fetching portfolio data:", error));

    // ✅ 원형 다이어그램 데이터 로드
    fetch("/get_pie_chart_data")
        .then(response => response.json())
        .then(data => {
            Plotly.newPlot("pie-chart", [{
                labels: data.labels,
                values: data.values,
                type: "pie"
            }]);

            let totalValueElement = document.getElementById("total-value");
            if (totalValueElement) {
                totalValueElement.innerText = `Total Value: ${data.total_value}`;
            }
        })
        .catch(error => console.error("Error fetching pie chart data:", error));

    // ✅ 포트폴리오 평가금액 + 수익률 그래프 (겹쳐서 표시)
    fetch("/get_account_value_data")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error fetching account value data:", data.error);
                return;
            }
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
        })
        .catch(error => console.error("Error fetching account value data:", error));

    // ✅ 환율 추세 데이터 로드
    fetch("/get_exchange_rate_data")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Exchange rate data error:", data.error);
                return;
            }

            Plotly.newPlot("exchange-rate-chart", [{
                x: data.dates,
                y: data.rates,
                type: "scatter",
                mode: "lines",
                name: "USD/KRW Exchange Rate",
                connectgaps: false
            }]);
        })
        .catch(error => console.error("Error fetching exchange rate data:", error));

    // ✅ Treemap 데이터 로드 함수
    function loadTreemapData() {
        fetch("/get_treemap_data")
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Error fetching Treemap data:", data.error);
                    return;
                }

                let sp500Element = document.getElementById("sp500-treemap");
                if (!sp500Element) {
                    console.error("Error: 'sp500-treemap' element is missing!");
                    return;
                }

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
            })
            .catch(error => console.error("Error fetching Treemap data:", error));

        fetch("/get_portfolio_sector_data")
            .then(response => response.json())
            .then(data => {
                let portfolioElement = document.getElementById("portfolio-treemap");
                if (!portfolioElement) {
                    console.error("Error: 'portfolio-treemap' element is missing!");
                    return;
                }

                let sectors = Object.keys(data);
                let values = sectors.map(sector => data[sector].total_value);
                let hover_texts = sectors.map(sector => {
                    let stocks = data[sector].stocks.map(s => {
                        let ticker = s.ticker ? s.ticker : "Unknown";  // ✅ NaN 방지
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
            })
            .catch(error => console.error("Error fetching portfolio sector data:", error));
    }

    // ✅ 페이지 로드 시 실행
    loadTreemapData();
    // ✅ 페이지 처음 로드 시 기존 관심 종목 불러오기
    fetch("/get_watchlist")
        .then(response => response.json())
        .then(data => {
            const watchlistItems = document.getElementById("watchlist-items");
            watchlistItems.innerHTML = "";
            data.watchlist.forEach(ticker => {
                const li = createWatchlistItem(ticker);
                watchlistItems.appendChild(li);
            });
        })
        .catch(error => console.error("Error loading watchlist:", error));

    // ✅ 관심 종목 추가 기능
    document.getElementById("watchlist-form").addEventListener("submit", function(event) {
        event.preventDefault();
        const ticker = document.getElementById("ticker").value.trim().toUpperCase();

        if (ticker) {
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
        }
    });
});