#!/usr/bin/env python3
"""
防瞌睡雲台系統啟動器
提供多種啟動模式選擇
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime

def print_banner():
    """顯示系統橫幅"""
    print("="*70)
    print("🎯 防瞌睡雲台系統啟動器")
    print("="*70)
    print("功能模組:")
    print("  ✅ 瞌睡偵測與警報")
    print("  ✅ 智能通知系統 (Telegram/LINE)")
    print("  ✅ 遠程網頁控制介面")
    print("  ✅ 事件記錄與監控")
    print("  ✅ 本地雙視窗控制")
    print("="*70)
    print(f"啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def run_system_test():
    """運行系統測試"""
    print("🧪 運行系統測試...")
    try:
        result = subprocess.run([sys.executable, "test_system.py"], 
                              cwd=os.path.dirname(__file__))
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 測試運行錯誤: {e}")
        return False

def run_integrated_system():
    """運行完整整合系統"""
    print("🚀 啟動完整整合系統...")
    try:
        subprocess.run([sys.executable, "modules/integrated_system.py"], 
                      cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\n⛔ 用戶中止系統")
    except Exception as e:
        print(f"❌ 系統運行錯誤: {e}")

def run_separated_system():
    """運行分離雙視窗系統"""
    print("🎮 啟動分離雙視窗系統...")
    try:
        subprocess.run([sys.executable, "modules/separated_dual_system.py"], 
                      cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\n⛔ 用戶中止系統")
    except Exception as e:
        print(f"❌ 系統運行錯誤: {e}")

def run_web_only():
    """只運行網頁控制系統"""
    print("🌐 啟動網頁控制系統...")
    try:
        subprocess.run([sys.executable, "modules/web_remote_control.py"], 
                      cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\n⛔ 用戶中止系統")
    except Exception as e:
        print(f"❌ 系統運行錯誤: {e}")

def run_notification_test():
    """測試通知系統"""
    print("📲 測試通知系統...")
    try:
        subprocess.run([sys.executable, "modules/notification_system.py"], 
                      cwd=os.path.dirname(__file__))
    except KeyboardInterrupt:
        print("\n⛔ 用戶中止測試")
    except Exception as e:
        print(f"❌ 通知測試錯誤: {e}")

def interactive_mode():
    """互動模式選擇"""
    while True:
        print("\n🎮 選擇啟動模式:")
        print("1. 🧪 系統測試 (檢查所有模組)")
        print("2. 🚀 完整整合系統 (推薦)")
        print("3. 🎯 分離雙視窗系統")
        print("4. 🌐 只啟動網頁控制")
        print("5. 📲 測試通知系統")
        print("6. 📋 顯示系統信息")
        print("0. ❌ 退出")
        
        try:
            choice = input("\n請輸入選項 (0-6): ").strip()
            
            if choice == "0":
                print("👋 再見!")
                break
            elif choice == "1":
                if not run_system_test():
                    print("\n⚠️  系統測試發現問題，建議先解決後再啟動完整系統")
                input("\n按 Enter 繼續...")
            elif choice == "2":
                run_integrated_system()
            elif choice == "3":
                run_separated_system()
            elif choice == "4":
                run_web_only()
            elif choice == "5":
                run_notification_test()
            elif choice == "6":
                show_system_info()
                input("\n按 Enter 繼續...")
            else:
                print("❌ 無效選項，請重新選擇")
                
        except KeyboardInterrupt:
            print("\n\n👋 再見!")
            break
        except Exception as e:
            print(f"❌ 錯誤: {e}")

def show_system_info():
    """顯示系統信息"""
    print("\n📋 系統信息:")
    print(f"  Python 版本: {sys.version}")
    print(f"  工作目錄: {os.getcwd()}")
    print(f"  系統路徑: {os.path.dirname(os.path.abspath(__file__))}")
    
    # 檢查重要文件
    important_files = [
        "config.py",
        "modules/integrated_system.py",
        "modules/separated_dual_system.py", 
        "modules/drowsiness_detector.py",
        "modules/notification_system.py",
        "modules/web_remote_control.py",
        "modules/event_recorder.py",
        "requirements.txt",
        "shape_predictor_68_face_landmarks.dat"
    ]
    
    print("\n📁 重要文件檢查:")
    for file_path in important_files:
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path}")
    
    # 檢查目錄
    important_dirs = ["modules", "templates", "static", "data"]
    
    print("\n📂 目錄檢查:")
    for dir_path in important_dirs:
        if os.path.exists(dir_path):
            print(f"  ✅ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/")

def main():
    """主程式"""
    parser = argparse.ArgumentParser(description="防瞌睡雲台系統啟動器")
    parser.add_argument("--mode", choices=["test", "integrated", "separated", "web", "notification"], 
                       help="直接指定啟動模式")
    parser.add_argument("--no-banner", action="store_true", help="不顯示橫幅")
    
    args = parser.parse_args()
    
    # 切換到腳本目錄
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if not args.no_banner:
        print_banner()
    
    # 直接模式
    if args.mode == "test":
        run_system_test()
    elif args.mode == "integrated":
        run_integrated_system()
    elif args.mode == "separated":
        run_separated_system()
    elif args.mode == "web":
        run_web_only()
    elif args.mode == "notification":
        run_notification_test()
    else:
        # 互動模式
        interactive_mode()

if __name__ == "__main__":
    main()