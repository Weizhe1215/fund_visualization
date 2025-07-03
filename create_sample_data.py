"""
创建示例数据文件
"""
import pandas as pd
import os
from datetime import datetime, timedelta
import random


def create_sample_nav_data():
    """创建示例净值数据"""
    # 生成一年的交易日数据
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    # 生成工作日（简化处理，实际应该排除节假日）
    dates = pd.date_range(start=start_date, end=end_date, freq='B')  # B表示工作日

    # 模拟净值走势（带一些随机波动）
    nav_values = []
    cumulative_nav_values = []
    base_nav = 1.0000
    base_cumulative = 1.0000

    for i, date in enumerate(dates):
        # 添加随机波动
        daily_return = random.normalvariate(0.0005, 0.02)  # 平均收益率0.05%，波动率2%
        base_nav *= (1 + daily_return)
        base_cumulative *= (1 + daily_return * 1.1)  # 累计净值稍微高一点

        nav_values.append(round(base_nav, 4))
        cumulative_nav_values.append(round(base_cumulative, 4))

    nav_df = pd.DataFrame({
        '日期': dates.strftime('%Y-%m-%d'),
        '单位净值': nav_values,
        '累计净值': cumulative_nav_values
    })

    return nav_df


def create_sample_holdings_data():
    """创建示例持仓数据"""
    # 季度报告日期
    report_dates = ['2024-03-31', '2024-06-30', '2024-09-30', '2024-12-31']

    # 股票池
    stock_pool = [
        {'code': '600519', 'name': '贵州茅台'},
        {'code': '000858', 'name': '五粮液'},
        {'code': '600036', 'name': '招商银行'},
        {'code': '000001', 'name': '平安银行'},
        {'code': '000002', 'name': '万科A'},
        {'code': '600276', 'name': '恒瑞医药'},
        {'code': '000568', 'name': '泸州老窖'},
        {'code': '002415', 'name': '海康威视'},
        {'code': '600887', 'name': '伊利股份'},
        {'code': '000063', 'name': '中兴通讯'},
        {'code': '002594', 'name': 'BYD'},
        {'code': '300750', 'name': '宁德时代'},
        {'code': '000725', 'name': '京东方A'},
        {'code': '002304', 'name': '洋河股份'},
        {'code': '000596', 'name': '古井贡酒'},
    ]

    holdings_data = []

    for date in report_dates:
        # 随机选择10-12只股票作为持仓
        selected_stocks = random.sample(stock_pool, random.randint(10, 12))

        # 生成随机持仓比例
        ratios = [random.uniform(1.0, 8.0) for _ in selected_stocks]
        total_ratio = sum(ratios)
        # 归一化到总和约85%（留15%现金）
        ratios = [r / total_ratio * 85 for r in ratios]

        for i, stock in enumerate(selected_stocks):
            holdings_data.append({
                '日期': date,
                '股票代码': stock['code'],
                '股票名称': stock['name'],
                '持仓比例': round(ratios[i], 2),
                '持仓市值': round(ratios[i] * 10000000, 0),  # 假设总规模1亿
                '持股数量': round(ratios[i] * 1000000, 0)  # 假设数量
            })

    holdings_df = pd.DataFrame(holdings_data)
    return holdings_df


def create_sample_index_components():
    """创建示例指数成分股数据"""
    # 沪深300成分股示例（部分）
    hs300_stocks = [
        {'code': '600519', 'name': '贵州茅台', 'weight': 4.2},
        {'code': '600036', 'name': '招商银行', 'weight': 2.8},
        {'code': '000858', 'name': '五粮液', 'weight': 2.1},
        {'code': '000001', 'name': '平安银行', 'weight': 1.9},
        {'code': '600887', 'name': '伊利股份', 'weight': 1.5},
        {'code': '600276', 'name': '恒瑞医药', 'weight': 1.3},
        {'code': '000002', 'name': '万科A', 'weight': 1.2},
        {'code': '000568', 'name': '泸州老窖', 'weight': 1.0},
    ]

    # 中证500成分股示例（部分）
    zz500_stocks = [
        {'code': '002415', 'name': '海康威视', 'weight': 0.8},
        {'code': '000063', 'name': '中兴通讯', 'weight': 0.7},
        {'code': '002594', 'name': 'BYD', 'weight': 0.9},
        {'code': '000725', 'name': '京东方A', 'weight': 0.6},
        {'code': '002304', 'name': '洋河股份', 'weight': 0.5},
        {'code': '000596', 'name': '古井贡酒', 'weight': 0.4},
    ]

    index_data = []
    date = '2024-12-31'  # 最新成分股日期

    # 添加沪深300成分股
    for stock in hs300_stocks:
        index_data.append({
            '指数代码': '000300',
            '指数名称': '沪深300',
            '股票代码': stock['code'],
            '股票名称': stock['name'],
            '权重': stock['weight'],
            '日期': date
        })

    # 添加中证500成分股
    for stock in zz500_stocks:
        index_data.append({
            '指数代码': '000905',
            '指数名称': '中证500',
            '股票代码': stock['code'],
            '股票名称': stock['name'],
            '权重': stock['weight'],
            '日期': date
        })

    # 添加创业板指成分股（使用部分中证500股票）
    for stock in zz500_stocks[:4]:
        index_data.append({
            '指数代码': '399006',
            '指数名称': '创业板指',
            '股票代码': stock['code'],
            '股票名称': stock['name'],
            '权重': stock['weight'] * 1.2,
            '日期': date
        })

    index_df = pd.DataFrame(index_data)
    return index_df


def main():
    """主函数"""
    print("📊 开始创建示例数据文件...")
    print("=" * 40)

    # 确保data目录存在
    os.makedirs('data', exist_ok=True)

    # 创建净值数据
    print("1️⃣ 创建净值数据...")
    nav_df = create_sample_nav_data()
    nav_df.to_csv('data/sample_nav.csv', index=False, encoding='utf-8-sig')
    print(f"   ✅ 净值数据: {len(nav_df)} 条记录")

    # 创建持仓数据
    print("2️⃣ 创建持仓数据...")
    holdings_df = create_sample_holdings_data()
    holdings_df.to_csv('data/sample_holdings.csv', index=False, encoding='utf-8-sig')
    print(f"   ✅ 持仓数据: {len(holdings_df)} 条记录")

    # 创建指数成分股数据
    print("3️⃣ 创建指数成分股数据...")
    index_df = create_sample_index_components()
    index_df.to_csv('data/index_components.csv', index=False, encoding='utf-8-sig')
    print(f"   ✅ 指数成分股数据: {len(index_df)} 条记录")

    print("\n🎉 示例数据文件创建完成！")
    print("📁 文件位置:")
    print("   - data/sample_nav.csv")
    print("   - data/sample_holdings.csv")
    print("   - data/index_components.csv")


if __name__ == "__main__":
    main()