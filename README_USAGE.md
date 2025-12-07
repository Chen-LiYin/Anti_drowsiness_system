# 整合防瞌睡雲台系統 使用說明

## 系統概述

這是一個完整的智能防瞌睡雲台系統，整合了瞌睡偵測、自動通知、遠程控制等功能。

### 主要功能

- **Phase 2**: 智能通知系統 (Telegram/LINE Bot)
- **Phase 3**: 遠程網頁控制介面 (虛擬搖桿 + 即時串流)
- **Phase 5**: 事件記錄與監控系統
- **本地控制**: 滑鼠控制雲台瞄準與射擊
- **即時監控**: OpenCV 瞌睡偵測與面部追蹤

---

## 快速開始

### 1. 環境要求

- **硬體**: Raspberry Pi 4 (推薦) 或兼容設備
- **攝像頭**: USB 攝像頭或 Pi Camera
- **舵機控制**: PCA9685 16 通道舵機驅動板
- **舵機**: 標準舵機 x2 (Pan/Tilt) + 連續旋轉舵機 x1 (Fire)
- **Python**: 3.8+

### 2. 安裝依賴

```bash
# 安裝系統依賴
sudo apt update
sudo apt install python3-pip python3-venv cmake build-essential

# 創建虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝 Python 依賴
pip install -r requirements.txt
```

### 3. 硬體連接

```
PCA9685 連接:
├── VCC → 5V
├── GND → GND
├── SDA → GPIO 2 (SDA)
└── SCL → GPIO 3 (SCL)

舵機連接:
├── 通道 1: Pan 舵機 (水平旋轉)
├── 通道 2: Tilt 舵機 (垂直旋轉)
└── 通道 4: Fire 舵機 (射擊機構)
```

### 4. 下載面部特徵模型

```bash
# 下載 dlib 面部特徵點模型
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 shape_predictor_68_face_landmarks.dat.bz2
```

---

## 配置設定

### 1. 基本配置 (config.py)

```python
# 攝像頭配置
CAMERA_INDEX = 0          # 攝像頭編號
CAMERA_WIDTH = 640        # 攝像頭解析度寬度
CAMERA_HEIGHT = 480       # 攝像頭解析度高度

# 瞌睡偵測閾值
EAR_THRESHOLD = 0.25      # 眼睛縱橫比閾值
EAR_CONSEC_FRAMES = 20    # 連續幀數閾值
```

### 2. 通知系統配置

#### Telegram Bot 設定:

1. 與 [@BotFather](https://t.me/botfather) 對話創建機器人
2. 獲取 Bot Token
3. 獲取聊天 ID (可使用 [@userinfobot](https://t.me/userinfobot))

```python
# config.py 中配置
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
TELEGRAM_ENABLED = True
```

### 3. 網頁控制配置

```python
# 網頁服務器配置
FLASK_HOST = "0.0.0.0"           # 允許外部訪問
FLASK_PORT = 5000                # 服務器埠號
CONTROL_PASSWORD = "drowsiness2024"  # 控制密碼
```

---

## 使用方式

### 1. 啟動完整系統

```bash
cd /path/to/anti_drowsiness_system
python modules/integrated_system.py
```

### 2. 本地控制介面

啟動後會開啟本地 pygame 視窗:

- **滑鼠移動**: 控制雲台瞄準
- **左鍵點擊**: 手動射擊
- **TAB 鍵**: 切換本地/遠程控制模式
- **R 鍵**: 重置雲台到中心位置
- **ESC 鍵**: 退出系統

### 3. 遠程網頁控制

#### 訪問控制介面:

```
主頁: http://[樹莓派IP]:5000/
控制台: http://[樹莓派IP]:5000/remote_control?auth=drowsiness2024
```

#### 網頁控制功能:

- **即時視訊串流**: 查看攝像頭畫面
- **虛擬搖桿**:
  - 左搖桿: 水平旋轉 (Pan, 0-180°)
  - 右搖桿: 垂直旋轉 (Tilt, 45-135°)
- **射擊按鈕**: 點擊進行射擊
- **射擊模式**: 單發/連發/持續
- **音效選擇**: 水槍/雷射/搞笑音效

---

## 通知機制

### 瞌睡警報內容

當系統檢測到瞌睡時，會發送包含以下信息的通知:

```
 瞌睡警報 - 立即行動！

 時間: 2024-12-03 12:30:45
 狀態: 嚴重瞌睡
 持續時間: 5.2 秒
 EAR值: 0.185
 眼睛閉合幀數: 25
 總瞌睡事件: 3 次

 立即控制: 點擊下方連結
 遠程喚醒系統已啟用

 遠程控制連結:
http://192.168.1.100:5000/remote_control?auth=drowsiness2024
```

### 附加功能

- **即時截圖**: 通知中包含瞌睡時的攝像頭截圖
- **甦醒通知**: 用戶清醒後自動發送甦醒通知

---

## 事件記錄系統

### 自動記錄事件

系統會自動記錄以下事件:

- **瞌睡事件**: 開始時間、持續時間、嚴重程度
- **射擊事件**: 本地/遠程、射擊模式、音效
- **控制事件**: 遠程控制開始/結束、控制者信息
- **甦醒事件**: 甦醒時間、總瞌睡時長

### 數據導出

系統關閉時會自動導出事件數據到 JSON 文件:

```json
{
  "statistics": {
    "total_drowsy_events": 5,
    "total_shots_fired": 12,
    "total_wake_ups": 5,
    "avg_drowsy_duration": 4.2,
    "session_duration": "02h 15m 33s"
  },
  "events": [...],
  "session_report": {...}
}
```

---

## 故障排除

### 常見問題

#### 1. 攝像頭無法啟動

```bash
# 檢查攝像頭
lsusb
v4l2-ctl --list-devices

# 測試攝像頭
python -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAILED')"
```

#### 2. PCA9685 連接問題

```bash
# 檢查 I2C 設備
sudo i2cdetect -y 1

# 應該看到地址 0x40 (PCA9685 默認地址)
```

#### 3. dlib 模型缺失

```bash
# 下載模型文件
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 shape_predictor_68_face_landmarks.dat.bz2

# 確保文件在正確位置
ls shape_predictor_68_face_landmarks.dat
```

#### 4. 網頁無法訪問

```bash
# 檢查防火牆
sudo ufw allow 5000

# 檢查服務器運行狀態
netstat -an | grep :5000
```

#### 5. 通知發送失敗

- 檢查網絡連接
- 確認 API Token 正確
- 檢查 Chat ID/User ID 格式

---

## 系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                    整合系統架構                                │
├─────────────────────────────────────────────────────────────┤
│  攝像頭輸入 → 瞌睡偵測 → 通知系統 → [Telegram/LINE]          │
│      ↓            ↓                                          │
│  本地控制 ← 雲台控制 → 遠程控制 → [網頁介面]                  │
│      ↓            ↓        ↓                                 │
│  事件記錄 ← 射擊控制 → 統計分析                               │
└─────────────────────────────────────────────────────────────┘
```

### 模塊說明

- **integrated_system.py**: 主要整合模塊
- **drowsiness_detector.py**: 瞌睡偵測引擎
- **notification_system.py**: 通知發送服務
- **web_remote_control.py**: 網頁控制服務
- **event_recorder.py**: 事件記錄系統

---

## 性能優化

### 建議設定

1. **攝像頭解析度**: 640x480 (平衡性能與精度)
2. **幀率限制**: 30 FPS (避免過度負載)
3. **通知冷卻**: 30 秒 (避免過度通知)
4. **事件緩存**: 最多 1000 個事件

### 硬體優化

- 使用高品質攝像頭提升偵測精度
- 確保充足電源供應舵機
- 使用散熱片維持系統溫度

---

## 安全考量

### 網絡安全

- 更改默認控制密碼
- 限制網頁訪問 IP 範圍
- 使用 HTTPS (生產環境)

### 數據安全

- 定期備份事件數據
- 設置日誌輪轉防止磁盤滿載
- 保護 API Token 安全

---

## 版本更新

### v1.0 功能清單

本地滑鼠控制介面  
 瞌睡偵測與警報  
 Telegram/LINE 通知  
 網頁遠程控制  
 虛擬搖桿操控  
 事件記錄系統  
 即時視訊串流

---

## 進階用法

### 自定義配置

1. 調整瞌睡偵測敏感度
2. 修改射擊參數
3. 添加新的音效文件
4. 自定義網頁界面樣式

### API 擴展

系統提供 REST API 接口，可用於第三方整合:

- `GET /api/status` - 獲取系統狀態
- `GET /api/stats` - 獲取統計數據
- WebSocket 接口支持即時控制

---
