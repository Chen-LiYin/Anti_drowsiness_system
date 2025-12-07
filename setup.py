#!/usr/bin/env python3
"""
防瞌睡雲台系統安裝腳本
自動處理依賴安裝和初始配置
"""

import os
import sys
import subprocess
import urllib.request
import shutil
from pathlib import Path

class SystemSetup:
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.errors = []
        self.warnings = []
        
    def print_step(self, message):
        """打印安裝步驟"""
        print(f"🔧 {message}")
    
    def print_success(self, message):
        """打印成功信息"""
        print(f"✅ {message}")
    
    def print_error(self, message):
        """打印錯誤信息"""
        print(f"❌ {message}")
        self.errors.append(message)
    
    def print_warning(self, message):
        """打印警告信息"""
        print(f"⚠️  {message}")
        self.warnings.append(message)
    
    def run_command(self, command, description):
        """運行命令"""
        self.print_step(description)
        try:
            result = subprocess.run(command, shell=True, check=True, 
                                  capture_output=True, text=True)
            self.print_success(f"{description} - 完成")
            return True
        except subprocess.CalledProcessError as e:
            self.print_error(f"{description} - 失敗: {e.stderr.strip()}")
            return False
    
    def check_python_version(self):
        """檢查 Python 版本"""
        self.print_step("檢查 Python 版本...")
        
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            self.print_success(f"Python 版本正常: {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            self.print_error(f"Python 版本過低: {version.major}.{version.minor}.{version.micro} (需要 3.8+)")
            return False
    
    def install_pip_requirements(self):
        """安裝 pip 依賴"""
        self.print_step("安裝 Python 依賴...")
        
        requirements_file = self.script_dir / "requirements.txt"
        
        if not requirements_file.exists():
            self.print_error("requirements.txt 文件不存在")
            return False
        
        # 升級 pip
        self.run_command(f"{sys.executable} -m pip install --upgrade pip", "升級 pip")
        
        # 安裝依賴
        return self.run_command(f"{sys.executable} -m pip install -r {requirements_file}", 
                               "安裝 Python 依賴")
    
    def download_dlib_model(self):
        """下載 dlib 面部特徵模型"""
        model_file = self.script_dir / "shape_predictor_68_face_landmarks.dat"
        
        if model_file.exists():
            self.print_success("dlib 面部特徵模型已存在")
            return True
        
        self.print_step("下載 dlib 面部特徵模型...")
        
        model_url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
        compressed_file = self.script_dir / "shape_predictor_68_face_landmarks.dat.bz2"
        
        try:
            # 下載壓縮文件
            urllib.request.urlretrieve(model_url, compressed_file)
            self.print_success("模型文件下載完成")
            
            # 解壓縮
            import bz2
            with bz2.BZ2File(compressed_file, 'rb') as source:
                with open(model_file, 'wb') as target:
                    shutil.copyfileobj(source, target)
            
            # 刪除壓縮文件
            compressed_file.unlink()
            
            self.print_success("dlib 模型解壓完成")
            return True
            
        except Exception as e:
            self.print_error(f"下載 dlib 模型失敗: {e}")
            self.print_warning("請手動下載模型文件:")
            self.print_warning("wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
            self.print_warning("bunzip2 shape_predictor_68_face_landmarks.dat.bz2")
            return False
    
    def setup_directories(self):
        """設置目錄結構"""
        self.print_step("創建目錄結構...")
        
        try:
            from config import Config
            Config.init_directories()
            self.print_success("目錄結構創建完成")
            return True
        except Exception as e:
            self.print_error(f"創建目錄失敗: {e}")
            return False
    
    def check_hardware_access(self):
        """檢查硬體訪問權限"""
        self.print_step("檢查硬體訪問權限...")
        
        # 檢查攝像頭
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                self.print_success("攝像頭訪問正常")
                cap.release()
            else:
                self.print_warning("攝像頭訪問失敗，請檢查攝像頭連接")
        except Exception as e:
            self.print_warning(f"攝像頭測試錯誤: {e}")
        
        # 檢查 I2C (樹莓派)
        i2c_device = Path("/dev/i2c-1")
        if i2c_device.exists():
            self.print_success("I2C 設備可訪問")
        else:
            self.print_warning("I2C 設備不可訪問，舵機控制可能無法使用")
            self.print_warning("請啟用 I2C: sudo raspi-config > Interface Options > I2C")
        
        return True
    
    def create_config_template(self):
        """創建配置模板"""
        self.print_step("檢查配置文件...")
        
        config_file = self.script_dir / "config.py"
        
        if not config_file.exists():
            self.print_error("config.py 文件不存在")
            return False
        
        # 檢查是否需要配置通知
        try:
            from config import Config
            config = Config()
            
            if not config.TELEGRAM_BOT_TOKEN and not config.LINE_CHANNEL_ACCESS_TOKEN:
                self.print_warning("通知系統未配置")
                self.print_warning("請在 config.py 中設置 Telegram 或 LINE API 配置")
        except Exception as e:
            self.print_error(f"配置檢查錯誤: {e}")
            return False
        
        self.print_success("配置文件檢查完成")
        return True
    
    def run_test_suite(self):
        """運行測試套件"""
        self.print_step("運行系統測試...")
        
        test_script = self.script_dir / "test_system.py"
        
        if not test_script.exists():
            self.print_error("test_system.py 文件不存在")
            return False
        
        try:
            result = subprocess.run([sys.executable, str(test_script)], 
                                  capture_output=True, text=True, cwd=self.script_dir)
            
            if result.returncode == 0:
                self.print_success("系統測試完成")
                return True
            else:
                self.print_warning("系統測試發現問題，請檢查輸出")
                print(result.stdout)
                return False
                
        except Exception as e:
            self.print_error(f"運行系統測試失敗: {e}")
            return False
    
    def setup_system(self):
        """執行完整安裝流程"""
        print("="*70)
        print("🚀 防瞌睡雲台系統安裝程式")
        print("="*70)
        print()
        
        steps = [
            ("檢查 Python 版本", self.check_python_version),
            ("安裝 Python 依賴", self.install_pip_requirements),
            ("下載 dlib 模型", self.download_dlib_model),
            ("設置目錄結構", self.setup_directories),
            ("檢查硬體訪問", self.check_hardware_access),
            ("檢查配置文件", self.create_config_template)
        ]
        
        success_count = 0
        total_steps = len(steps)
        
        for step_name, step_func in steps:
            print(f"\n📋 步驟: {step_name}")
            print("-" * 50)
            
            if step_func():
                success_count += 1
            
            print()
        
        # 顯示安裝結果
        print("="*70)
        print("📊 安裝結果")
        print("="*70)
        print(f"完成步驟: {success_count}/{total_steps}")
        
        if self.errors:
            print(f"\n❌ 錯誤 ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️  警告 ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print(f"\n{'✅ 安裝完成!' if success_count == total_steps else '⚠️  安裝部分完成'}")
        
        if success_count == total_steps:
            print("\n🎯 現在您可以運行:")
            print("   python start_system.py")
        else:
            print("\n🔧 請解決上述問題後重新運行安裝程式")
        
        print("="*70)
        
        return success_count == total_steps

def main():
    """主程式"""
    setup = SystemSetup()
    
    try:
        success = setup.setup_system()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⛔ 用戶中止安裝")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 安裝過程發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()