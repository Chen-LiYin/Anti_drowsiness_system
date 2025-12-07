#!/usr/bin/env python3
"""
整合防瞌睡雲台系統 - 系統測試腳本
用於驗證各個模塊的功能是否正常
"""

import sys
import os
import time
import traceback
import importlib
from datetime import datetime

# 添加模塊路徑
sys.path.append(os.path.dirname(__file__))

class SystemTester:
    def __init__(self):
        """初始化測試器"""
        self.test_results = {}
        self.start_time = time.time()
        
        print("="*70)
        print("🧪 整合防瞌睡雲台系統 - 系統測試")
        print("="*70)
        print(f"開始時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    def test_module_import(self, module_name, description):
        """測試模塊導入"""
        print(f"📦 測試 {description}...")
        
        try:
            importlib.import_module(module_name)
            print(f"✅ {description} - 導入成功")
            return True
        except ImportError as e:
            print(f"❌ {description} - 導入失敗: {e}")
            return False
        except Exception as e:
            print(f"❌ {description} - 錯誤: {e}")
            return False
    
    def test_dependencies(self):
        """測試基礎依賴"""
        print("🔍 測試基礎依賴...")
        
        dependencies = [
            ('cv2', 'OpenCV'),
            ('numpy', 'NumPy'),
            ('pygame', 'Pygame'),
            ('flask', 'Flask'),
            ('flask_socketio', 'Flask-SocketIO'),
            ('requests', 'Requests'),
            ('json', 'JSON'),
            ('threading', 'Threading')
        ]
        
        passed = 0
        total = len(dependencies)
        
        for module, name in dependencies:
            if self.test_module_import(module, name):
                passed += 1
        
        self.test_results['dependencies'] = f"{passed}/{total}"
        print(f"📊 基礎依賴測試結果: {passed}/{total}")
        print()
        
        return passed == total
    
    def test_custom_modules(self):
        """測試自定義模塊"""
        print("🔧 測試自定義模塊...")
        
        modules = [
            ('config', '配置模塊'),
            ('modules.drowsiness_detector', '瞌睡偵測器'),
            ('modules.notification_system', '通知系統'),
            ('modules.event_recorder', '事件記錄器'),
            ('modules.web_remote_control', '網頁遠程控制'),
            ('modules.integrated_system', '整合系統')
        ]
        
        passed = 0
        total = len(modules)
        
        for module, name in modules:
            if self.test_module_import(module, name):
                passed += 1
        
        self.test_results['custom_modules'] = f"{passed}/{total}"
        print(f"📊 自定義模塊測試結果: {passed}/{total}")
        print()
        
        return passed == total
    
    def test_camera_access(self):
        """測試攝像頭訪問"""
        print("📷 測試攝像頭訪問...")
        
        try:
            import cv2
            
            # 嘗試打開攝像頭
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                print("❌ 攝像頭 - 無法打開 (索引 0)")
                
                # 嘗試其他索引
                for i in range(1, 4):
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        print(f"✅ 攝像頭 - 找到可用攝像頭 (索引 {i})")
                        cap.release()
                        self.test_results['camera'] = f"可用 (索引 {i})"
                        return True
                
                print("❌ 攝像頭 - 未找到可用攝像頭")
                self.test_results['camera'] = "不可用"
                return False
            
            # 測試讀取幀
            ret, frame = cap.read()
            
            if ret and frame is not None:
                h, w, c = frame.shape
                print(f"✅ 攝像頭 - 成功讀取幀 ({w}x{h})")
                self.test_results['camera'] = f"可用 ({w}x{h})"
                success = True
            else:
                print("❌ 攝像頭 - 無法讀取幀")
                self.test_results['camera'] = "讀取失敗"
                success = False
            
            cap.release()
            return success
            
        except Exception as e:
            print(f"❌ 攝像頭測試錯誤: {e}")
            self.test_results['camera'] = f"錯誤: {str(e)}"
            return False
    
    def test_dlib_model(self):
        """測試 dlib 面部特徵模型"""
        print("🎭 測試 dlib 面部特徵模型...")
        
        try:
            import dlib
            
            model_path = "shape_predictor_68_face_landmarks.dat"
            
            if not os.path.exists(model_path):
                print(f"❌ dlib 模型 - 文件不存在: {model_path}")
                print("請下載模型文件:")
                print("wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
                print("bunzip2 shape_predictor_68_face_landmarks.dat.bz2")
                self.test_results['dlib_model'] = "文件不存在"
                return False
            
            # 嘗試載入模型
            predictor = dlib.shape_predictor(model_path)
            print("✅ dlib 模型 - 載入成功")
            self.test_results['dlib_model'] = "可用"
            return True
            
        except ImportError:
            print("❌ dlib - 模塊未安裝")
            self.test_results['dlib_model'] = "dlib 未安裝"
            return False
        except Exception as e:
            print(f"❌ dlib 模型測試錯誤: {e}")
            self.test_results['dlib_model'] = f"錯誤: {str(e)}"
            return False
    
    def test_servo_hardware(self):
        """測試舵機硬體"""
        print("🎯 測試舵機硬體...")
        
        try:
            from adafruit_servokit import ServoKit
            
            # 嘗試初始化 PCA9685
            kit = ServoKit(channels=16)
            
            print("✅ 舵機硬體 - PCA9685 初始化成功")
            
            # 測試舵機設置 (不移動)
            kit.servo[1].set_pulse_width_range(500, 2500)
            kit.servo[2].set_pulse_width_range(500, 2500)
            
            print("✅ 舵機硬體 - 舵機配置成功")
            self.test_results['servo_hardware'] = "可用"
            return True
            
        except ImportError:
            print("❌ 舵機硬體 - adafruit-servokit 未安裝")
            self.test_results['servo_hardware'] = "依賴未安裝"
            return False
        except Exception as e:
            print(f"❌ 舵機硬體 - 無法訪問 PCA9685: {e}")
            print("可能原因:")
            print("  1. PCA9685 未連接")
            print("  2. I2C 未啟用") 
            print("  3. 權限不足")
            self.test_results['servo_hardware'] = f"硬體錯誤: {str(e)[:50]}"
            return False
    
    def test_notification_config(self):
        """測試通知配置"""
        print("📲 測試通知配置...")
        
        try:
            from config import Config
            config = Config()
            
            telegram_configured = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
            
            if telegram_configured:
                print("✅ Telegram 配置 - 已設置")
            else:
                print("⚠️  Telegram 配置 - 未完整設置")
            
            if telegram_configured :
                self.test_results['notification_config'] = "已配置"
                return True
            else:
                print("❌ 通知配置 - 未配置任何通知服務")
                self.test_results['notification_config'] = "未配置"
                return False
                
        except Exception as e:
            print(f"❌ 通知配置測試錯誤: {e}")
            self.test_results['notification_config'] = f"錯誤: {str(e)}"
            return False
    
    def test_file_system(self):
        """測試文件系統權限"""
        print("📁 測試文件系統權限...")
        
        try:
            from config import Config
            config = Config()
            
            # 測試目錄創建
            Config.init_directories()
            
            test_dirs = [
                'data',
                'static',
                'static/sounds',
                'static/css',
                'static/js'
            ]
            
            all_dirs_ok = True
            
            for dir_path in test_dirs:
                if os.path.exists(dir_path):
                    print(f"✅ 目錄 - {dir_path} 存在")
                else:
                    print(f"❌ 目錄 - {dir_path} 不存在")
                    all_dirs_ok = False
            
            # 測試文件寫入
            test_file = "data/test_write.txt"
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                print("✅ 文件寫入 - 成功")
            except Exception as e:
                print(f"❌ 文件寫入 - 失敗: {e}")
                all_dirs_ok = False
            
            if all_dirs_ok:
                self.test_results['file_system'] = "正常"
                return True
            else:
                self.test_results['file_system'] = "錯誤"
                return False
                
        except Exception as e:
            print(f"❌ 文件系統測試錯誤: {e}")
            self.test_results['file_system'] = f"錯誤: {str(e)}"
            return False
    
    def test_network_access(self):
        """測試網絡訪問"""
        print("🌐 測試網絡訪問...")
        
        try:
            import requests
            
            # 測試基本網絡連接
            response = requests.get('https://httpbin.org/ip', timeout=10)
            
            if response.status_code == 200:
                print("✅ 網絡訪問 - 基本連接正常")
                
                # 測試 Telegram API 連接
                try:
                    tg_response = requests.get('https://api.telegram.org/', timeout=5)
                    if tg_response.status_code == 200:
                        print("✅ Telegram API - 可訪問")
                except:
                    print("⚠️  Telegram API - 連接超時")
                
                self.test_results['network'] = "正常"
                return True
            else:
                print(f"❌ 網絡訪問 - HTTP 狀態碼: {response.status_code}")
                self.test_results['network'] = f"HTTP {response.status_code}"
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ 網絡訪問 - 無法連接到互聯網")
            self.test_results['network'] = "無連接"
            return False
        except Exception as e:
            print(f"❌ 網絡訪問測試錯誤: {e}")
            self.test_results['network'] = f"錯誤: {str(e)}"
            return False
    
    def run_functionality_test(self):
        """運行功能測試"""
        print("⚙️  運行功能測試...")
        
        try:
            # 測試事件記錄器
            print("📝 測試事件記錄器...")
            from modules.event_recorder import EventRecorder
            from config import Config
            
            recorder = EventRecorder(Config())
            test_event = recorder.create_event('test_event', {'test': True})
            
            if test_event:
                print("✅ 事件記錄器 - 功能正常")
                self.test_results['event_recorder'] = "正常"
            else:
                print("❌ 事件記錄器 - 創建事件失敗")
                self.test_results['event_recorder'] = "失敗"
                
        except Exception as e:
            print(f"❌ 功能測試錯誤: {e}")
            self.test_results['functionality'] = f"錯誤: {str(e)}"
            return False
        
        return True
    
    def generate_report(self):
        """生成測試報告"""
        duration = time.time() - self.start_time
        
        print()
        print("="*70)
        print("📋 測試報告")
        print("="*70)
        print(f"測試時間: {duration:.2f} 秒")
        print()
        
        print("📊 測試結果概覽:")
        for category, result in self.test_results.items():
            status = "✅" if "錯誤" not in result and "失敗" not in result and result != "不可用" else "❌"
            print(f"  {status} {category}: {result}")
        
        print()
        print("🔧 問題修復建議:")
        
        if 'camera' in self.test_results and "不可用" in self.test_results['camera']:
            print("  📷 攝像頭問題:")
            print("    - 檢查攝像頭連接")
            print("    - 確認攝像頭驅動程式")
            print("    - 檢查權限設置")
        
        if 'dlib_model' in self.test_results and "不存在" in self.test_results['dlib_model']:
            print("  🎭 dlib 模型問題:")
            print("    - 下載模型: wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
            print("    - 解壓: bunzip2 shape_predictor_68_face_landmarks.dat.bz2")
        
        if 'servo_hardware' in self.test_results and "錯誤" in self.test_results['servo_hardware']:
            print("  🎯 舵機硬體問題:")
            print("    - 檢查 PCA9685 連接")
            print("    - 啟用 I2C: sudo raspi-config > Interfacing Options > I2C")
            print("    - 檢查 I2C 設備: sudo i2cdetect -y 1")
        
        if 'notification_config' in self.test_results and "未配置" in self.test_results['notification_config']:
            print("  📲 通知配置問題:")
            print("    - 設置 Telegram Bot Token 和 Chat ID")
            print("    - 或設置 LINE Channel Access Token 和 User ID")
        
        print()
        print("✨ 如果所有測試都通過，您可以運行:")
        print("   python modules/integrated_system.py")
        print()
        print("="*70)
    
    def run_all_tests(self):
        """運行所有測試"""
        tests = [
            ('基礎依賴', self.test_dependencies),
            ('自定義模塊', self.test_custom_modules),
            ('攝像頭訪問', self.test_camera_access),
            ('dlib 模型', self.test_dlib_model),
            ('舵機硬體', self.test_servo_hardware),
            ('通知配置', self.test_notification_config),
            ('文件系統', self.test_file_system),
            ('網絡訪問', self.test_network_access),
            ('功能測試', self.run_functionality_test)
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"❌ {test_name} - 未預期錯誤: {e}")
                traceback.print_exc()
            
            print()  # 空行分隔
        
        self.generate_report()


def main():
    """主程式"""
    print("🧪 開始系統測試...")
    print()
    
    tester = SystemTester()
    tester.run_all_tests()
    
    print("🏁 系統測試完成")


if __name__ == "__main__":
    main()