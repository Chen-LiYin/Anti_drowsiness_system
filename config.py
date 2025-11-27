import os

class Config:
    """系統配置類別"""
    
    # ===== Flask 配置 =====
    SECRET_KEY = 'anti-drowsiness-secret-key-2024'
    DEBUG = True
    
    # ===== 瞌睡偵測配置 =====
    # EAR (Eye Aspect Ratio) 配置
    EAR_THRESHOLD = 0.25
    EAR_CONSEC_FRAMES = 20
    MEDIUM_DROWSY_FRAMES = 40
    SEVERE_DROWSY_FRAMES = 60
    
    # MAR (Mouth Aspect Ratio) 配置
    MAR_THRESHOLD = 0.75
    YAWN_CONSEC_FRAMES = 15
    
    # ===== 攝像頭配置 =====
    CAMERA_INDEX = 0
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    CAMERA_FPS = 30
    
    # ===== GPIO 配置 =====
    SERVO_PAN_PIN = 17
    SERVO_TILT_PIN = 18
    WATER_PUMP_PIN = 23
    LED_PIN = 24
    
    # ===== PCA9685 舵機控制配置 =====
    SERVO_PAN_CHANNEL = 0    # Pan 舵機通道
    SERVO_TILT_CHANNEL = 1   # Tilt 舵機通道
    
    # 舵機角度範圍
    PAN_MIN = 0
    PAN_MAX = 180
    TILT_MIN = 45
    TILT_MAX = 135
    
    # 舵機校正偏移
    PAN_OFFSET = 0
    TILT_OFFSET = 0
    
    # 舵機平滑移動參數
    SERVO_SMOOTH_STEPS = 5
    SERVO_SMOOTH_DELAY = 0.02
    
    # 人臉追蹤死區（像素）
    TRACKING_DEAD_ZONE = 30
    
    # ===== 數據儲存配置 =====
    DATA_DIR = 'data'
    LOG_DIR = os.path.join(DATA_DIR, 'logs')
    RECORDING_DIR = os.path.join(DATA_DIR, 'recordings')
    SCREENSHOT_DIR = os.path.join(DATA_DIR, 'screenshots')
    DATABASE_PATH = os.path.join(DATA_DIR, 'drowsiness.db')
    
    # 自動截圖
    AUTO_SCREENSHOT = True
    SCREENSHOT_ON_DROWSY = True
    
    # ===== UI 配置 =====
    SHOW_FPS = True
    SHOW_STATISTICS = True
    
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