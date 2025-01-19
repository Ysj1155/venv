# tests/test_notifier.py
from notification.notifier import send_discord_notification
import os

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1330090131343937629/IBysAPiz-dFqruMtLnRVIU19OjPieF8k-izzqCePZjLCyhJwwbMowiqKRsPT5l1ORqrG"

def test_send_discord_notification():
    """
    Discord 알림 전송 테스트.
    """
    webhook_url = "https://discord.com/api/webhooks/1330090131343937629/IBysAPiz-dFqruMtLnRVIU19OjPieF8k-izzqCePZjLCyhJwwbMowiqKRsPT5l1ORqrG"  # 웹훅 URL 설정
    title = "Test Notification"
    description = "This is a test message sent from the notifier module."
    
    try:
        send_discord_notification(webhook_url, title, description)
        print("Discord notification test passed.")
    except Exception as e:
        print(f"Discord notification test failed: {e}")

if __name__ == "__main__":
    test_send_discord_notification()

OWNED_STOCKS = {
    'DBC': {'quantity': 8, 'avg_price': 22.2550},
}
INTERESTED_STOCKS = ['DBC', 'QQQ', 'MOO']