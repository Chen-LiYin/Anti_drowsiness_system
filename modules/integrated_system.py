#!/usr/bin/env python3
"""
整合防瞌睡雲台系統 - 完整版本
整合所有 Phase：瞌睡偵測、通知系統、遠程控制、事件記錄
"""

import pygame
import cv2
import numpy as np
import time
import threading
import sys
import os
from datetime import datetime
from queue import Queue
import requests

# 添加父目錄到路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from modules.drowsiness_detector import DrowsinessDetector
from modules.notification_system import NotificationSystem
from modules.event_recorder import EventRecorder
from modules.web_remote_control import WebRemoteControl
from adafruit_servokit import ServoKit
from config import Config

class IntegratedAntiDrowsinessSystem:
    def __init__(self, config=None):
        """初始化完整的防瞌睡雲台系統"""
        print("="*70)
        print("🚀 初始化整合防瞌睡雲台系統")
        print("="*70)
        
        # 配置
        self.config = config or Config()
        
        # 初始化 pygame
        pygame.init()
        
        # 設定視窗大小
        self.screen_width = self.config.CAMERA_WIDTH
        self.screen_height = self.config.CAMERA_HEIGHT
        
        # 創建本地控制視窗
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("本地控制 - ESC 退出")
        pygame.mouse.set_visible(False)
        
        # 初始化攝像頭
        self.init_camera()
        
        # 初始化各個子系統
        self.init_drowsiness_detector()
        self.init_turret_control()
        self.init_notification_system()
        self.init_event_recorder()
        self.init_web_remote_control()
        
        # 系統狀態
        self.running = True
        self.local_control_active = True
        self.remote_control_active = False
        
        # 共享數據
        self.current_frame = None  # 純淨畫面（供遠端網頁使用）
        self.processed_frame = None  # 瞌睡偵測畫面（供本地顯示使用）
        self.frame_lock = threading.Lock()
        self.control_lock = threading.Lock()
        
        # 瞌睡狀態追踪
        self.drowsy_session_active = False
        self.drowsy_start_time = None
        self.notification_sent = False
        
        # 線程控制
        self.threads = []
        
        print("✅ 整合系統初始化完成")
        self.print_system_info()
    
    def init_camera(self):
        """初始化攝像頭"""
        print("📷 初始化攝像頭...")
        
        self.cap = cv2.VideoCapture(self.config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.CAMERA_FPS)
        
        if not self.cap.isOpened():
            raise Exception("❌ 無法開啟攝像頭")
        
        # 測試讀取一幀
        ret, test_frame = self.cap.read()
        if not ret:
            raise Exception("❌ 無法讀取攝像頭畫面")
        
        print(f"✅ 攝像頭初始化成功 ({test_frame.shape[1]}x{test_frame.shape[0]})")
    
    def init_drowsiness_detector(self):
        """初始化瞌睡偵測器"""
        print("😴 初始化瞌睡偵測器...")
        
        try:
            self.drowsiness_detector = DrowsinessDetector(self.config)
            print("✅ 瞌睡偵測器初始化成功")
        except Exception as e:
            print(f"❌ 瞌睡偵測器初始化失敗: {e}")
            raise
    
    def init_turret_control(self):
        """初始化雲台控制"""
        print("🎯 初始化雲台控制...")
        
        try:
            # 初始化 PCA9685
            self.kit = ServoKit(channels=16)
            
            # 設定舵機參數
            self.kit.servo[1].set_pulse_width_range(500, 2500)  # Pan
            self.kit.servo[2].set_pulse_width_range(500, 2500)  # Tilt
            self.kit.continuous_servo[4].throttle = 0  # Fire
            
            # 雲台參數
            self.pan_channel = 1
            self.tilt_channel = 2
            self.fire_channel = 4
            
            self.pan_center = 90
            self.pan_min = 45
            self.pan_max = 135
            self.current_pan = self.pan_center
            
            self.tilt_center = 90
            self.tilt_min = 45
            self.tilt_max = 135
            self.current_tilt = self.tilt_center
            
            # 射擊參數
            self.fire_speed = 0.9
            self.fire_duration = 0.36
            self.fire_reset_duration = 0.37
            self.last_fire_time = 0
            self.fire_cooldown = 0.5
            
            # 重置到中心位置
            self.reset_turret_position()
            
            print("✅ 雲台控制初始化成功")
            
        except Exception as e:
            print(f"❌ 雲台控制初始化失敗: {e}")
            self.kit = None
            print("⚠️  將以模擬模式運行")
    
    def init_notification_system(self):
        """初始化通知系統"""
        print("📲 初始化通知系統...")
        
        try:
            self.notification_system = NotificationSystem(self.config)
            print("✅ 通知系統初始化成功")
        except Exception as e:
            print(f"❌ 通知系統初始化失敗: {e}")
            self.notification_system = None
    
    def init_event_recorder(self):
        """初始化事件記錄系統"""
        print("📝 初始化事件記錄系統...")
        
        try:
            self.event_recorder = EventRecorder(self.config)
            print("✅ 事件記錄系統初始化成功")
        except Exception as e:
            print(f"❌ 事件記錄系統初始化失敗: {e}")
            self.event_recorder = None
    
    def init_web_remote_control(self):
        """初始化網頁遠程控制系統"""
        print("🌐 初始化網頁遠程控制系統...")
        
        if not self.config.REMOTE_CONTROL_ENABLED:
            print("⚠️  遠程控制功能已停用")
            self.web_control = None
            return
        
        try:
            self.web_control = WebRemoteControl(self.config)
            
            # 設置控制回調
            self.web_control.set_control_callbacks(
                pan_callback=self.remote_pan_control,
                tilt_callback=self.remote_tilt_control,
                fire_callback=self.remote_fire_control
            )
            
            # 設置事件記錄器
            if self.event_recorder:
                self.web_control.set_event_recorder(self.event_recorder)
            
            print("✅ 網頁遠程控制系統初始化成功")
            
        except Exception as e:
            print(f"❌ 網頁遠程控制系統初始化失敗: {e}")
            self.web_control = None
    
    def print_system_info(self):
        """打印系統信息"""
        print(f"\\n📋 系統配置信息:")
        print(f"   攝像頭解析度: {self.config.CAMERA_WIDTH}x{self.config.CAMERA_HEIGHT}")
        print(f"   瞌睡偵測: {'啟用' if self.drowsiness_detector else '停用'}")
        print(f"   雲台控制: {'啟用' if self.kit else '停用(模擬)'}")
        print(f"   通知系統: {'啟用' if self.notification_system else '停用'}")
        print(f"   事件記錄: {'啟用' if self.event_recorder else '停用'}")
        print(f"   遠程控制: {'啟用' if self.web_control else '停用'}")
        
        if self.web_control:
            print(f"   \\n🌐 遠程控制URL:")
            print(f"   主頁: http://{self.config.FLASK_HOST}:{self.config.FLASK_PORT}/")
            print(f"   控制: http://{self.config.FLASK_HOST}:{self.config.FLASK_PORT}/remote_control?auth={self.config.CONTROL_PASSWORD}")
        
        print(f"\\n🎮 本地控制:")
        print(f"   - 滑鼠移動: 控制雲台瞄準")
        print(f"   - 左鍵點擊: 手動射擊")
        print(f"   - TAB 鍵: 切換本地/遠程控制模式")
        print(f"   - R 鍵: 重置雲台位置")
        print(f"   - ESC 鍵: 退出系統")
        print("="*70)
    
    def reset_turret_position(self):
        """重置雲台位置"""
        if not self.kit:
            print("🎯 模擬重置雲台位置...")
            return
        
        print("🎯 重置雲台位置...")
        self.current_pan = self.pan_center
        self.current_tilt = self.tilt_center
        
        self.kit.servo[self.pan_channel].angle = self.current_pan
        self.kit.servo[self.tilt_channel].angle = self.current_tilt
        self.kit.continuous_servo[self.fire_channel].throttle = 0
        
        time.sleep(1)
        print("✅ 雲台已重置到中心位置")
    
    def update_pan(self, mouse_x):
        """更新 Pan 位置（本地控制）"""
        if not self.local_control_active:
            return
        
        with self.control_lock:
            ratio = mouse_x / self.screen_width
            target_angle = self.pan_min + ratio * (self.pan_max - self.pan_min)
            target_angle = max(self.pan_min, min(self.pan_max, target_angle))
            
            if abs(target_angle - self.current_pan) > 2:
                self.current_pan = target_angle
                
                if self.kit:
                    self.kit.servo[self.pan_channel].angle = target_angle
    
    def update_tilt(self, mouse_y):
        """更新 Tilt 位置（本地控制）"""
        if not self.local_control_active:
            return
        
        with self.control_lock:
            ratio = mouse_y / self.screen_height
            target_tilt = self.tilt_min + ratio * (self.tilt_max - self.tilt_min)
            target_tilt = max(self.tilt_min, min(self.tilt_max, target_tilt))
            
            if abs(target_tilt - self.current_tilt) > 3:
                self.current_tilt = target_tilt
                
                if self.kit:
                    self.kit.servo[self.tilt_channel].angle = target_tilt
    
    def remote_pan_control(self, angle):
        """遠程 Pan 控制"""
        with self.control_lock:
            self.current_pan = angle
            
            if self.kit:
                self.kit.servo[self.pan_channel].angle = angle
            
            print(f"🌐 遠程Pan控制: {angle:.1f}°")
    
    def remote_tilt_control(self, angle):
        """遠程 Tilt 控制"""
        with self.control_lock:
            self.current_tilt = angle
            
            if self.kit:
                self.kit.servo[self.tilt_channel].angle = angle
            
            print(f"🌐 遠程Tilt控制: {angle:.1f}°")
    
    def remote_fire_control(self, shot_data):
        """遠程射擊控制"""
        print(f"🌐 遠程射擊請求: {shot_data}")
        return self.fire_shot(shot_data)
    
    def fire_shot(self, shot_data=None):
        """執行射擊動作"""
        current_time = time.time()
        
        if current_time - self.last_fire_time < self.fire_cooldown:
            print(f"🚫 射擊冷卻中... ({self.fire_cooldown - (current_time - self.last_fire_time):.1f}s)")
            return False
        
        is_remote = shot_data and shot_data.get('remote', False)
        fire_mode = shot_data.get('mode', 'single') if shot_data else 'single'
        
        print(f"🔫 {'遠程' if is_remote else '本地'}射擊！模式: {fire_mode}")
        
        if self.kit:
            # 執行射擊動作
            self.kit.continuous_servo[self.fire_channel].throttle = -self.fire_speed
            time.sleep(self.fire_duration)
            
            self.kit.continuous_servo[self.fire_channel].throttle = self.fire_speed
            time.sleep(self.fire_reset_duration)
            
            self.kit.continuous_servo[self.fire_channel].throttle = 0
        else:
            # 模擬射擊
            print("🔫 模擬射擊動作...")
            time.sleep(0.5)
        
        self.last_fire_time = current_time
        
        # 記錄射擊事件
        if self.event_recorder:
            self.event_recorder.record_shot_fired(shot_data)
        
        return True
    
    def handle_drowsiness_detected(self, drowsiness_result, current_frame):
        """處理瞌睡偵測"""
        # 檢查是否進入瞌睡狀態
        should_alert = drowsiness_result.get('should_alert', False)
        current_state = drowsiness_result.get('state', 'normal')
        alert_level = drowsiness_result.get('alert_level', 0)

        print(f"[偵測] 狀態: {current_state}, 警報級別: {alert_level}, should_alert: {should_alert}")

        # 修正：狀態名稱是 "Drowsy"（大寫），alert_level >= 3 代表瞌睡
        if should_alert or current_state == 'Drowsy' or alert_level >= 3:
            if not self.drowsy_session_active:
                # 開始新的瞌睡會話
                print(f"\n🚨 檢測到瞌睡狀態: {current_state}")
                self.drowsy_session_active = True
                self.drowsy_start_time = time.time()
                self.notification_sent = False

                # 記錄瞌睡開始事件
                if self.event_recorder:
                    self.event_recorder.record_drowsiness_start(drowsiness_result, current_frame)

            # 發送通知（如果尚未發送）
            if not self.notification_sent and self.notification_system:
                print("📲 嘗試發送 Telegram 通知...")
                if self.notification_system.send_drowsiness_alert(drowsiness_result, current_frame):
                    self.notification_sent = True
                    print("✅ 瞌睡警報通知已發送")
                else:
                    print("❌ 瞌睡警報通知發送失敗")

        elif current_state == 'Alert' and self.drowsy_session_active:
            # 瞌睡狀態結束
            drowsy_duration = time.time() - self.drowsy_start_time if self.drowsy_start_time else 0
            print(f"\\n😊 用戶已甦醒！瞌睡持續時間: {drowsy_duration:.1f} 秒")
            
            # 記錄瞌睡結束事件
            if self.event_recorder:
                self.event_recorder.record_drowsiness_end(current_frame)
            
            # 發送甦醒通知
            if self.notification_system:
                self.notification_system.send_wake_up_notification()
            
            # 重置瞌睡狀態
            self.drowsy_session_active = False
            self.drowsy_start_time = None
            self.notification_sent = False
    
    def opencv_to_pygame(self, cv_image):
        """將 OpenCV 影像轉換為 pygame surface"""
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        
        h, w = rgb_image.shape[:2]
        if w != self.screen_width or h != self.screen_height:
            rgb_image = cv2.resize(rgb_image, (self.screen_width, self.screen_height))
        
        return pygame.surfarray.make_surface(rgb_image.swapaxes(0, 1))
    
    def draw_crosshair(self, mouse_pos):
        """繪製準星"""
        center_x, center_y = self.screen_width // 2, self.screen_height // 2
        
        # 根據射擊狀態決定準心顏色
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        crosshair_color = (255, 255, 255) if fire_ready else (255, 100, 100)
        
        # 繪製十字準心
        pygame.draw.line(self.screen, crosshair_color, 
                        (center_x - 20, center_y), (center_x + 20, center_y), 2)
        pygame.draw.line(self.screen, crosshair_color, 
                        (center_x, center_y - 20), (center_x, center_y + 20), 2)
        
        # 繪製滑鼠位置
        pygame.draw.circle(self.screen, (255, 0, 0), mouse_pos, 5)
        
        # 控制狀態指示
        if self.local_control_active:
            pygame.draw.circle(self.screen, (0, 255, 0), (center_x, center_y), 30, 1)
        else:
            pygame.draw.circle(self.screen, (255, 165, 0), (center_x, center_y), 30, 1)
    
    def run_main_loop(self):
        """主要控制迴圈（本地控制視窗）"""
        print("\\n🎮 啟動本地控制視窗...")
        
        clock = pygame.time.Clock()
        
        while self.running:
            # 處理事件
            mouse_pos = pygame.mouse.get_pos()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_TAB:
                        self.local_control_active = not self.local_control_active
                        print(f"🎮 本地控制: {'啟用' if self.local_control_active else '停用'}")
                    elif event.key == pygame.K_r:
                        self.reset_turret_position()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and self.local_control_active:  # 左鍵射擊
                        self.fire_shot({'remote': False, 'mode': 'single'})
                
                elif event.type == pygame.MOUSEMOTION:
                    # 更新雲台位置
                    if self.local_control_active:
                        self.update_pan(mouse_pos[0])
                        self.update_tilt(mouse_pos[1])
            
            # 獲取瞌睡偵測畫面（本地顯示用）
            display_frame = None
            with self.frame_lock:
                if self.processed_frame is not None:
                    display_frame = self.processed_frame.copy()

            # 繪製背景
            if display_frame is not None:
                camera_surface = self.opencv_to_pygame(display_frame)
                self.screen.blit(camera_surface, (0, 0))
            else:
                self.screen.fill((30, 30, 30))
            
            # 繪製準星
            self.draw_crosshair(mouse_pos)
            
            # 更新顯示
            pygame.display.flip()
            clock.tick(30)
        
        print("🎮 本地控制視窗已關閉")
    
    def run_camera_processing(self):
        """攝像頭處理線程"""
        print("📷 啟動攝像頭處理線程...")
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                if not ret:
                    print("❌ 無法讀取攝像頭畫面")
                    time.sleep(0.1)
                    continue
                
                # 瞌睡偵測處理
                if self.drowsiness_detector:
                    processed_frame, drowsiness_result = self.drowsiness_detector.process_frame(frame)

                    # 處理瞌睡偵測結果
                    if drowsiness_result:
                        self.handle_drowsiness_detected(drowsiness_result, frame)

                    # 保存瞌睡偵測畫面給本地顯示
                    with self.frame_lock:
                        self.current_frame = frame.copy()  # 純淨畫面（給遠端網頁）
                        self.processed_frame = processed_frame.copy()  # 瞌睡偵測畫面（給本地顯示）
                else:
                    # 如果沒有瞌睡偵測，兩者都使用純淨畫面
                    with self.frame_lock:
                        self.current_frame = frame.copy()
                        self.processed_frame = frame.copy()

                # 更新網頁串流（使用純淨畫面）
                if self.web_control:
                    self.web_control.update_frame(frame)
                
            except Exception as e:
                print(f"❌ 攝像頭處理錯誤: {e}")
                time.sleep(0.1)
        
        print("📷 攝像頭處理線程已結束")
    
    def run_web_server(self):
        """運行網頁服務器線程"""
        if not self.web_control:
            return
        
        print("🌐 啟動網頁服務器線程...")
        
        try:
            # 運行 Flask 應用（在子線程中）
            self.web_control.run(debug=False)
        except Exception as e:
            print(f"❌ 網頁服務器錯誤: {e}")
    
    def run(self):
        """運行完整系統"""
        try:
            print("\\n🚀 啟動完整防瞌睡雲台系統...")
            
            # 啟動攝像頭處理線程
            camera_thread = threading.Thread(target=self.run_camera_processing, daemon=True)
            camera_thread.start()
            self.threads.append(camera_thread)
            
            # 啟動網頁服務器線程
            if self.web_control:
                web_thread = threading.Thread(target=self.run_web_server, daemon=True)
                web_thread.start()
                self.threads.append(web_thread)
            
            # 短暫延遲以確保所有線程正常啟動
            time.sleep(2)
            
            # 運行主控制迴圈
            self.run_main_loop()
            
        except KeyboardInterrupt:
            print("\\n⛔ 用戶中斷")
        except Exception as e:
            print(f"\\n❌ 系統錯誤: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理系統資源"""
        print("\\n🧹 清理系統資源...")
        
        # 停止所有線程
        self.running = False
        
        # 等待線程結束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2)
        
        # 重置雲台
        try:
            if self.kit:
                self.kit.servo[self.pan_channel].angle = 90
                self.kit.servo[self.tilt_channel].angle = 90
                self.kit.continuous_servo[self.fire_channel].throttle = 0
        except:
            pass
        
        # 關閉攝像頭
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        
        # 關閉視窗
        cv2.destroyAllWindows()
        pygame.quit()
        
        # 顯示最終統計
        if self.event_recorder:
            stats = self.event_recorder.get_statistics()
            print(f"\\n📊 最終統計報告:")
            print(f"   運行時間: {stats['session_duration_str']}")
            print(f"   瞌睡事件: {stats['total_drowsy_events']} 次")
            print(f"   射擊次數: {stats['total_shots_fired']} 次")
            print(f"   喚醒次數: {stats['total_wake_ups']} 次")
            
            # 導出事件數據
            export_file = self.event_recorder.export_data()
            if export_file:
                print(f"   事件數據已導出: {export_file}")
        
        print("✅ 系統已完全關閉")


def main():
    """主程式入口"""
    print("="*70)
    print("🎯 整合防瞌睡雲台系統 v1.0")
    print("="*70)
    print("功能模組:")
    print("  ✅ Phase 2: 智能通知系統 (Telegram/LINE)")
    print("  ✅ Phase 3: 遠程網頁控制介面")
    print("  ✅ Phase 5: 事件記錄與監控系統")
    print("  ✅ 本地雙視窗控制")
    print("  ✅ 即時視訊串流")
    print("  ✅ 虛擬搖桿控制")
    print("="*70)
    
    try:
        from config import Config
        config = Config()
        
        # 初始化並運行系統
        system = IntegratedAntiDrowsinessSystem(config)
        system.run()
        
    except Exception as e:
        print(f"\\n❌ 系統啟動失敗: {e}")
        print("\\n🔍 檢查項目:")
        print("  1. 攝像頭是否正常連接？")
        print("  2. PCA9685 舵機控制板是否正常？")
        print("  3. 是否已下載 dlib 面部特徵點模型？")
        print("  4. 相關依賴套件是否已安裝？")
        print("  5. 網絡連接是否正常？(遠程控制功能)")
        print("  6. API Token 是否正確設置？(通知功能)")


if __name__ == "__main__":
    main()