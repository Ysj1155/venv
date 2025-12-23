# notifications/notifier.py
import requests
import os

webhook_url = os.getenv("https://discord.com/api/webhooks/1330090131343937629/IBysAPiz-dFqruMtLnRVIU19OjPieF8k-izzqCePZjLCyhJwwbMowiqKRsPT5l1ORqrG")

def send_discord_notification(webhook_url, title, description, color=5814783, image_url=None, link_url=None):
    """
    Discord 웹훅을 사용하여 알림을 전송합니다.
    Args:
        webhook_url (str): Discord 웹훅 URL.
        title (str): 알림 제목.
        description (str): 알림 내용.
        color (int): 메시지 색상 (기본값: 파란색).
        image_url (str): 메시지에 포함할 이미지 URL (옵션).
        link_url (str): 메시지에 포함할 링크 URL (옵션).
    """
    embed = {
        "title": title,
        "description": description,
        "color": color
    }

    # 이미지 URL 추가
    if image_url:
        embed["image"] = {"url": image_url}

    # 링크 URL 추가
    if link_url:
        embed["url"] = link_url

    data = {"embeds": [embed]}
    
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print(f"Discord notification sent: {title}")
    else:
        print(f"Failed to send Discord notification: {response.status_code} - {response.text}")
