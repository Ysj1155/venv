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

    // 포트폴리오 평가금액 그래프
    fetch("/get_total_value_data")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error("Error fetching total value data:", data.error);
                return;
            }

            Plotly.newPlot("profit-chart", [{
                x: data.dates,
                y: data.total_values,
                type: "scatter",
                mode: "lines+markers",
                name: "Total Account Value"
            }]);
        })
        .catch(error => console.error("Error fetching total value data:", error));

    // 환율 추세 데이터 로드
    fetch("/get_exchange_rate_data")
    .then(response => response.json())
    .then(data => {
        console.log("🚀 Fetched exchange rate data:", data);  // ✅ JSON 응답 확인

        if (data.error) {
            console.error("Exchange rate data error:", data.error);
            return;
        }

        // ✅ NaN 값이 포함된 데이터 확인
        data.rates.forEach((rate, index) => {
            if (rate === null) {
                console.warn(`⚠️ Null value detected at index ${index}, date: ${data.dates[index]}`);
            }
        });

        let validDates = data.dates;
        let validRates = data.rates;

        console.log("📌 Final Data for Plotly:", validDates, validRates);

        // ✅ Plotly 그래프 생성 (끊어지는 데이터 적용)
        Plotly.newPlot("exchange-rate-chart", [{
            x: validDates,
            y: validRates,
            type: "scatter",
            mode: "lines",
            name: "USD/KRW Exchange Rate",
            connectgaps: false  // ✅ None 값이 있으면 그래프를 끊어주도록 설정
        }]);
    })
    .catch(error => console.error("Error fetching exchange rate data:", error));


    // 관심 종목 추가 기능
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
});
