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
from modules.joystick_ui import VirtualJoystick, FireButton
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
        self.init_sound_system()
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
        self.drowsy_trigger_time = None  # 第一次檢測到瞌睡的時間
        self.alert_trigger_time = None   # 第一次檢測到清醒的時間
        self.drowsy_threshold = 30  # 瞌睡確認時間（秒）
        self.alert_threshold = 30   # 清醒確認時間（秒）
        
        # 線程控制
        self.threads = []

        # 初始化虛擬搖桿和按鈕（本地控制 UI）
        self.init_local_ui()

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

    def init_sound_system(self):
        """初始化音效系統"""
        print("🔊 初始化音效系統...")

        try:
            # 初始化 pygame mixer
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)

            # 載入音效檔案
            self.sounds = {}
            sound_dir = self.config.SOUND_EFFECTS_DIR

            for sound_file in self.config.AVAILABLE_SOUNDS:
                sound_name = sound_file.replace('.mp3', '').replace('.wav', '')
                sound_path = os.path.join(sound_dir, sound_file)

                if os.path.exists(sound_path):
                    try:
                        self.sounds[sound_name] = pygame.mixer.Sound(sound_path)
                        print(f"  ✅ 載入音效: {sound_name}")
                    except Exception as e:
                        print(f"  ⚠️  無法載入 {sound_file}: {e}")
                else:
                    print(f"  ⚠️  找不到音效檔案: {sound_path}")

            # 設定預設音效
            self.current_sound = 'water_gun'

            if self.sounds:
                print(f"✅ 音效系統初始化成功（載入 {len(self.sounds)} 個音效）")
            else:
                print("⚠️  音效系統初始化完成，但未載入任何音效檔案")

        except Exception as e:
            print(f"❌ 音效系統初始化失敗: {e}")
            self.sounds = {}

    def init_local_ui(self):
        """初始化本地控制 UI（搖桿和按鈕）"""
        print("🎮 初始化本地控制 UI...")

        # 搖桿位置（左下角）
        joystick_x = 80
        joystick_y = self.screen_height - 80

        # 射擊按鈕位置（右下角）
        fire_button_x = self.screen_width - 80
        fire_button_y = self.screen_height - 80

        # 創建虛擬搖桿
        self.joystick = VirtualJoystick(joystick_x, joystick_y, outer_radius=60, inner_radius=25)

        # 創建射擊按鈕
        self.fire_button = FireButton(fire_button_x, fire_button_y, radius=40)

        print("✅ 本地控制 UI 初始化完成")

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
            # 設置通知系統（用於發送一次性控制連結）
            if self.notification_system:
                self.web_control.set_notification_system(self.notification_system)
            
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
        print(f"   - 拖動左下搖桿: 控制雲台瞄準")
        print(f"   - 點擊右下按鈕: 手動射擊")
        print(f"   - TAB 鍵: 切換本地控制開/關")
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

    def set_pan(self, angle):
        """設置 Pan 角度（本地搖桿控制）"""
        if not self.local_control_active:
            return

        with self.control_lock:
            target_angle = max(self.pan_min, min(self.pan_max, angle))

            if abs(target_angle - self.current_pan) > 1:
                self.current_pan = target_angle

                if self.kit:
                    self.kit.servo[self.pan_channel].angle = target_angle

    def set_tilt(self, angle):
        """設置 Tilt 角度（本地搖桿控制）"""
        if not self.local_control_active:
            return

        with self.control_lock:
            target_angle = max(self.tilt_min, min(self.tilt_max, angle))

            if abs(target_angle - self.current_tilt) > 1:
                self.current_tilt = target_angle

                if self.kit:
                    self.kit.servo[self.tilt_channel].angle = target_angle

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
        sound_effect = shot_data.get('sound', self.current_sound) if shot_data else self.current_sound

        print(f"🔫 {'遠程' if is_remote else '本地'}射擊！模式: {fire_mode}, 音效: {sound_effect}")

        # 播放音效
        if self.sounds and sound_effect in self.sounds:
            try:
                self.sounds[sound_effect].play()
                print(f"🔊 播放音效: {sound_effect}")
            except Exception as e:
                print(f"⚠️  音效播放失敗: {e}")

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

    def play_winner_sound(self):
        """播放獲勝者提示音"""
        # 播放勝利音效（可以使用任何可用的音效）
        if self.sounds:
            # 優先使用特殊音效，如果沒有則使用水槍音效
            winner_sounds = ['小黃鴨', '鴨子聲', 'water_gun']
            for sound in winner_sounds:
                if sound in self.sounds:
                    try:
                        self.sounds[sound].play()
                        print(f"🎵 播放獲勝者提示音: {sound}")
                        break
                    except Exception as e:
                        print(f"⚠️ 音效播放失敗: {e}")

    def handle_drowsiness_detected(self, drowsiness_result, current_frame):
        """處理瞌睡偵測（增加時間門檻，減少誤判）"""
        # 檢查是否進入瞌睡狀態
        current_state = drowsiness_result.get('state', 'normal')
        alert_level = drowsiness_result.get('alert_level', 0)

        # 瞌睡檢測：alert_level >= 2
        if alert_level >= 2 or current_state == 'Drowsy':
            # 重置清醒計時器
            self.alert_trigger_time = None

            if not self.drowsy_session_active:
                # 記錄第一次檢測到瞌睡的時間
                if self.drowsy_trigger_time is None:
                    self.drowsy_trigger_time = time.time()
                    print(f"⚠️ 偵測到瞌睡跡象 (級別 {alert_level})，開始計時...")

                # 檢查是否持續 30 秒
                elapsed_time = time.time() - self.drowsy_trigger_time
                if elapsed_time >= self.drowsy_threshold:
                    # 確認瞌睡，開始新的瞌睡會話
                    print(f"\n🚨 確認瞌睡狀態 (持續 {elapsed_time:.1f} 秒): {current_state}")
                    self.drowsy_session_active = True
                    self.drowsy_start_time = time.time()
                    self.notification_sent = False
                    self.drowsy_trigger_time = None  # 重置

                    # 記錄瞌睡開始事件
                    if self.event_recorder:
                        self.event_recorder.record_drowsiness_start(drowsiness_result, current_frame)

                    # 啟動聊天會話
                    if self.web_control:
                        self.web_control.start_chat_session()
                        print("💬 聊天會話已啟動")

                    # 自動授予遠端控制權限（緊急模式）
                    if self.web_control:
                        self.web_control.grant_emergency_control(reason=f"偵測到瞌睡：{current_state}")

            # 如果已經在瞌睡會話中，發送通知（如果尚未發送）
            if self.drowsy_session_active and not self.notification_sent and self.notification_system:
                print("📲 嘗試發送 Telegram 通知...")
                if self.notification_system.send_drowsiness_alert(drowsiness_result, current_frame):
                    self.notification_sent = True
                    print("✅ 瞌睡警報通知已發送")
                else:
                    print("❌ 瞌睡警報通知發送失敗")
        else:
            # 沒有瞌睡跡象，重置瞌睡計時器
            if self.drowsy_trigger_time is not None:
                print("✓ 瞌睡跡象消失，重置計時器")
            self.drowsy_trigger_time = None

        # 清醒狀態檢測（需要持續 30 秒才確認）
        if current_state == 'Alert' and self.drowsy_session_active:
            # 記錄第一次檢測到清醒的時間
            if self.alert_trigger_time is None:
                self.alert_trigger_time = time.time()
                drowsy_duration = time.time() - self.drowsy_start_time if self.drowsy_start_time else 0
                print(f"✓ 偵測到清醒跡象（已瞌睡 {drowsy_duration:.1f} 秒），開始計時...")

            # 檢查是否持續清醒 30 秒
            alert_elapsed_time = time.time() - self.alert_trigger_time
            if alert_elapsed_time >= self.alert_threshold:
                # 確認清醒，結束瞌睡會話
                drowsy_duration = time.time() - self.drowsy_start_time if self.drowsy_start_time else 0
                print(f"\n😊 確認用戶已甦醒 (持續清醒 {alert_elapsed_time:.1f} 秒)！瞌睡總時長: {drowsy_duration:.1f} 秒")

                # 結束聊天會話並獲取最高票留言
                top_message = None
                if self.web_control:
                    top_message = self.web_control.end_chat_session()
                    if top_message:
                        print(f"\n🏆 最高票留言: {top_message['username']}: {top_message['message']}")
                        print(f"   票數: {top_message['votes']}")
                        # 播放提示音
                        self.play_winner_sound()
                        # 注意：最高票者已在 end_chat_session() 中自動獲得控制權

                # 記錄瞌睡結束事件
                if self.event_recorder:
                    self.event_recorder.record_drowsiness_end(current_frame)

                # 發送甦醒通知
                if self.notification_system:
                    self.notification_system.send_wake_up_notification()

                # 重置所有狀態
                self.drowsy_session_active = False
                self.drowsy_start_time = None
                self.notification_sent = False
                self.alert_trigger_time = None
        else:
            # 如果在瞌睡會話中但沒有清醒跡象，重置清醒計時器
            if self.drowsy_session_active and self.alert_trigger_time is not None:
                print("⚠️ 清醒跡象消失，重置清醒計時器")
                self.alert_trigger_time = None
    
    def opencv_to_pygame(self, cv_image):
        """將 OpenCV 影像轉換為 pygame surface"""
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        
        h, w = rgb_image.shape[:2]
        if w != self.screen_width or h != self.screen_height:
            rgb_image = cv2.resize(rgb_image, (self.screen_width, self.screen_height))
        
        return pygame.surfarray.make_surface(rgb_image.swapaxes(0, 1))
    
    def draw_status_info(self):
        """繪製狀態信息"""
        font = pygame.font.Font(None, 24)

        # 繪製控制狀態
        if self.local_control_active:
            status_text = font.render("本地控制: 啟用", True, (0, 255, 0))
        else:
            status_text = font.render("本地控制: 停用", True, (255, 165, 0))
        self.screen.blit(status_text, (10, 10))

        # 繪製雲台角度
        pan_text = font.render(f"Pan: {self.current_pan:.0f}°", True, (255, 255, 255))
        self.screen.blit(pan_text, (10, 35))

        tilt_text = font.render(f"Tilt: {self.current_tilt:.0f}°", True, (255, 255, 255))
        self.screen.blit(tilt_text, (10, 60))

        # 繪製射擊狀態
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        if fire_ready:
            fire_text = font.render("射擊: 就緒", True, (0, 255, 0))
        else:
            cooldown_left = self.fire_cooldown - time_since_fire
            fire_text = font.render(f"射擊: {cooldown_left:.1f}s", True, (255, 100, 100))
        self.screen.blit(fire_text, (10, 85))

        # 繪製操作說明
        help_font = pygame.font.Font(None, 18)
        help_texts = [
            "TAB: 切換本地控制",
            "R: 重置雲台位置",
            "ESC: 退出系統"
        ]
        y_offset = self.screen_height - 60
        for text in help_texts:
            help_surface = help_font.render(text, True, (180, 180, 180))
            self.screen.blit(help_surface, (10, y_offset))
            y_offset += 20
    
    def run_main_loop(self):
        """主要控制迴圈（本地控制視窗）"""
        print("\\n🎮 啟動本地控制視窗...")

        clock = pygame.time.Clock()
        pygame.mouse.set_visible(True)  # 顯示滑鼠游標

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
                    if event.button == 1:  # 左鍵
                        # 檢查是否點擊搖桿
                        if self.local_control_active:
                            self.joystick.handle_mouse_down(mouse_pos[0], mouse_pos[1])

                        # 檢查是否點擊射擊按鈕
                        if self.local_control_active and self.fire_button.handle_mouse_down(mouse_pos[0], mouse_pos[1]):
                            self.fire_shot({'remote': False, 'mode': 'single'})

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:  # 左鍵放開
                        self.joystick.handle_mouse_up()
                        self.fire_button.handle_mouse_up()

                elif event.type == pygame.MOUSEMOTION:
                    # 更新搖桿位置
                    if self.local_control_active:
                        self.joystick.handle_mouse_motion(mouse_pos[0], mouse_pos[1])

            # 根據搖桿控制雲台
            if self.local_control_active and self.joystick.is_dragging:
                joy_x, joy_y = self.joystick.get_values()
                # 將搖桿值 (-1到1) 映射到雲台角度
                target_pan = self.pan_center + (joy_x * (self.pan_max - self.pan_min) / 2)
                target_tilt = self.tilt_center + (joy_y * (self.tilt_max - self.tilt_min) / 2)
                self.set_pan(target_pan)
                self.set_tilt(target_tilt)

            # 更新射擊按鈕冷卻狀態
            time_since_fire = time.time() - self.last_fire_time
            self.fire_button.set_cooldown(time_since_fire < self.fire_cooldown)

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

            # 繪製搖桿和射擊按鈕
            self.joystick.draw(self.screen)
            self.fire_button.draw(self.screen)

            # 繪製狀態信息
            self.draw_status_info()

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
                
                # 保存純淨畫面（process_frame 會修改傳入的 frame）
                clean_frame = frame.copy()

                # 瞌睡偵測處理
                if self.drowsiness_detector:
                    processed_frame, drowsiness_result = self.drowsiness_detector.process_frame(frame)

                    # 處理瞌睡偵測結果
                    if drowsiness_result:
                        self.handle_drowsiness_detected(drowsiness_result, clean_frame)

                    # 保存畫面給本地和遠端顯示
                    with self.frame_lock:
                        self.current_frame = clean_frame  # 純淨畫面（給遠端網頁）
                        self.processed_frame = processed_frame  # 瞌睡偵測畫面（給本地顯示）
                else:
                    # 如果沒有瞌睡偵測，兩者都使用純淨畫面
                    with self.frame_lock:
                        self.current_frame = clean_frame
                        self.processed_frame = clean_frame

                # 更新網頁串流（使用純淨畫面）
                if self.web_control:
                    self.web_control.update_frame(clean_frame)
                
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
            # 音頻串流將在用戶點擊啟用按鈕時才開始
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