#!/usr/bin/env python3
"""
網頁遠程控制系統 - Phase 3
使用 Flask + SocketIO 實現即時網頁控制介面
支援即時視訊串流、虛擬搖桿控制、射擊控制等功能
"""

from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
import cv2
import base64
import json
import time
import threading
from datetime import datetime
import os
import sys
import numpy as np

# 音頻串流
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("⚠️ PyAudio 未安裝，音頻串流功能將不可用")

# 添加父目錄到路徑
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import Config

class WebRemoteControl:
    def __init__(self, config=None):
        """初始化網頁遠程控制系統"""
        self.config = config or Config()
        
        # Flask 應用
        self.app = Flask(__name__, 
                        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
        
        self.app.config['SECRET_KEY'] = self.config.SECRET_KEY
        
        # SocketIO
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", 
                               async_mode='threading', logger=False, engineio_logger=False)
        
        # 控制狀態
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.connected_clients = set()
        self.control_active = False
        self.current_controller = None
        
        # 雲台控制回調
        self.pan_callback = None
        self.tilt_callback = None
        self.fire_callback = None
        
        # 雲台狀態
        self.current_pan = 90  # 中心位置
        self.current_tilt = 90
        self.pan_min, self.pan_max = 45, 135
        self.tilt_min, self.tilt_max = 45, 135
        
        # 射擊狀態
        self.last_fire_time = 0
        self.fire_cooldown = 0.5
        self.fire_mode = 'single'  # single, burst, continuous
        self.current_sound = 'water_gun'
        
        # 統計數據
        self.session_start_time = time.time()
        self.remote_stats = {
            'connections': 0,
            'total_shots': 0,
            'control_time': 0,
            'last_activity': None
        }

        # 音頻串流
        self.audio_enabled = AUDIO_AVAILABLE
        self.audio_stream = None
        self.audio_thread = None
        self.audio_running = False

        self.setup_routes()
        self.setup_socketio_events()

        print("網頁遠程控制系統已初始化")
        print(f"  - Flask 主機: {self.config.FLASK_HOST}:{self.config.FLASK_PORT}")
        print(f"  - 控制密碼: {self.config.CONTROL_PASSWORD}")
        print(f"  - 音頻串流: {'啟用' if self.audio_enabled else '停用'}")
    
    def setup_routes(self):
        """設置 Flask 路由"""
        
        @self.app.route('/')
        def index():
            """主頁"""
            return render_template('index.html')
        
        @self.app.route('/remote_control')
        def remote_control():
            """遠程控制頁面"""
            # 簡單的密碼驗證
            auth_token = request.args.get('auth', '')
            if auth_token != self.config.CONTROL_PASSWORD:
                return "❌ 無效的訪問權限", 403
            
            return render_template('remote_control.html',
                                 config={
                                     'pan_min': self.pan_min,
                                     'pan_max': self.pan_max,
                                     'tilt_min': self.tilt_min,
                                     'tilt_max': self.tilt_max,
                                     'sounds': self.config.AVAILABLE_SOUNDS,
                                     'CONTROL_PASSWORD': self.config.CONTROL_PASSWORD
                                 })
        
        @self.app.route('/video_feed')
        def video_feed():
            """視訊串流"""
            auth_token = request.args.get('auth', '')
            if auth_token != self.config.CONTROL_PASSWORD:
                return "❌ 無效的訪問權限", 403
            
            return Response(self.generate_video_stream(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/api/status')
        def api_status():
            """獲取系統狀態"""
            return jsonify({
                'pan': self.current_pan,
                'tilt': self.current_tilt,
                'fire_ready': (time.time() - self.last_fire_time) >= self.fire_cooldown,
                'fire_mode': self.fire_mode,
                'sound_effect': self.current_sound,
                'connected_clients': len(self.connected_clients),
                'control_active': self.control_active,
                'uptime': time.time() - self.session_start_time
            })
        
        @self.app.route('/api/stats')
        def api_stats():
            """獲取統計數據"""
            stats = self.remote_stats.copy()
            stats['session_duration'] = time.time() - self.session_start_time
            return jsonify(stats)
    
    def setup_socketio_events(self):
        """設置 SocketIO 事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客戶端連接"""
            client_id = request.sid
            client_ip = request.environ.get('REMOTE_ADDR', 'unknown')
            
            print(f"🌐 客戶端連接: {client_id} ({client_ip})")
            
            self.connected_clients.add(client_id)
            self.remote_stats['connections'] += 1
            self.remote_stats['last_activity'] = datetime.now().isoformat()
            
            join_room('controllers')
            
            # 發送當前狀態
            emit('status_update', {
                'pan': self.current_pan,
                'tilt': self.current_tilt,
                'fire_ready': (time.time() - self.last_fire_time) >= self.fire_cooldown,
                'fire_mode': self.fire_mode,
                'sound_effect': self.current_sound
            })
            
            # 記錄連接事件
            if hasattr(self, 'event_recorder'):
                self.event_recorder.record_remote_control_start({
                    'ip': client_ip,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'session_id': client_id
                })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客戶端斷開"""
            client_id = request.sid
            
            print(f"❌ 客戶端斷開: {client_id}")
            
            if client_id in self.connected_clients:
                self.connected_clients.remove(client_id)
            
            # 如果是當前控制者，釋放控制權
            if self.current_controller == client_id:
                self.control_active = False
                self.current_controller = None
                print("🔓 控制權已釋放")
            
            leave_room('controllers')
        
        @self.socketio.on('control_start')
        def handle_control_start(data=None):
            """開始控制"""
            client_id = request.sid
            
            # 檢查是否已有其他控制者
            if self.control_active and self.current_controller != client_id:
                emit('control_denied', {
                    'message': '已有其他用戶在控制中',
                    'current_controller': self.current_controller
                })
                return
            
            self.control_active = True
            self.current_controller = client_id
            
            print(f"🎮 控制權授予: {client_id}")
            
            emit('control_granted', {'controller_id': client_id})
            emit('controller_change', {
                'active': True, 
                'controller': client_id
            }, room='controllers')
        
        @self.socketio.on('control_end')
        def handle_control_end():
            """結束控制"""
            client_id = request.sid
            
            if self.current_controller == client_id:
                self.control_active = False
                self.current_controller = None
                
                print(f"🔓 控制權釋放: {client_id}")
                
                emit('controller_change', {
                    'active': False, 
                    'controller': None
                }, room='controllers')
        
        @self.socketio.on('pan_control')
        def handle_pan_control(data):
            """Pan 控制"""
            if not self.is_authorized_controller(request.sid):
                return
            
            try:
                target_angle = float(data.get('angle', 90))
                target_angle = max(self.pan_min, min(self.pan_max, target_angle))
                
                self.current_pan = target_angle
                
                # 調用雲台控制回調
                if self.pan_callback:
                    self.pan_callback(target_angle)
                
                # 廣播位置更新
                self.socketio.emit('position_update', {
                    'pan': self.current_pan,
                    'tilt': self.current_tilt
                }, room='controllers')
                
                self.remote_stats['last_activity'] = datetime.now().isoformat()
                
            except (ValueError, TypeError) as e:
                print(f"Pan 控制錯誤: {e}")
        
        @self.socketio.on('tilt_control')
        def handle_tilt_control(data):
            """Tilt 控制"""
            if not self.is_authorized_controller(request.sid):
                return
            
            try:
                target_angle = float(data.get('angle', 90))
                target_angle = max(self.tilt_min, min(self.tilt_max, target_angle))
                
                self.current_tilt = target_angle
                
                # 調用雲台控制回調
                if self.tilt_callback:
                    self.tilt_callback(target_angle)
                
                # 廣播位置更新
                self.socketio.emit('position_update', {
                    'pan': self.current_pan,
                    'tilt': self.current_tilt
                }, room='controllers')
                
                self.remote_stats['last_activity'] = datetime.now().isoformat()
                
            except (ValueError, TypeError) as e:
                print(f"Tilt 控制錯誤: {e}")
        
        @self.socketio.on('fire_control')
        def handle_fire_control(data):
            """射擊控制"""
            if not self.is_authorized_controller(request.sid):
                return
            
            current_time = time.time()
            
            # 檢查射擊冷卻
            if current_time - self.last_fire_time < self.fire_cooldown:
                emit('fire_denied', {
                    'message': '射擊冷卻中',
                    'cooldown': self.fire_cooldown - (current_time - self.last_fire_time)
                })
                return
            
            # 獲取射擊參數
            fire_mode = data.get('mode', 'single')
            sound_effect = data.get('sound', 'water_gun')
            
            print(f"🔫 遠程射擊: {fire_mode} ({sound_effect})")
            
            # 調用射擊回調
            if self.fire_callback:
                shot_data = {
                    'remote': True,
                    'controller': request.sid,
                    'mode': fire_mode,
                    'sound': sound_effect
                }
                
                success = self.fire_callback(shot_data)
                
                if success:
                    self.last_fire_time = current_time
                    self.remote_stats['total_shots'] += 1
                    
                    # 廣播射擊事件
                    self.socketio.emit('fire_executed', {
                        'mode': fire_mode,
                        'sound': sound_effect,
                        'timestamp': datetime.now().isoformat()
                    }, room='controllers')
                    
                    emit('fire_success', {'message': '射擊成功'})
                    
                    # 記錄射擊事件
                    if hasattr(self, 'event_recorder'):
                        self.event_recorder.record_shot_fired(shot_data)
                else:
                    emit('fire_error', {'message': '射擊失敗'})
        
        @self.socketio.on('mode_change')
        def handle_mode_change(data):
            """射擊模式變更"""
            if not self.is_authorized_controller(request.sid):
                return
            
            new_mode = data.get('mode', 'single')
            if new_mode in ['single', 'burst', 'continuous']:
                self.fire_mode = new_mode
                
                self.socketio.emit('mode_update', {
                    'mode': new_mode
                }, room='controllers')
                
                print(f"🎯 射擊模式變更: {new_mode}")
        
        @self.socketio.on('sound_change')
        def handle_sound_change(data):
            """音效變更"""
            if not self.is_authorized_controller(request.sid):
                return
            
            new_sound = data.get('sound', 'water_gun')
            if new_sound in self.config.AVAILABLE_SOUNDS:
                self.current_sound = new_sound
                
                self.socketio.emit('sound_update', {
                    'sound': new_sound
                }, room='controllers')
                
                print(f"🔊 音效變更: {new_sound}")
    
    def is_authorized_controller(self, client_id):
        """檢查是否為授權控制者"""
        return self.control_active and self.current_controller == client_id
    
    def update_frame(self, frame):
        """更新視訊幀"""
        with self.frame_lock:
            self.current_frame = frame.copy() if frame is not None else None
    
    def generate_video_stream(self):
        """生成視訊串流"""
        while True:
            try:
                with self.frame_lock:
                    if self.current_frame is not None:
                        frame = self.current_frame.copy()
                    else:
                        # 創建黑色畫面
                        frame = cv2.imread('static/no_signal.jpg') if os.path.exists('static/no_signal.jpg') else \
                               cv2.resize(cv2.imread('static/no_video.png'), (640, 480)) if os.path.exists('static/no_video.png') else \
                               np.zeros((480, 640, 3), dtype=np.uint8)
                
                # 添加準星
                frame = self.add_crosshair(frame)
                
                # 添加狀態信息
                frame = self.add_status_overlay(frame)
                
                # 編碼為JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
            except Exception as e:
                print(f"視訊串流錯誤: {e}")
            
            time.sleep(1/30)  # 30 FPS
    
    def add_crosshair(self, frame):
        """添加準星"""
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2
        
        # 紅色準星
        color = (0, 0, 255)  # BGR格式
        thickness = 2
        size = 20
        
        # 十字準星
        cv2.line(frame, (center_x - size, center_y), (center_x + size, center_y), color, thickness)
        cv2.line(frame, (center_x, center_y - size), (center_x, center_y + size), color, thickness)
        
        # 圓圈
        cv2.circle(frame, (center_x, center_y), 30, color, 1)
        
        return frame
    
    def add_status_overlay(self, frame):
        """添加狀態疊加信息"""
        # 狀態信息
        status_text = []
        
        # 雲台位置
        status_text.append(f"Pan: {self.current_pan:.0f}° Tilt: {self.current_tilt:.0f}°")
        
        # 射擊狀態
        time_since_fire = time.time() - self.last_fire_time
        fire_ready = time_since_fire >= self.fire_cooldown
        status_text.append(f"Fire: {'Ready' if fire_ready else f'Cooldown {self.fire_cooldown - time_since_fire:.1f}s'}")
        
        # 控制狀態
        if self.control_active:
            status_text.append(f"Controller: Active ({self.current_controller[:8]})")
        else:
            status_text.append("Controller: None")
        
        # 連接數
        status_text.append(f"Clients: {len(self.connected_clients)}")
        
        # 繪製半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (300, 10 + len(status_text) * 25 + 10), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # 繪製文字
        y_offset = 30
        for text in status_text:
            cv2.putText(frame, text, (15, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset += 25
        
        return frame
    
    def set_control_callbacks(self, pan_callback=None, tilt_callback=None, fire_callback=None):
        """設置控制回調函數"""
        self.pan_callback = pan_callback
        self.tilt_callback = tilt_callback
        self.fire_callback = fire_callback
        print("✅ 控制回調已設置")
    
    def set_event_recorder(self, event_recorder):
        """設置事件記錄器"""
        self.event_recorder = event_recorder
        print("✅ 事件記錄器已設置")

    def grant_emergency_control(self, reason="偵測到瞌睡"):
        """瞌睡下自動授予遠端控制權限"""
        print(f"\n 瞌睡下模式啟動: {reason}")

        # 廣播瞌睡下控制模式給所有連接的客戶端
        self.socketio.emit('emergency_control_available', {
            'reason': reason,
            'message': f'瞌睡下模式：{reason} - 控制權已自動開放',
            'auto_grant': True
        }, room='controllers')

        # 如果有連接的客戶端，授予第一個客戶端控制權
        if self.connected_clients and not self.control_active:
            first_client = list(self.connected_clients)[0]
            self.control_active = True
            self.current_controller = first_client

            self.socketio.emit('control_granted', {
                'controller_id': first_client,
                'emergency': True
            }, room=first_client)

            print(f"✅ 緊急控制權已授予客戶端: {first_client}")
            return True

        return False

    def revoke_remote_control(self, reason="用戶已甦醒"):
        """撤銷遠端控制權限"""
        if self.control_active and self.current_controller:
            print(f"\n🔓 撤銷遠端控制權限: {reason}")

            # 通知遠端控制者控制權已被撤銷
            self.socketio.emit('control_revoked', {
                'reason': reason,
                'message': f'控制權已被撤銷：{reason}'
            }, room='controllers')

            # 釋放控制權
            self.control_active = False
            self.current_controller = None

            print("✅ 遠端控制權限已撤銷")
            return True
        return False

    def start_audio_stream(self):
        """啟動音頻串流"""
        if not self.audio_enabled:
            print("⚠️ 音頻功能未啟用")
            return False

        if self.audio_running:
            print("⚠️ 音頻串流已在運行")
            return False

        try:
            self.audio_running = True
            self.audio_thread = threading.Thread(target=self.stream_audio, daemon=True)
            self.audio_thread.start()
            print("🎤 音頻串流已啟動")
            return True
        except Exception as e:
            print(f"❌ 音頻串流啟動失敗: {e}")
            self.audio_running = False
            return False

    def stop_audio_stream(self):
        """停止音頻串流"""
        if not self.audio_running:
            return

        self.audio_running = False
        if self.audio_thread:
            self.audio_thread.join(timeout=2)

        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass

        print("🎤 音頻串流已停止")

    def stream_audio(self):
        """音頻串流線程"""
        try:
            # 音頻參數
            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000

            # 初始化 PyAudio
            p = pyaudio.PyAudio()

            # 開啟音頻串流
            self.audio_stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            print(f"🎤 麥克風已開啟 (採樣率: {RATE}Hz, 通道: {CHANNELS})")

            while self.audio_running:
                try:
                    # 讀取音頻數據
                    audio_data = self.audio_stream.read(CHUNK, exception_on_overflow=False)

                    # 轉換為 base64 並通過 SocketIO 發送
                    audio_base64 = base64.b64encode(audio_data).decode('utf-8')

                    self.socketio.emit('audio_stream', {
                        'data': audio_base64,
                        'rate': RATE,
                        'channels': CHANNELS
                    }, room='controllers')

                except Exception as e:
                    if self.audio_running:
                        print(f"⚠️ 音頻讀取錯誤: {e}")
                    break

        except Exception as e:
            print(f"❌ 音頻串流錯誤: {e}")
        finally:
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except:
                    pass
            try:
                p.terminate()
            except:
                pass

    def run(self, debug=None, host=None, port=None):
        """運行 Flask 應用"""
        host = host or self.config.FLASK_HOST
        port = port or self.config.FLASK_PORT
        debug = debug if debug is not None else self.config.FLASK_DEBUG
        
        print(f"\n🌐 啟動網頁遠程控制服務...")
        print(f"   主機: {host}:{port}")
        print(f"   控制URL: http://{host}:{port}/remote_control?auth={self.config.CONTROL_PASSWORD}")
        print(f"   視訊URL: http://{host}:{port}/video_feed?auth={self.config.CONTROL_PASSWORD}")
        
        self.socketio.run(self.app, host=host, port=port, debug=debug)


def main():
    """測試用主程式"""
    import numpy as np
    
    print("="*60)
    print("網頁遠程控制系統測試")
    print("="*60)
    
    from config import Config
    config = Config()
    
    # 初始化遠程控制系統
    web_control = WebRemoteControl(config)
    
    # 模擬雲台控制回調
    def mock_pan_control(angle):
        print(f"🎯 Pan 控制: {angle}°")
    
    def mock_tilt_control(angle):
        print(f"📐 Tilt 控制: {angle}°")
    
    def mock_fire_control(shot_data):
        print(f"🔫 射擊: {shot_data}")
        return True  # 模擬成功
    
    web_control.set_control_callbacks(mock_pan_control, mock_tilt_control, mock_fire_control)
    
    # 創建模擬視訊幀
    def generate_test_frame():
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, "TEST CAMERA FEED", (200, 240), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        return frame
    
    # 更新測試幀
    import threading
    def update_test_frames():
        while True:
            test_frame = generate_test_frame()
            web_control.update_frame(test_frame)
            time.sleep(1/30)  # 30 FPS
    
    frame_thread = threading.Thread(target=update_test_frames, daemon=True)
    frame_thread.start()
    
    # 運行 Flask 應用
    try:
        web_control.run()
    except KeyboardInterrupt:
        print("\n👋 網頁遠程控制系統已停止")


if __name__ == "__main__":
    main()