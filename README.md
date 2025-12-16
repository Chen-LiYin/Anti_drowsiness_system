# 還敢睡啊！！

### 防瞌睡雲台監控系統

一個結合電腦視覺、硬體控制與社交互動的智能防瞌睡系統。當偵測到使用者瞌睡時，系統會自動發送通知給朋友們，透過聊天室投票決定誰能遠端操控雲台發射水槍來喚醒你。

## Demo 影片

https://youtu.be/X8LtaIqvhPk

## Demo 成品照片

![alt text](<截圖 2025-12-16 上午10.00.16.png>)
![alt text](<截圖 2025-12-16 上午10.00.38.png>)

## 心得

老師教的超好玩，學到很多硬體的概念，實作做出好玩的專案可以給自己用用看，最難的應該是手作的部分，尤其是黏版機的線，一開始是用有彈力的線，結果都拉不動，後來是用杜幫線，但拉幾次就會斷，每次都要黏新的，但手作真的好玩，實際看到實體有在動的感覺很有趣。

---

## 快速導航

- [Demo 影片](#demo-影片)
- [Demo 成品照片](#demo-成品照片)
- [心得](#心得)
- [專案簡介](#專案簡介)
- [硬體需求](#硬體需求)
- [軟體環境設定](#軟體環境設定)
- [核心模組說明](#核心模組說明)
- [系統運作流程](#系統運作流程)
- [快速開始](#快速開始)
- [網頁控制介面](#網頁控制介面)
- [調整參數](#調整參數)
- [故障排除](#故障排除)
- [資料夾結構](#資料夾結構)
- [安全提醒](#安全提醒)
- [樹梅派設定](#樹梅派設定)

---

## 專案簡介

這個系統主要功能包括：

- **即時瞌睡偵測**：使用電腦視覺技術分析眼睛與嘴巴狀態
- **自動化雲台控制**：透過舵機控制水平/垂直轉動與射擊機構
- **Telegram 通知系統**：即時推播瞌睡警報與截圖
- **互動聊天室**：朋友們可以留言、投票，獲勝者取得遠端控制權
- **網頁遠端控制**：透過虛擬搖桿操控雲台射擊水槍
- **事件記錄與統計**：完整記錄瞌睡事件、射擊次數等資料

## 硬體需求

### 必要硬體

- **樹莓派 4**
- **攝像頭**（樹莓派官方鏡頭）
- **PCA9685 舵機驅動板**（16 通道 I2C 介面）
- **MG996R 標準舵機 x2**（用於 Pan/Tilt 雲台控制）
- **MG996R 連續旋轉舵機 x1**（用於射擊機構）
- **水槍裝置**（可自行製作或改裝）
- **藍芽喇吧**

### 硬體接線

```
樹莓派 GPIO
├── SDA (GPIO 2) ──→ PCA9685 SDA
├── SCL (GPIO 3) ──→ PCA9685 SCL
└── GND ──────────→ PCA9685 GND

PCA9685 舵機驅動板
├── 通道 0 (SERVO_PAN_CHANNEL) ──→ Pan 舵機（水平旋轉）
├── 通道 1 (SERVO_TILT_CHANNEL) ─→ Tilt 舵機（垂直旋轉）
└── 通道 4 ─────────────────────→ Fire 舵機（射擊機構）

※ PCA9685 I2C 地址預設為 0x40
```

### 硬體接線圖

```

┌─────────────────┐
│  樹莓派 4        │
│                 │
│  Pin 1 (3.3V)───┼───→ PCA9685 VCC
│  Pin 3 (SDA)────┼───→ PCA9685 SDA
│  Pin 5 (SCL)────┼───→ PCA9685 SCL
│  Pin 6 (GND)────┼───→ PCA9685 GND
└─────────────────┘

┌─────────────────┐          ┌──────────────┐
│  外部 5V 電源    │          │  PCA9685     │
│                 │          │              │
│  +5V ───────────┼─────────→│ V+ (藍色端子)│
│  GND ───────────┼─────────→│ GND          │
└─────────────────┘          └──────────────┘
│
┌────────────────┴────────────────┐
│                                  │
┌─────▼─────┐                    ┌──────▼──────┐
│ MG996R    │                    │  MG996R     │
│ (Pan)     │                    │  (Tilt)     │
│           │                    │             │
│ 橙 → PWM 0│                    │  橙 → PWM 1 │
│ 紅 → V+   │                    │  紅 → V+    │
│ 棕 → GND  │                    │  棕 → GND   │
└───────────┘                    └─────────────┘



```

## 軟體環境設定

### 1. 系統需求

- Python 3.7 或以上版本
- Raspberry Pi OS（或其他 Debian 系 Linux）
- 已啟用 I2C 介面（透過 `raspi-config` 設定）

### 2. 安裝系統依賴

```bash
# 更新套件清單
sudo apt update

# 安裝 OpenCV 相關依賴
sudo apt install -y python3-opencv libopencv-dev

# 安裝 dlib 依賴（編譯所需）
sudo apt install -y cmake build-essential libboost-all-dev

# 安裝 I2C 工具
sudo apt install -y i2c-tools python3-smbus

# 安裝音訊相關套件
sudo apt install -y portaudio19-dev python3-pyaudio

# 安裝 TTS 語音引擎（選用）
sudo apt install -y espeak
```

### 3. 安裝 Python 套件

```bash
# 建立虛擬環境（建議）
python3 -m venv venv
source venv/bin/activate

# 安裝 Python 依賴套件
pip install -r requirements.txt

# 如果 dlib 安裝失敗，可嘗試預編譯版本
pip install dlib --no-cache-dir
```

### 4. 下載 dlib 面部特徵模型

```bash
# 下載 68 點面部特徵預測模型
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 shape_predictor_68_face_landmarks.dat.bz2
mv shape_predictor_68_face_landmarks.dat ./
```

### 5. 設定 Telegram Bot

參考連結：https://allenplay.net/articles/2024-05-01-telegram-bot-get-chat-id/

```bash
# 1. 在 Telegram 搜尋 @BotFather
# 2. 傳送 /newbot 建立新機器人
# 3. 取得 BOT_TOKEN

# 4. 取得你的 CHAT_ID（傳送訊息給 @userinfobot）
# 5. 編輯 config.py，填入 Token 與 Chat ID
```

編輯 `config.py`:

```python
TELEGRAM_BOT_TOKEN = "你的_BOT_TOKEN"
TELEGRAM_CHAT_ID = "你的_CHAT_ID"
```

## 核心模組說明

### 1. `modules/drowsiness_detector.py` - 瞌睡偵測器

**核心技術：**

- **EAR (Eye Aspect Ratio)**：計算眼睛長寬比例，判斷眼睛是否閉合
- **MAR (Mouth Aspect Ratio)**：計算嘴巴長寬比例，判斷是否打哈欠
- 使用 dlib 68 點面部特徵偵測

**關鍵參數：**

```python
EAR_THRESHOLD = 0.25          # EAR 低於此值視為閉眼
EAR_CONSEC_FRAMES = 20        # 連續 20 幀閉眼觸發瞌睡
MAR_THRESHOLD = 0.75          # MAR 高於此值視為打哈欠
```

**狀態判定：**

- `Alert`：清醒狀態
- `Tired`：疲倦（眼睛開始閉合）
- `Yawning`：打哈欠
- `Drowsy`：瞌睡中

### 2. `modules/turret_controller.py` - 雲台控制器

**功能：**

- 透過 I2C 直接控制 PCA9685 晶片
- 平滑移動演算法（避免舵機抖動）

**核心方法：**

```python
set_pan(angle)      # 設定水平角度 (45°-135°)
set_tilt(angle)     # 設定垂直角度 (45°-135°)
fire(duration)      # 射擊指定時間（秒）
```

### 3. `modules/notification_system.py` - 通知系統

**功能：**

- 發送 Telegram 訊息通知
- 附加瞌睡截圖
- 生成聊天室互動連結（90 秒投票倒數）
- 通知冷卻機制（30 秒內不重複通知）

**通知內容：**

- 瞌睡警報時間與持續時間
- 當前 EAR 數值
- 即時截圖
- 聊天室連結

### 4. `modules/web_remote_control.py` - 網頁遠端控制

**技術架構：**

- Flask + SocketIO（WebSocket 即時通訊）
- 即時視訊串流（MJPEG）
- 虛擬搖桿控制介面

**核心功能：**

- 即時視訊串流（`/video_feed`）
- 虛擬搖桿控制雲台方向
- 射擊按鈕（單發/連發/持續）
- 音效選擇器（5 種音效）
- 聊天室系統（90 秒投票機制）

**聊天室流程：**

1. 瞌睡觸發後，生成 90 秒倒數聊天室
2. 朋友們可留言（每人限一則，最多 50 字）
3. 其他人可對留言投票
4. 時間結束時，最高票者獲得一次性控制 Token
5. 獲勝者取得專屬控制連結，其他人獲得監控連結

### 5. `modules/integrated_system.py` - 完整整合系統

**整合所有模組：**

- 攝像頭影像處理
- 瞌睡狀態偵測
- 雲台自動控制
- Telegram 通知推播
- 網頁遠端控制伺服器
- 事件記錄系統
- TTS 語音播報

**智能防誤判機制：**

- **15 秒瞌睡確認**：避免短暫閉眼被誤判
- **15 秒清醒確認**：確保使用者真正清醒
- **通知冷卻時間**：避免通知轟炸

### 6. `modules/event_recorder.py` - 事件記錄系統

**記錄事件類型：**

- 瞌睡開始/結束時間
- 射擊事件記錄
- 遠端控制行為
- 自動截圖儲存

**統計分析：**

- 總瞌睡次數與平均時長
- 射擊次數統計
- 成功喚醒次數
- 資料匯出為 JSON 格式

## 系統運作流程

```
┌─────────────────────────────────────────────────┐
│ 1. 攝像頭即時捕捉影像                              │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 2. DrowsinessDetector 分析面部特徵                 │
│    - 計算 EAR（眼睛長寬比）                         │
│    - 計算 MAR（嘴巴長寬比）                         │
│    - 判斷狀態：Alert/Tired/Yawning/Drowsy         │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 3. 瞌睡狀態觸發（15 秒確認機制）                     │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 4. NotificationSystem 發送 Telegram 通知          │
│    - 瞌睡警報訊息                                  │
│    - 附加截圖                                     │
│    - 聊天室連結（90 秒倒數）                       │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 5. 聊天室互動（chat.html）                         │
│    - 朋友們留言（每人限一則）                        │
│    - 投票選出最佳留言(當使用者清醒時會語音播放此留言內容)│
│    - 90 秒倒數計時                                │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 6. 時間結束 → 最高票者獲勝                          │
│    - 系統生成一次性 Token                          │
│    - 發送獲勝者專屬控制連結                         │
│    - 輸家獲得監控連結                              │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 7. 獲勝者遠端操控雲台（remote_control.html）         │
│    - 虛擬搖桿控制 Pan/Tilt                         │
│    - 射擊按鈕發射水槍                              │
│    - 選擇發射音效                                  │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 8. 使用者清醒（15 秒確認機制）                       │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 9. 系統 TTS 語音播報最高票留言                       │
│    - 使用 pyttsx3 或 espeak                       │
└─────────────┬───────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ 10. 發送甦醒通知 & 重置系統                         │
└─────────────────────────────────────────────────┘
```

## 快速開始

### 方法 0：（推薦）

要注意啟動虛擬環境，因為安裝項目是在虛擬環境的

```bash
1. 進入專案目錄
cd ~/Anti_drowsiness_system

2. 啟動虛擬環境
source venv/bin/activate

3.安裝項目
pip3 install -r requirements.txt

4. 啟動 測試檔案
python test_system.py

4. 啟動 正式檔案
python modules/integrated_system.py
```

### 方法一：使用啟動器

```bash
# 執行啟動器
python start_system.py
```

選單選項：

1. **系統測試**：測試各模組功能
2. **完整整合系統**：啟動所有功能（推薦）
3. **分離雙視窗系統**：分離瞌睡偵測與雲台控制
4. **只啟動網頁控制**：單獨測試遠端控制
5. **測試通知系統**：測試 Telegram 通知

### 方法二：直接啟動主程式

```bash
# 啟動完整整合系統
python -c "from modules.integrated_system import IntegratedSystem; system = IntegratedSystem(); system.run()"
```

### 方法三：只啟動網頁伺服器

```bash
# 啟動 Flask 伺服器
python app.py
```

然後瀏覽器開啟：`http://樹莓派IP:5000`

## 網頁控制介面

### 控制頁面

- **首頁**：`http://<樹莓派IP>:5000/`
- **聊天室**：`http://<樹莓派IP>:5000/chat`
- **遠端控制**：`http://<樹莓派IP>:5000/remote_control`
- **監控頁面**：`http://<樹莓派IP>:5000/monitor`

### 控制密碼

預設密碼：`drowsiness2024`（可在 `config.py` 修改）

## 調整參數

編輯 [config.py](config.py) 來調整系統參數：

```python
# 瞌睡偵測靈敏度
EAR_THRESHOLD = 0.25          # 降低此值 = 更敏感
EAR_CONSEC_FRAMES = 20        # 增加幀數 = 較不易觸發

# 雲台角度範圍
PAN_MIN = 45                  # Pan 最小角度
PAN_MAX = 135                 # Pan 最大角度
TILT_MIN = 45                 # Tilt 最小角度
TILT_MAX = 135                # Tilt 最大角度

# 聊天室時間
CHAT_DURATION = 90            # 聊天室倒數秒數（在 web_remote_control.py）

# 通知冷卻
NOTIFICATION_COOLDOWN = 30    # 秒
```

## 故障排除

### 問題 1：攝像頭無法開啟

```bash
# 檢查攝像頭是否被辨識
ls /dev/video*

# 測試攝像頭
python -c "import cv2; cap = cv2.VideoCapture(0); print('成功' if cap.isOpened() else '失敗')"
```

### 問題 2：I2C 裝置無法偵測

```bash
# 啟用 I2C
sudo raspi-config
# 選擇：Interface Options → I2C → Enable

# 檢查 I2C 裝置
sudo i2cdetect -y 1
# 應該看到 0x40（PCA9685 預設地址）
```

### 問題 3：dlib 面部特徵模型找不到

```bash
# 確認模型檔案存在
ls -lh shape_predictor_68_face_landmarks.dat

# 如果不存在，重新下載
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 shape_predictor_68_face_landmarks.dat.bz2
```

### 問題 4：舵機不動作

```bash
# 測試舵機
python test_servo.py

# 檢查電源供應（舵機需要外接 5V 電源，不可使用樹莓派供電）
```

## 資料夾結構

```
anti_drowsiness_system/
├── app.py                              # Flask 主程式
├── config.py                           # 系統配置檔
├── start_system.py                     # 系統啟動器
├── requirements.txt                    # Python 依賴套件
├── shape_predictor_68_face_landmarks.dat  # dlib 面部特徵模型
│
├── modules/                            # 核心模組
│   ├── drowsiness_detector.py          # 瞌睡偵測器
│   ├── turret_controller.py            # 雲台控制器
│   ├── notification_system.py          # 通知系統
│   ├── web_remote_control.py           # 網頁遠端控制
│   ├── integrated_system.py            # 完整整合系統
│   ├── event_recorder.py               # 事件記錄系統
│   └── joystick_ui.py                  # 虛擬搖桿 UI
│
├── templates/                          # HTML 模板
│   ├── index.html                      # 首頁
│   ├── chat.html                       # 聊天室頁面
│   ├── remote_control.html             # 遠端控制頁面
│   └── monitor.html                    # 監控頁面
│
├── static/                             # 靜態資源
│   └── sounds/                         # 音效檔案
│       ├── water_gun.mp3
│       ├── 小黃鴨.mp3
│       ├── 巴掌聲.mp3
│       ├── 放屁.mp3
│       └── 鴨子聲.mp3
│
└── data/                               # 資料儲存
    ├── logs/                           # 系統日誌
    ├── screenshots/                    # 截圖儲存
    ├── recordings/                     # 錄影儲存
    └── events.json                     # 事件記錄
```

## 安全提醒

- 水槍射擊請注意周圍環境安全
- 避免對準電子設備或其他不適當目標
- 建議使用低壓力水槍，避免造成傷害

## 樹梅派設定

- 設定記憶卡
  - 格式化
    ![alt text](<截圖 2025-09-23 下午2.35.45.png>)
  - 格式化後，重新安裝 image，等他安裝完就可以了
- 記憶卡設定好後，插入樹梅派
- 會進行一些基本的設定
  - 設定語言（Taiwan > 設定英文 language）
  - 設定密碼（要用簡單的就好:12345，才不會擔心有資安問題）
  - enable 相關設定（看 eeclasss 老師設定的）
  - username 可以從 terminal 看

### 執行程式碼

1. 編譯程式寫程式碼
2. 切記不要使用編譯程式的 run，要用 terminal 的指令來執行
3. 切到母資料夾，執行該檔案名稱
4. control+c 結束該檔案

```python
python3 led_blink.py
```

![alt text](<截圖 2025-09-23 下午3.21.08.png>)

### **常見問題**

- cannot connect to desktop
  - 連 html 到電腦螢幕
- cloude 問題
  - 網路沒連到
  - **檢查 VNC 設定**
  ```bash
  sudo raspi-config
  ```
  進入 "Interface Options" → "VNC" → 確保已啟用(enable)
- session 問題
  - 重新開機（直接拔電源）

---
