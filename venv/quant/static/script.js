document.addEventListener("DOMContentLoaded", function () {
    function showTab(tabId) {
        document.querySelectorAll(".tab-content").forEach(tab => tab.style.display = "none");
        document.getElementById(tabId).style.display = "block";

        document.querySelectorAll(".nav-link").forEach(link => link.classList.remove("active"));
        document.getElementById(`tab-${tabId}`).classList.add("active");
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
            if (!tableBody) {
                console.error("Error: 'portfolio-table-body' element is missing!");
                return;
            }
            tableBody.innerHTML = ""; // 기존 데이터 초기화
            data.forEach(row => {
                    let tr = document.createElement("tr");

                    let profitLossColor = "black";  // 기본 색상
                    let profitRateColor = "black";

                    // ✅ 기준 데이터와 비교하여 색상 변경
                    if (referenceDataMap[row.ticker]) {
                        let refProfitLoss = referenceDataMap[row.ticker].profit_loss;
                        let refProfitRate = referenceDataMap[row.ticker].profit_rate;

                        if (row.profit_loss > refProfitLoss) {
                            profitLossColor = "red";  // 이득 증가
                        } else if (row.profit_loss < refProfitLoss) {
                            profitLossColor = "blue"; // 손해 증가
                        }

                        if (row.profit_rate > refProfitRate) {
                            profitRateColor = "red";  // 손익률 증가
                        } else if (row.profit_rate < refProfitRate) {
                            profitRateColor = "blue"; // 손익률 감소
                        }
                    }
                tr.innerHTML = `
                    <td>${row.account_number}</td>
                    <td>${row.ticker}</td>
                    <td>${row.quantity}</td>
                    <td>${row.purchase_amount.toLocaleString()} KRW</td>
                    <td>${row.evaluation_amount.toLocaleString()} KRW</td>
                    <td>${row.profit_loss.toLocaleString()} KRW</td>
                    <td>${row.profit_rate.toFixed(2)}%</td>
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

    // ✅ 관심 종목 추가 기능
    document.getElementById("watchlist-form").addEventListener("submit", function(event) {
        event.preventDefault();
        const ticker = document.getElementById("ticker").value.trim();

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
                    const listItem = document.createElement("li");
                    listItem.textContent = ticker;
                    document.getElementById("watchlist-items").appendChild(listItem);
                    document.getElementById("ticker").value = "";
                }
            });
        }
    });
});
