"""
使用示例数据初始化系统
"""
import pandas as pd
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from database.database import DatabaseManager
from config import COLUMN_MAPPING


def process_nav_data(file_path):
    """处理净值数据"""
    df = pd.read_csv(file_path, encoding='utf-8-sig')

    # 标准化列名
    column_map = {}
    for col in df.columns:
        if col in ['日期', 'Date', 'date']:
            column_map[col] = 'date'
        elif col in ['单位净值', '净值', 'NAV', 'nav_value']:
            column_map[col] = 'nav_value'
        elif col in ['累计净值', '累积净值', 'Cumulative NAV', 'cumulative_nav']:
            column_map[col] = 'cumulative_nav'

    df = df.rename(columns=column_map)

    # 确保必需列存在
    if 'date' not in df.columns or 'nav_value' not in df.columns:
        raise ValueError("净值数据缺少必需列: 日期、单位净值")

    return df[['date', 'nav_value', 'cumulative_nav']].copy()


def process_holdings_data(file_path):
    """处理持仓数据"""
    df = pd.read_csv(file_path, encoding='utf-8-sig')

    # 标准化列名
    column_map = {}
    for col in df.columns:
        if col in ['日期', 'Date', 'date']:
            column_map[col] = 'date'
        elif col in ['股票代码', '证券代码', 'Stock Code', 'stock_code', '代码']:
            column_map[col] = 'stock_code'
        elif col in ['股票名称', '证券名称', 'Stock Name', 'stock_name', '名称']:
            column_map[col] = 'stock_name'
        elif col in ['持仓比例', '占比', 'Position Ratio', 'position_ratio', '比例']:
            column_map[col] = 'position_ratio'
        elif col in ['持仓市值', '市值', 'Market Value', 'market_value']:
            column_map[col] = 'market_value'
        elif col in ['持股数量', '股数', 'Shares', 'shares', '数量']:
            column_map[col] = 'shares'

    df = df.rename(columns=column_map)

    # 确保必需列存在
    required_cols = ['date', 'stock_code']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"持仓数据缺少必需列: {col}")

    # 填充缺失的列
    if 'stock_name' not in df.columns:
        df['stock_name'] = ''
    if 'position_ratio' not in df.columns:
        df['position_ratio'] = None
    if 'market_value' not in df.columns:
        df['market_value'] = None
    if 'shares' not in df.columns:
        df['shares'] = None

    return df[['date', 'stock_code', 'stock_name', 'position_ratio', 'market_value', 'shares']].copy()


def init_system_with_sample_data():
    """使用示例数据初始化系统"""
    print("🚀 开始使用示例数据初始化系统...")
    print("=" * 50)

    # 初始化数据库
    print("1️⃣ 初始化数据库...")
    db = DatabaseManager()

    # 添加示例产品
    print("2️⃣ 添加示例产品...")
    success1 = db.add_product("DEMO001", "演示基金A", "用于演示的基金产品")
    success2 = db.add_product("DEMO002", "演示基金B", "另一个演示基金产品")

    if not success1 or not success2:
        print("❌ 添加产品失败")
        return False

    # 导入净值数据
    print("3️⃣ 导入净值数据...")
    nav_file = "data/sample_nav.csv"
    if os.path.exists(nav_file):
        try:
            nav_df = process_nav_data(nav_file)
            success3 = db.add_nav_data("DEMO001", nav_df)

            # 为第二个产品创建稍微不同的净值数据
            nav_df2 = nav_df.copy()
            nav_df2['nav_value'] = nav_df2['nav_value'] * 1.05  # 稍微调整
            nav_df2['cumulative_nav'] = nav_df2['cumulative_nav'] * 1.08
            success4 = db.add_nav_data("DEMO002", nav_df2)

            if not success3 or not success4:
                print("❌ 导入净值数据失败")
                return False
        except Exception as e:
            print(f"❌ 处理净值数据失败: {e}")
            return False
    else:
        print(f"❌ 找不到净值数据文件: {nav_file}")
        return False

    # 导入持仓数据
    print("4️⃣ 导入持仓数据...")
    holdings_file = "data/sample_holdings.csv"
    if os.path.exists(holdings_file):
        try:
            holdings_df = process_holdings_data(holdings_file)
            success5 = db.add_holdings_data("DEMO001", holdings_df)

            # 为第二个产品使用相同的持仓数据
            success6 = db.add_holdings_data("DEMO002", holdings_df)

            if not success5 or not success6:
                print("❌ 导入持仓数据失败")
                return False
        except Exception as e:
            print(f"❌ 处理持仓数据失败: {e}")
            return False
    else:
        print(f"❌ 找不到持仓数据文件: {holdings_file}")
        return False

    # 验证数据
    print("5️⃣ 验证导入的数据...")
    products = db.get_products()
    print(f"   产品数量: {len(products)}")

    for product in products:
        code = product['product_code']
        nav_data = db.get_nav_data(code)
        available_dates = db.get_available_dates(code)

        print(f"   {product['product_name']} ({code}):")
        print(f"     - 净值记录: {len(nav_data)} 条")
        print(f"     - 持仓日期: {len(available_dates)} 个")

        if available_dates:
            latest_holdings = db.get_holdings_by_date(code, available_dates[0])
            print(f"     - 最新持仓股票数: {len(latest_holdings)} 只")

    print("\n🎉 系统初始化完成！")
    print("=" * 50)
    print("🎯 下一步:")
    print("1. 运行 streamlit run app.py")
    print("2. 在浏览器中查看系统")
    print("3. 测试各项功能")

    return True


def main():
    """主函数"""
    # 检查示例数据文件是否存在
    required_files = ["data/sample_nav.csv", "data/sample_holdings.csv"]
    missing_files = [f for f in required_files if not os.path.exists(f)]

    if missing_files:
        print("❌ 缺少示例数据文件:")
        for f in missing_files:
            print(f"   - {f}")
        print("\n请先运行: python create_sample_data.py")
        sys.exit(1)

    # 初始化系统
    success = init_system_with_sample_data()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()