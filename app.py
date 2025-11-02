"""
Flask 應用程式主入口
整合改良版瞌睡偵測系統
"""

from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
import cv2
import time
import threading
import logging
from datetime import datetime
import os

from config import Config
from modules.drowsiness_detector import DrowsinessDetector

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化 Flask
app = Flask(__name__)
app.config.from_object(Config)

# 初始化 SocketIO
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='eventlet'
)

# 全域變數
detector = None
camera = None
monitoring_active = False
monitoring_thread = None
last_result = None
frame_count = 0


def init_system():
    """初始化系統"""
    global detector, camera
    
    try:
        logger.info("🚀 初始化瞌睡偵測系統...")
        
        # 初始化配置
        config = Config()
        
        # 初始化瞌睡偵測器
        detector = DrowsinessDetector(config)
        logger.info("✅ 瞌睡偵測器初始化成功")
        
        # 初始化攝像頭
        camera = cv2.VideoCapture(config.CAMERA_INDEX)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        camera.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        
        if not camera.isOpened():
            raise Exception("無法開啟攝像頭")
        
        logger.info("✅ 攝像頭初始化成功")
        logger.info("="*60)
        logger.info("系統配置:")
        logger.info(f"  EAR 閾值: {config.EAR_THRESHOLD}")
        logger.info(f"  EAR 連續幀數: {config.EAR_CONSEC_FRAMES}")
        logger.info(f"  MAR 閾值: {config.MAR_THRESHOLD}")
        logger.info(f"  打哈欠連續幀數: {config.YAWN_CONSEC_FRAMES}")
        logger.info(f"  影像尺寸: {config.CAMERA_WIDTH}x{config.CAMERA_HEIGHT}")
        logger.info("="*60)
        
        return True
    except Exception as e:
        logger.error(f"❌ 系統初始化失敗: {e}")
        return False


def generate_frames():
    """生成視訊串流"""
    global detector, camera, last_result, frame_count, monitoring_active
    
    fps_start_time = time.time()
    fps_frame_count = 0
    current_fps = 0
    
    while monitoring_active:
        if camera is None:
            break
        
        ret, frame = camera.read()
        if not ret:
            logger.warning("⚠️  無法讀取影像幀")
            continue
        
        try:
            # 處理影像幀
            processed_frame, result = detector.process_frame(frame)
            last_result = result
            frame_count += 1
            
            # 計算 FPS
            fps_frame_count += 1
            if time.time() - fps_start_time >= 1.0:
                current_fps = fps_frame_count / (time.time() - fps_start_time)
                fps_start_time = time.time()
                fps_frame_count = 0
            
            # 顯示 FPS
            if Config.SHOW_FPS:
                cv2.putText(processed_frame, f"FPS: {current_fps:.1f}", 
                           (processed_frame.shape[1] - 120, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # 發送結果到前端（每 10 幀發送一次）
            if frame_count % 10 == 0:
                socketio.emit('detection_result', {
                    'state': result['state'],
                    'alert_level': result['alert_level'],
                    'ear': round(result['ear'], 3),
                    'mar': round(result['mar'], 3),
                    'eye_counter': result['eye_counter'],
                    'yawn_counter': result['yawn_counter'],
                    'total_drowsy': result['total_drowsy'],
                    'total_yawns': result['total_yawns'],
                    'timestamp': result['timestamp'],
                    'fps': round(current_fps, 1)
                })
            
            # 瞌睡警報處理
            if result['should_alert']:
                handle_drowsy_alert(result, processed_frame)
            
            # 打哈欠警告處理
            if result['should_warn'] and not result['should_alert']:
                handle_yawn_warning(result)
            
            # 編碼為 JPEG
            ret, buffer = cv2.imencode('.jpg', processed_frame, 
                                      [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            # 生成串流
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
        except Exception as e:
            logger.error(f"❌ 處理影像時發生錯誤: {e}")
            continue
        
        # 控制幀率
        time.sleep(0.01)


def handle_drowsy_alert(result, frame):
    """處理瞌睡警報"""
    global detector
    
    # 避免頻繁發送通知
    current_time = time.time()
    if current_time - detector.stats['last_alert_time'] < Config.MIN_FIRE_INTERVAL:
        return
    
    logger.warning(f"⚠️  瞌睡警報！EAR: {result['ear']:.3f}, 持續: {result['eye_counter']} 幀")
    
    # 發送 WebSocket 通知
    socketio.emit('drowsy_alert', {
        'level': result['alert_level'],
        'ear': result['ear'],
        'duration': result['drowsy_duration'],
        'timestamp': datetime.now().isoformat()
    })
    
    # 截圖（如果啟用）
    if Config.AUTO_SCREENSHOT and Config.SCREENSHOT_ON_DROWSY:
        screenshot_path = save_screenshot(frame, 'drowsy')
        logger.info(f"📸 已保存截圖: {screenshot_path}")
    
    # 更新統計
    detector.stats['alerts_sent'] += 1
    detector.stats['last_alert_time'] = current_time
    
    # TODO: 觸發水槍發射（待實作）
    # trigger_water_gun()


def handle_yawn_warning(result):
    """處理打哈欠警告"""
    logger.info(f"🥱 偵測到打哈欠！MAR: {result['mar']:.3f}, 持續: {result['yawn_counter']} 幀")
    
    # 發送 WebSocket 通知
    socketio.emit('yawn_warning', {
        'mar': result['mar'],
        'duration': result['yawn_duration'],
        'timestamp': datetime.now().isoformat()
    })


def save_screenshot(frame, event_type):
    """保存截圖"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{event_type}_{timestamp}.jpg"
    filepath = os.path.join(Config.SCREENSHOT_DIR, filename)
    
    cv2.imwrite(filepath, frame)
    return filepath


# ===== Flask 路由 =====

@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')


@app.route('/monitor')
def monitor():
    """監控頁面"""
    return render_template('monitor.html')


@app.route('/control')
def control():
    """控制頁面"""
    return render_template('control.html')


@app.route('/history')
def history():
    """歷史記錄頁面"""
    return render_template('history.html')


@app.route('/settings')
def settings():
    """設定頁面"""
    return render_template('settings.html')


@app.route('/video_feed')
def video_feed():
    """視訊串流端點"""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ===== API 端點 =====

@app.route('/api/start', methods=['POST'])
def start_monitoring():
    """開始監控"""
    global monitoring_active
    
    if not monitoring_active:
        monitoring_active = True
        logger.info("🎬 監控已啟動")
        return jsonify({'status': 'success', 'message': '監控已啟動'})
    else:
        return jsonify({'status': 'info', 'message': '監控已在運行中'})


@app.route('/api/stop', methods=['POST'])
def stop_monitoring():
    """停止監控"""
    global monitoring_active
    
    monitoring_active = False
    logger.info("⏸️  監控已停止")
    return jsonify({'status': 'success', 'message': '監控已停止'})


@app.route('/api/status', methods=['GET'])
def get_status():
    """獲取系統狀態"""
    if detector and last_result:
        return jsonify({
            'monitoring_active': monitoring_active,
            'current_state': last_result['state'],
            'alert_level': last_result['alert_level'],
            'ear': round(last_result['ear'], 3),
            'mar': round(last_result['mar'], 3),
            'total_drowsy': last_result['total_drowsy'],
            'total_yawns': last_result['total_yawns']
        })
    else:
        return jsonify({
            'monitoring_active': False,
            'current_state': 'Inactive',
            'alert_level': 0
        })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """獲取統計數據"""
    if detector:
        stats = detector.get_statistics()
        return jsonify(stats)
    else:
        return jsonify({'error': '系統未初始化'}), 500


@app.route('/api/reset_stats', methods=['POST'])
def reset_stats():
    """重置統計數據"""
    if detector:
        detector.reset_statistics()
        logger.info("📊 統計數據已重置")
        return jsonify({'status': 'success', 'message': '統計數據已重置'})
    else:
        return jsonify({'error': '系統未初始化'}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """獲取配置資訊"""
    return jsonify({
        'ear_threshold': Config.EAR_THRESHOLD,
        'ear_consec_frames': Config.EAR_CONSEC_FRAMES,
        'mar_threshold': Config.MAR_THRESHOLD,
        'yawn_consec_frames': Config.YAWN_CONSEC_FRAMES,
        'camera_width': Config.CAMERA_WIDTH,
        'camera_height': Config.CAMERA_HEIGHT
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置（動態調整閾值）"""
    data = request.get_json()
    
    if 'ear_threshold' in data:
        Config.EAR_THRESHOLD = float(data['ear_threshold'])
        if detector:
            detector.EYE_AR_THRESH = Config.EAR_THRESHOLD
    
    if 'mar_threshold' in data:
        Config.MAR_THRESHOLD = float(data['mar_threshold'])
        if detector:
            detector.MOUTH_AR_THRESH = Config.MAR_THRESHOLD
    
    logger.info(f"⚙️  配置已更新: EAR={Config.EAR_THRESHOLD}, MAR={Config.MAR_THRESHOLD}")
    return jsonify({'status': 'success', 'message': '配置已更新'})


# ===== WebSocket 事件 =====

@socketio.on('connect')
def handle_connect():
    """WebSocket 連接"""
    logger.info('🔌 客戶端已連接')
    emit('connection_response', {
        'status': 'connected',
        'message': '已連接到伺服器',
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket 斷開"""
    logger.info('🔌 客戶端已斷開')


@socketio.on('request_status')
def handle_request_status():
    """客戶端請求狀態更新"""
    if last_result:
        emit('detection_result', last_result)


# ===== 錯誤處理 =====

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"伺服器錯誤: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ===== 主程式 =====

if __name__ == '__main__':
    print("="*60)
    print("🎯 智能防瞌睡系統 v2.0")
    print("="*60)
    print()
    
    if init_system():
        print("✅ 系統初始化成功")
        print()
        print("🌐 啟動 Web 伺服器...")
        print(f"   URL: http://0.0.0.0:5000")
        print(f"   監控頁面: http://0.0.0.0:5000/monitor")
        print(f"   控制頁面: http://0.0.0.0:5000/control")
        print()
        print("按 Ctrl+C 停止伺服器")
        print("="*60)
        print()
        
        try:
            socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        except KeyboardInterrupt:
            print("\n⚠️  正在關閉系統...")
            monitoring_active = False
            if camera:
                camera.release()
            print("✅ 系統已安全關閉")
    else:
        print("❌ 系統初始化失敗，無法啟動伺服器")