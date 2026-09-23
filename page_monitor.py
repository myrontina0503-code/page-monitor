import requests
import os
import json
import hashlib
import re
from datetime import datetime

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

def compute_hash(content):
    """計算內容哈希值"""
    if not content:
        return None
    return hashlib.md5(content.encode()).hexdigest()

def extract_price(content, selector=None):
    """提取頁面中的價格"""
    try:
        if not selector:
            # 通用價格提取
            prices = re.findall(r'[\$￥¥]\s*[\d,]+\.?\d*', content)
            return prices[0] if prices else None
        # 簡單的 CSS 選擇器支持（只支持類名和 ID）
        if selector.startswith('.'):
            class_name = selector[1:]
            match = re.search(f'class=["\']([^"\']*{class_name}[^"\']*)["\']', content)
            if match:
                # 找到該元素後的內容
                start = content.find(match.group(0))
                snippet = content[start:start+500]
                prices = re.findall(r'[\$￥¥]\s*[\d,]+\.?\d*', snippet)
                return prices[0] if prices else None
        return None
    except:
        return None

def check_keywords(content, keywords, mode="appear"):
    """檢查關鍵字出現或消失"""
    if not keywords:
        return False, []
    
    found_keywords = []
    for keyword in keywords:
        if keyword in content:
            found_keywords.append(keyword)
    
    if mode == "appear":
        return len(found_keywords) > 0, found_keywords
    elif mode == "disappear":
        return len(found_keywords) < len(keywords), [k for k in keywords if k not in content]
    return False, []

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
        mode = page.get("mode", "change")
        
        print(f"\n📄 檢查: {page_name} (模式: {mode})")
        
        # 下載內容
        content = get_page_content(page_url)
        if not content:
            print(f"   ⚠️ 無法下載，跳過")
            new_hashes[page_id] = old_hashes.get(page_id, {})
            continue
        
        # 根據模式檢查
        notification = None
        
        if mode == "change":
            # 模式 1：有異動就通知
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
                    "message": "頁面內容已更新"
                }
        
        elif mode == "keyword_appear":
            # 模式 2：關鍵字出現通知
            keywords = page.get("keywords", [])
            has_keywords, found = check_keywords(content, keywords, "appear")
            
            new_hashes[page_id] = {"type": "keyword", "keywords": keywords, "found": found}
            
            if has_keywords:
                print(f"   ⚠️ 偵測到關鍵字: {', '.join(found)}")
                notification = {
                    "page_name": page_name,
                    "message": f"偵測到關鍵字: {', '.join(found)}"
                }
            else:
                print(f"   ✓ 無相關關鍵字")
        
        elif mode == "keyword_disappear":
            # 模式 3：關鍵字消失通知
            keywords = page.get("keywords", [])
            has_disappeared, disappeared = check_keywords(content, keywords, "disappear")
            
            new_hashes[page_id] = {"type": "keyword_disappear", "keywords": keywords}
            
            if has_disappeared:
                print(f"   ⚠️ 以下關鍵字已消失: {', '.join(disappeared)}")
                notification = {
                    "page_name": page_name,
                    "message": f"以下關鍵字已消失: {', '.join(disappeared)}"
                }
            else:
                print(f"   ✓ 所有關鍵字都還在")
        
        elif mode == "price":
            # 模式 4：價格變化通知
            price_selector = page.get("price_selector")
            new_price = extract_price(content, price_selector)
            
            new_hashes[page_id] = {"type": "price", "value": new_price}
            old_price = old_hashes.get(page_id, {}).get("value")
            
            if old_price is None:
                print(f"   ℹ️ 首次監控，價格: {new_price}")
            elif old_price == new_price:
                print(f"   ✓ 價格無變化: {new_price}")
            else:
                print(f"   ⚠️ 價格已變化: {old_price} → {new_price}")
                notification = {
                    "page_name": page_name,
                    "message": f"價格已變化: {old_price} → {new_price}"
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
