# test_microphone.py
import pyaudio

p = pyaudio.PyAudio()

print("=== 可用的音頻設備 ===")
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"設備 {i}: {info['name']}")
    print(f"  最大輸入聲道: {info['maxInputChannels']}")
    print(f"  預設採樣率: {info['defaultSampleRate']}")
    print()

p.terminate()