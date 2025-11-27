#!/usr/bin/env python3
"""
簡單的舵機測試程式
測試 MG996R 是否能正常工作
"""

import time
import smbus

def test_servo():
    """測試單一舵機"""
    print("🎮 開始測試 MG996R 舵機...")
    
    try:
        # 初始化 I2C
        bus = smbus.SMBus(1)
        pca9685_addr = 0x40
        
        print("📡 初始化 PCA9685...")
        
        # 初始化 PCA9685
        # 進入睡眠模式
        bus.write_byte_data(pca9685_addr, 0x00, 0x10)
        time.sleep(0.005)
        
        # 設定 PWM 頻率為 50Hz
        bus.write_byte_data(pca9685_addr, 0xFE, 0x79)
        
        # 喚醒並啟用自動增量
        bus.write_byte_data(pca9685_addr, 0x00, 0xA0)
        time.sleep(0.005)
        
        print("✅ PCA9685 初始化完成")
        
        # 測試通道 0 (Pan)
        channel = 0
        
        print(f"\n🔄 測試通道 {channel}...")
        
        # 測試不同角度
        test_angles = [0, 45, 90, 135, 180, 90]  # 最後回到中間
        
        for angle in test_angles:
            print(f"  → 設定角度: {angle}°")
            
            # 計算脈衝寬度 (0.5ms~2.5ms)
            # 0° = 0.5ms = 102
            # 180° = 2.5ms = 512
            pulse = int(102 + 410 * angle / 180)
            
            # 計算暫存器地址
            base_reg = 0x06 + 4 * channel
            
            # 寫入 PWM 值
            bus.write_i2c_block_data(
                pca9685_addr, 
                base_reg,
                [0, 0, pulse & 0xFF, pulse >> 8]
            )
            
            print(f"    脈衝值: {pulse}")
            time.sleep(1.5)  # 等待舵機移動
        
        print("\n✅ 測試完成！")
        
        # 詢問是否要進行手動測試
        print("\n🎯 想要手動測試特定角度嗎？")
        print("輸入角度 (0-180)，或按 Enter 結束：")
        
        while True:
            try:
                user_input = input("角度: ").strip()
                if not user_input:
                    break
                
                angle = float(user_input)
                if 0 <= angle <= 180:
                    pulse = int(102 + 410 * angle / 180)
                    base_reg = 0x06 + 4 * channel
                    
                    bus.write_i2c_block_data(
                        pca9685_addr, 
                        base_reg,
                        [0, 0, pulse & 0xFF, pulse >> 8]
                    )
                    print(f"✅ 設定為 {angle}°")
                else:
                    print("❌ 角度必須在 0-180 之間")
                    
            except ValueError:
                print("❌ 請輸入有效數字")
            except KeyboardInterrupt:
                break
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        print("\n🔍 檢查事項:")
        print("  1. PCA9685 是否正確連接到 I2C?")
        print("  2. I2C 是否已啟用? (sudo raspi-config)")
        print("  3. 舵機電源是否充足? (建議外接 5V 電源)")
        print("  4. 線路連接是否正確?")
        
    print("\n👋 測試結束")

if __name__ == "__main__":
    test_servo()