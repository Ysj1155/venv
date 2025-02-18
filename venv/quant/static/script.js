document.addEventListener("DOMContentLoaded", function () {
    function showTab(tabId) {
        document.querySelectorAll(".tab-content").forEach(tab => tab.style.display = "none");
        document.getElementById(tabId).style.display = "block";

        document.querySelectorAll(".nav-link").forEach(link => link.classList.remove("active"));
        document.getElementById(`tab-${tabId}`).classList.add("active");
    }

    window.showTab = showTab; // 글로벌 함수 등록
    });
    // ✅ 원형 다이어그램 데이터 로드
    fetch("/get_pie_chart_data")
        .then(response => response.json())
        .then(data => {
            Plotly.newPlot("pie-chart", [{
                labels: data.labels,
                values: data.values,
                type: "pie"
            }]);

            // 총액 표시
            document.getElementById("total-value").innerText = `Total Value: ${data.total_value}`;
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
                yaxis: "y1"  // ✅ 1차 Y축
            };

            let profitTrace = {
                x: data.dates,
                y: data.profits,
                type: "scatter",
                mode: "lines",
                name: "Account Profit (%)",
                yaxis: "y2",  // ✅ 2차 Y축 (수익률)
                line: { color: "red", dash: "dot" }  // ✅ 스타일 적용 (점선)
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

    // ✅ Treemap 데이터 로드
function loadTreemapData() {
        // ✅ S&P 500 섹터 Treemap
        fetch("/get_treemap_data")
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Error fetching Treemap data:", data.error);
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
                    height: 600, width: 600  // ✅ 크기 조정
                });
            })
            .catch(error => console.error("Error fetching Treemap data:", error));

        // ✅ 내 포트폴리오 섹터 Treemap
        fetch("/get_portfolio_sector_data")
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Error fetching Portfolio Treemap data:", data.error);
                    return;
                }

                let fig_portfolio = {
                    type: "treemap",
                    labels: data.sectors,
                    parents: Array(data.sectors.length).fill(""),
                    values: data.values,
                    textinfo: "label+value",
                    marker: {
                        colorscale: "Blues"
                    }
                };

                Plotly.newPlot("portfolio-treemap", [fig_portfolio], {
                    title: "내 포트폴리오 섹터 분포",
                    height: 600, width: 600  // ✅ 크기 조정
                });
            })
            .catch(error => console.error("Error fetching Portfolio Treemap data:", error));
    }

    // ✅ Treemap 데이터 로드
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
                    document.getElementById("watchlist").appendChild(listItem);
                    document.getElementById("ticker").value = "";
                }
            });
        }
    });