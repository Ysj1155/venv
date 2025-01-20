document.addEventListener("DOMContentLoaded", function () {
    // 원형 다이어그램 Placeholder 데이터
    const pieData = {
        labels: ["Cash", "Stock A", "Stock B", "Stock C"],
        values: [40, 30, 20, 10],
        type: "pie"
    };

    // 원형 다이어그램 생성
    Plotly.newPlot("pie-chart", [pieData]);

    // 총액 계산 및 표시
    const totalValue = pieData.values.reduce((acc, val) => acc + val, 0);
    document.getElementById("total-value").innerText = `Total Value: $${totalValue}`;

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