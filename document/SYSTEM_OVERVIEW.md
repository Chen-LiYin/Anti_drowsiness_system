# 防瞌睡雲台系統 - 系統概覽

## 快速開始

```bash
# 1. 安裝系統
python setup.py

# 2. 啟動系統
python start_system.py

# 3. 訪問網頁控制
http://localhost:5000/remote_control?auth=drowsiness2024
```

---

## 系統架構

```
防瞌睡雲台系統
├──  本地控制模塊
│   ├── separated_dual_system.py    # 分離雙視窗系統
│   └── integrated_system.py        # 完整整合系統
├──  瞌睡偵測模塊
│   └── drowsiness_detector.py      # OpenCV + dlib 偵測
├──  通知系統模塊
│   └── notification_system.py      # Telegram 通知
├──  網頁控制模塊
│   ├── web_remote_control.py       # Flask + SocketIO 後端
│   └── templates/                  # HTML 前端介面
├──  事件記錄模塊
│   └── event_recorder.py          # JSON 事件記錄
└──   配置與工具
    ├── config.py                  # 系統配置
    ├── setup.py                   # 安裝腳本
    ├── start_system.py            # 啟動器
    └── test_system.py             # 系統測試
```

---

## 操作模式

### 1. 本地控制模式

- **分離雙視窗**: 瞄準視窗 + 偵測視窗
- **滑鼠控制**: 移動控制雲台，點擊射擊
- **鍵盤快捷鍵**: TAB(切換), R(重置), ESC(退出)

### 2. 遠程網頁控制

- **即時視訊**: 攝像頭串流顯示
- **虛擬搖桿**: 觸控/滑鼠控制雲台
- **射擊控制**: 多種模式和音效選擇
- **多用戶**: 支援多人同時觀看，單人控制

### 3. 自動監控模式

- **瞌睡偵測**: 即時面部分析
- **智能警報**: Telegram/LINE 推播通知
- **事件記錄**: 完整行為日誌

---

## 通知功能

### 警報內容

```
 瞌睡警報 - 立即行動！

 時間: 2024-12-03 12:30:45
 狀態: 嚴重瞌睡
 持續時間: 5.2 秒
 EAR值: 0.185
 眼睛閉合幀數: 25

 遠程控制連結:
http://[IP]:5000/remote_control?auth=drowsiness2024
```

### 支援平台

- **Telegram Bot**: 即時推播 + 圖片
- **LINE Messaging**: 文字通知
- **網頁通知**: 瀏覽器推送

---

## 硬體需求

### 核心硬體

```
樹莓派 4 (2GB+)
├── USB 攝像頭 或 Pi Camera
├── PCA9685 舵機驅動板
├── 標準舵機 x2 (Pan/Tilt)
├── 連續舵機 x1 (Fire)
└── 外接電源 (舵機供電)
```

### 連接方式

```
PCA9685 接線:
├── VCC → 5V
├── GND → GND
├── SDA → GPIO 2
└── SCL → GPIO 3

舵機分配:
├── 通道 1: Pan (水平)
├── 通道 2: Tilt (垂直)
└── 通道 4: Fire (射擊)
```

---

## 網頁介面功能

### 控制台功能

- 即時視訊串流
- 雙虛擬搖桿控制
- 射擊按鈕 (單發/連發/持續)
- 音效選擇 (水槍/雷射/搞笑)
- 即時狀態顯示
- 緊急停止功能

### 監控面板

- 系統狀態監控
- 連線用戶統計
- 事件記錄查看
- 性能指標顯示

---

## 事件記錄

### 自動記錄事件

```json
{
  "drowsiness_events": "瞌睡發生與結束",
  "shot_events": "本地/遠程射擊記錄",
  "control_events": "遠程控制開始/結束",
  "system_events": "系統啟動/關閉"
}
```

### 統計分析

- 瞌睡頻率分析
- 射擊效果統計
- 反應時間記錄
- 使用行為報告

---

## 安全設置

### 存取控制

- 密碼保護控制介面
- IP 限制訪問(可選)
- 單一控制者機制

### 數據安全

- 本地事件存儲
- 自動數據備份
- 隱私數據清理

---

## 快速命令

```bash
# 系統測試
python test_system.py

# 啟動模式選擇
python start_system.py

# 直接啟動完整系統
python start_system.py --mode integrated

# 只啟動網頁控制
python start_system.py --mode web

# 測試通知系統
python start_system.py --mode notification
```

---

## 故障排除

### 常見問題

| 問題           | 解決方案                 |
| -------------- | ------------------------ |
| 攝像頭無法訪問 | 檢查設備連接，確認權限   |
| 舵機無響應     | 確認 I2C 啟用，檢查接線  |
| 網頁無法訪問   | 檢查防火牆，確認埠號     |
| 通知發送失敗   | 檢查 API Token，網路連線 |
| dlib 模型錯誤  | 下載面部特徵點模型文件   |

### 系統要求檢查

```bash
# Python 版本 (需要 3.8+)
python --version

# 檢查 I2C 設備
sudo i2cdetect -y 1

# 測試攝像頭
python -c "import cv2; cap=cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAILED')"
```

---

## 性能優化

### 建議配置

- **攝像頭解析度**: 640x480 (平衡效能)
- **處理幀率**: 30 FPS
- **瞌睡檢測**: EAR < 0.25, 連續 20 幀
- **通知冷卻**: 30 秒防止過度推播

### 硬體優化

- 使用高品質攝像頭
- 確保穩定電源供應
- 添加散熱措施

---

## 版本特色

### v1.0 完整功能

**Phase 2**: Telegram/LINE 智能通知  
 **Phase 3**: 網頁遠程控制 + 虛擬搖桿  
 **Phase 5**: 完整事件記錄與監控  
 **額外**: 本地雙視窗控制介面

### 核心價值

- **實用性**: 真正解決瞌睡問題
- **可擴展**: 模塊化設計，易於擴展
- **易部署**: 一鍵安裝，簡單配置
- **現代化**: 響應式網頁，移動友好
