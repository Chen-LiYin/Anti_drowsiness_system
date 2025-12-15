#!/usr/bin/env python3
"""
音訊系統診斷工具
用於檢查 TTS 和麥克風配置
"""

import sys

print("=" * 50)
print("音訊系統診斷工具")
print("=" * 50)

# 1. 檢查 pyttsx3
print("\n[1/4] 檢查 pyttsx3 安裝...")
try:
    import pyttsx3
    print("✅ pyttsx3 已安裝")

    print("\n[2/4] 測試 TTS 引擎初始化...")

    # 方案 1: 嘗試使用 pyttsx3
    print("\n   方案 1: 測試 pyttsx3 + espeak...")
    try:
        engine = pyttsx3.init(driverName='espeak')
        print("   ✅ TTS 引擎初始化成功")

        # 不要取得 voices，直接嘗試播放
        print("   測試語音播放（應該會聽到聲音）...")
        engine.say("測試語音")
        engine.runAndWait()
        print("   ✅ pyttsx3 語音播放成功！")

    except Exception as e:
        print(f"   ❌ pyttsx3 失敗: {e}")

        # 方案 2: 使用 espeak 命令列
        print("\n   方案 2: 測試 espeak 命令列...")
        try:
            import subprocess

            # 測試 espeak 是否可用
            result = subprocess.run(['espeak', '--version'],
                                  capture_output=True,
                                  text=True,
                                  check=True)
            print(f"   ✅ espeak 已安裝: {result.stdout.strip()}")

            # 測試語音播放
            print("   測試語音播放（應該會聽到聲音）...")
            subprocess.run(['espeak', '-v', 'zh', '測試中文語音'], check=False)
            subprocess.run(['espeak', 'Testing English voice'], check=False)
            print("   ✅ espeak 命令列播放成功！")
            print("   💡 建議：系統將使用 espeak 命令列作為 TTS 引擎")

        except FileNotFoundError:
            print("   ❌ espeak 未安裝")
            print("   解決方案：")
            print("   sudo apt-get update")
            print("   sudo apt-get install espeak espeak-ng")
        except Exception as e2:
            print(f"   ❌ espeak 命令列也失敗: {e2}")

except ImportError:
    print("❌ pyttsx3 未安裝")
    print("   解決方案: pip install pyttsx3")

# 2. 檢查 PyAudio
print("\n[3/4] 檢查 PyAudio 安裝...")
try:
    import pyaudio
    print("✅ PyAudio 已安裝")

    print("\n[4/4] 檢查可用的音訊設備...")
    p = pyaudio.PyAudio()

    print("\n可用的輸入設備：")
    print("-" * 50)

    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:  # 只顯示輸入設備
            print(f"\n設備 ID: {i}")
            print(f"  名稱: {info['name']}")
            print(f"  最大輸入通道: {info['maxInputChannels']}")
            print(f"  預設採樣率: {int(info['defaultSampleRate'])} Hz")

            # 測試設備 ID 2
            if i == 2:
                print("\n  ⭐ 這是您的 USB 麥克風！")
                print(f"  正在測試錄音功能...")

                # 測試不同的採樣率
                test_rates = [44100, 48000, 16000, 8000]
                working_rate = None

                for rate in test_rates:
                    try:
                        test_stream = p.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=rate,
                            input=True,
                            input_device_index=i,
                            frames_per_buffer=1024
                        )

                        # 讀取一小段數據
                        data = test_stream.read(1024, exception_on_overflow=False)
                        test_stream.stop_stream()
                        test_stream.close()

                        print(f"    ✅ 採樣率 {rate} Hz 可用")
                        if not working_rate:
                            working_rate = rate

                    except Exception as e:
                        print(f"    ❌ 採樣率 {rate} Hz 失敗: {e}")

                if working_rate:
                    print(f"\n  💡 建議使用採樣率: {working_rate} Hz")
                else:
                    print(f"\n  ⚠️ 所有採樣率都失敗，請檢查麥克風連接")

    p.terminate()
    print("\n" + "=" * 50)
    print("診斷完成！")
    print("=" * 50)

except ImportError:
    print("❌ PyAudio 未安裝")
    print("   解決方案: sudo apt-get install python3-pyaudio")
except Exception as e:
    print(f"❌ PyAudio 檢查失敗: {e}")

print("\n如果有任何錯誤，請參考上述解決方案或將錯誤訊息回報給開發者。")
