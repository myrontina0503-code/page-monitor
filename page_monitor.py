import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

# ==================== 設定區域 ====================
# 監控的網頁清單 - 改成妳要監控的網址和關鍵詞
PAGES_TO_MONITOR = [
    {
        "name": "衛理高中公告",
        "url": "https://www.wlgsh.tp.edu.tw/nss/s/hiwesley/link1",
        "selector": "body",
        "keywords": [],
    },
    {
        "name": "安創共契",
        "url": "https://gsmarket.adi.gov.tw/portal/%E6%9C%80%E6%96%B0%E6%B6%88%E6%81%AF?code=TenderNotice",
        "selector": "body",
        "keywords": [],
    },
    {
        "name": "達人女中",
        "url": "https://sites.google.com/trgsh.tp.edu.tw/junior#h.6zh8fotzcre",
        "selector": "body",
        "keywords": [],
    },
] 

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")  # GitHub Secrets 裡設定
MAIL_TO = os.getenv("NOTIFY_EMAIL")  # GitHub Secrets 裡設定

# ==================== 主要邏輯 ====================
def fetch_page_content(url, selector):
    """抓取網頁內容"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.select_one(selector)
        
        if element:
            return element.get_text(strip=True)
        else:
            return None
    except Exception as e:
        return f"Error: {str(e)}"

def check_content_changes(page_config):
    """檢查內容是否變化"""
    current_content = fetch_page_content(page_config["url"], page_config["selector"])
    
    if current_content is None:
        return {
            "changed": False,
            "status": "error",
            "message": f"找不到選擇器: {page_config['selector']}"
        }
    
    # 檢查關鍵詞
    if page_config.get("keywords"):
        has_keywords = any(kw in current_content for kw in page_config["keywords"])
        if not has_keywords:
            return {
                "changed": False,
                "status": "no_keywords",
                "message": f"內容中沒有找到關鍵詞"
            }
    
    # 讀取上次保存的內容
    history_file = f"/tmp/{page_config['name']}_history.txt"
    last_content = ""
    
    if os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            last_content = f.read()
    
    # 保存當前內容
    with open(history_file, 'w', encoding='utf-8') as f:
        f.write(current_content)
    
    # 比較內容
    if current_content != last_content and last_content:
        return {
            "changed": True,
            "old_content": last_content[:200],
            "new_content": current_content[:200],
            "message": "✅ 檢測到內容變化！"
        }
    elif not last_content:
        return {
            "changed": False,
            "status": "first_run",
            "message": "首次執行，已保存內容基準"
        }
    else:
        return {
            "changed": False,
            "status": "no_change",
            "message": "內容未變化"
        }

def send_slack_notification(page_name, result):
    """發送 Slack 通知"""
    if not SLACK_WEBHOOK:
        return
    
    if result["status"] == "error":
        color = "danger"
        title = f"❌ {page_name} - 監控錯誤"
    else:
        color = "good"
        title = f"🔔 {page_name} - 內容已更新"
    
    message = {
        "attachments": [
            {
                "color": color,
                "title": title,
                "text": result.get("message", ""),
                "fields": [
                    {
                        "title": "舊內容 (前 200 字)",
                        "value": result.get("old_content", "N/A"),
                        "short": False
                    },
                    {
                        "title": "新內容 (前 200 字)",
                        "value": result.get("new_content", "N/A"),
                        "short": False
                    },
                    {
                        "title": "時間",
                        "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "short": True
                    }
                ]
            }
        ]
    }
    
    try:
        requests.post(SLACK_WEBHOOK, json=message)
        print(f"✓ Slack 通知已發送: {page_name}")
    except Exception as e:
        print(f"✗ Slack 通知失敗: {str(e)}")

def send_mail_notification(page_name, result):
    """發送郵件通知 (使用 GitHub 內建或 SMTP)"""
    if not MAIL_TO:
        return
    
    # 簡單做法：如果妳有設定 SMTP_HOST，就用這個
    # 否則可以用 Web3Forms 或其他免費郵件服務
    print(f"📧 郵件通知 (需額外設定): {page_name}")

# ==================== 主程式 ====================
if __name__ == "__main__":
    print(f"🕐 監控開始時間: {datetime.now()}\n")
    
    for page in PAGES_TO_MONITOR:
        print(f"檢查: {page['name']} ({page['url']})")
        result = check_content_changes(page)
        
        if result["changed"]:
            print(f"  → {result['message']}")
            send_slack_notification(page['name'], result)
            send_mail_notification(page['name'], result)
        else:
            print(f"  → {result['message']}")
        print()
    
    print("✓ 監控週期完成")