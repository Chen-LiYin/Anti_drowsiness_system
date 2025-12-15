import pyaudio

p = pyaudio.PyAudio()

print("------------------------------------------------")
print("請尋找你的 USB 麥克風 (例如: USB Audio Device)")
print("------------------------------------------------")

for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    # 只顯示輸入裝置 (maxInputChannels > 0)
    if info['maxInputChannels'] > 0:
        print(f"裝置 ID: {i} - {info['name']}")
        print(f"    最大輸入聲道: {info['maxInputChannels']}")
        print(f"    預設採樣率: {info['defaultSampleRate']}")
        print("------------------------------------------------")

p.terminate()