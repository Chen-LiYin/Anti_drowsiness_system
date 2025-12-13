#!/usr/bin/env python3
"""
事件記錄系統 - Phase 5
記錄瞌睡事件、射擊事件、喚醒數據等
"""

import json
import time
import os
import cv2
from datetime import datetime
from collections import deque
import threading

class EventRecorder:
    def __init__(self, config=None):
        """初始化事件記錄系統"""
        from config import Config
        self.config = config or Config()
        
        # 事件數據
        self.events = deque(maxlen=1000)  # 保留最近1000個事件
        self.current_session = None
        self.session_start_time = time.time()
        
        # 文件路徑
        self.event_log_path = self.config.EVENT_LOG_PATH
        
        # 統計數據
        self.stats = {
            'total_drowsy_events': 0,
            'total_shots_fired': 0,
            'total_wake_ups': 0,
            'avg_drowsy_duration': 0,
            'avg_wake_time': 0,
            'session_start': datetime.now().isoformat()
        }
        
        # 線程鎖
        self.lock = threading.Lock()

        # 不載入歷史數據，每次啟動都是全新開始
        # self.load_events()  # 註解掉，讓數據每次重置

        print("事件記錄系統已初始化")
        print(f"  - 事件記錄文件: {self.event_log_path}")
        print(f"  - 本次會話從零開始（數據不累積）")
    
    def create_event(self, event_type, data=None):
        """創建新事件"""
        with self.lock:
            event = {
                'id': int(time.time() * 1000),  # 使用時間戳作為ID
                'type': event_type,
                'timestamp': datetime.now().isoformat(),
                'session_id': id(self),  # 使用對象ID作為session ID
                'data': data or {}
            }
            
            self.events.append(event)
            self.save_events()
            
            return event
    
    def record_drowsiness_start(self, drowsiness_result, frame=None):
        """記錄瞌睡開始事件"""
        screenshot_path = None
        
        # 保存截圖（如果啟用）
        if frame is not None and self.config.AUTO_SCREENSHOT_ON_EVENT:
            screenshot_path = self.save_screenshot(frame, 'drowsy_start')
        
        event_data = {
            'ear': drowsiness_result.get('ear', 0),
            'eye_counter': drowsiness_result.get('eye_counter', 0),
            'state': drowsiness_result.get('state', 'drowsy'),
            'screenshot': screenshot_path
        }
        
        event = self.create_event('drowsiness_start', event_data)
        
        # 開始新的瞌睡會話
        self.current_session = {
            'start_time': time.time(),
            'start_event_id': event['id'],
            'drowsy_duration': 0,
            'shots_fired': 0,
            'wake_time': None,
            'total_duration': 0
        }
        
        self.stats['total_drowsy_events'] += 1
        
        print(f"📝 記錄瞌睡開始事件: {event['id']}")
        return event
    
    def record_drowsiness_end(self, frame=None):
        """記錄瞌睡結束/喚醒事件"""
        if not self.current_session:
            return None
        
        current_time = time.time()
        total_duration = current_time - self.current_session['start_time']
        
        screenshot_path = None
        if frame is not None and self.config.AUTO_SCREENSHOT_ON_EVENT:
            screenshot_path = self.save_screenshot(frame, 'wake_up')
        
        event_data = {
            'drowsy_duration': total_duration,
            'shots_fired': self.current_session['shots_fired'],
            'wake_time': total_duration,
            'session_id': self.current_session['start_event_id'],
            'screenshot': screenshot_path
        }
        
        event = self.create_event('drowsiness_end', event_data)
        
        # 更新統計
        self.stats['total_wake_ups'] += 1
        
        # 計算平均值
        if self.stats['total_drowsy_events'] > 0:
            self.stats['avg_drowsy_duration'] = (
                (self.stats['avg_drowsy_duration'] * (self.stats['total_drowsy_events'] - 1) + total_duration) /
                self.stats['total_drowsy_events']
            )
        
        if self.stats['total_wake_ups'] > 0:
            self.stats['avg_wake_time'] = (
                (self.stats['avg_wake_time'] * (self.stats['total_wake_ups'] - 1) + total_duration) /
                self.stats['total_wake_ups']
            )
        
        print(f"📝 記錄喚醒事件: {event['id']} (持續 {total_duration:.1f}秒)")
        
        # 結束當前會話
        self.current_session = None
        
        return event
    
    def record_shot_fired(self, shot_data=None):
        """記錄射擊事件"""
        event_data = {
            'remote_control': shot_data.get('remote', False) if shot_data else False,
            'controller_info': shot_data.get('controller', 'unknown') if shot_data else 'local',
            'fire_mode': shot_data.get('mode', 'single') if shot_data else 'single',
            'sound_effect': shot_data.get('sound', 'default') if shot_data else 'default'
        }
        
        # 如果在瞌睡會話中，增加射擊計數
        if self.current_session:
            self.current_session['shots_fired'] += 1
        
        self.stats['total_shots_fired'] += 1
        
        event = self.create_event('shot_fired', event_data)
        
        print(f"📝 記錄射擊事件: {event['id']}")
        return event
    
    def record_remote_control_start(self, controller_info=None):
        """記錄遠程控制開始"""
        event_data = {
            'controller_ip': controller_info.get('ip', 'unknown') if controller_info else 'unknown',
            'user_agent': controller_info.get('user_agent', '') if controller_info else '',
            'session_id': controller_info.get('session_id', '') if controller_info else ''
        }
        
        event = self.create_event('remote_control_start', event_data)
        print(f"📝 記錄遠程控制開始: {event['id']}")
        return event
    
    def record_remote_control_end(self, duration=0):
        """記錄遠程控制結束"""
        event_data = {
            'duration': duration
        }
        
        event = self.create_event('remote_control_end', event_data)
        print(f"📝 記錄遠程控制結束: {event['id']}")
        return event
    
    def save_screenshot(self, frame, event_type):
        """保存事件截圖"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{event_type}_{timestamp}.jpg"
            filepath = os.path.join(self.config.SCREENSHOT_DIR, filename)
            
            # 添加事件標記到圖片
            frame_with_text = frame.copy()
            cv2.putText(frame_with_text, f"Event: {event_type}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(frame_with_text, f"Time: {timestamp}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imwrite(filepath, frame_with_text)
            
            # 返回相對路徑
            return os.path.relpath(filepath)
            
        except Exception as e:
            print(f"截圖保存失敗: {e}")
            return None
    
    def save_events(self):
        """保存事件到文件"""
        try:
            data = {
                'events': list(self.events),
                'stats': self.stats,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.event_log_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"事件保存失敗: {e}")
    
    def load_events(self):
        """從文件載入事件"""
        try:
            if os.path.exists(self.event_log_path):
                with open(self.event_log_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 載入事件（只載入最近的）
                events = data.get('events', [])
                self.events.extend(events[-500:])  # 只載入最近500個事件
                
                # 載入統計（保留累積數據）
                saved_stats = data.get('stats', {})
                for key, value in saved_stats.items():
                    if key in self.stats and key.startswith(('total_', 'avg_')):
                        self.stats[key] = value
                
                print(f"已載入 {len(events)} 個歷史事件")
                
        except Exception as e:
            print(f"事件載入失敗: {e}")
    
    def get_statistics(self):
        """獲取統計數據"""
        with self.lock:
            current_time = time.time()
            session_duration = current_time - self.session_start_time
            
            stats = self.stats.copy()
            stats.update({
                'session_duration': session_duration,
                'session_duration_str': f"{session_duration//3600:.0f}h {(session_duration%3600)//60:.0f}m {session_duration%60:.0f}s",
                'events_in_session': len(self.events),
                'current_session_active': self.current_session is not None
            })
            
            return stats
    
    def get_recent_events(self, limit=50, event_type=None):
        """獲取最近的事件"""
        with self.lock:
            events = list(self.events)
            
            # 過濾事件類型
            if event_type:
                events = [e for e in events if e['type'] == event_type]
            
            # 返回最近的事件
            return events[-limit:] if limit else events
    
    def generate_session_report(self):
        """生成會話報告"""
        stats = self.get_statistics()
        recent_events = self.get_recent_events(20)
        
        report = {
            'session_summary': {
                'duration': stats['session_duration_str'],
                'total_drowsy_events': stats['total_drowsy_events'],
                'total_shots_fired': stats['total_shots_fired'],
                'total_wake_ups': stats['total_wake_ups'],
                'avg_drowsy_duration': f"{stats['avg_drowsy_duration']:.1f}s",
                'avg_wake_time': f"{stats['avg_wake_time']:.1f}s"
            },
            'recent_events': recent_events[-10:],  # 最近10個事件
            'recommendations': self.generate_recommendations(stats)
        }
        
        return report
    
    def generate_recommendations(self, stats):
        """基於統計數據生成建議"""
        recommendations = []
        
        if stats['total_drowsy_events'] > 5:
            recommendations.append("檢測到多次瞌睡事件，建議適當休息")
        
        if stats['avg_drowsy_duration'] > 10:
            recommendations.append("平均瞌睡時間較長，建議調整系統敏感度")
        
        if stats['total_shots_fired'] > stats['total_wake_ups'] * 3:
            recommendations.append("射擊效果可能不佳，建議調整射擊參數")
        
        if len(recommendations) == 0:
            recommendations.append("系統運行良好，繼續保持")
        
        return recommendations
    
    def export_data(self, filepath=None):
        """導出數據"""
        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"event_export_{timestamp}.json"
        
        try:
            export_data = {
                'export_info': {
                    'timestamp': datetime.now().isoformat(),
                    'version': '1.0',
                    'total_events': len(self.events)
                },
                'statistics': self.get_statistics(),
                'events': list(self.events),
                'session_report': self.generate_session_report()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            print(f"數據已導出到: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"數據導出失敗: {e}")
            return None


def main():
    """測試事件記錄系統"""
    print("="*50)
    print("事件記錄系統測試")
    print("="*50)
    
    from config import Config
    config = Config()
    
    # 初始化事件記錄器
    recorder = EventRecorder(config)
    
    # 測試事件記錄
    print("\n測試事件記錄...")
    
    # 模擬瞌睡事件
    drowsy_result = {
        'ear': 0.15,
        'eye_counter': 25,
        'state': 'severe_drowsy'
    }
    
    recorder.record_drowsiness_start(drowsy_result)
    
    # 模擬射擊事件
    time.sleep(1)
    recorder.record_shot_fired({'remote': True, 'mode': 'continuous'})
    
    # 模擬喚醒事件
    time.sleep(2)
    recorder.record_drowsiness_end()
    
    # 顯示統計
    stats = recorder.get_statistics()
    print(f"\n統計數據:")
    print(f"  瞌睡事件: {stats['total_drowsy_events']}")
    print(f"  射擊次數: {stats['total_shots_fired']}")
    print(f"  喚醒次數: {stats['total_wake_ups']}")
    
    # 生成報告
    report = recorder.generate_session_report()
    print(f"\n會話報告:")
    print(json.dumps(report['session_summary'], indent=2, ensure_ascii=False))
    
    print("\n✅ 事件記錄系統測試完成")


if __name__ == "__main__":
    main()