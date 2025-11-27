import time 
from adafruit_servokit import ServoKit

print("🎮 舵機測試開始...")

# 360度舵機位置追蹤
servo360_positions = {0: 0, 4: 0}  # 記錄當前位置

def move_360_to_angle(channel, target_angle, speed=0.3):
    """將360度舵機移動到指定角度"""
    current_pos = servo360_positions[channel]
    target_angle = target_angle % 360  # 確保角度在0-360範圍
    
    # 計算最短路徑
    diff = target_angle - current_pos
    if diff > 180:
        diff -= 360
    elif diff < -180:
        diff += 360
    
    print(f"  通道 {channel}: {current_pos}° → {target_angle}° (移動 {diff:+.1f}°)")
    
    if abs(diff) < 2:  # 已經很接近目標
        kit.continuous_servo[channel].throttle = 0
        return
    
    # 設定旋轉方向和速度
    direction = 1 if diff > 0 else -1
    kit.continuous_servo[channel].throttle = direction * speed
    
    # 計算旋轉時間（粗略估計）
    rotation_time = abs(diff) / 180.0 * 1.0  # 假設180度需要1秒
    
    start_time = time.time()
    while time.time() - start_time < rotation_time:
        time.sleep(0.1)
        # 更新位置估計
        elapsed = time.time() - start_time
        moved = direction * speed * elapsed * 180  # 粗略計算
        servo360_positions[channel] = (current_pos + moved) % 360
    
    # 停止並更新最終位置
    kit.continuous_servo[channel].throttle = 0
    servo360_positions[channel] = target_angle
    time.sleep(0.2)  # 給舵機時間停下

try:
    # 初始化 ServoKit
    print("📡 初始化 PCA9685...")
    kit = ServoKit(channels=16)
    print("✅ PCA9685 初始化成功")
    
    # 設定舵機參數
    kit.servo[1].set_pulse_width_range(500, 2500)  # 通道1 - 普通舵機
    kit.servo[2].set_pulse_width_range(500, 2500)  # 通道2 - 普通舵機
    kit.servo[3].set_pulse_width_range(500, 2500)  # 通道3 - 普通舵機
    
    # 停止360度舵機
    kit.continuous_servo[0].throttle = 0  # 通道0 - 360度舵機
    kit.continuous_servo[4].throttle = 0  # 通道4 - 360度舵機
    
    print("✅ 舵機參數已設定")
    print("   通道 0, 4: 360度舵機（支援角度控制）")
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
    
    # 測試360度舵機的角度控制 (0, 4)
    print("  測試通道 0 (360度舵機角度控制)...")
    test_360_angles = [0, 90, 180, 270, 0]
    for angle in test_360_angles:
        print(f"    → 移動到 {angle}°")
        move_360_to_angle(0, angle)
        time.sleep(1)
    
    print("  測試通道 4 (360度舵機角度控制)...")
    for angle in test_360_angles:
        print(f"    → 移動到 {angle}°")
        move_360_to_angle(4, angle)
        time.sleep(1)
    
    print("✅ 自動測試完成")
    
    # 手動控制
    print("\n🎯 手動控制模式")
    print("指令格式:")
    print("普通舵機 (1,2,3):")
    print("  1 角度  - 控制通道 1 (角度 0-180)")
    print("  2 角度  - 控制通道 2 (角度 0-180)")
    print("  3 角度  - 控制通道 3 (角度 0-180)")
    print("360度舵機角度控制 (0,4):")
    print("  0 角度  - 控制通道 0 移動到指定角度 (0-359)")
    print("  4 角度  - 控制通道 4 移動到指定角度 (0-359)")
    print("360度舵機速度控制:")
    print("  s0 速度 - 通道 0 連續旋轉 (速度 -1.0 到 1.0)")
    print("  s4 速度 - 通道 4 連續旋轉 (速度 -1.0 到 1.0)")
    print("特殊指令:")
    print("  pos - 顯示360度舵機當前位置")
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
            elif cmd == 'pos':
                print(f"360度舵機位置: 通道0={servo360_positions[0]:.1f}°, 通道4={servo360_positions[4]:.1f}°")
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
                    # 360度舵機 - 角度控制
                    if 0 <= value <= 359:
                        channel = int(channel_cmd)
                        print(f"移動通道 {channel} 到 {value}°")
                        move_360_to_angle(channel, value)
                    else:
                        print("❌ 角度必須在 0-359 之間")
                        
                elif channel_cmd in ['s0', 's4']:
                    # 360度舵機 - 速度控制
                    if -1.0 <= value <= 1.0:
                        channel = int(channel_cmd[1])
                        print(f"設定通道 {channel} 連續旋轉速度: {value}")
                        kit.continuous_servo[channel].throttle = value
                    else:
                        print("❌ 速度必須在 -1.0 到 1.0 之間")
                        
                else:
                    print("❌ 通道指令錯誤")
            else:
                print("❌ 格式錯誤")
                print("範例: '1 90' (普通舵機) 或 '0 270' (360度角度) 或 's0 0.5' (360度速度)")
                
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