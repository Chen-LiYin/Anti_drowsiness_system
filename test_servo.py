import time 
from adafruit_servokit import ServoKit

print("🎮 MG996R 舵機測試開始...")

try:
    # 初始化 ServoKit
    print("📡 初始化 PCA9685...")
    kit = ServoKit(channels=16)
    print("✅ PCA9685 初始化成功")
    
    # 設定舵機參數（MG996R 適用）
    kit.servo[0].set_pulse_width_range(500, 2500)  # 通道0
    kit.servo[1].set_pulse_width_range(500, 2500)  # 通道1
    kit.servo[2].set_pulse_width_range(500, 2500)  # 通道2
    kit.servo[3].set_pulse_width_range(500, 2500)  # 通道3
    kit.servo[4].set_pulse_width_range(500, 2500)  # 通道4
    print("✅ 舵機參數已設定（通道 0, 1, 2, 3, 4）")
    
    # 先測試一些固定角度
    print("\n🔄 執行自動測試...")
    test_angles = [90, 0, 180, 90]  # 中間→左→右→中間
    
    # 測試所有通道
    for channel in [0, 1, 2, 3, 4]:
        print(f"  測試通道 {channel}...")
        for angle in test_angles:
            print(f"    → 通道 {channel} 角度: {angle}°")
            kit.servo[channel].angle = angle
            time.sleep(1.5)  # 縮短等待時間
    
    print("✅ 自動測試完成")
    
    # 手動控制
    print("\n🎯 手動控制模式")
    print("指令格式:")
    print("  0 角度  - 控制通道 0")
    print("  1 角度  - 控制通道 1") 
    print("  2 角度  - 控制通道 2")
    print("  3 角度  - 控制通道 3")
    print("  4 角度  - 控制通道 4")
    print("  all 角度 - 同時控制所有舵機")
    print("  q - 結束程式")
    
    while True:
        try:
            cmd = input("\n指令: ").strip().lower()
            if cmd == 'q':
                break
            
            parts = cmd.split()
            if len(parts) == 2:
                channel_cmd = parts[0]
                angle = int(parts[1])
                
                if 0 <= angle <= 180:
                    if channel_cmd in ['0', '1', '2', '3', '4']:
                        channel = int(channel_cmd)
                        print(f"設定通道 {channel}: {angle}°")
                        kit.servo[channel].angle = angle
                    elif channel_cmd == 'all':
                        print(f"設定所有舵機: {angle}°")
                        for ch in [0, 1, 2, 3, 4]:
                            kit.servo[ch].angle = angle
                    else:
                        print("❌ 通道指令錯誤，使用 0、1、2、3、4 或 all")
                else:
                    print("❌ 角度必須在 0-180 之間")
            else:
                print("❌ 格式錯誤，例如: '0 90' 或 '4 45' 或 'all 90'")
                
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