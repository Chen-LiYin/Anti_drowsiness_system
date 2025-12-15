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
import socket
import secrets

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

        # 聊天室系統
        self.vote_end_time = 0  # 新增：用來記錄「什麼時候」結束
        self.chat_active = False
        self.chat_session_id = None
        self.chat_messages = []  # [{id, user_id, username, message, votes, timestamp}]
        self.chat_votes = {}  # {user_id: message_id} - 記錄每個用戶投給誰
        self.chat_timer_thread = None
        self.chat_time_remaining = 0
        self.chat_timer_active = False
        self.user_nicknames = {}  # {session_id: nickname}
        # 一次性控制連結 token 存儲: {token: {'expires_at': float, 'used': bool}}
        self.one_time_tokens = {}
        self.notification_system = None

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
            token = request.args.get('token', '')

            # 若未提供密碼，但提供一次性 token 且該 token 仍存在且未過期，允許進入
            token_valid_for_render = False
            if token:
                info = self.one_time_tokens.get(token)
                if info and (not info.get('used')) and time.time() < info.get('expires_at', 0):
                    token_valid_for_render = True

            if auth_token != self.config.CONTROL_PASSWORD and not token_valid_for_render:
                return "❌ 無效的訪問權限", 403
            
            return render_template('remote_control.html',
                                 config={
                                     'pan_min': self.pan_min,
                                     'pan_max': self.pan_max,
                                     'tilt_min': self.tilt_min,
                                     'tilt_max': self.tilt_max,
                                     'sounds': self.config.AVAILABLE_SOUNDS,
                                     'CONTROL_PASSWORD': self.config.CONTROL_PASSWORD,
                                     'monitor_only': False
                                 })

        @self.app.route('/chat')
        def chat_page():
            """獨立聊天室頁面"""
            return render_template('chat.html')

        @self.app.route('/monitor_only')
        def monitor_only():
            """只看監控畫面（無搖桿/射擊）"""
            auth_token = request.args.get('auth', '')
            token = request.args.get('token', '')

            token_valid_for_render = False
            if token:
                info = self.one_time_tokens.get(token)
                if info and (not info.get('used')) and time.time() < info.get('expires_at', 0):
                    token_valid_for_render = True

            if auth_token != self.config.CONTROL_PASSWORD and not token_valid_for_render:
                return "❌ 無效的訪問權限", 403

            return render_template('remote_control.html',
                                 config={
                                     'pan_min': self.pan_min,
                                     'pan_max': self.pan_max,
                                     'tilt_min': self.tilt_min,
                                     'tilt_max': self.tilt_max,
                                     'sounds': self.config.AVAILABLE_SOUNDS,
                                     'CONTROL_PASSWORD': self.config.CONTROL_PASSWORD,
                                     'monitor_only': True
                                 })

        @self.app.route('/monitor')
        def monitor_page():
            """獨立監控頁面（無搖桿）"""
            auth_token = request.args.get('auth', '')
            token = request.args.get('token', '')

            token_valid_for_render = False
            if token:
                info = self.one_time_tokens.get(token)
                if info and (not info.get('used')) and time.time() < info.get('expires_at', 0):
                    token_valid_for_render = True

            if auth_token != self.config.CONTROL_PASSWORD and not token_valid_for_render:
                return "❌ 無效的訪問權限", 403

            return render_template('monitor.html',
                                 config={
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
            
            # 1. 發送當前硬體狀態 (雲台、開火冷卻等)
            emit('status_update', {
                'pan': self.current_pan,
                'tilt': self.current_tilt,
                'fire_ready': (time.time() - self.last_fire_time) >= self.fire_cooldown,
                'fire_mode': self.fire_mode,
                'sound_effect': self.current_sound
            })

            # ==========================================
            # 2. 【新增】同步聊天室倒數狀態 (解決後進者沒秒數問題)
            # ==========================================
            # 檢查是否正在進行聊天室活動
            if hasattr(self, 'chat_active') and self.chat_active:
                # 檢查倒數時間是否還沒結束
                if hasattr(self, 'vote_end_time'):
                    current_time = time.time()
                    if self.vote_end_time > current_time:
                        # 計算剩餘秒數
                        remaining_seconds = int(self.vote_end_time - current_time)
                        
                        if remaining_seconds > 0:
                            print(f"⏱️ 補發倒數時間給 {client_id}: 剩餘 {remaining_seconds} 秒")
                            # 單獨發送給這個新連線的人
                            emit('chat_session_started', {
                                'duration': remaining_seconds, # 這裡傳的是「剩下的時間」
                                'message': '⚠️ 投票進行中，請盡快參與！'
                            })
            # ==========================================
            
            # 3. 記錄連接事件
            if hasattr(self, 'event_recorder') and self.event_recorder:
                self.event_recorder.record_remote_control_start({
                    'ip': client_ip,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'session_id': client_id
                })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客戶端斷開"""
            client_id = request.sid

            print("\n" + "="*50)
            print("❌ 客戶端斷開連接")
            print(f"  - 客戶端 ID: {client_id}")
            print(f"  - 是否為控制者: {self.current_controller == client_id}")
            print(f"  - 剩餘連接數: {len(self.connected_clients) - 1}")
            print("="*50 + "\n")

            if client_id in self.connected_clients:
                self.connected_clients.remove(client_id)

            # 如果是當前控制者，釋放控制權
            if self.current_controller == client_id:
                self.control_active = False
                self.current_controller = None
                print("🔓 控制權已釋放（控制者斷線）")

            leave_room('controllers')
        
        @self.socketio.on('control_start')
        def handle_control_start(data=None):
            """開始控制"""
            client_id = request.sid

            print("\n" + "="*50)
            print("📥 收到控制權請求")
            print(f"  - 請求者 ID: {client_id}")
            print(f"  - 當前控制狀態: {self.control_active}")
            print(f"  - 當前控制者: {self.current_controller}")
            print(f"  - 連接的客戶端: {self.connected_clients}")
            print("="*50 + "\n")

            # 檢查是否已有其他控制者
            if self.control_active and self.current_controller != client_id:
                print(f"❌ 拒絕控制權請求 - 已有其他控制者: {self.current_controller}")
                emit('control_denied', {
                    'message': '已有其他用戶在控制中',
                    'current_controller': self.current_controller
                })
                return

            self.control_active = True
            self.current_controller = client_id

            print(f"✅ 控制權已授予: {client_id}")

            emit('control_granted', {'controller_id': client_id, 'emergency': False})
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

        @self.socketio.on('audio_enable')
        def handle_audio_enable(data):
            """音頻啟用/停用"""
            enable = data.get('enable', False)

            if enable:
                print(f"🎤 客戶端 {request.sid} 請求啟用音頻")
                if self.start_audio_stream():
                    emit('audio_status', {'enabled': True, 'message': '音頻串流已啟動'})
                else:
                    emit('audio_status', {'enabled': False, 'message': '音頻串流啟動失敗'})
            else:
                print(f"🔇 客戶端 {request.sid} 請求停用音頻")
                self.stop_audio_stream()
                emit('audio_status', {'enabled': False, 'message': '音頻串流已停止'})

        # ========== 聊天室事件處理 ==========

        @self.socketio.on('set_nickname')
        def handle_set_nickname(data):
            """設置用戶暱稱"""
            nickname = data.get('nickname', '').strip()
            if nickname and len(nickname) <= 20:
                self.user_nicknames[request.sid] = nickname
                emit('nickname_set', {'nickname': nickname})
                print(f"👤 用戶設置暱稱: {request.sid} -> {nickname}")

        @self.socketio.on('send_message')
        def handle_send_message(data):
            """發送聊天訊息（隨時可用）"""
            user_id = request.sid
            message_text = data.get('message', '').strip()

            print(f"[CHAT] recv send_message from {user_id}: '{message_text}' (chat_active={self.chat_active})")

            # 驗證訊息
            if not message_text:
                emit('chat_error', {'message': '訊息不能為空'})
                return

            if len(message_text) > 50:
                emit('chat_error', {'message': '訊息不能超過 50 字'})
                return

            # 檢查用戶是否已經發送過訊息
            for msg in self.chat_messages:
                if msg['user_id'] == user_id:
                    emit('chat_error', {'message': '您已經發送過訊息了'})
                    return

            # 創建訊息
            username = self.user_nicknames.get(user_id, f'用戶{user_id[:8]}')
            message_id = f"msg_{len(self.chat_messages)}_{int(time.time() * 1000)}"

            new_message = {
                'id': message_id,
                'user_id': user_id,
                'username': username,
                'message': message_text,
                'votes': 0,
                'timestamp': datetime.now().isoformat()
            }

            self.chat_messages.append(new_message)

            # 廣播新訊息
            print(f"[CHAT] broadcasting new_message id={message_id} user={username}")
            self.socketio.emit('new_message', new_message, room='controllers')

            status_text = "（等待主人睡著開始投票）" if not self.chat_active else "（投票進行中）"
            print(f"💬 新訊息 {status_text}: {username}: {message_text}")


        @self.socketio.on('vote_message')
        def handle_vote_message(data):
            """投票給訊息"""
            if not self.chat_active:
                emit('chat_error', {'message': '聊天室未開啟'})
                return

            user_id = request.sid
            message_id = data.get('message_id')

            print(f"[CHAT] recv vote_message from {user_id}: message_id={message_id}")

            if not message_id:
                emit('chat_error', {'message': '無效的訊息 ID'})
                return

            # 檢查用戶是否已經投過票
            if user_id in self.chat_votes:
                emit('chat_error', {'message': '您已經投過票了'})
                return

            # 找到訊息
            message = None
            for msg in self.chat_messages:
                if msg['id'] == message_id:
                    message = msg
                    break

            if not message:
                emit('chat_error', {'message': '找不到該訊息'})
                return

            # 不能投給自己
            if message['user_id'] == user_id:
                emit('chat_error', {'message': '不能投給自己的訊息'})
                return

            # 記錄投票
            self.chat_votes[user_id] = message_id
            message['votes'] += 1

            # 廣播投票更新
            self.socketio.emit('vote_update', {
                'message_id': message_id,
                'votes': message['votes']
            }, room='controllers')

            emit('vote_success', {'message': '投票成功'})

            print(f"🗳️ 投票: {user_id[:8]} -> {message['username']}")

        @self.socketio.on('get_chat_status')
        def handle_get_chat_status():
            """獲取聊天室狀態"""
            emit('chat_status', {
                'active': self.chat_active,
                'time_remaining': self.chat_time_remaining,
                'messages': self.chat_messages,
                'user_voted': request.sid in self.chat_votes
            })

        @self.socketio.on('claim_token')
        def handle_claim_token(data):
            """使用一次性 token 要求控制權"""
            token = data.get('token') if data else None
            sid = request.sid
            if not token:
                emit('control_denied', {'message': '缺少 token'})
                return

            valid = self.validate_and_use_token(token)
            if not valid:
                emit('control_denied', {'message': '無效或已過期的 token'})
                return

            # ★★★ 如果已有其他控制者，強制撤銷 ★★★
            if self.control_active and self.current_controller and self.current_controller != sid:
                old_controller = self.current_controller
                print(f"⚠️ 強制撤銷舊控制者: {old_controller} (新獲勝者: {sid})")

                # 通知舊控制者被撤銷
                self.socketio.emit('control_revoked', {
                    'reason': '新的獲勝者使用 token 獲取控制權',
                    'message': '控制權已被新的獲勝者接管'
                }, room=old_controller)

            # 授予控制權給該連線
            self.control_active = True
            self.current_controller = sid

            emit('control_granted', {'controller_id': sid, 'emergency': False, 'reason': 'token'})
            self.socketio.emit('controller_change', {
                'active': True,
                'controller': sid
            }, room='controllers')
            print(f"✅ 使用 token 授予控制權: {sid}")
    
    def is_authorized_controller(self, client_id):
        """檢查是否為授權控制者"""
        return self.control_active and self.current_controller == client_id

    # ========== 一次性 token 管理 ==========
    def generate_one_time_token(self, ttl=300):
        """生成一次性 token，預設有效期 ttl 秒"""
        token = secrets.token_urlsafe(16)
        self.one_time_tokens[token] = {
            'expires_at': time.time() + ttl,
            'used': False
        }
        print(f"[TOKEN] generated token={token} ttl={ttl}s")
        return token

    def validate_and_use_token(self, token):
        info = self.one_time_tokens.get(token)
        if not info:
            return False
        if info.get('used'):
            return False
        if time.time() > info.get('expires_at', 0):
            # token 過期，移除
            try:
                del self.one_time_tokens[token]
            except KeyError:
                pass
            return False

        # 標記為已使用
        info['used'] = True
        return True

    def set_notification_system(self, notification_system):
        """將 NotificationSystem 傳入以便發送控制連結"""
        self.notification_system = notification_system
        print("✅ 已設定 NotificationSystem 到 WebRemoteControl")
    
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

    # ========== 聊天室管理方法 ==========

    def start_chat_session(self, duration=60):
        """開始聊天會話（瞌睡時觸發）"""
        if self.chat_active:
            print("⚠️ 聊天室已經開啟")
            return False

        # 生成新的聊天會話 ID
        self.chat_session_id = f"chat_{int(time.time() * 1000)}"
        self.chat_active = True
        self.vote_end_time = time.time() + duration # 計算出未來的結束時間點
        self.chat_messages = []
        self.chat_votes = {}
        self.chat_time_remaining = 60
        self.chat_timer_active = True

        print(f"\n💬 聊天會話開始: {self.chat_session_id}")
        print("⏱️ 倒數計時器: 60 秒")

        # 廣播聊天室開啟事件
        self.socketio.emit('chat_session_started', {
            'session_id': self.chat_session_id,
            'duration': duration,
            'message': '主人睡著了！快來留言吧！'
        }, room='controllers')

        # 啟動倒數計時器
        self.chat_timer_thread = threading.Thread(target=self.chat_timer_countdown, daemon=True)
        self.chat_timer_thread.start()

        return True

    def chat_timer_countdown(self):
        """聊天室倒數計時器"""
        while self.chat_timer_active and self.chat_time_remaining > 0:
            time.sleep(1)
            self.chat_time_remaining -= 1

            # 每秒廣播剩餘時間
            self.socketio.emit('chat_timer_update', {
                'time_remaining': self.chat_time_remaining
            }, room='controllers')

            # 倒數最後 10 秒時顯示警告
            if self.chat_time_remaining == 10:
                self.socketio.emit('chat_warning', {
                    'message': '剩餘 10 秒！'
                }, room='controllers')

        # 時間到，自動結束聊天會話並計算最高票
        if self.chat_timer_active:
            print("\n⏰ 聊天時間結束，開始計算最高票...")
            self.socketio.emit('chat_timer_ended', {
                'message': '聊天時間結束！投票已截止，正在計算結果...'
            }, room='controllers')

            # ★★★ 自動結束聊天會話，計算最高票並授予控制權 ★★★
            self.end_chat_session()

    def end_chat_session(self):
        """結束聊天會話（醒來時觸發）"""
        if not self.chat_active:
            return None

        # 停止計時器
        self.chat_timer_active = False

        # 獲取最高票訊息
        top_message = self.get_top_voted_message()
        print(f"\n💬 聊天會話結束: {self.chat_session_id}")

        if top_message:
            print(f"🏆 最高票訊息: {top_message['username']}: {top_message['message']} ({top_message['votes']} 票)")

            # 授予最高票者控制權（先處理授權/產生 token/發送 control_link）
            winner_user_id = top_message['user_id']
            control_url = self.award_control_to_winner(winner_user_id, top_message)

            # 廣播聊天會話結束，並在 payload 中提示是否有 control_url（不包含 token 本文）
            self.socketio.emit('chat_session_ended', {
                'top_message': top_message,
                'message': '主人醒來了！',
                'control_url': control_url
            }, room='controllers')
        else:
            # 沒有最高票訊息，直接廣播結束
            self.socketio.emit('chat_session_ended', {
                'top_message': None,
                'message': '主人醒來了！',
                'control_url': None
            }, room='controllers')

        # 清理聊天狀態，準備下一輪
        self.chat_active = False
        # 延遲5秒後清空訊息列表，讓前端有時間顯示獲勝者
        def clear_chat_data():
            time.sleep(5)
            self.chat_messages = []
            self.chat_votes = {}
            self.chat_session_id = None
            print("✨ 聊天室已清空，準備下一輪")

        threading.Thread(target=clear_chat_data, daemon=True).start()

        return top_message

    def get_top_voted_message(self):
        """獲取最高票的訊息"""
        if not self.chat_messages:
            return None

        # 按票數排序
        sorted_messages = sorted(self.chat_messages, key=lambda x: x['votes'], reverse=True)

        return sorted_messages[0] if sorted_messages else None

    def award_control_to_winner(self, winner_user_id, top_message):
        """授予最高票者控制權"""
        winner_nickname = top_message.get('username')
        
        # --- 1. ID 修正邏輯 (處理重新連線) ---
        # 嘗試透過暱稱尋找最新的 sid
        current_sids_for_nick = [sid for sid, nick in self.user_nicknames.items() if nick == winner_nickname]
        if current_sids_for_nick:
            winner_user_id = current_sids_for_nick[0] # 更新為最新的 ID

        # --- 2. 統一準備資料 (Token & URLs) ---
        # 在這裡一次性生成 Token 和網址，供後面所有邏輯使用，避免重複生成不一致
        token = self.generate_one_time_token()
        local_ip = self.get_local_ip()
        
        # 控制連結 (給贏家)
        control_url = f"http://{local_ip}:{self.config.FLASK_PORT}/remote_control?auth={self.config.CONTROL_PASSWORD}&token={token}"
        # 監控連結 (給輸家)
        monitor_url = f"http://{local_ip}:{self.config.FLASK_PORT}/monitor?auth={self.config.CONTROL_PASSWORD}"


        # --- 4. 判斷獲勝者是否在線 ---
        is_winner_online = winner_user_id in self.connected_clients

        if not is_winner_online:
            print(f"⚠️ 獲勝者 {winner_nickname} ({winner_user_id[:8]}) 已離線")
            
            # 通知管理員/控制器房間
            self.socketio.emit('winner_offline', {
                'message': f'獲勝者 {winner_nickname} 已離線，已產生連結供轉發',
                'control_url': control_url 
            }, room='controllers')

            # 給所有在線的人發送監控連結 (因為沒人獲得即時控制權)
            self.socketio.emit('monitor_link', {'url': monitor_url}, broadcast=True)
            
            return control_url

        # --- 5. 獲勝者在線：發送控制連結 ---

        # A. 撤銷舊權限（如果有的話）
        if self.control_active and self.current_controller:
            print(f"⚠️ 撤銷舊控制者: {self.current_controller[:8]} (準備給新獲勝者)")
            self.revoke_remote_control(reason="最高票者獲得控制權")

        # B. ★★★ 不要在這裡立即設定控制者 ★★★
        # 因為獲勝者目前在聊天室（Socket ID: winner_user_id）
        # 當他點擊連結進入控制頁面時，會有新的 Socket ID
        # 屆時會通過 claim_token 來獲得控制權
        print(f"🎫 為獲勝者 {winner_nickname} 生成控制連結（包含 token）")

        # C. 發送控制權事件 (給贏家)
        # 這裡包含 control_link 事件，前端收到會跳出金色 Toastify
        try:
            self.socketio.emit('control_link', {
                'url': control_url,
                'token': token,
                'message': '恭喜獲得控制權！'
            }, room=winner_user_id)

        except Exception as e:
            print(f"⚠️ 發送控制連結給獲勝者失敗: {e}")

        # D. 發送監控連結 (給除了贏家以外的所有人)
        # 這裡使用 broadcast=True 但配合 skip_sid (如果你的 socketio 版本支援) 
        # 或者用迴圈，你原本的迴圈寫法是最穩的：
        for cid in list(self.connected_clients):
            if cid != winner_user_id:
                self.socketio.emit('monitor_link', {'url': monitor_url}, room=cid)

        # E. 公告結果 (給所有人)
        self.socketio.emit('winner_announced', {
            'winner': winner_nickname,
            'message': top_message.get('message', ''),
            'votes': top_message.get('votes', 0)
        }, broadcast=True) # 建議用 broadcast=True 確保大家都看得到

        return control_url

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
        """後端錄音並推播 (已針對 USB PnP Sound Device ID:2 設定)"""
        
        # ============ 硬體參數設定 ============
        MIC_INDEX = 2          # ★★★ 填入你剛剛查到的 ID
        CHUNK = 1024           # 每次讀取的封包大小
        FORMAT = pyaudio.paInt16 
        CHANNELS = 1           # 你的麥克風是單聲道
        RATE = 44100           # 你的麥克風預設採樣率
        # ====================================

        p = pyaudio.PyAudio()
        
        try:
            print(f"🎤 嘗試開啟裝置 ID: {MIC_INDEX} (Rate: {RATE})")
            
            # 開啟音訊串流
            self.audio_stream = p.open(format=FORMAT,
                                     channels=CHANNELS,
                                     rate=RATE,
                                     input=True,
                                     input_device_index=MIC_INDEX, # ★★★ 指定 ID 2
                                     frames_per_buffer=CHUNK)
            
            print(f"✅ 樹莓派錄音啟動成功！正在推流中...")
            
            while self.audio_running:
                try:
                    # 讀取數據 (exception_on_overflow=False 防止樹莓派忙碌時崩潰)
                    data = self.audio_stream.read(CHUNK, exception_on_overflow=False)
                    
                    # 轉碼
                    encoded_data = base64.b64encode(data).decode('utf-8')
                    
                    # 發送 (強制廣播給所有網頁)
                    self.socketio.emit('audio_stream', {
                        'data': encoded_data,
                        'rate': RATE,
                        'channels': CHANNELS
                    }, namespace='/', broadcast=True)
                    
                    # 極短暫睡眠釋放 CPU
                    self.socketio.sleep(0.001)
                    
                except Exception as inner_e:
                    print(f"⚠️ 錄音迴圈錯誤: {inner_e}")
                    continue
                    
        except Exception as e:
            print(f"❌ 無法開啟麥克風 (ID: {MIC_INDEX}): {e}")
            print("💡 請檢查 USB 麥克風是否鬆脫，或嘗試重新插拔")
        finally:
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except:
                    pass
            p.terminate()
            print("🛑 錄音執行緒已結束")
    def get_local_ip(self):
        """獲取本機的 IP 地址"""
        try:
            # 創建一個 UDP socket 來獲取本機 IP（不會實際發送數據）
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 連接到外部地址（這裡使用 Google DNS）
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            print(f"⚠️ 無法獲取本地 IP: {e}")
            # 如果失敗，返回 localhost
            return "localhost"

    def run(self, debug=None, host=None, port=None):
        """運行 Flask 應用"""
        host = host or self.config.FLASK_HOST
        port = port or self.config.FLASK_PORT
        debug = debug if debug is not None else self.config.FLASK_DEBUG

        # 獲取實際的本地 IP 地址用於顯示
        local_ip = self.get_local_ip()

        print(f"\n🌐 啟動網頁遠程控制服務...")
        print(f"   綁定地址: {host}:{port}")
        print(f"   本地網路 IP: {local_ip}")
        print(f"   控制URL: http://{local_ip}:{port}/remote_control?auth={self.config.CONTROL_PASSWORD}")
        print(f"   視訊URL: http://{local_ip}:{port}/video_feed?auth={self.config.CONTROL_PASSWORD}")

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