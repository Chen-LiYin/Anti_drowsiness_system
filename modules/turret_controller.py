#!/usr/bin/env python3
"""
基礎舵機測試 - 測試單個舵機是否能動
"""

import time
import board
import busio
from adafruit_servokit import ServoKit

print("="*60)
print("🎮 舵機基礎測試")
print("="*60)
print()

# 步驟 1: 初始化 I2C
print("步驟 1: 初始化 I2C...")
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    print("✅ I2C 初始化成功")
except Exception as e:
    print(f"❌ I2C 初始化失敗: {e}")
    print("\n請確認：")
    print("  1. I2C 已啟用（sudo raspi-config）")
    print("  2. 接線正確（SDA、SCL）")
    exit(1)

# 步驟 2: 初始化 PCA9685
print("\n步驟 2: 初始化 PCA9685...")
try:
    kit = ServoKit(channels=16)
    print("✅ PCA9685 初始化成功")
except Exception as e:
    print(f"❌ PCA9685 初始化失敗: {e}")
    print("\n請確認：")
    print("  1. PCA9685 已接電（VCC、GND）")
    print("  2. 執行 sudo i2cdetect -y 1 確認地址 0x40")
    exit(1)

# 步驟 3: 選擇要測試的通道
print("\n步驟 3: 選擇舵機通道")
print("您的舵機接在 PCA9685 的哪個通道？")
print("（通常是 0-15，如果是第一個就輸入 0）")

while True:
    try:
        channel = int(input("請輸入通道編號 (0-15): "))
        if 0 <= channel <= 15:
            break
        else:
            print("❌ 請輸入 0-15 之間的數字")
    except ValueError:
        print("❌ 請輸入有效的數字")

print(f"✅ 將測試通道 {channel}")

# 步驟 4: 測試舵機
print("\n步驟 4: 開始測試舵機...")
print("="*60)

try:
    print("\n⚠️  請確認：")
    print("  1. 舵機已連接到 PCA9685")
    print("  2. 外部 5V 電源已接上（V+ 和 GND）")
    print("  3. 舵機三條線連接正確：")
    print("     - 棕色/黑色 → GND")
    print("     - 紅色 → V+")
    print("     - 橙色/黃色 → PWM")
    
    input("\n按 Enter 開始測試...")
    
    print("\n" + "="*60)
    print("🎬 測試開始！")
    print("="*60)
    
    # 測試 1: 中間位置（90度）
    print("\n測試 1: 移動到中間位置 (90°)")
    kit.servo[channel].angle = 90
    print("→ 舵機應該移動到中間位置")
    time.sleep(2)
    
    # 測試 2: 最小位置（0度）
    print("\n測試 2: 移動到最小位置 (0°)")
    kit.servo[channel].angle = 0
    print("→ 舵機應該逆時針轉到底")
    time.sleep(2)
    
    # 測試 3: 最大位置（180度）
    print("\n測試 3: 移動到最大位置 (180°)")
    kit.servo[channel].angle = 180
    print("→ 舵機應該順時針轉到底")
    time.sleep(2)
    
    # 測試 4: 回到中間
    print("\n測試 4: 回到中間位置 (90°)")
    kit.servo[channel].angle = 90
    print("→ 舵機應該回到中間")
    time.sleep(1)
    
    # 測試 5: 連續掃描
    print("\n測試 5: 連續掃描測試")
    print("→ 舵機將來回掃描 3 次")
    
    for i in range(3):
        print(f"  第 {i+1} 次掃描...")
        
        # 0 → 180
        for angle in range(0, 181, 15):
            kit.servo[channel].angle = angle
            time.sleep(0.1)
        
        # 180 → 0
        for angle in range(180, -1, -15):
            kit.servo[channel].angle = angle
            time.sleep(0.1)
    
    # 回到中間
    kit.servo[channel].angle = 90
    
    print("\n" + "="*60)
    print("✅ 測試完成！")
    print("="*60)
    
    # 詢問結果
    print("\n舵機有正常移動嗎？")
    result = input("(y/n): ").lower()
    
    if result == 'y':
        print("\n🎉 太好了！舵機工作正常！")
        print("\n下一步:")
        print("  • 如果要測試第二個舵機，再執行一次這個程式")
        print("  • 如果兩個舵機都正常，可以開始整合到雲台控制")
    else:
        print("\n🔧 故障排除:")
        print("  1. 檢查舵機接線（GND、V+、PWM）")
        print("  2. 確認外部 5V 電源已接上且足夠（建議 3A 以上）")
        print("  3. 檢查舵機是否損壞（換一個試試）")
        print("  4. 確認 V+ 電源端子有電壓（用三用電表測量）")

except KeyboardInterrupt:
    print("\n\n⚠️  測試中斷")
    kit.servo[channel].angle = 90
    print("→ 舵機已回到中間位置")

except Exception as e:
    print(f"\n❌ 測試過程發生錯誤: {e}")
    print("\n可能的原因:")
    print("  1. 舵機沒有接好")
    print("  2. 外部電源沒接或電壓不足")
    print("  3. PCA9685 損壞")

finally:
    print("\n✅ 測試程式結束")