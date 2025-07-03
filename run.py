"""
应用启动脚本
检查环境并启动Streamlit应用
"""
import os
import sys
import subprocess
from pathlib import Path


def check_environment():
    """检查运行环境"""
    print("🔍 检查运行环境...")

    # 检查必需文件
    required_files = [
        "app.py",
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


def start_streamlit():
    """启动Streamlit应用"""
    print("🚀 启动Streamlit应用...")

    try:
        # 设置Streamlit配置
        env = os.environ.copy()
        env['STREAMLIT_SERVER_HEADLESS'] = 'true'
        env['STREAMLIT_SERVER_PORT'] = '8502'

        # 启动命令
        cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]

        print("=" * 50)
        print("🌐 应用正在启动...")
        print("📱 浏览器将自动打开 http://localhost:8502")
        print("⏹️  按 Ctrl+C 停止应用")
        print("=" * 50)

        # 运行应用
        subprocess.run(cmd, env=env)

    except KeyboardInterrupt:
        print("\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

    return True


def main():
    """主函数"""
    print("📈 基金可视化系统启动器")
    print("=" * 50)

    # 检查环境
    if not check_environment():
        print("\n⚠️  环境检查失败，请解决问题后重试")
        sys.exit(1)

    # 显示系统信息
    if os.path.exists("fund_data.db"):
        from database.database import DatabaseManager
        db = DatabaseManager()
        products = db.get_products()
        print(f"📊 数据库中有 {len(products)} 个产品")

    print("✅ 环境检查通过")

    # 启动应用
    success = start_streamlit()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()