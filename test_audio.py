#!/usr/bin/env python3
"""
測試音頻系統
"""

print("=" * 60)
print("音頻系統測試")
print("=" * 60)

# 測試 PyAudio 安裝
print("\n1. 檢查 PyAudio 安裝...")
try:
    import pyaudio
    print("✅ PyAudio 已安裝")

    # 初始化 PyAudio
    p = pyaudio.PyAudio()
    print(f"✅ PyAudio 版本: {pyaudio.__version__}")

    # 列出可用的音頻設備
    print("\n2. 可用的音頻輸入設備:")
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    input_devices = []
    for i in range(0, numdevices):
        device_info = p.get_device_info_by_host_api_device_index(0, i)
        if device_info.get('maxInputChannels') > 0:
            input_devices.append(device_info)
            print(f"  [{i}] {device_info.get('name')}")
            print(f"      採樣率: {int(device_info.get('defaultSampleRate'))} Hz")
            print(f"      輸入通道: {device_info.get('maxInputChannels')}")

    if not input_devices:
        print("❌ 找不到可用的音頻輸入設備")
    else:
        # 測試錄音
        print("\n3. 測試麥克風錄音...")
        try:
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000

            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            print(f"✅ 麥克風已開啟 (採樣率: {RATE}Hz)")
            print("   正在錄音 3 秒...")

            # 錄音 3 秒
            frames = []
            for i in range(0, int(RATE / CHUNK * 3)):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

            stream.stop_stream()
            stream.close()

            print("✅ 錄音成功！")
            print(f"   錄製了 {len(frames)} 個音頻幀")

        except Exception as e:
            print(f"❌ 麥克風測試失敗: {e}")
            print("\n可能的原因：")
            print("  1. 麥克風權限未授予")
            print("  2. 麥克風被其他應用程式佔用")
            print("  3. 系統設定問題")

    p.terminate()

except ImportError as e:
    print("❌ PyAudio 未安裝")
    print("\n安裝方法：")
    print("  macOS:")
    print("    brew install portaudio")
    print("    pip install pyaudio")
    print("\n  Linux:")
    print("    sudo apt-get install portaudio19-dev")
    print("    pip install pyaudio")
    print("\n  Windows:")
    print("    pip install pyaudio")

except Exception as e:
    print(f"❌ 錯誤: {e}")

print("\n" + "=" * 60)
print("測試完成")
print("=" * 60)
