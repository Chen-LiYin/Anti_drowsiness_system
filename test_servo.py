import time 
from adafruit_servokit import ServoKit

print("🎮 MG996R 舵機測試開始...")

try:
    # 初始化 ServoKit
    print("📡 初始化 PCA9685...")
    kit = ServoKit(channels=16)
    print("✅ PCA9685 初始化成功")
    
    # 設定舵機參數
    # 通道 0, 4: 360度連續旋轉舵機 (使用 continuous_servo)
    # 通道 1, 2, 3: 普通舵機 (使用 servo)
    kit.servo[1].set_pulse_width_range(500, 2500)  # 通道1 - 普通舵機
    kit.servo[2].set_pulse_width_range(500, 2500)  # 通道2 - 普通舵機
    kit.servo[3].set_pulse_width_range(500, 2500)  # 通道3 - 普通舵機
    
    # 停止連續旋轉舵機
    kit.continuous_servo[0].throttle = 0  # 通道0 - 360度舵機
    kit.continuous_servo[4].throttle = 0  # 通道4 - 360度舵機
    
    print("✅ 舵機參數已設定")
    print("   通道 0, 4: 360度連續旋轉舵機")
    print("   通道 1, 2, 3: 普通舵機")
    
    # 先測試一些固定角度
    print("\n🔄 執行自動測試...")
    
    # 測試普通舵機 (1, 2, 3)
    test_angles = [90, 0, 180, 90]
    for channel in [1, 2, 3]:
        print(f"  測試通道 {channel} (普通舵機)...")
        for angle in test_angles:
            print(f"    → 通道 {channel} 角度: {angle}°")
            kit.servo[channel].angle = angle
            time.sleep(1.5)
    
    # 測試連續旋轉舵機 (0, 4)
    print("  測試通道 0 (360度舵機)...")
    print("    → 順時針旋轉")
    kit.continuous_servo[0].throttle = 0.5
    time.sleep(2)
    print("    → 停止")
    kit.continuous_servo[0].throttle = 0
    time.sleep(1)
    print("    → 逆時針旋轉")
    kit.continuous_servo[0].throttle = -0.5
    time.sleep(2)
    print("    → 停止")
    kit.continuous_servo[0].throttle = 0
    
    print("  測試通道 4 (360度舵機)...")
    print("    → 順時針旋轉")
    kit.continuous_servo[4].throttle = 0.5
    time.sleep(2)
    print("    → 停止")
    kit.continuous_servo[4].throttle = 0
    time.sleep(1)
    print("    → 逆時針旋轉")
    kit.continuous_servo[4].throttle = -0.5
    time.sleep(2)
    print("    → 停止")
    kit.continuous_servo[4].throttle = 0
    
    print("✅ 自動測試完成")
    
    # 手動控制
    print("\n🎯 手動控制模式")
    print("指令格式:")
    print("普通舵機 (1,2,3):")
    print("  1 角度  - 控制通道 1 (角度 0-180)")
    print("  2 角度  - 控制通道 2 (角度 0-180)")
    print("  3 角度  - 控制通道 3 (角度 0-180)")
    print("360度舵機 (0,4):")
    print("  0 速度  - 控制通道 0 (速度 -1.0 到 1.0, 0=停止)")
    print("  4 速度  - 控制通道 4 (速度 -1.0 到 1.0, 0=停止)")
    print("特殊指令:")
    print("  stop - 停止所有360度舵機")
    print("  q - 結束程式")
    
    while True:
        try:
            cmd = input("\n指令: ").strip().lower()
            if cmd == 'q':
                break
            elif cmd == 'stop':
                print("停止所有360度舵機")
                kit.continuous_servo[0].throttle = 0
                kit.continuous_servo[4].throttle = 0
                continue
            
            parts = cmd.split()
            if len(parts) == 2:
                channel_cmd = parts[0]
                value = float(parts[1])
                
                if channel_cmd in ['1', '2', '3']:
                    # 普通舵機 - 角度控制
                    if 0 <= value <= 180:
                        channel = int(channel_cmd)
                        print(f"設定通道 {channel} 角度: {value}°")
                        kit.servo[channel].angle = value
                    else:
                        print("❌ 角度必須在 0-180 之間")
                        
                elif channel_cmd in ['0', '4']:
                    # 360度舵機 - 速度控制
                    if -1.0 <= value <= 1.0:
                        channel = int(channel_cmd)
                        print(f"設定通道 {channel} 速度: {value} ({'停止' if value == 0 else '順時針' if value > 0 else '逆時針'})")
                        kit.continuous_servo[channel].throttle = value
                    else:
                        print("❌ 速度必須在 -1.0 到 1.0 之間")
                        
                else:
                    print("❌ 通道指令錯誤，使用 0,1,2,3,4")
            else:
                print("❌ 格式錯誤")
                print("範例: '1 90' (普通舵機) 或 '0 0.5' (360度舵機)")
                
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