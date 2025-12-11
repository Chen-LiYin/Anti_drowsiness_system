#!/usr/bin/env python3
"""
通知系統模塊 - Phase 2
支援 Telegram Bot API
當偵測到瞌睡時，發送包含狀態、截圖和控制連結的通知
"""

import requests
import cv2
import base64
import io
import time
from datetime import datetime
from PIL import Image
import os
import sys

# 添加父目錄到路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import Config

class NotificationSystem:
    def __init__(self, config=None):
        """初始化通知系統"""
        self.config = config or Config()
        
        # Telegram 配置
        self.telegram_enabled = self.config.TELEGRAM_ENABLED and bool(self.config.TELEGRAM_BOT_TOKEN)
        self.telegram_bot_token = self.config.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = self.config.TELEGRAM_CHAT_ID

        # 通知狀態
        self.last_notification_time = 0
        self.notification_cooldown = 30  # 30秒冷卻時間避免過度通知

        print(f"通知系統初始化:")
        print(f"  - Telegram: {'啟用' if self.telegram_enabled else '停用'}")
    
    def capture_screenshot(self, frame):
        """捕獲當前畫面並轉換為base64"""
        try:
            # 添加時間戳記到圖片
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            frame_with_text = frame.copy()
            
            # 添加半透明背景
            overlay = frame_with_text.copy()
            cv2.rectangle(overlay, (10, 10), (400, 60), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame_with_text, 0.3, 0, frame_with_text)
            
            # 添加文字
            cv2.putText(frame_with_text, f"Drowsiness Alert: {timestamp}", 
                       (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame_with_text, "Anti-Drowsiness System", 
                       (15, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            
            # 轉換為JPEG格式
            _, buffer = cv2.imencode('.jpg', frame_with_text)
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return image_base64
        except Exception as e:
            print(f"截圖失敗: {e}")
            return None
    
    def generate_control_link(self):
        """生成遠程控制連結"""
        # 假設Flask應用運行在5000埠
        base_url = f"http://{self.config.FLASK_HOST}:{self.config.FLASK_PORT}" #localhost
        ngork_url = "https://pentapodic-gage-blier.ngrok-free.dev" #ngork tunnel URL
        control_url = f"{ngork_url}/remote_control?auth={self.config.CONTROL_PASSWORD}"
        return control_url
    
    def format_drowsiness_message(self, drowsiness_result):
        """格式化瞌睡警報訊息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state = drowsiness_result.get('state', 'Unknown')
        duration = drowsiness_result.get('drowsy_duration', 0)
        ear_value = drowsiness_result.get('ear', 0)
        eye_counter = drowsiness_result.get('eye_counter', 0)
        total_drowsy = drowsiness_result.get('total_drowsy', 0)

        message = f"""[瞌睡警報] - 有人要睡著了！！

時間: {timestamp}
狀態: {state}
持續時間: {duration:.1f} 秒
眼睛閉合幀數: {eye_counter}
總瞌睡事件: {total_drowsy} 次

立即控制: 點擊下方連結
遠程喚醒系統已啟用"""

        return message
    
    def send_telegram_notification(self, message, image_base64=None, control_url=None):
        """發送Telegram通知"""
        if not self.telegram_enabled:
            return False
        
        try:
            # 發送文字訊息
            telegram_api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            
            # 添加控制連結到訊息
            if control_url:
                message += f"\n\n[遠程控制連結]\n{control_url}"
            
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(telegram_api_url, data=payload, timeout=10)
            
            if response.status_code == 200:
                print("Telegram文字通知發送成功")
                
                # 發送圖片
                if image_base64:
                    self.send_telegram_photo(image_base64)
                
                return True
            else:
                print(f"Telegram通知發送失敗: {response.text}")
                return False
                
        except Exception as e:
            print(f"Telegram通知錯誤: {e}")
            return False
    
    def send_telegram_photo(self, image_base64):
        """發送Telegram圖片"""
        try:
            photo_api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"
            
            # 解碼base64圖片
            image_data = base64.b64decode(image_base64)
            
            files = {'photo': ('screenshot.jpg', image_data, 'image/jpeg')}
            data = {
                'chat_id': self.telegram_chat_id,
                'caption': '[即時攝像頭畫面]'
            }
            
            response = requests.post(photo_api_url, files=files, data=data, timeout=15)
            
            if response.status_code == 200:
                print("Telegram圖片發送成功")
            else:
                print(f"Telegram圖片發送失敗: {response.text}")
                
        except Exception as e:
            print(f"Telegram圖片發送錯誤: {e}")

    def send_drowsiness_alert(self, drowsiness_result, current_frame=None):
        """發送瞌睡警報通知"""
        current_time = time.time()
        
        # 檢查冷卻時間
        if current_time - self.last_notification_time < self.notification_cooldown:
            print(f"通知冷卻中，剩餘 {self.notification_cooldown - (current_time - self.last_notification_time):.1f} 秒")
            return False
        
        print("\n" + "="*50)
        print("[發送瞌睡警報通知]")
        print("="*50)

        # 格式化訊息
        message = self.format_drowsiness_message(drowsiness_result)

        # 捕獲截圖
        image_base64 = None
        if current_frame is not None:
            image_base64 = self.capture_screenshot(current_frame)

        # 生成控制連結
        control_url = self.generate_control_link()

        # 發送通知
        telegram_success = False

        if self.telegram_enabled:
            telegram_success = self.send_telegram_notification(message, image_base64, control_url)

        # 更新通知時間
        if telegram_success:
            self.last_notification_time = current_time

            print("通知發送結果:")
            print("  [成功] Telegram: 成功")

            print("="*50)
            return True
        else:
            if self.telegram_enabled:
                print("  [失敗] Telegram: 失敗")
            print("[通知發送失敗]")
            print("="*50)
            return False
    
    def send_wake_up_notification(self):
        """發送用戶已甦醒的通知"""
        if not self.telegram_enabled:
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"""[用戶已甦醒]

時間: {timestamp}
狀態: 清醒
系統狀態: 正常監控中
警報解除"""

        telegram_success = False

        if self.telegram_enabled:
            telegram_success = self.send_telegram_notification(message)

        return telegram_success
    
    def test_notification_system(self):
        """測試通知系統"""
        print("\n[測試通知系統]")

        test_result = {
            'state': 'Testing',
            'drowsy_duration': 5.5,
            'ear': 0.15,
            'eye_counter': 25,
            'total_drowsy': 1
        }

        # 創建測試截圖
        test_frame = None
        try:
            # 創建一個簡單的測試圖片
            import numpy as np
            test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128  # 灰色背景
            cv2.putText(test_frame, "NOTIFICATION SYSTEM TEST",
                       (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        except:
            pass

        success = self.send_drowsiness_alert(test_result, test_frame)

        if success:
            print("[成功] 通知系統測試成功")
        else:
            print("[失敗] 通知系統測試失敗")
            print("\n檢查項目:")
            print("  1. 是否已設置API Token？")
            print("  2. 網絡連接是否正常？")
            print("  3. Chat ID 是否正確？")

        return success


def main():
    """測試用主程式"""
    print("="*60)
    print("通知系統測試程式")
    print("="*60)

    # 檢查配置
    config = Config()

    print("\n現在配置:")
    print(f"  Telegram啟用: {config.TELEGRAM_ENABLED}")
    print(f"  Telegram Token: {'已設置' if config.TELEGRAM_BOT_TOKEN else '未設置'}")

    if not config.TELEGRAM_ENABLED:
        print("\n[錯誤] 尚未啟用通知服務")
        print("\n請在config.py中設置API Token並啟用服務:")
        print("  1. 設置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
        print("  2. 將 TELEGRAM_ENABLED 設為 True")
        return

    # 初始化並測試通知系統
    notification_system = NotificationSystem(config)
    notification_system.test_notification_system()


if __name__ == "__main__":
    main()