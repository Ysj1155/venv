document.addEventListener("DOMContentLoaded", function () {
    // 원형 다이어그램 데이터 로드
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
    });

    // 전체 자산 수익률 그래프 데이터 로드
    fetch("/get_graph_data")
        .then(response => response.json())
        .then(data => {
            Plotly.newPlot("profit-chart", [{
                x: data.dates,
                y: data.profits,
                type: "scatter",
                mode: "lines+markers",
                name: "Cumulative Profit"
            }]);
        });

    // 환율 추세 데이터 로드
    fetch("/get_exchange_rate_data")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Exchange rate data error:", data.error);
                return;
            }

            // 환율 추세 그래프 생성
            Plotly.newPlot("exchange-rate-chart", [{
                x: data.dates,
                y: data.rates,
                type: "scatter",
                mode: "lines+markers",
                name: "USD to KRW Trend"
            }]);
        })
        .catch(error => console.error("Error fetching exchange rate data:", error));

    document.addEventListener("DOMContentLoaded", function () {
    // 날짜별 계좌 총 평가금액 그래프
    fetch("/get_total_value_data")
        .then(response => response.json())
        .then(data => {
            Plotly.newPlot("total-value-chart", [{
                x: data.dates,
                y: data.total_values,
                type: "scatter",
                mode: "lines+markers",
                name: "Total Account Value"
            }]);
        })
        .catch(error => console.error("Error fetching total value data:", error));
});
    // 폼 제출 처리
    document.getElementById("stock-form").addEventListener("submit", function (event) {
        event.preventDefault();
        const formData = new FormData(event.target);
        fetch("/add_stock", {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            location.reload();
        });
    });
});
