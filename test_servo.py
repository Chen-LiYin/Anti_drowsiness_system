import time 
from adafruit_servokit import ServoKit

print("🎮 MG996R 舵機測試開始...")

try:
    # 初始化 ServoKit
    print("📡 初始化 PCA9685...")
    kit = ServoKit(channels=16)
    print("✅ PCA9685 初始化成功")
    
    # 設定舵機參數（MG996R 適用）
    kit.servo[0].set_pulse_width_range(500, 2500)  # 調整脈衝寬度範圍
    print("✅ 舵機參數已設定")
    
    # 先測試一些固定角度
    print("\n🔄 執行自動測試...")
    test_angles = [90, 0, 180, 90]  # 中間→左→右→中間
    
    for angle in test_angles:
        print(f"  → 設定角度: {angle}°")
        kit.servo[0].angle = angle
        time.sleep(2)  # 給舵機足夠時間移動
    
    print("✅ 自動測試完成")
    
    # 手動控制
    print("\n🎯 手動控制模式")
    print("輸入角度 (0-180)，或 'q' 結束：")
    
    while True:
        try:
            a = input("角度: ").strip()
            if a.lower() == 'q':
                break
            angle = int(a)
            if 0 <= angle <= 180:
                print(f"設定角度: {angle}°")
                kit.servo[0].angle = angle
            else:
                print("❌ 角度必須在 0-180 之間")
        except ValueError:
            print("❌ 請輸入有效數字")
        except KeyboardInterrupt:
            break

except Exception as e:
    print(f"❌ 錯誤: {e}")
    print("\n🔍 檢查項目:")
    print("  1. 舵機是否有外接電源？")
    print("  2. 訊號線是否正確連接到通道 0？")
    print("  3. 舵機是否正常（用三用電錶檢查）？")

print("\n👋 測試結束")