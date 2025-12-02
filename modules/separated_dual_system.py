#!/usr/bin/env python3
"""
分離式雙視窗系統
- 視窗1: 純淨瞄準控制（攝像頭影像 + 準星，只有滑鼠射擊控制）
- 視窗2: 獨立瞌睡偵測（完整分析界面，發送瞌睡通知）
- 完全分離，無自動射擊
"""

import pygame
import cv2
import numpy as np
import time
import threading
import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from modules.drowsiness_detector import DrowsinessDetector
from adafruit_servokit import ServoKit
from config import Config

class SeparatedDualSystem:
    def __init__(self):
        """初始化分離式雙視窗系統"""
        # 初始化 pygame
        pygame.init()
        
        # 配置參數
        self.config = Config()
        
        # 初始化攝像頭以獲取實際解析度
        temp_cap = cv2.VideoCapture(self.config.CAMERA_INDEX)
        temp_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.CAMERA_WIDTH)
        temp_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.CAMERA_HEIGHT)
        
        # 獲取實際的攝像頭解析度
        actual_width = int(temp_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(temp_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        temp_cap.release()
        
        self.screen_width = actual_width
        self.screen_height = actual_height
        
        print(f"攝像頭實際解析度: {actual_width}x{actual_height}")
        
        # 創建純淨瞄準視窗
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("瞄準控制 - ESC 退出")
        pygame.mouse.set_visible(False)  # 隱藏滑鼠，只顯示準星
        
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
        self.kit = ServoKit(channels=16)
        self.setup_servos()
        self.setup_turret_params()
        
        # 共享數據和鎖
        self.current_frame = None
        self.drowsiness_result = None
        self.frame_lock = threading.Lock()
        
        # 系統狀態
        self.running = True
        self.detection_window_running = True
        self.show_targeting_info = False
        
        # 瞌睡通知
        self.last_drowsy_alert_time = 0
        self.alert_cooldown = 5.0  # 5秒內不重複通知
        
        print("分離式雙視窗系統初始化完成")
        print("系統說明:")
        print("   瞄準視窗: 純淨攝像頭影像 + 準星控制")
        print("   偵測視窗: 完整瞌睡分析界面")
        print("   瞌睡時: 只發送通知訊息，無自動射擊")
        print("\n控制方式:")
        print("   - 滑鼠移動: 控制雲台瞄準")
        print("   - 左鍵點擊: 手動射擊")
        print("   - TAB 鍵: 顯示/隱藏瞄準資訊")
        print("   - R 鍵: 重置雲台位置")
        print("   - ESC 鍵: 退出系統")
    
    def setup_servos(self):
        """設定舵機參數"""
        self.kit.servo[1].set_pulse_width_range(500, 2500)  # Pan
        self.kit.servo[2].set_pulse_width_range(500, 2500)  # Tilt
        self.kit.continuous_servo[4].throttle = 0  # Fire
        print("舵機初始化完成")
    
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
        self.fire_speed = 0.9          # 提升速度到90%
        self.fire_duration = 0.36      # 增加30度角度 (原90度+30度=120度)
        self.fire_reset_duration = 0.37  # 對應的復位時間
        self.last_fire_time = 0
        self.fire_cooldown = 0.5       # 稍微縮短冷卻時間
        
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
        print("雲台已重置到中心位置")
    
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
    
    def fire_shot(self):
        """執行射擊動作"""
        current_time = time.time()
        
        if current_time - self.last_fire_time < self.fire_cooldown:
            print("射擊冷卻中...")
            return False
        
        print("射擊！")
        
        # 射擊動作
        self.kit.continuous_servo[self.fire_channel].throttle = -self.fire_speed
        time.sleep(self.fire_duration)
        
        self.kit.continuous_servo[self.fire_channel].throttle = self.fire_speed
        time.sleep(self.fire_reset_duration)
        
        self.kit.continuous_servo[self.fire_channel].throttle = 0
        
        self.last_fire_time = current_time
        return True
    
    def send_drowsiness_alert(self, result):
        """發送瞌睡警報通知"""
        current_time = time.time()
        
        # 檢查是否需要發送警報（避免過度通知）
        if current_time - self.last_drowsy_alert_time < self.alert_cooldown:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        state = result.get('state', 'Unknown')
        
        print(f"\n{'='*50}")
        print(f"瞌睡警報通知 - {timestamp}")
        print(f"{'='*50}")
        print(f"狀態: {state}")
        print(f"持續時間: {result.get('drowsy_duration', 0):.1f} 秒")
        print(f"眼睛閉合幀數: {result.get('eye_counter', 0)}")
        print(f"EAR 值: {result.get('ear', 0):.3f}")
        print(f"總瞌睡事件: {result.get('total_drowsy', 0)} 次")
        print(f"{'='*50}\n")
        
        self.last_drowsy_alert_time = current_time
    
    def opencv_to_pygame(self, cv_image):
        """將 OpenCV 影像轉換為 pygame surface"""
        # 直接轉換為RGB，保持原始比例
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        
        # 確保影像大小與視窗匹配
        h, w = rgb_image.shape[:2]
        if w != self.screen_width or h != self.screen_height:
            rgb_image = cv2.resize(rgb_image, (self.screen_width, self.screen_height))
        
        # 轉換為 pygame surface（轉置以正確顯示）
        return pygame.surfarray.make_surface(rgb_image.swapaxes(0, 1))
    
    def run_detection_window(self):
        """運行瞌睡偵測視窗（OpenCV）"""
        print("啟動瞌睡偵測視窗...")
        
        # 設定視窗位置（避免與 pygame 視窗重疊）
        cv2.namedWindow('瞌睡偵測系統', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('瞌睡偵測系統', 640, 480)
        cv2.moveWindow('瞌睡偵測系統', 850, 50)  # 移到右側
        
        while self.detection_window_running and self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("無法讀取攝像頭畫面")
                break
            
            # 更新共享數據（在處理前先保存原始影像）
            with self.frame_lock:
                self.current_frame = frame.copy()  # 保存純淨的原始影像給瞄準視窗
                self.drowsiness_result = None  # 暫時清空結果
            
            # 瞌睡偵測處理
            processed_frame, result = self.drowsiness_detector.process_frame(frame)
            
            # 更新瞌睡偵測結果
            with self.frame_lock:
                self.drowsiness_result = result
            
            # 檢查是否需要發送瞌睡警報
            if result.get('should_alert', False):
                self.send_drowsiness_alert(result)
            
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
                print(f"\n偵測統計:")
                print(f"   運行時間: {stats['runtime_str']}")
                print(f"   瞌睡事件: {stats['total_drowsy_events']} 次")
                print(f"   打哈欠事件: {stats['total_yawn_events']} 次")
                print(f"   當前狀態: {stats['current_state']}\n")
            elif key == ord('r'):
                # 重置統計
                self.drowsiness_detector.reset_statistics()
                print("瞌睡偵測統計已重置")
        
        cv2.destroyAllWindows()
        print("瞌睡偵測視窗已關閉")
    
    def draw_pure_crosshair(self, mouse_pos):
        """繪製純淨的十字準星"""
        # 繪製十字準心（參考原始邏輯）
        center_x, center_y = self.screen_width // 2, self.screen_height // 2
        
        # 根據射擊狀態決定準心顏色
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        crosshair_color = (255, 255, 255) if fire_ready else (255, 100, 100)
        
        # 繪製中心十字準心（比原版稍大）
        pygame.draw.line(self.screen, crosshair_color, 
                        (center_x - 20, center_y), (center_x + 20, center_y), 2)
        pygame.draw.line(self.screen, crosshair_color, 
                        (center_x, center_y - 20), (center_x, center_y + 20), 2)
        
        # 繪製死區（射擊精確度範圍）
        dead_zone = 20
        dead_zone_rect = pygame.Rect(center_x - dead_zone, center_y - dead_zone, 
                                   dead_zone * 2, dead_zone * 2)
        pygame.draw.rect(self.screen, (100, 100, 100), dead_zone_rect, 1)
        
        # 繪製滑鼠位置（紅色圓點）
        pygame.draw.circle(self.screen, (255, 0, 0), mouse_pos, 5)
        
        # 額外的準星指示圈（射擊狀態）
        if fire_ready:
            # 就緒時顯示綠色圓圈
            pygame.draw.circle(self.screen, (0, 255, 0), (center_x, center_y), 30, 1)
        else:
            # 冷卻時顯示進度圓弧
            progress = time_since_fire / self.fire_cooldown
            angle = int(360 * progress)
            if angle < 360:
                points = []
                for i in range(angle):
                    x = center_x + 25 * np.cos(np.radians(i - 90))
                    y = center_y + 25 * np.sin(np.radians(i - 90))
                    points.append((x, y))
                if len(points) > 1:
                    pygame.draw.lines(self.screen, (255, 165, 0), False, points, 2)
    
    def draw_targeting_info(self):
        """繪製瞄準資訊（可選顯示）"""
        if not self.show_targeting_info:
            return
        
        font_small = pygame.font.Font(None, 24)
        
        # 半透明背景
        info_surface = pygame.Surface((200, 120))
        info_surface.set_alpha(120)
        info_surface.fill((0, 0, 0))
        self.screen.blit(info_surface, (10, 10))
        
        # 雲台位置
        pan_rel = self.current_pan - 90
        pan_text = font_small.render(f"Pan: {pan_rel:+.0f}°", True, (255, 255, 255))
        self.screen.blit(pan_text, (15, 15))
        
        tilt_text = font_small.render(f"Tilt: {self.current_tilt:.0f}°", True, (255, 255, 255))
        self.screen.blit(tilt_text, (15, 35))
        
        # 射擊狀態
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        fire_color = (0, 255, 0) if fire_ready else (255, 100, 100)
        fire_text = font_small.render(
            f"射擊: {'就緒' if fire_ready else f'{self.fire_cooldown - time_since_fire:.1f}s'}", 
            True, fire_color
        )
        self.screen.blit(fire_text, (15, 55))
        
        # 控制提示
        help_text = font_small.render("TAB:資訊 R:重置 ESC:退出", True, (200, 200, 200))
        self.screen.blit(help_text, (15, 85))
    
    def run_targeting_window(self):
        """運行純淨瞄準控制視窗（pygame）"""
        print("啟動純淨瞄準控制視窗...")
        
        # 設定 pygame 視窗位置
        os.environ['SDL_VIDEO_WINDOW_POS'] = '50,50'  # 左上角位置
        
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
                        self.show_targeting_info = not self.show_targeting_info
                        print(f"瞄準資訊: {'顯示' if self.show_targeting_info else '隱藏'}")
                    elif event.key == pygame.K_r:
                        self.reset_position()
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左鍵射擊
                        self.fire_shot()
                
                elif event.type == pygame.MOUSEMOTION:
                    # 更新雲台位置
                    self.update_pan(mouse_pos[0])
                    self.update_tilt(mouse_pos[1])
            
            # 獲取純淨攝像頭影像
            current_frame = None
            with self.frame_lock:
                if self.current_frame is not None:
                    current_frame = self.current_frame.copy()
            
            # 繪製純淨背景（原始攝像頭影像）
            if current_frame is not None:
                camera_surface = self.opencv_to_pygame(current_frame)
                self.screen.blit(camera_surface, (0, 0))
            else:
                self.screen.fill((30, 30, 30))  # 深灰色背景
                font = pygame.font.Font(None, 48)
                text = font.render("等待攝像頭...", True, (255, 255, 255))
                text_rect = text.get_rect(center=(self.screen_width//2, self.screen_height//2))
                self.screen.blit(text, text_rect)
            
            # 繪製純淨準星
            self.draw_pure_crosshair(mouse_pos)
            
            # 繪製瞄準資訊（可選）
            self.draw_targeting_info()
            
            # 更新顯示
            pygame.display.flip()
            clock.tick(30)
        
        print("純淨瞄準控制視窗已關閉")
    
    def run(self):
        """主要運行迴圈"""
        print("\n啟動分離式雙視窗系統...")
        print("視窗佈局: 左側=瞄準控制, 右側=瞌睡偵測\n")
        
        # 啟動瞌睡偵測視窗線程
        detection_thread = threading.Thread(target=self.run_detection_window, daemon=True)
        detection_thread.start()
        
        try:
            # 運行純淨瞄準控制視窗（主線程）
            self.run_targeting_window()
            
        except KeyboardInterrupt:
            print("\n使用者中斷")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理資源"""
        print("\n關閉分離式雙視窗系統...")
        
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
        
        # 關閉視窗
        cv2.destroyAllWindows()
        pygame.quit()
        
        # 顯示最終統計
        if hasattr(self, 'drowsiness_detector'):
            stats = self.drowsiness_detector.get_statistics()
            print(f"\n最終統計報告:")
            print(f"   運行時間: {stats['runtime_str']}")
            print(f"   瞌睡事件: {stats['total_drowsy_events']} 次")
            print(f"   打哈欠事件: {stats['total_yawn_events']} 次")
        
        print("系統已完全關閉")


def main():
    """主程式入口"""
    print("=" * 70)
    print("分離式雙視窗雲台系統")
    print("=" * 70)
    print("系統特色:")
    print("  純淨瞄準視窗: 原始攝像頭影像 + 專業準星")
    print("  瞌睡偵測視窗: 完整分析界面 + 即時通知")
    print("  手動射擊: 只有滑鼠控制，無自動射擊")
    print("  訊息通知: 瞌睡時發送警報訊息")
    print("  獨立運行: 兩個視窗完全分離")
    print("=" * 70)
    print()
    
    try:
        system = SeparatedDualSystem()
        system.run()
    except Exception as e:
        print(f"系統錯誤: {e}")
        print("\n檢查項目:")
        print("  1. 攝像頭是否正常連接？")
        print("  2. PCA9685 舵機控制板是否正常？")
        print("  3. 是否已下載 dlib 面部特徵點模型？")
        print("  4. 相關依賴套件是否已安裝？")


if __name__ == "__main__":
    main()