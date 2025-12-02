#!/usr/bin/env python3
"""
雙視窗整合式雲台瞌睡防範系統
- 瞌睡偵測視窗：顯示詳細的偵測分析（OpenCV）
- 瞄準控制視窗：攝像頭影像背景 + 準星介面（pygame）
- 偵測到瞌睡時自動射擊
"""

import pygame
import cv2
import numpy as np
import time
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from modules.drowsiness_detector import DrowsinessDetector
from config import Config

class DualWindowTurretSystem:
    def __init__(self):
        """初始化雙視窗系統"""
        # 初始化 pygame
        pygame.init()
        
        # 配置參數
        self.config = Config()
        self.screen_width = 800
        self.screen_height = 600
        
        # 創建 pygame 瞄準視窗
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("瞄準控制介面 - ESC 退出")
        
        # 初始化攝像頭
        print("初始化攝像頭...")
        self.cap = cv2.VideoCapture(self.config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.CAMERA_HEIGHT)
        
        if not self.cap.isOpened():
            raise Exception("無法開啟攝像頭")
        
        # 初始化瞌睡偵測器
        print("初始化瞌睡偵測器...")
        self.drowsiness_detector = DrowsinessDetector(self.config)
        
        # 初始化雲台控制
        print("初始化雲台控制...")
        from adafruit_servokit import ServoKit
        self.kit = ServoKit(channels=16)
        self.setup_servos()
        self.setup_turret_params()
        
        # 系統狀態
        self.auto_fire_enabled = True
        self.last_auto_fire_time = 0
        self.auto_fire_cooldown = 2.0
        
        # 共享數據
        self.current_frame = None
        self.drowsiness_result = None
        self.frame_lock = threading.Lock()
        
        # 視窗控制
        self.running = True
        self.detection_window_running = True
        
        print("✅ 雙視窗系統初始化完成")
        print("介面說明:")
        print("   - 瞌睡偵測視窗: 顯示詳細分析結果")
        print("   - 瞄準控制視窗: 滑鼠控制 + 準星介面")
        print("控制方式:")
        print("   - 滑鼠移動: 控制 Pan/Tilt")
        print("   - 左鍵點擊: 手動射擊")
        print("   - 空白鍵: 切換自動/手動模式")
        print("   - R 鍵: 重置雲台位置")
        print("   - ESC 鍵: 退出系統")
    
    def setup_servos(self):
        """設定舵機參數"""
        # 普通舵機設定
        self.kit.servo[1].set_pulse_width_range(500, 2500)  # Pan
        self.kit.servo[2].set_pulse_width_range(500, 2500)  # Tilt
        
        # 停止射擊舵機
        self.kit.continuous_servo[4].throttle = 0  # Fire
    
    def setup_turret_params(self):
        """設定雲台參數"""
        # Pan 控制
        self.pan_channel = 1
        self.pan_center = 90
        self.pan_min = 0
        self.pan_max = 180
        self.current_pan = self.pan_center
        
        # Tilt 控制
        self.tilt_channel = 2
        self.tilt_min = 45
        self.tilt_max = 135
        self.tilt_center = 90
        self.current_tilt = self.tilt_center
        
        # 射擊控制
        self.fire_channel = 4
        self.fire_speed = 0.7
        self.fire_duration = 0.35
        self.fire_reset_duration = 0.358
        self.last_fire_time = 0
        self.fire_cooldown = 0.6
        
        # 重置到初始位置
        self.reset_position()
    
    def reset_position(self):
        """重置雲台位置"""
        print("重置雲台位置...")
        self.current_pan = self.pan_center
        self.current_tilt = self.tilt_center
        
        self.kit.servo[self.pan_channel].angle = self.current_pan
        self.kit.servo[self.tilt_channel].angle = self.current_tilt
        self.kit.continuous_servo[self.fire_channel].throttle = 0
        
        time.sleep(1)
        print("✅ 雲台已重置")
    
    def update_pan(self, mouse_x):
        """更新 Pan 位置"""
        ratio = mouse_x / self.screen_width
        target_angle = self.pan_min + ratio * (self.pan_max - self.pan_min)
        target_angle = max(self.pan_min, min(self.pan_max, target_angle))
        
        if abs(target_angle - self.current_pan) > 2:
            self.current_pan = target_angle
            self.kit.servo[self.pan_channel].angle = target_angle
    
    def update_tilt(self, mouse_y):
        """更新 Tilt 位置"""
        ratio = mouse_y / self.screen_height
        target_tilt = self.tilt_min + ratio * (self.tilt_max - self.tilt_min)
        target_tilt = max(self.tilt_min, min(self.tilt_max, target_tilt))
        
        if abs(target_tilt - self.current_tilt) > 3:
            self.current_tilt = target_tilt
            self.kit.servo[self.tilt_channel].angle = target_tilt
    
    def fire_shot(self, shot_type="manual"):
        """執行射擊"""
        current_time = time.time()
        
        if current_time - self.last_fire_time < self.fire_cooldown:
            return False
        
        print(f"🎯 {shot_type} 射擊！")
        
        # 射擊動作
        self.kit.continuous_servo[self.fire_channel].throttle = -self.fire_speed
        time.sleep(self.fire_duration)
        
        self.kit.continuous_servo[self.fire_channel].throttle = self.fire_speed
        time.sleep(self.fire_reset_duration)
        
        self.kit.continuous_servo[self.fire_channel].throttle = 0
        
        self.last_fire_time = current_time
        return True
    
    def opencv_to_pygame(self, cv_image):
        """將 OpenCV 影像轉換為 pygame surface"""
        # 轉換顏色空間 BGR -> RGB
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        
        # 轉換影像方向（OpenCV 和 pygame 的座標系不同）
        rgb_image = np.rot90(rgb_image)
        rgb_image = np.flipud(rgb_image)
        
        # 調整影像大小以符合視窗
        h, w = rgb_image.shape[:2]
        if w != self.screen_width or h != self.screen_height:
            rgb_image = cv2.resize(rgb_image, (self.screen_width, self.screen_height))
        
        # 創建 pygame surface
        pygame_image = pygame.surfarray.make_surface(rgb_image)
        return pygame_image
    
    def run_detection_window(self):
        """運行瞌睡偵測視窗（OpenCV）"""
        print("🔍 啟動瞌睡偵測視窗...")
        
        while self.detection_window_running and self.running:
            # 讀取攝像頭畫面
            ret, frame = self.cap.read()
            if not ret:
                print("❌ 無法讀取攝像頭畫面")
                break
            
            # 瞌睡偵測處理
            processed_frame, result = self.drowsiness_detector.process_frame(frame)
            
            # 更新共享數據
            with self.frame_lock:
                self.current_frame = frame.copy()  # 原始影像給 pygame 使用
                self.drowsiness_result = result
            
            # 處理瞌睡警報
            self.handle_drowsiness_alert(result)
            
            # 顯示偵測視窗
            cv2.imshow('瞌睡偵測系統', processed_frame)
            
            # 按鍵處理
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # ESC
                self.running = False
                break
            elif key == ord('s'):
                # 顯示統計
                stats = self.drowsiness_detector.get_statistics()
                print(f"\n📊 統計: 運行時間 {stats['runtime_str']}, 瞌睡事件 {stats['total_drowsy_events']} 次")
            elif key == ord('r'):
                # 重置統計
                self.drowsiness_detector.reset_statistics()
                print("✅ 瞌睡偵測統計已重置")
        
        # 關閉偵測視窗
        cv2.destroyAllWindows()
        print("🔍 瞌睡偵測視窗已關閉")
    
    def draw_targeting_ui(self, mouse_pos, drowsiness_result):
        """繪製瞄準介面 UI"""
        # 繪製十字準星
        center_x, center_y = self.screen_width // 2, self.screen_height // 2
        crosshair_color = (0, 255, 0) if drowsiness_result and drowsiness_result.get('state') == 'Alert' else (255, 0, 0)
        
        # 主準星線
        pygame.draw.line(self.screen, crosshair_color, 
                        (center_x - 30, center_y), (center_x + 30, center_y), 3)
        pygame.draw.line(self.screen, crosshair_color, 
                        (center_x, center_y - 30), (center_x, center_y + 30), 3)
        
        # 中心點
        pygame.draw.circle(self.screen, crosshair_color, (center_x, center_y), 5, 2)
        
        # 射擊死區
        dead_zone = 20
        dead_zone_rect = pygame.Rect(center_x - dead_zone, center_y - dead_zone, 
                                   dead_zone * 2, dead_zone * 2)
        pygame.draw.rect(self.screen, (100, 100, 100), dead_zone_rect, 1)
        
        # 滑鼠位置指示
        pygame.draw.circle(self.screen, (255, 255, 0), mouse_pos, 8, 2)
        
        # 字體
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 36)
        font_small = pygame.font.Font(None, 24)
        
        # 狀態顯示（左上）
        if drowsiness_result:
            state = drowsiness_result.get('state', 'Unknown')
            state_colors = {
                'Alert': (0, 255, 0),
                'Tired': (255, 255, 0),
                'Yawning': (255, 165, 0),
                'Drowsy': (255, 0, 0),
                'No Face': (128, 128, 128)
            }
            color = state_colors.get(state, (255, 255, 255))
            state_text = font_medium.render(f"狀態: {state}", True, color)
            self.screen.blit(state_text, (10, 10))
        
        # 模式顯示
        mode_text = "自動" if self.auto_fire_enabled else "手動"
        mode_color = (0, 255, 0) if self.auto_fire_enabled else (255, 255, 0)
        mode_surface = font_medium.render(f"模式: {mode_text}", True, mode_color)
        self.screen.blit(mode_surface, (10, 50))
        
        # 雲台位置（左上）
        pan_rel = self.current_pan - 90
        pan_text = font_small.render(f"Pan: {pan_rel:+.0f}°", True, (255, 255, 255))
        self.screen.blit(pan_text, (10, 90))
        
        tilt_text = font_small.render(f"Tilt: {self.current_tilt:.0f}°", True, (255, 255, 255))
        self.screen.blit(tilt_text, (10, 115))
        
        # 射擊狀態（左上）
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        fire_color = (0, 255, 0) if fire_ready else (255, 100, 100)
        fire_text = font_small.render(
            f"射擊: {'就緒' if fire_ready else f'{self.fire_cooldown - time_since_fire:.1f}s'}", 
            True, fire_color
        )
        self.screen.blit(fire_text, (10, 140))
        
        # 瞄準資訊（中央上方）
        range_text = font_small.render(f"範圍: Pan ±90°, Tilt 45-135°", True, (200, 200, 200))
        text_rect = range_text.get_rect(center=(self.screen_width//2, 30))
        self.screen.blit(range_text, text_rect)
        
        # 警報顯示（中央）
        if drowsiness_result and drowsiness_result.get('should_alert', False):
            if int(time.time() * 4) % 2 == 0:  # 快速閃爍
                alert_text = font_large.render("⚡ 瞌睡警報 ⚡", True, (255, 0, 0))
                text_rect = alert_text.get_rect(center=(self.screen_width//2, 120))
                self.screen.blit(alert_text, text_rect)
        
        # 控制說明（右下角）
        instructions = [
            "滑鼠: 控制瞄準",
            "左鍵: 射擊",
            "空白: 模式",
            "R: 重置",
            "ESC: 退出"
        ]
        
        for i, instruction in enumerate(instructions):
            text = font_small.render(instruction, True, (200, 200, 200))
            self.screen.blit(text, (self.screen_width - 150, self.screen_height - 120 + i * 20))
    
    def handle_drowsiness_alert(self, drowsiness_result):
        """處理瞌睡警報"""
        if not self.auto_fire_enabled:
            return
        
        current_time = time.time()
        
        # 檢查是否需要自動射擊
        if (drowsiness_result.get('should_alert', False) and 
            current_time - self.last_auto_fire_time >= self.auto_fire_cooldown):
            
            if self.fire_shot("自動"):
                self.last_auto_fire_time = current_time
                print("🚨 瞌睡偵測觸發自動射擊！")
    
    def run_targeting_window(self):
        """運行瞄準控制視窗（pygame）"""
        print("🎯 啟動瞄準控制視窗...")
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
                    elif event.key == pygame.K_SPACE:
                        # 切換自動/手動模式
                        self.auto_fire_enabled = not self.auto_fire_enabled
                        mode = "自動" if self.auto_fire_enabled else "手動"
                        print(f"🔄 切換為 {mode} 模式")
                    elif event.key == pygame.K_r:
                        # 重置雲台位置
                        self.reset_position()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左鍵手動射擊
                        self.fire_shot("手動")
                
                elif event.type == pygame.MOUSEMOTION:
                    # 控制雲台
                    self.update_pan(mouse_pos[0])
                    self.update_tilt(mouse_pos[1])
            
            # 獲取共享數據
            current_frame = None
            drowsiness_result = None
            with self.frame_lock:
                if self.current_frame is not None:
                    current_frame = self.current_frame.copy()
                drowsiness_result = self.drowsiness_result
            
            # 繪製背景（攝像頭影像）
            if current_frame is not None:
                camera_surface = self.opencv_to_pygame(current_frame)
                self.screen.blit(camera_surface, (0, 0))
            else:
                # 無攝像頭畫面時顯示黑色背景
                self.screen.fill((0, 0, 0))
            
            # 繪製瞄準 UI
            self.draw_targeting_ui(mouse_pos, drowsiness_result)
            
            # 更新顯示
            pygame.display.flip()
            clock.tick(30)
        
        print("🎯 瞄準控制視窗已關閉")
    
    def run(self):
        """主要運行迴圈"""
        print("\n🚀 啟動雙視窗系統...")
        
        # 啟動瞌睡偵測視窗線程
        detection_thread = threading.Thread(target=self.run_detection_window, daemon=True)
        detection_thread.start()
        
        try:
            # 運行瞄準控制視窗（主線程）
            self.run_targeting_window()
            
        except KeyboardInterrupt:
            print("\n⚠️ 使用者中斷")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理資源"""
        print("\n🔧 關閉系統...")
        
        # 停止所有線程
        self.running = False
        self.detection_window_running = False
        
        # 重置雲台
        try:
            self.kit.servo[self.pan_channel].angle = 90
            self.kit.servo[self.tilt_channel].angle = 90
            self.kit.continuous_servo[self.fire_channel].throttle = 0
        except:
            pass
        
        # 關閉攝像頭
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        
        # 關閉 OpenCV 視窗
        cv2.destroyAllWindows()
        
        # 關閉 pygame
        pygame.quit()
        
        # 顯示統計
        if hasattr(self, 'drowsiness_detector'):
            stats = self.drowsiness_detector.get_statistics()
            print(f"\n📊 運行統計:")
            print(f"   運行時間: {stats['runtime_str']}")
            print(f"   瞌睡事件: {stats['total_drowsy_events']} 次")
            print(f"   打哈欠事件: {stats['total_yawn_events']} 次")
        
        print("✅ 系統已關閉")


def main():
    """主程式入口"""
    print("=" * 60)
    print("🎯 雙視窗整合式雲台瞌睡防範系統")
    print("=" * 60)
    print("功能特色:")
    print("  ✓ 分離式雙視窗介面")
    print("  ✓ 即時瞌睡偵測（OpenCV 視窗）")
    print("  ✓ 專業瞄準控制（pygame 視窗）")
    print("  ✓ 攝像頭影像背景")
    print("  ✓ 自動射擊警示")
    print("  ✓ 手動雲台控制")
    print("=" * 60)
    print()
    
    try:
        system = DualWindowTurretSystem()
        system.run()
    except Exception as e:
        print(f"❌ 系統錯誤: {e}")
        print("\n檢查項目:")
        print("  1. 攝像頭是否正常連接？")
        print("  2. PCA9685 舵機控制板是否正常？")
        print("  3. 是否已下載 dlib 面部特徵點模型？")
        print("  4. 相關依賴套件是否已安裝？")


if __name__ == "__main__":
    main()