#!/usr/bin/env python3
"""
雲台控制模組 - 使用 smbus（不依賴 Adafruit 庫）
控制 Pan-Tilt 雲台追蹤人臉
"""

import time
import logging
import smbus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TurretController:
    """雲台控制器 - smbus 版本"""
    
    def __init__(self, config):
        """
        初始化雲台控制器
        
        Args:
            config: 配置物件
        """
        self.config = config
        
        try:
            # 初始化 I2C
            self.bus = smbus.SMBus(1)
            self.pca9685_addr = 0x40
            
            # 初始化 PCA9685
            self._init_pca9685()
            
            logger.info("✅ PCA9685 初始化成功")
            
            # 設定舵機通道
            self.pan_channel = getattr(config, 'SERVO_PAN_CHANNEL', 0)
            self.tilt_channel = getattr(config, 'SERVO_TILT_CHANNEL', 1)
            
            # 角度範圍
            self.pan_min = getattr(config, 'PAN_MIN', 45)
            self.pan_max = getattr(config, 'PAN_MAX', 135)
            self.tilt_min = getattr(config, 'TILT_MIN', 45)
            self.tilt_max = getattr(config, 'TILT_MAX', 135)
            
            # 當前角度
            self.current_pan = 90
            self.current_tilt = 90
            
            # 校正值
            self.pan_offset = getattr(config, 'PAN_OFFSET', 0)
            self.tilt_offset = getattr(config, 'TILT_OFFSET', 0)
            
            # 平滑移動參數
            self.smooth_steps = getattr(config, 'SERVO_SMOOTH_STEPS', 5)
            self.smooth_delay = getattr(config, 'SERVO_SMOOTH_DELAY', 0.02)
            
            # 回到中心位置
            self.center()
            
            logger.info(f"✅ 雲台控制器初始化完成")
            logger.info(f"   Pan 通道: {self.pan_channel}, 範圍: {self.pan_min}-{self.pan_max}°")
            logger.info(f"   Tilt 通道: {self.tilt_channel}, 範圍: {self.tilt_min}-{self.tilt_max}°")
            
        except Exception as e:
            logger.error(f"❌ 雲台初始化失敗: {e}")
            raise
    
    def _init_pca9685(self):
        """初始化 PCA9685 晶片"""
        # 進入睡眠模式
        self.bus.write_byte_data(self.pca9685_addr, 0x00, 0x10)
        time.sleep(0.005)
        
        # 設定 PWM 頻率為 50Hz（舵機標準）
        # prescale = 25MHz / (4096 * 50Hz) - 1 = 121 (0x79)
        self.bus.write_byte_data(self.pca9685_addr, 0xFE, 0x79)
        
        # 喚醒並啟用自動增量
        self.bus.write_byte_data(self.pca9685_addr, 0x00, 0xA0)
        time.sleep(0.005)
    
    def _set_servo_angle(self, channel, angle):
        """
        設定舵機角度
        
        Args:
            channel: 通道編號 (0-15)
            angle: 角度 (0-180)
        """
        # 限制角度範圍
        angle = max(0, min(180, angle))
        
        # 計算脈衝寬度
        # 0° = 0.5ms = 102 (0.5/20*4096)
        # 180° = 2.5ms = 512 (2.5/20*4096)
        pulse = int(102 + 410 * angle / 180)
        
        # 計算暫存器地址
        base_reg = 0x06 + 4 * channel
        
        # 寫入 PWM 值
        self.bus.write_i2c_block_data(
            self.pca9685_addr, 
            base_reg,
            [0, 0, pulse & 0xFF, pulse >> 8]
        )
    
    def set_pan(self, angle, smooth=True):
        """
        設定水平旋轉角度
        
        Args:
            angle: 角度 (0-180)
            smooth: 是否平滑移動
        """
        # 限制範圍並加入校正值
        angle = max(self.pan_min, min(self.pan_max, angle))
        angle += self.pan_offset
        angle = max(0, min(180, angle))
        
        if smooth and abs(angle - self.current_pan) > 5:
            self._smooth_move(self.pan_channel, self.current_pan, angle)
        else:
            self._set_servo_angle(self.pan_channel, angle)
        
        self.current_pan = angle
        logger.debug(f"Pan → {angle}°")
    
    def set_tilt(self, angle, smooth=True):
        """
        設定俯仰角度
        
        Args:
            angle: 角度 (0-180)
            smooth: 是否平滑移動
        """
        # 限制範圍並加入校正值
        angle = max(self.tilt_min, min(self.tilt_max, angle))
        angle += self.tilt_offset
        angle = max(0, min(180, angle))
        
        if smooth and abs(angle - self.current_tilt) > 5:
            self._smooth_move(self.tilt_channel, self.current_tilt, angle)
        else:
            self._set_servo_angle(self.tilt_channel, angle)
        
        self.current_tilt = angle
        logger.debug(f"Tilt → {angle}°")
    
    def set_position(self, pan, tilt, smooth=True):
        """
        同時設定 Pan 和 Tilt
        
        Args:
            pan: 水平角度
            tilt: 俯仰角度
            smooth: 是否平滑移動
        """
        self.set_pan(pan, smooth)
        time.sleep(0.01)  # 小延遲避免 I2C 衝突
        self.set_tilt(tilt, smooth)
    
    def center(self):
        """回到中心位置"""
        logger.info("🎯 雲台回中")
        self.set_position(90, 90, smooth=True)
        time.sleep(0.5)
    
    def track_face(self, face_rect, frame_shape):
        """
        追蹤臉部位置
        
        Args:
            face_rect: 臉部矩形 (x, y, w, h)
            frame_shape: 影像尺寸 (height, width)
        """
        if face_rect is None:
            return
        
        x, y, w, h = face_rect
        height, width = frame_shape[:2]
        
        # 計算臉部中心點
        face_center_x = x + w // 2
        face_center_y = y + h // 2
        
        # 計算偏移（相對於畫面中心）
        offset_x = face_center_x - width // 2
        offset_y = face_center_y - height // 2
        
        # 設定死區（避免抖動）
        dead_zone = getattr(self.config, 'TRACKING_DEAD_ZONE', 30)
        
        # 計算需要移動的角度
        pan_adjustment = 0
        tilt_adjustment = 0
        
        if abs(offset_x) > dead_zone:
            # 水平方向：臉在右邊 → 雲台往右轉（增加角度）
            pan_adjustment = int(offset_x / width * 30)  # 最大調整 30 度
        
        if abs(offset_y) > dead_zone:
            # 垂直方向：臉在下面 → 雲台往下轉（增加角度）
            tilt_adjustment = int(offset_y / height * 20)  # 最大調整 20 度
        
        # 應用調整
        new_pan = self.current_pan + pan_adjustment
        new_tilt = self.current_tilt + tilt_adjustment
        
        # 設定新位置
        if pan_adjustment != 0 or tilt_adjustment != 0:
            self.set_position(new_pan, new_tilt, smooth=True)
            logger.debug(f"追蹤調整: Pan {pan_adjustment:+d}°, Tilt {tilt_adjustment:+d}°")
    
    def _smooth_move(self, channel, start_angle, end_angle):
        """
        平滑移動到目標角度
        
        Args:
            channel: 舵機通道
            start_angle: 起始角度
            end_angle: 目標角度
        """
        step_size = (end_angle - start_angle) / self.smooth_steps
        
        for i in range(self.smooth_steps):
            angle = start_angle + step_size * (i + 1)
            self._set_servo_angle(channel, int(angle))
            time.sleep(self.smooth_delay)
    
    def sweep_test(self):
        """測試掃描動作"""
        logger.info("🔄 執行雲台測試掃描...")
        
        # 水平掃描
        logger.info("水平掃描...")
        for angle in range(45, 136, 15):
            self.set_pan(angle)
            time.sleep(0.3)
        
        self.set_pan(90)
        time.sleep(0.5)
        
        # 垂直掃描
        logger.info("垂直掃描...")
        for angle in range(60, 121, 10):
            self.set_tilt(angle)
            time.sleep(0.3)
        
        # 回中心
        self.center()
        logger.info("✅ 測試完成")
    
    def cleanup(self):
        """清理資源"""
        logger.info("🔄 雲台回到中心位置...")
        self.center()
        logger.info("✅ 雲台控制器已關閉")


def main():
    """測試程式"""
    import sys
    sys.path.append('..')
    from config import Config
    
    print("="*60)
    print("🎮 雲台控制測試")
    print("="*60)
    
    config = Config()
    turret = TurretController(config)
    
    try:
        # 執行測試掃描
        turret.sweep_test()
        
        print("\n手動控制測試：")
        print("  → 向左")
        turret.set_pan(45)
        time.sleep(1)
        
        print("  → 向右")
        turret.set_pan(135)
        time.sleep(1)
        
        print("  → 向上")
        turret.set_tilt(60)
        time.sleep(1)
        
        print("  → 向下")
        turret.set_tilt(120)
        time.sleep(1)
        
        print("  → 回中心")
        turret.center()
        
        print("\n✅ 所有測試完成！")
        
    except KeyboardInterrupt:
        print("\n⚠️  使用者中斷")
    finally:
        turret.cleanup()


if __name__ == "__main__":
    main()