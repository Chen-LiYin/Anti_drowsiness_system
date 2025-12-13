#!/usr/bin/env python3
"""
虛擬搖桿 UI 模組
用於本地 pygame 視窗和網頁遠端控制的搖桿介面
"""

import pygame
import math


class VirtualJoystick:
    """虛擬搖桿類別"""

    def __init__(self, x, y, outer_radius=60, inner_radius=25):
        """
        初始化虛擬搖桿

        Args:
            x: 搖桿中心 X 座標
            y: 搖桿中心 Y 座標
            outer_radius: 外圈半徑
            inner_radius: 內圈（搖桿頭）半徑
        """
        self.base_x = x
        self.base_y = y
        self.outer_radius = outer_radius
        self.inner_radius = inner_radius

        # 搖桿頭當前位置
        self.stick_x = x
        self.stick_y = y

        # 是否正在拖動
        self.is_dragging = False

        # 輸出值（-1.0 到 1.0）
        self.output_x = 0.0
        self.output_y = 0.0

    def handle_mouse_down(self, mouse_x, mouse_y):
        """處理滑鼠按下事件"""
        # 檢查是否點擊在搖桿區域內
        distance = math.sqrt((mouse_x - self.base_x)**2 + (mouse_y - self.base_y)**2)
        if distance <= self.outer_radius:
            self.is_dragging = True
            self.update_stick_position(mouse_x, mouse_y)
            return True
        return False

    def handle_mouse_up(self):
        """處理滑鼠放開事件"""
        if self.is_dragging:
            self.is_dragging = False
            # 搖桿回中
            self.stick_x = self.base_x
            self.stick_y = self.base_y
            self.output_x = 0.0
            self.output_y = 0.0
            return True
        return False

    def handle_mouse_motion(self, mouse_x, mouse_y):
        """處理滑鼠移動事件"""
        if self.is_dragging:
            self.update_stick_position(mouse_x, mouse_y)
            return True
        return False

    def update_stick_position(self, mouse_x, mouse_y):
        """更新搖桿頭位置"""
        # 計算相對於中心的位移
        dx = mouse_x - self.base_x
        dy = mouse_y - self.base_y

        # 計算距離
        distance = math.sqrt(dx**2 + dy**2)

        # 限制在外圈範圍內
        max_distance = self.outer_radius - self.inner_radius
        if distance > max_distance:
            # 正規化並乘以最大距離
            dx = (dx / distance) * max_distance
            dy = (dy / distance) * max_distance
            distance = max_distance

        # 更新搖桿頭位置
        self.stick_x = self.base_x + dx
        self.stick_y = self.base_y + dy

        # 計算輸出值（-1.0 到 1.0）
        self.output_x = dx / max_distance if max_distance > 0 else 0.0
        self.output_y = dy / max_distance if max_distance > 0 else 0.0

    def draw(self, surface):
        """繪製搖桿"""
        # 繪製外圈（底座）
        pygame.draw.circle(surface, (50, 50, 50), (int(self.base_x), int(self.base_y)),
                          self.outer_radius, 0)
        pygame.draw.circle(surface, (100, 100, 100), (int(self.base_x), int(self.base_y)),
                          self.outer_radius, 2)

        # 繪製十字線
        cross_length = self.outer_radius - 10
        pygame.draw.line(surface, (80, 80, 80),
                        (self.base_x - cross_length, self.base_y),
                        (self.base_x + cross_length, self.base_y), 1)
        pygame.draw.line(surface, (80, 80, 80),
                        (self.base_x, self.base_y - cross_length),
                        (self.base_x, self.base_y + cross_length), 1)

        # 繪製搖桿頭（內圈）
        if self.is_dragging:
            color = (100, 200, 255)  # 拖動時是藍色
        else:
            color = (150, 150, 150)  # 靜止時是灰色

        pygame.draw.circle(surface, color, (int(self.stick_x), int(self.stick_y)),
                          self.inner_radius, 0)
        pygame.draw.circle(surface, (200, 200, 200), (int(self.stick_x), int(self.stick_y)),
                          self.inner_radius, 2)

    def get_values(self):
        """獲取搖桿輸出值"""
        return self.output_x, self.output_y


class FireButton:
    """射擊按鈕類別"""

    def __init__(self, x, y, radius=40):
        """
        初始化射擊按鈕

        Args:
            x: 按鈕中心 X 座標
            y: 按鈕中心 Y 座標
            radius: 按鈕半徑
        """
        self.x = x
        self.y = y
        self.radius = radius
        self.is_pressed = False
        self.cooldown = False

    def handle_mouse_down(self, mouse_x, mouse_y):
        """處理滑鼠按下事件"""
        distance = math.sqrt((mouse_x - self.x)**2 + (mouse_y - self.y)**2)
        if distance <= self.radius:
            self.is_pressed = True
            return True
        return False

    def handle_mouse_up(self):
        """處理滑鼠放開事件"""
        if self.is_pressed:
            self.is_pressed = False
            return True
        return False

    def set_cooldown(self, cooldown):
        """設置冷卻狀態"""
        self.cooldown = cooldown

    def draw(self, surface):
        """繪製射擊按鈕"""
        # 根據狀態選擇顏色
        if self.cooldown:
            color = (100, 100, 100)  # 冷卻中是灰色
            text_color = (150, 150, 150)
        elif self.is_pressed:
            color = (255, 100, 100)  # 按下是亮紅色
            text_color = (255, 255, 255)
        else:
            color = (200, 50, 50)    # 正常是紅色
            text_color = (255, 255, 255)

        # 繪製按鈕圓形
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), self.radius, 0)
        pygame.draw.circle(surface, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 3)

        # 繪製文字
        font = pygame.font.Font(None, 30)
        text = font.render("FIRE", True, text_color)
        text_rect = text.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(text, text_rect)
