from notification.notifier import send_discord_notification
# Discord 웹훅 URL 설정
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1330090131343937629/IBysAPiz-dFqruMtLnRVIU19OjPieF8k-izzqCePZjLCyhJwwbMowiqKRsPT5l1ORqrG"

def test_send_notification():
    """
    Discord 알림 테스트 함수
    """
    try:
        send_discord_notification(
            webhook_url="https://discord.com/api/webhooks/1330090131343937629/IBysAPiz-dFqruMtLnRVIU19OjPieF8k-izzqCePZjLCyhJwwbMowiqKRsPT5l1ORqrG",
            title="Trading Alert: AAPL",
            description="AAPL: Golden Cross detected! Check your portfolio for updates.",
            color=16711680,  # 빨간색
            image_url="https://example.com/chart.png",  # 이미지 URL
            link_url="https://www.tradingview.com/symbols/NASDAQ-AAPL/"  # 하이퍼링크 URL
        )
        print("Test notification sent successfully.")
    except Exception as e:
        print(f"Error during notification test: {e}")

# 테스트 실행
if __name__ == "__main__":
    test_send_notification()
