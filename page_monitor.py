import requests
import os
from datetime import datetime
from bs4 import BeautifulSoup

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")

def test_slack():
    """簡單測試 Slack 通知"""
    if not SLACK_WEBHOOK:
        print("❌ SLACK_WEBHOOK 未設定！")
        return
    
    message = {
        "text": f"🔔 網頁監控測試 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n衛理高中公告、安創共契、達人女中都在監控中！"
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK, json=message)
        print(f"✓ Slack 訊息已發送 (HTTP {response.status_code})")
    except Exception as e:
        print(f"✗ Slack 訊息失敗: {str(e)}")

if __name__ == "__main__":
    print("🕐 開始監控")
    test_slack()
    print("✓ 完成")