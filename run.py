"""
应用启动脚本
检查环境并启动Streamlit应用
支持同时启动内部系统和外部系统
"""
import os
import sys
import subprocess
import threading
import time
from pathlib import Path


def check_environment():
    """检查运行环境"""
    print("🔍 检查运行环境...")

    # 检查必需文件
    required_files = [
        "app.py",
        "external_app.py",  # 新增检查
        "config.py",
        "database/database.py",
        "fund_data.db"
    ]

    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)

    if missing_files:
        print("❌ 缺少必需文件:")
        for f in missing_files:
            print(f"   - {f}")

        if "fund_data.db" in missing_files:
            print("\n💡 提示: 请先运行 python init_with_sample_data.py 初始化数据库")

        return False

    # 检查Python包
    try:
        import streamlit
        import plotly
        import pandas
        print("✅ 依赖包检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("💡 请运行: pip install -r requirements.txt")
        return False

    return True


def start_internal_app():
    """启动内部管理系统"""
    print("🚀 启动内部管理系统...")

    try:
        env = os.environ.copy()
        env['STREAMLIT_SERVER_HEADLESS'] = 'true'
        env['STREAMLIT_SERVER_PORT'] = '8080'

        cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8080"]

        # 运行内部系统
        subprocess.run(cmd, env=env)

    except Exception as e:
        print(f"❌ 内部系统启动失败: {e}")


def start_external_app():
    """启动外部用户系统"""
    print("🌐 启动外部用户系统...")

    try:
        env = os.environ.copy()
        env['STREAMLIT_SERVER_HEADLESS'] = 'true'
        env['STREAMLIT_SERVER_PORT'] = '8800'

        cmd = [sys.executable, "-m", "streamlit", "run", "external_app.py", "--server.port", "8800"]

        # 运行外部系统
        subprocess.run(cmd, env=env)

    except Exception as e:
        print(f"❌ 外部系统启动失败: {e}")


def start_single_app(app_type):
    """启动单个应用"""
    if app_type == "internal":
        start_internal_app()
    elif app_type == "external":
        start_external_app()


def start_both_apps():
    """同时启动两个应用"""
    print("🚀 同时启动内部和外部系统...")

    # 创建两个线程分别启动应用
    internal_thread = threading.Thread(target=start_internal_app, daemon=True)
    external_thread = threading.Thread(target=start_external_app, daemon=True)

    # 启动线程
    internal_thread.start()
    time.sleep(2)  # 稍微延迟启动第二个应用
    external_thread.start()

    print("=" * 60)
    print("🎉 两个系统已启动！")
    print("📊 内部管理系统: http://localhost:8080")
    print("📱 外部用户系统: http://localhost:8800")
    print("⏹️  按 Ctrl+C 停止所有应用")
    print("=" * 60)

    try:
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 正在停止所有应用...")


def show_menu():
    """显示启动菜单"""
    print("\n📈 基金可视化系统启动器")
    print("=" * 50)
    print("请选择启动模式：")
    print("1️⃣  启动内部管理系统 (端口 8080)")
    print("2️⃣  启动外部用户系统 (端口 8800)")
    print("3️⃣  同时启动两个系统")
    print("0️⃣  退出")
    print("=" * 50)

    while True:
        choice = input("请输入选择 (0-3): ").strip()

        if choice == "1":
            return "internal"
        elif choice == "2":
            return "external"
        elif choice == "3":
            return "both"
        elif choice == "0":
            return "exit"
        else:
            print("❌ 无效选择，请输入 0-3")


def main():
    """主函数"""
    # 检查环境
    if not check_environment():
        print("\n⚠️  环境检查失败，请解决问题后重试")
        sys.exit(1)

    # 显示系统信息
    if os.path.exists("fund_data.db"):
        try:
            from database.database import DatabaseManager
            db = DatabaseManager()
            products = db.get_products()
            print(f"📊 数据库中有 {len(products)} 个产品")
        except Exception:
            print("📊 数据库连接正常")

    print("✅ 环境检查通过")

    # 显示菜单并获取选择
    choice = show_menu()

    if choice == "exit":
        print("👋 再见！")
        sys.exit(0)

    try:
        if choice == "internal":
            start_single_app("internal")
        elif choice == "external":
            start_single_app("external")
        elif choice == "both":
            start_both_apps()

    except KeyboardInterrupt:
        print("\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()