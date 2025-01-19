# tests/test_notifier.py
from notification.notifier import send_discord_notification
import os
webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

def test_send_discord_notification():
    """
    Discord 알림 전송 테스트.
    """
    webhook_url = "YOUR_DISCORD_WEBHOOK_URL"  # 웹훅 URL 설정
    title = "Test Notification"
    description = "This is a test message sent from the notifier module."
    
    try:
        send_discord_notification(webhook_url, title, description)
        print("Discord notification test passed.")
    except Exception as e:
        print(f"Discord notification test failed: {e}")

if __name__ == "__main__":
    test_send_discord_notification()
