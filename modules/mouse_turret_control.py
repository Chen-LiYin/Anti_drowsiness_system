#!/usr/bin/env python3
"""
滑鼠控制雲台射擊系統
- 滑鼠水平移動: Pan (通道 0 - 360度舵機)
- 滑鼠垂直移動: Tilt (通道 1 - 普通舵機)
- 左鍵點擊: 射擊 (通道 2 - 普通舵機)
"""

import pygame
import time
import math
from adafruit_servokit import ServoKit

class MouseTurretControl:
    def __init__(self):
        # 初始化 pygame
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("滑鼠雲台控制 - ESC 鍵退出")
        pygame.mouse.set_visible(True)
        
        # 初始化 ServoKit
        print("📡 初始化 PCA9685...")
        self.kit = ServoKit(channels=16)
        
        # 舵機配置
        self.setup_servos()
        
        # 控制參數
        self.screen_width = 800
        self.screen_height = 600
        self.dead_zone = 20  # 死區，避免抖動
        
        # Pan 控制 (360度舵機)
        self.pan_channel = 0
        self.pan_position = 0  # 當前角度 (0-359)
        self.pan_sensitivity = 0.5  # 敏感度
        
        # Tilt 控制 (普通舵機)
        self.tilt_channel = 1
        self.tilt_min = 30   # 最小角度
        self.tilt_max = 150  # 最大角度
        self.tilt_center = 90
        self.current_tilt = self.tilt_center
        
        # 射擊控制 (普通舵機)
        self.fire_channel = 2
        self.fire_ready_angle = 90   # 待機角度
        self.fire_shoot_angle = 45   # 射擊角度
        self.fire_duration = 0.5     # 射擊持續時間(秒)
        self.last_fire_time = 0
        self.fire_cooldown = 1.0     # 射擊冷卻時間(秒)
        
        # 初始化位置
        self.reset_position()
        
        print("✅ 滑鼠雲台控制系統已啟動")
        print("🎯 控制說明:")
        print("   - 滑鼠左右移動: Pan 控制")
        print("   - 滑鼠上下移動: Tilt 控制")
        print("   - 左鍵點擊: 射擊")
        print("   - ESC 鍵: 退出程式")
    
    def setup_servos(self):
        """設定舵機參數"""
        # 普通舵機設定
        self.kit.servo[1].set_pulse_width_range(500, 2500)  # Tilt
        self.kit.servo[2].set_pulse_width_range(500, 2500)  # Fire
        
        # 停止 Pan 舵機 (360度)
        self.kit.continuous_servo[0].throttle = 0
        print("✅ 舵機初始化完成")
    
    def reset_position(self):
        """重置到中心位置"""
        print("🎯 重置雲台位置...")
        
        # Pan 歸零
        self.pan_position = 0
        self.kit.continuous_servo[self.pan_channel].throttle = 0
        
        # Tilt 回中心
        self.current_tilt = self.tilt_center
        self.kit.servo[self.tilt_channel].angle = self.current_tilt
        
        # 射擊舵機回待機位置
        self.kit.servo[self.fire_channel].angle = self.fire_ready_angle
        
        time.sleep(1)
        print("✅ 雲台已重置")
    
    def move_pan_to_angle(self, target_angle, speed=0.3):
        """移動 Pan 到指定角度"""
        target_angle = target_angle % 360
        current_pos = self.pan_position
        
        # 計算最短路徑
        diff = target_angle - current_pos
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        
        if abs(diff) < 2:  # 已經很接近
            self.kit.continuous_servo[self.pan_channel].throttle = 0
            return
        
        # 開始旋轉
        direction = 1 if diff > 0 else -1
        self.kit.continuous_servo[self.pan_channel].throttle = direction * speed
        
        # 計算旋轉時間
        rotation_time = abs(diff) / 360.0 * 2.0  # 假設360度需要2秒
        
        start_time = time.time()
        while time.time() - start_time < rotation_time:
            time.sleep(0.01)
        
        # 停止並更新位置
        self.kit.continuous_servo[self.pan_channel].throttle = 0
        self.pan_position = target_angle
    
    def update_tilt(self, mouse_y):
        """根據滑鼠 Y 座標更新 Tilt"""
        # 映射滑鼠 Y 座標到舵機角度
        # 滑鼠在上方 → 小角度 (向上看)
        # 滑鼠在下方 → 大角度 (向下看)
        ratio = mouse_y / self.screen_height
        target_tilt = self.tilt_min + ratio * (self.tilt_max - self.tilt_min)
        target_tilt = max(self.tilt_min, min(self.tilt_max, target_tilt))
        
        # 死區檢查
        if abs(target_tilt - self.current_tilt) > 2:
            self.current_tilt = target_tilt
            self.kit.servo[self.tilt_channel].angle = target_tilt
    
    def update_pan(self, mouse_x):
        """根據滑鼠 X 座標更新 Pan"""
        # 映射滑鼠 X 座標到角度
        center_x = self.screen_width // 2
        offset_x = mouse_x - center_x
        
        # 死區檢查
        if abs(offset_x) > self.dead_zone:
            # 計算目標角度
            angle_offset = (offset_x / center_x) * 180 * self.pan_sensitivity
            target_angle = (self.pan_position + angle_offset) % 360
            
            # 移動到目標角度
            self.move_pan_to_angle(target_angle, speed=0.2)
    
    def fire_shot(self):
        """執行射擊動作"""
        current_time = time.time()
        
        # 檢查冷卻時間
        if current_time - self.last_fire_time < self.fire_cooldown:
            print("🔥 射擊冷卻中...")
            return
        
        print("🔥 射擊！")
        
        # 射擊動作
        self.kit.servo[self.fire_channel].angle = self.fire_shoot_angle
        time.sleep(self.fire_duration)
        self.kit.servo[self.fire_channel].angle = self.fire_ready_angle
        
        self.last_fire_time = current_time
    
    def draw_ui(self, mouse_pos):
        """繪製使用者介面"""
        self.screen.fill((50, 50, 50))  # 深灰色背景
        
        # 繪製十字準心
        center_x, center_y = self.screen_width // 2, self.screen_height // 2
        pygame.draw.line(self.screen, (255, 255, 255), 
                        (center_x - 20, center_y), (center_x + 20, center_y), 2)
        pygame.draw.line(self.screen, (255, 255, 255), 
                        (center_x, center_y - 20), (center_x, center_y + 20), 2)
        
        # 繪製死區
        dead_zone_rect = pygame.Rect(center_x - self.dead_zone, center_y - self.dead_zone, 
                                   self.dead_zone * 2, self.dead_zone * 2)
        pygame.draw.rect(self.screen, (100, 100, 100), dead_zone_rect, 1)
        
        # 繪製滑鼠位置
        pygame.draw.circle(self.screen, (255, 0, 0), mouse_pos, 5)
        
        # 顯示狀態資訊
        font = pygame.font.Font(None, 36)
        
        # Pan 位置
        pan_text = font.render(f"Pan: {self.pan_position:.1f}°", True, (255, 255, 255))
        self.screen.blit(pan_text, (10, 10))
        
        # Tilt 位置
        tilt_text = font.render(f"Tilt: {self.current_tilt:.1f}°", True, (255, 255, 255))
        self.screen.blit(tilt_text, (10, 50))
        
        # 射擊冷卻
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        fire_color = (0, 255, 0) if fire_ready else (255, 100, 100)
        fire_text = font.render(f"射擊: {'就緒' if fire_ready else f'冷卻 {self.fire_cooldown - time_since_fire:.1f}s'}", 
                               True, fire_color)
        self.screen.blit(fire_text, (10, 90))
        
        # 控制說明
        small_font = pygame.font.Font(None, 24)
        instructions = [
            "滑鼠移動: 控制 Pan/Tilt",
            "左鍵點擊: 射擊",
            "ESC: 退出"
        ]
        for i, instruction in enumerate(instructions):
            text = small_font.render(instruction, True, (200, 200, 200))
            self.screen.blit(text, (10, self.screen_height - 80 + i * 25))
        
        pygame.display.flip()
    
    def run(self):
        """主要控制迴圈"""
        clock = pygame.time.Clock()
        running = True
        
        try:
            while running:
                mouse_pos = pygame.mouse.get_pos()
                
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_r:  # R 鍵重置
                            self.reset_position()
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:  # 左鍵
                            self.fire_shot()
                    elif event.type == pygame.MOUSEMOTION:
                        # 更新舵機位置
                        self.update_pan(mouse_pos[0])
                        self.update_tilt(mouse_pos[1])
                
                # 繪製介面
                self.draw_ui(mouse_pos)
                
                # 限制幀率
                clock.tick(60)
                
        except KeyboardInterrupt:
            print("\n⚠️  使用者中斷")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理資源"""
        print("\n🔄 關閉雲台控制系統...")
        
        # 停止所有舵機
        self.kit.continuous_servo[self.pan_channel].throttle = 0
        self.kit.servo[self.tilt_channel].angle = 90
        self.kit.servo[self.fire_channel].angle = self.fire_ready_angle
        
        pygame.quit()
        print("✅ 系統已關閉")


def main():
    """主程式"""
    print("🎮 滑鼠雲台控制系統")
    print("=" * 50)
    
    try:
        controller = MouseTurretControl()
        controller.run()
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        print("\n🔍 檢查項目:")
        print("  1. 是否已安裝 pygame? (pip install pygame)")
        print("  2. PCA9685 是否正常連接?")
        print("  3. 舵機是否正確連接?")

if __name__ == "__main__":
    main()