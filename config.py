import os

class Config:
    """系統配置類別"""
    
    # Flask 配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    DEBUG = True
    
    # 瞌睡偵測配置
    EAR_THRESHOLD = 0.25          # 眼睛長寬比閾值
    EAR_CONSEC_FRAMES = 20        # 連續幀數閾值（輕度）
    MEDIUM_DROWSY_FRAMES = 40     # 中度瞌睡幀數
    SEVERE_DROWSY_FRAMES = 60     # 重度瞌睡幀數
    AR_THRESHOLD = 0.75          # 嘴巴長寬比閾值
    YAWN_CONSEC_FRAMES = 15       # 打哈欠連續幀數

    # 頭部姿態配置（可選）
    HEAD_POSE_ENABLED = False     # 是否啟用頭部姿態偵測
    HEAD_DOWN_ANGLE = 20          # 頭部下垂角度閾值（度）
    
    # 攝像頭配置
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    CAMERA_FPS = 60
    
    # GPIO 配置
    # SERVO_PAN_PIN = 17           # 水平伺服馬達
    # SERVO_TILT_PIN = 18          # 垂直伺服馬達
    # WATER_PUMP_PIN = 23          # 水泵繼電器
    # LED_PIN = 24                 # LED 指示燈
    
    # 水槍配置
    # FIRE_DURATION = 1.0          # 發射持續時間（秒）
    # MIN_FIRE_INTERVAL = 30       # 最小發射間隔（秒）
    
    # 通知配置
    # TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or ''
    # TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') or ''

    # 通知條件
    NOTIFY_ON_LIGHT_DROWSY = False    # 輕度瞌睡時通知
    NOTIFY_ON_MEDIUM_DROWSY = True    # 中度瞌睡時通知
    NOTIFY_ON_SEVERE_DROWSY = True    # 重度瞌睡時通知
    NOTIFY_ON_YAWN = False            # 打哈欠時通知

     # 音效配置
    SOUND_ENABLED = True
    SOUND_VOLUME = 0.7            # 音量（0.0-1.0）
    ALERT_SOUND_FILE = 'static/sounds/alert.mp3'
    WARNING_SOUND_FILE = 'static/sounds/warning.mp3'

    # 自動截圖
    AUTO_SCREENSHOT = True
    SCREENSHOT_ON_DROWSY = True
    SCREENSHOT_ON_YAWN = False

    # 數據儲存配置
    # DATA_DIR = 'data'
    # LOG_DIR = os.path.join(DATA_DIR, 'logs')
    # RECORDING_DIR = os.path.join(DATA_DIR, 'recordings')
    

   # 資料庫
    DATABASE_ENABLED = False
    DATABASE_PATH = os.path.join(DATA_DIR, 'drowsiness.db')
    
    # WebSocket 配置
    SOCKETIO_MESSAGE_QUEUE = None
    SOCKETIO_ASYNC_MODE = 'eventlet'
    
    # 效能配置
    FRAME_SKIP = 0                # 跳過幀數（0=不跳過）
    DETECTION_INTERVAL = 1        # 偵測間隔（幀）
    
    # UI 配置
    UI_LANGUAGE = 'zh-TW'         # 介面語言
    UI_THEME = 'dark'             # 主題（dark/light）
    SHOW_FPS = True               # 顯示 FPS
    SHOW_STATISTICS = True        # 顯示統計資訊
    
    # 安全配置
    MAX_FAILED_DETECTIONS = 100   # 最大連續偵測失敗次數
    AUTO_RESTART_ON_ERROR = True  # 錯誤時自動重啟
    
    # 確保目錄存在
    @staticmethod
    def init_directories():
        """初始化所有必要的目錄"""
        dirs = [
            Config.DATA_DIR,
            Config.LOG_DIR,
            Config.RECORDING_DIR,
            Config.SCREENSHOT_DIR,
            'static/sounds'
        ]
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)
        print("✅ 目錄初始化完成")


# 初始化目錄
Config.init_directories()