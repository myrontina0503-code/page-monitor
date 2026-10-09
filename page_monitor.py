import requests
import os
import json
import hashlib
import re
from datetime import datetime
from bs4 import BeautifulSoup

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")
CONFIG_FILE = "config.json"
HASHES_FILE = "page_hashes.json"

def load_config():
    """載入配置文件"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 無法讀取 config.json: {str(e)}")
        return {"pages": []}

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

def extract_content_by_selector(html_content, selector):
    """根據 CSS 選擇器提取頁面內容"""
    if not selector:
        # 如果沒有指定選擇器，用整個頁面
        return html_content
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 支持 class 選擇器（.classname）
        if selector.startswith('.'):
            class_name = selector[1:]
            elements = soup.find_all(class_=class_name)
            if elements:
                content = ''.join(str(elem) for elem in elements)
                return content
        
        # 支持 ID 選擇器（#idname）
        elif selector.startswith('#'):
            id_name = selector[1:]
            element = soup.find(id=id_name)
            if element:
                return str(element)
        
        # 如果選擇器沒找到，用整個頁面
        print(f"   ⚠️ 未找到選擇器 '{selector}'，改用整個頁面")
        return html_content
    
    except Exception as e:
        print(f"   ⚠️ 選擇器提取失敗: {str(e)}，改用整個頁面")
        return html_content

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
        except:
            pass
    return {}

def save_hashes(hashes):
    """保存新的哈希值"""
    try:
        with open(HASHES_FILE, "w", encoding="utf-8") as f:
            json.dump(hashes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ 無法保存 {HASHES_FILE}: {str(e)}")

def send_slack_notification(notifications):
    """發送 Slack 通知"""
    if not SLACK_WEBHOOK or not notifications:
        return False

    message_text = f"🔔 網頁監控異動通知 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for notif in notifications:
        message_text += f"📍 {notif['page_name']}\n"
        message_text += f"   {notif['message']}\n\n"

    message = {"text": message_text}

    try:
        response = requests.post(SLACK_WEBHOOK, json=message)
        if response.status_code == 200:
            print(f"✓ Slack 通知已發送 ({len(notifications)} 個異動)")
            return True
        else:
            print(f"❌ Slack 發送失敗 (HTTP {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Slack 發送錯誤: {str(e)}")
        return False

def monitor_pages():
    """監控頁面"""
    print(f"🕐 開始監控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    config = load_config()
    old_hashes = load_hashes()
    new_hashes = {}
    notifications = []

    for page in config.get("pages", []):
        if not page.get("enabled", True):
            continue
        
        page_id = page.get("id")
        page_name = page.get("name")
        page_url = page.get("url")
        selector = page.get("selector")
        mode = page.get("mode", "change")
        
        print(f"\n📄 檢查: {page_name} (模式: {mode})")
        if selector:
            print(f"   🔍 選擇器: {selector}")
        
        # 下載內容
        content = get_page_content(page_url)
        if not content:
            print(f"   ⚠️ 無法下載，跳過")
            new_hashes[page_id] = old_hashes.get(page_id, {})
            continue
        
        # 只比對選擇器範圍內的內容
        content = extract_content_by_selector(content, selector)
        
        notification = None
        
        # 有異動就通知
        new_hash = compute_hash(content)
        new_hashes[page_id] = {"type": "hash", "value": new_hash}
        old_hash = old_hashes.get(page_id, {}).get("value")
        
        if old_hash is None:
            print(f"   ℹ️ 首次監控")
        elif old_hash == new_hash:
            print(f"   ✓ 無異動")
        else:
            print(f"   ⚠️ 檢測到異動！")
            notification = {
                "page_name": page_name,
                "message": f"頁面內容已更新\n   {page_url}"
            }
        
        if notification:
            notifications.append(notification)
    
    # 保存新的哈希值
    save_hashes(new_hashes)
    
    # 發送通知（如果有異動）
    if notifications:
        send_slack_notification(notifications)
    else:
        print("\n✓ 本次監控完成，無異動")
    
    print("✓ 完成")

if __name__ == "__main__":
    monitor_pages()
