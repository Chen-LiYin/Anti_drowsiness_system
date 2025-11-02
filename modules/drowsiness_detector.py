"""
瞌睡偵測模組 - 基於 Driver-Drowsiness-Detection 專案改良
結合 EAR (Eye Aspect Ratio) 和 MAR (Mouth Aspect Ratio) 算法
"""

import cv2
import dlib
import numpy as np
from scipy.spatial import distance as dist
from imutils import face_utils
import time
from collections import deque
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DrowsinessDetector:
    """瞌睡偵測器類別 """
    
    # 面部特徵點索引（dlib 68點模型）
    FACIAL_LANDMARKS_IDXS = {
        "mouth": (48, 68),
        "right_eyebrow": (17, 22),
        "left_eyebrow": (22, 27),
        "right_eye": (36, 42),
        "left_eye": (42, 48),
        "nose": (27, 35),
        "jaw": (0, 17)
    }
    
    def __init__(self, config):
        """
        初始化瞌睡偵測器
        
        Args:
            config: 配置物件
        """
        self.config = config
        
        # 載入 dlib 偵測器和預測器
        try:
            self.detector = dlib.get_frontal_face_detector()
            self.predictor = dlib.shape_predictor(
                "shape_predictor_68_face_landmarks.dat"
            )
            logger.info("✅ dlib 模型載入成功")
        except Exception as e:
            logger.error(f"❌ dlib 模型載入失敗: {e}")
            logger.info("💡 請下載模型：wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
            raise
        
        # 眼睛和嘴巴特徵點索引
        (self.lStart, self.lEnd) = self.FACIAL_LANDMARKS_IDXS["left_eye"]
        (self.rStart, self.rEnd) = self.FACIAL_LANDMARKS_IDXS["right_eye"]
        (self.mStart, self.mEnd) = self.FACIAL_LANDMARKS_IDXS["mouth"]
        
        # 閾值設定
        self.EYE_AR_THRESH = getattr(config, 'EAR_THRESHOLD', 0.25)
        self.EYE_AR_CONSEC_FRAMES = getattr(config, 'EAR_CONSEC_FRAMES', 20)
        self.MOUTH_AR_THRESH = getattr(config, 'MAR_THRESHOLD', 0.75)
        self.YAWN_CONSEC_FRAMES = getattr(config, 'YAWN_CONSEC_FRAMES', 15)
        
        # 狀態計數器
        self.eye_counter = 0
        self.yawn_counter = 0
        self.total_drowsy = 0
        self.total_yawns = 0
        
        # 狀態追蹤
        self.drowsy_start_time = None
        self.yawn_start_time = None
        self.current_state = "Alert"  # Alert, Drowsy, Yawning
        
        # 歷史記錄（用於平滑）
        self.ear_history = deque(maxlen=10)
        self.mar_history = deque(maxlen=10)
        
        # 警報標記
        self.drowsy_alert_active = False
        self.yawn_alert_active = False
        
        # 統計數據
        self.stats = {
            'total_frames': 0,
            'drowsy_frames': 0,
            'yawn_frames': 0,
            'total_drowsy_events': 0,
            'total_yawn_events': 0,
            'alerts_sent': 0,
            'session_start': time.time(),
            'last_alert_time': 0
        }
    
    def calculate_eye_aspect_ratio(self, eye):
        """
        計算眼睛長寬比 (Eye Aspect Ratio)
        
        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        
        Args:
            eye: 眼睛的6個特徵點座標
            
        Returns:
            float: EAR 值
        """
        # 計算垂直距離
        A = dist.euclidean(eye[1], eye[5])
        B = dist.euclidean(eye[2], eye[4])
        
        # 計算水平距離
        C = dist.euclidean(eye[0], eye[3])
        
        # EAR 公式
        ear = (A + B) / (2.0 * C)
        return ear
    
    def calculate_mouth_aspect_ratio(self, mouth):
        """
        計算嘴巴長寬比 (Mouth Aspect Ratio)
        用於偵測打哈欠
        
        MAR = (||p2-p8|| + ||p3-p7|| + ||p4-p6||) / (2 * ||p1-p5||)
        
        Args:
            mouth: 嘴巴的特徵點座標
            
        Returns:
            float: MAR 值
        """
        # 垂直距離
        A = dist.euclidean(mouth[2], mouth[10])   # 51, 59
        B = dist.euclidean(mouth[4], mouth[8])    # 53, 57
        C = dist.euclidean(mouth[6], mouth[6])    # 55, 55 (中點)
        
        # 水平距離
        D = dist.euclidean(mouth[0], mouth[6])    # 49, 55
        
        # MAR 公式（簡化版）
        mar = (A + B) / (2.0 * D)
        return mar
    
    def calculate_head_pose(self, shape, frame_shape):
        """
        計算頭部姿態（可選功能）
        用於偵測頭部下垂
        
        Args:
            shape: 面部特徵點
            frame_shape: 影像尺寸
            
        Returns:
            tuple: (pitch, yaw, roll) 角度
        """
        # 2D 影像點
        image_points = np.array([
            shape[30],     # 鼻尖
            shape[8],      # 下巴
            shape[36],     # 左眼左角
            shape[45],     # 右眼右角
            shape[48],     # 左嘴角
            shape[54]      # 右嘴角
        ], dtype="double")
        
        # 3D 模型點
        model_points = np.array([
            (0.0, 0.0, 0.0),             # 鼻尖
            (0.0, -330.0, -65.0),        # 下巴
            (-225.0, 170.0, -135.0),     # 左眼左角
            (225.0, 170.0, -135.0),      # 右眼右角
            (-150.0, -150.0, -125.0),    # 左嘴角
            (150.0, -150.0, -125.0)      # 右嘴角
        ])
        
        # 相機參數
        focal_length = frame_shape[1]
        center = (frame_shape[1] / 2, frame_shape[0] / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype="double")
        
        dist_coeffs = np.zeros((4, 1))
        
        # 求解 PnP
        (success, rotation_vector, translation_vector) = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )
        
        # 轉換為歐拉角
        rotation_mat, _ = cv2.Rodrigues(rotation_vector)
        pose_mat = cv2.hconcat((rotation_mat, translation_vector))
        _, _, _, _, _, _, euler_angles = cv2.decomposeProjectionMatrix(pose_mat)
        
        pitch, yaw, roll = euler_angles.flatten()[:3]
        
        return pitch, yaw, roll
    
    def detect_face_landmarks(self, frame):
        """
        偵測面部特徵點
        
        Args:
            frame: OpenCV 影像幀
            
        Returns:
            tuple: (灰階影像, 臉部矩形, 特徵點)
        """
        # 轉換為灰階
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 偵測臉部
        faces = self.detector(gray, 0)
        
        if len(faces) == 0:
            return gray, None, None
        
        # 只處理第一張臉
        face = faces[0]
        
        # 獲取面部特徵點
        shape = self.predictor(gray, face)
        shape = face_utils.shape_to_np(shape)
        
        return gray, face, shape
    
    def analyze_drowsiness(self, ear, mar):
        """
        分析瞌睡和打哈欠狀態
        
        Args:
            ear: 眼睛長寬比
            mar: 嘴巴長寬比
            
        Returns:
            dict: 分析結果
        """
        self.stats['total_frames'] += 1
        
        # === 眼睛閉合偵測 ===
        if ear < self.EYE_AR_THRESH:
            self.eye_counter += 1
            self.stats['drowsy_frames'] += 1
            
            if self.drowsy_start_time is None:
                self.drowsy_start_time = time.time()
            
            # 判斷是否觸發瞌睡警報
            if self.eye_counter >= self.EYE_AR_CONSEC_FRAMES:
                if not self.drowsy_alert_active:
                    self.drowsy_alert_active = True
                    self.total_drowsy += 1
                    self.stats['total_drowsy_events'] += 1
                    logger.warning(f"⚠️  瞌睡警報！持續 {self.eye_counter} 幀")
        else:
            # 眼睛睜開，重置
            if self.eye_counter >= self.EYE_AR_CONSEC_FRAMES:
                logger.info(f"✅ 使用者清醒（之前瞌睡 {self.eye_counter} 幀）")
            
            self.eye_counter = 0
            self.drowsy_start_time = None
            self.drowsy_alert_active = False
        
        # === 打哈欠偵測 ===
        if mar > self.MOUTH_AR_THRESH:
            self.yawn_counter += 1
            self.stats['yawn_frames'] += 1
            
            if self.yawn_start_time is None:
                self.yawn_start_time = time.time()
            
            # 判斷是否觸發打哈欠警報
            if self.yawn_counter >= self.YAWN_CONSEC_FRAMES:
                if not self.yawn_alert_active:
                    self.yawn_alert_active = True
                    self.total_yawns += 1
                    self.stats['total_yawn_events'] += 1
                    logger.info(f"🥱 偵測到打哈欠！持續 {self.yawn_counter} 幀")
        else:
            # 嘴巴閉合，重置
            self.yawn_counter = 0
            self.yawn_start_time = None
            self.yawn_alert_active = False
        
        # === 判斷當前狀態 ===
        if self.drowsy_alert_active:
            self.current_state = "Drowsy"
            alert_level = 3
        elif self.yawn_alert_active:
            self.current_state = "Yawning"
            alert_level = 2
        elif self.eye_counter > 0 or self.yawn_counter > 0:
            self.current_state = "Tired"
            alert_level = 1
        else:
            self.current_state = "Alert"
            alert_level = 0
        
        # === 計算持續時間 ===
        drowsy_duration = 0
        if self.drowsy_start_time:
            drowsy_duration = time.time() - self.drowsy_start_time
        
        yawn_duration = 0
        if self.yawn_start_time:
            yawn_duration = time.time() - self.yawn_start_time
        
        # === 構建結果 ===
        result = {
            'state': self.current_state,
            'alert_level': alert_level,
            'ear': ear,
            'mar': mar,
            'eye_counter': self.eye_counter,
            'yawn_counter': self.yawn_counter,
            'drowsy_duration': drowsy_duration,
            'yawn_duration': yawn_duration,
            'total_drowsy': self.total_drowsy,
            'total_yawns': self.total_yawns,
            'should_alert': alert_level >= 3,
            'should_warn': alert_level >= 2,
            'timestamp': time.time()
        }
        
        return result
    
    def process_frame(self, frame):
        """
        處理單一影像幀
        
        Args:
            frame: OpenCV 影像幀
            
        Returns:
            tuple: (處理後的影像, 分析結果)
        """
        # 偵測面部特徵點
        gray, face, shape = self.detect_face_landmarks(frame)
        
        if face is None or shape is None:
            # 未找到臉部
            result = {
                'state': 'No Face',
                'alert_level': 0,
                'ear': 0,
                'mar': 0,
                'eye_counter': 0,
                'yawn_counter': 0,
                'drowsy_duration': 0,
                'yawn_duration': 0,
                'total_drowsy': self.total_drowsy,
                'total_yawns': self.total_yawns,
                'should_alert': False,
                'should_warn': False,
                'timestamp': time.time()
            }
            
            # 顯示警告
            cv2.putText(frame, "No Face Detected!", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            return frame, result
        
        # === 提取特徵點 ===
        leftEye = shape[self.lStart:self.lEnd]
        rightEye = shape[self.rStart:self.rEnd]
        mouth = shape[self.mStart:self.mEnd]
        
        # === 計算 EAR 和 MAR ===
        leftEAR = self.calculate_eye_aspect_ratio(leftEye)
        rightEAR = self.calculate_eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0
        
        mar = self.calculate_mouth_aspect_ratio(mouth)
        
        # 平滑處理
        self.ear_history.append(ear)
        self.mar_history.append(mar)
        smoothed_ear = np.mean(self.ear_history)
        smoothed_mar = np.mean(self.mar_history)
        
        # === 分析瞌睡狀態 ===
        result = self.analyze_drowsiness(smoothed_ear, smoothed_mar)
        
        # === 繪製視覺化 ===
        frame = self.draw_visualization(
            frame, leftEye, rightEye, mouth, face, result
        )
        
        return frame, result
    
    def draw_visualization(self, frame, leftEye, rightEye, mouth, face, result):
        """
        在影像上繪製視覺化資訊
        
        Args:
            frame: 影像幀
            leftEye: 左眼特徵點
            rightEye: 右眼特徵點
            mouth: 嘴巴特徵點
            face: 臉部矩形
            result: 分析結果
            
        Returns:
            處理後的影像
        """
        # === 繪製輪廓 ===
        leftEyeHull = cv2.convexHull(leftEye)
        rightEyeHull = cv2.convexHull(rightEye)
        mouthHull = cv2.convexHull(mouth)
        
        # 根據狀態選擇顏色
        state_colors = {
            'Alert': (0, 255, 0),      # 綠色
            'Tired': (0, 255, 255),    # 黃色
            'Yawning': (255, 165, 0),  # 橙色
            'Drowsy': (0, 0, 255)      # 紅色
        }
        color = state_colors.get(result['state'], (255, 255, 255))
        
        # 繪製眼睛輪廓
        cv2.drawContours(frame, [leftEyeHull], -1, color, 1)
        cv2.drawContours(frame, [rightEyeHull], -1, color, 1)
        
        # 繪製嘴巴輪廓
        mouth_color = (0, 0, 255) if result['yawn_counter'] > 0 else (0, 255, 0)
        cv2.drawContours(frame, [mouthHull], -1, mouth_color, 1)
        
        # === 繪製臉部矩形 ===
        x, y, w, h = face.left(), face.top(), face.width(), face.height()
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        
        # === 顯示資訊面板 ===
        # EAR 值
        cv2.putText(frame, f"EAR: {result['ear']:.3f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # MAR 值
        cv2.putText(frame, f"MAR: {result['mar']:.3f}", (10, 55),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, mouth_color, 2)
        
        # 狀態
        cv2.putText(frame, f"State: {result['state']}", (10, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # 眼睛計數器
        if result['eye_counter'] > 0:
            cv2.putText(frame, f"Eye Closed: {result['eye_counter']} frames", 
                       (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        # 打哈欠計數器
        if result['yawn_counter'] > 0:
            cv2.putText(frame, f"Yawning: {result['yawn_counter']} frames", 
                       (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
        
        # === 統計資訊 ===
        cv2.putText(frame, f"Drowsy Events: {result['total_drowsy']}", 
                   (10, frame.shape[0] - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        cv2.putText(frame, f"Yawn Events: {result['total_yawns']}", 
                   (10, frame.shape[0] - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # === 警報顯示 ===
        if result['should_alert']:
            # 瞌睡警報 - 紅色大字閃爍
            if int(time.time() * 2) % 2 == 0:  # 閃爍效果
                cv2.putText(frame, "!!! DROWSY ALERT !!!", 
                           (frame.shape[1]//2 - 200, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
                
                # 畫紅色邊框
                cv2.rectangle(frame, (0, 0), 
                             (frame.shape[1], frame.shape[0]), 
                             (0, 0, 255), 10)
        
        elif result['should_warn']:
            # 打哈欠警告 - 橙色
            cv2.putText(frame, "Yawning Detected", 
                       (frame.shape[1]//2 - 150, 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)
        
        # 時間戳
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def get_statistics(self):
        """
        獲取統計數據
        
        Returns:
            dict: 統計資訊
        """
        runtime = time.time() - self.stats['session_start']
        
        return {
            'runtime': runtime,
            'runtime_str': time.strftime('%H:%M:%S', time.gmtime(runtime)),
            'total_frames': self.stats['total_frames'],
            'drowsy_frames': self.stats['drowsy_frames'],
            'yawn_frames': self.stats['yawn_frames'],
            'drowsy_percentage': (self.stats['drowsy_frames'] / 
                                 max(self.stats['total_frames'], 1)) * 100,
            'yawn_percentage': (self.stats['yawn_frames'] / 
                               max(self.stats['total_frames'], 1)) * 100,
            'total_drowsy_events': self.stats['total_drowsy_events'],
            'total_yawn_events': self.stats['total_yawn_events'],
            'alerts_sent': self.stats['alerts_sent'],
            'current_state': self.current_state
        }
    
    def reset_statistics(self):
        """重置統計數據"""
        self.stats = {
            'total_frames': 0,
            'drowsy_frames': 0,
            'yawn_frames': 0,
            'total_drowsy_events': 0,
            'total_yawn_events': 0,
            'alerts_sent': 0,
            'session_start': time.time(),
            'last_alert_time': 0
        }
        self.total_drowsy = 0
        self.total_yawns = 0
        logger.info("📊 統計數據已重置")


def main():
    """測試主程式"""
    from config import Config
    
    print("="*60)
    print("🎥 瞌睡偵測系統測試")
    print("="*60)
    print("功能：")
    print("  ✓ 眼睛閉合偵測 (EAR)")
    print("  ✓ 打哈欠偵測 (MAR)")
    print("  ✓ 多級警報系統")
    print("  ✓ 即時統計數據")
    print("="*60)
    print()
    
    # 初始化
    config = Config()
    detector = DrowsinessDetector(config)
    
    # 開啟攝像頭
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    
    if not cap.isOpened():
        print("❌ 無法開啟攝像頭")
        return
    
    print("✅ 系統啟動成功！")
    print("📹 按 'q' 退出 | 按 's' 顯示統計 | 按 'r' 重置統計\n")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("❌ 無法讀取影像")
                break
            
            # 處理影像幀
            processed_frame, result = detector.process_frame(frame)
            
            # 顯示結果
            cv2.imshow('Drowsiness Detection System', processed_frame)
            
            # 按鍵處理
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('s'):
                # 顯示統計
                stats = detector.get_statistics()
                print("\n" + "="*60)
                print("📊 即時統計")
                print("="*60)
                print(f"運行時間: {stats['runtime_str']}")
                print(f"總幀數: {stats['total_frames']:,}")
                print(f"瞌睡幀數: {stats['drowsy_frames']:,} ({stats['drowsy_percentage']:.1f}%)")
                print(f"打哈欠幀數: {stats['yawn_frames']:,} ({stats['yawn_percentage']:.1f}%)")
                print(f"瞌睡事件: {stats['total_drowsy_events']} 次")
                print(f"打哈欠事件: {stats['total_yawn_events']} 次")
                print(f"當前狀態: {stats['current_state']}")
                print("="*60 + "\n")
            elif key == ord('r'):
                # 重置統計
                detector.reset_statistics()
                print("✅ 統計數據已重置\n")
                
    except KeyboardInterrupt:
        print("\n⚠️  使用者中斷")
    finally:
        # 最終統計
        stats = detector.get_statistics()
        print("\n" + "="*60)
        print("📊 最終統計報告")
        print("="*60)
        print(f"運行時間: {stats['runtime_str']}")
        print(f"總幀數: {stats['total_frames']:,}")
        print(f"瞌睡幀數: {stats['drowsy_frames']:,} ({stats['drowsy_percentage']:.1f}%)")
        print(f"打哈欠幀數: {stats['yawn_frames']:,} ({stats['yawn_percentage']:.1f}%)")
        print(f"瞌睡事件: {stats['total_drowsy_events']} 次")
        print(f"打哈欠事件: {stats['total_yawn_events']} 次")
        print("="*60)
        
        # 清理資源
        cap.release()
        cv2.destroyAllWindows()
        print("✅ 系統已關閉")


if __name__ == "__main__":
    main()