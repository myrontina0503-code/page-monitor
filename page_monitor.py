import requests
import os
import json
import hashlib
from datetime import datetime

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
HASHES_FILE = "page_hashes.json"

# 要監控的頁面
PAGES_TO_MONITOR = [
    {
        "name": "衛理高中公告",
        "url": "https://www.wlgsh.tp.edu.tw/nss/s/hiwesley/link1",
    },
    {
        "name": "安創共契",
        "url": "https://gsmarket.adi.gov.tw/portal/%E6%9C%80%E6%96%B0%E6%B6%88%E6%81%AF?code=TenderNotice",
    },
    {
        "name": "達人女中",
        "url": "https://sites.google.com/trgsh.tp.edu.tw/junior#h.6zh8fotzcre",
    },
]

def get_page_content(url):
    """下載頁面內容"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        print(f"❌ 無法下載 {url}: {str(e)}")
        return None

def compute_hash(content):
    """計算內容哈希值"""
    if not content:
        return None
    return hashlib.md5(content.encode()).hexdigest()

def load_hashes():
    """載入上次保存的哈希值"""
    if os.path.exists(HASHES_FILE):
        try:
            with open(HASHES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 無法讀取 {HASHES_FILE}: {str(e)}")
    return {}

def save_hashes(hashes):
    """保存新的哈希值"""
    try:
        with open(HASHES_FILE, "w", encoding="utf-8") as f:
            json.dump(hashes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ 無法保存 {HASHES_FILE}: {str(e)}")

def send_slack_notification(changes):
    """發送 Slack 通知"""
    if not SLACK_WEBHOOK:
        print("❌ SLACK_WEBHOOK 未設定！")
        return False

    if not changes:
        print("✓ 無頁面變化，不發送通知")
        return True

    message_text = f"🔔 網頁監控異動通知 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    message_text += "🔄 偵測到以下頁面有異動：\n"
    for change in changes:
        message_text += f"• {change}\n"

    message = {"text": message_text}

    try:
        response = requests.post(SLACK_WEBHOOK, json=message)
        if response.status_code == 200:
            print(f"✓ Slack 通知已發送 (異動：{len(changes)} 頁)")
            return True
        else:
            print(f"❌ Slack 發送失敗 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Slack 發送錯誤: {str(e)}")
        return False

def monitor_pages():
    """監控頁面變化"""
    print(f"🕐 開始監控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    old_hashes = load_hashes()
    new_hashes = {}
    changes = []

    for page in PAGES_TO_MONITOR:
        page_name = page["name"]
        page_url = page["url"]
        
        print(f"\n📄 檢查: {page_name}")
        
        content = get_page_content(page_url)
        if not content:
            print(f"   ⚠️ 無法下載，跳過")
            new_hashes[page_name] = old_hashes.get(page_name, "")
            continue
        
        new_hash = compute_hash(content)
        new_hashes[page_name] = new_hash
        
        old_hash = old_hashes.get(page_name)
        
        if old_hash == "":
            print(f"   ℹ️ 首次監控")
        elif old_hash == new_hash:
            print(f"   ✓ 無異動")
        else:
            print(f"   ⚠️ 檢測到異動！")
            changes.append(page_name)
    
    save_hashes(new_hashes)
    
    if changes:
        send_slack_notification(changes)
    else:
        print("\n✓ 本次監控完成，無異動")
    
    print("✓ 完成")

if __name__ == "__main__":
    monitor_pages()
