#!/usr/bin/env python3
"""
整合式雲台瞌睡防範系統
- 結合瞌睡偵測和自動射擊功能
- 使用攝像頭影像作為 pygame 介面背景
- 偵測到瞌睡時自動射擊
"""

import pygame
import cv2
import numpy as np
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from modules.mouse_turret_control import MouseTurretControl
from modules.drowsiness_detector import DrowsinessDetector
from config import Config

class IntegratedTurretSystem:
    def __init__(self):
        """初始化整合系統"""
        # 初始化 pygame
        pygame.init()
        
        # 配置參數
        self.config = Config()
        self.screen_width = 800
        self.screen_height = 600
        
        # 創建顯示視窗
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("瞌睡防範雲台系統 - ESC 退出")
        
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
        
        # 初始化雲台控制（只使用舵機部分，不創建 pygame 視窗）
        print("初始化雲台控制...")
        from adafruit_servokit import ServoKit
        self.kit = ServoKit(channels=16)
        self.setup_servos()
        self.setup_turret_params()
        
        # 系統狀態
        self.auto_fire_enabled = True
        self.manual_mode = False
        self.last_auto_fire_time = 0
        self.auto_fire_cooldown = 2.0  # 自動射擊冷卻時間
        
        # UI 狀態
        self.show_debug_info = True
        self.camera_surface = None
        
        print("✅ 整合系統初始化完成")
        print("控制說明:")
        print("   - 滑鼠移動: 手動控制 Pan/Tilt")
        print("   - 左鍵點擊: 手動射擊")
        print("   - 空白鍵: 切換自動/手動模式")
        print("   - TAB 鍵: 顯示/隱藏調試資訊")
        print("   - R 鍵: 重置雲台位置")
        print("   - ESC 鍵: 退出")
    
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
    
    def draw_ui_overlay(self, drowsiness_result):
        """繪製 UI 疊加層"""
        # 半透明疊加層
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(100)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))
        
        # 字體
        font_large = pygame.font.Font(None, 48)
        font_medium = pygame.font.Font(None, 36)
        font_small = pygame.font.Font(None, 24)
        
        # 狀態顯示
        state = drowsiness_result.get('state', 'Unknown')
        state_colors = {
            'Alert': (0, 255, 0),
            'Tired': (255, 255, 0),
            'Yawning': (255, 165, 0),
            'Drowsy': (255, 0, 0),
            'No Face': (128, 128, 128)
        }
        color = state_colors.get(state, (255, 255, 255))
        
        # 主要狀態顯示
        state_text = font_large.render(f"狀態: {state}", True, color)
        self.screen.blit(state_text, (10, 10))
        
        # 模式顯示
        mode_text = "自動模式" if self.auto_fire_enabled else "手動模式"
        mode_color = (0, 255, 0) if self.auto_fire_enabled else (255, 255, 0)
        mode_surface = font_medium.render(f"模式: {mode_text}", True, mode_color)
        self.screen.blit(mode_surface, (10, 70))
        
        # 雲台位置
        pan_rel = self.current_pan - 90
        pan_text = font_medium.render(f"Pan: {pan_rel:.1f}°", True, (255, 255, 255))
        self.screen.blit(pan_text, (10, 110))
        
        tilt_text = font_medium.render(f"Tilt: {self.current_tilt:.1f}°", True, (255, 255, 255))
        self.screen.blit(tilt_text, (10, 150))
        
        # 射擊冷卻
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        fire_color = (0, 255, 0) if fire_ready else (255, 100, 100)
        fire_text = font_medium.render(
            f"射擊: {'就緒' if fire_ready else f'冷卻 {self.fire_cooldown - time_since_fire:.1f}s'}", 
            True, fire_color
        )
        self.screen.blit(fire_text, (10, 190))
        
        # 調試資訊
        if self.show_debug_info and 'ear' in drowsiness_result:
            debug_y = 250
            ear_text = font_small.render(f"EAR: {drowsiness_result['ear']:.3f}", True, (255, 255, 255))
            self.screen.blit(ear_text, (10, debug_y))
            
            mar_text = font_small.render(f"MAR: {drowsiness_result['mar']:.3f}", True, (255, 255, 255))
            self.screen.blit(mar_text, (10, debug_y + 25))
            
            if drowsiness_result['eye_counter'] > 0:
                eye_text = font_small.render(f"眼睛閉合: {drowsiness_result['eye_counter']} 幀", True, (255, 0, 0))
                self.screen.blit(eye_text, (10, debug_y + 50))
            
            if drowsiness_result['yawn_counter'] > 0:
                yawn_text = font_small.render(f"打哈欠: {drowsiness_result['yawn_counter']} 幀", True, (255, 165, 0))
                self.screen.blit(yawn_text, (10, debug_y + 75))
        
        # 瞌睡警報
        if drowsiness_result.get('should_alert', False):
            if int(time.time() * 3) % 2 == 0:  # 閃爍效果
                alert_text = font_large.render("!!! 瞌睡警報 !!!", True, (255, 0, 0))
                text_rect = alert_text.get_rect(center=(self.screen_width//2, 100))
                self.screen.blit(alert_text, text_rect)
                
                # 紅色邊框
                pygame.draw.rect(self.screen, (255, 0, 0), 
                               (0, 0, self.screen_width, self.screen_height), 8)
        
        # 控制說明（右下角）
        instructions = [
            "滑鼠移動: 手動控制",
            "左鍵: 手動射擊",
            "空白鍵: 切換模式",
            "TAB: 顯示/隱藏資訊",
            "R: 重置位置",
            "ESC: 退出"
        ]
        
        for i, instruction in enumerate(instructions):
            text = font_small.render(instruction, True, (200, 200, 200))
            self.screen.blit(text, (self.screen_width - 200, self.screen_height - 150 + i * 20))
    
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
    
    def run(self):
        """主要運行迴圈"""
        clock = pygame.time.Clock()
        running = True
        
        try:
            while running:
                # 讀取攝像頭畫面
                ret, frame = self.cap.read()
                if not ret:
                    print("❌ 無法讀取攝像頭畫面")
                    break
                
                # 瞌睡偵測處理
                processed_frame, drowsiness_result = self.drowsiness_detector.process_frame(frame)
                
                # 轉換為 pygame surface 並顯示為背景
                self.camera_surface = self.opencv_to_pygame(processed_frame)
                self.screen.blit(self.camera_surface, (0, 0))
                
                # 處理事件
                mouse_pos = pygame.mouse.get_pos()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_SPACE:
                            # 切換自動/手動模式
                            self.auto_fire_enabled = not self.auto_fire_enabled
                            mode = "自動" if self.auto_fire_enabled else "手動"
                            print(f"🔄 切換為 {mode} 模式")
                        elif event.key == pygame.K_TAB:
                            # 切換調試資訊顯示
                            self.show_debug_info = not self.show_debug_info
                        elif event.key == pygame.K_r:
                            # 重置雲台位置
                            self.reset_position()
                    
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # 左鍵手動射擊
                            self.fire_shot("手動")
                    
                    elif event.type == pygame.MOUSEMOTION:
                        # 手動控制雲台
                        if not self.auto_fire_enabled:
                            self.update_pan(mouse_pos[0])
                            self.update_tilt(mouse_pos[1])
                
                # 處理瞌睡警報
                self.handle_drowsiness_alert(drowsiness_result)
                
                # 繪製 UI 疊加層
                self.draw_ui_overlay(drowsiness_result)
                
                # 更新顯示
                pygame.display.flip()
                clock.tick(30)
                
        except KeyboardInterrupt:
            print("\n⚠️ 使用者中斷")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理資源"""
        print("\n🔧 關閉系統...")
        
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
    print("🎯 整合式雲台瞌睡防範系統")
    print("=" * 60)
    print("功能特色:")
    print("  ✓ 即時瞌睡偵測")
    print("  ✓ 自動射擊警示")
    print("  ✓ 手動雲台控制")
    print("  ✓ 攝像頭即時影像背景")
    print("=" * 60)
    print()
    
    try:
        system = IntegratedTurretSystem()
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