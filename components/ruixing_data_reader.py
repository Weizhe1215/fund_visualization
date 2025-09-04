"""
瑞幸1号产品专用数据读取器
处理 Z:\Administrator\Desktop\交易数据导出\Stock 路径下的 Account-*.csv 文件
同时获取期货数据
"""
import os
import pandas as pd
from datetime import datetime, timedelta
import glob
import re


def get_ruixing_files_by_date(target_date):
    """
    获取指定日期的瑞幸1号所有文件

    Args:
        target_date: 目标日期，格式可以是 '20250822' 或 '2025-08-22'

    Returns:
        list: 该日期的所有文件路径，按时间排序
    """
    base_path = r"C:\shared_data\QMT"

    if not os.path.exists(base_path):
        print(f"❌ 瑞幸1号数据路径不存在: {base_path}")
        return []

    # 标准化日期格式为 YYYYMMDD
    if isinstance(target_date, str):
        if '-' in target_date:
            target_date = target_date.replace('-', '')
        elif len(target_date) == 8:
            pass  # 已经是正确格式
        else:
            print(f"❌ 日期格式错误: {target_date}")
            return []

    # 查找该日期的所有文件
    pattern = f"Account-{target_date}_*.csv"
    file_pattern = os.path.join(base_path, pattern)
    files = glob.glob(file_pattern)

    if not files:
        print(f"❌ 未找到日期 {target_date} 的瑞幸1号文件")
        return []

    # 解析时间并排序
    file_info = []
    for file_path in files:
        filename = os.path.basename(file_path)
        # 提取时间部分：Account-20250822_145034.csv -> 145034
        match = re.search(r'Account-\d{8}_(\d{6})\.csv', filename)
        if match:
            time_str = match.group(1)
            try:
                # 转换为时间对象用于排序
                time_obj = datetime.strptime(time_str, '%H%M%S').time()
                file_info.append({
                    'file_path': file_path,
                    'time_str': time_str,
                    'time_obj': time_obj,
                    'filename': filename
                })
            except ValueError:
                continue

    # 按时间排序
    file_info.sort(key=lambda x: x['time_obj'])

    return [info['file_path'] for info in file_info]


def get_ruixing_latest_file_by_date(target_date):
    """
    获取指定日期的最后一个瑞幸1号文件

    Args:
        target_date: 目标日期

    Returns:
        str: 最新文件路径，如果没有则返回 None
    """
    files = get_ruixing_files_by_date(target_date)
    return files[-1] if files else None


def read_ruixing_equity_asset(file_path):
    """
    读取瑞幸1号文件中的总资产数据（现货部分）

    Args:
        file_path: 文件路径

    Returns:
        float: 现货总资产值，如果读取失败返回 None
    """
    try:
        # 尝试不同编码读取CSV
        encodings = ['utf-8-sig', 'gbk', 'utf-8', 'gb2312']
        df = None

        for encoding in encodings:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if df is None:
            print(f"❌ 无法读取文件: {file_path}")
            return None

        # 查找总资产列
        total_asset_col = None
        for col in df.columns:
            if '总资产' in col:
                total_asset_col = col
                break

        if total_asset_col is None:
            print(f"❌ 未找到总资产列，可用列: {df.columns.tolist()}")
            return None

        # 提取总资产值（假设只有一行数据或取第一行）
        total_asset = df[total_asset_col].iloc[0]

        # 转换为数值
        if pd.isna(total_asset):
            return None

        total_asset = pd.to_numeric(total_asset, errors='coerce')

        print(f"✅ 成功读取瑞幸1号现货资产: {total_asset:,.0f}")
        return total_asset

    except Exception as e:
        print(f"❌ 读取瑞幸1号文件失败: {file_path}, 错误: {e}")
        return None


def get_ruixing_equity_asset_by_date(target_date):
    """
    获取指定日期瑞幸1号的现货总资产

    Args:
        target_date: 目标日期，支持 '20250822' 或 '2025-08-22' 格式

    Returns:
        float: 现货总资产值，如果获取失败返回 None
    """
    latest_file = get_ruixing_latest_file_by_date(target_date)
    if not latest_file:
        return None

    return read_ruixing_equity_asset(latest_file)


def get_previous_trading_date(current_date=None):
    """
    获取前一个交易日

    Args:
        current_date: 当前日期，如果为None则使用今天

    Returns:
        str: 前一个交易日，格式 'YYYYMMDD'
    """
    if current_date is None:
        current_date = datetime.now().date()
    elif isinstance(current_date, str):
        if len(current_date) == 8:  # YYYYMMDD格式
            current_date = datetime.strptime(current_date, '%Y%m%d').date()
        else:  # YYYY-MM-DD格式
            current_date = datetime.strptime(current_date, '%Y-%m-%d').date()

    base_path = r"C:\shared_data\QMT"

    # 向前查找最多10天（避免无限循环）
    for i in range(1, 11):
        check_date = current_date - timedelta(days=i)
        check_date_str = check_date.strftime('%Y%m%d')

        # 检查该日期是否有数据文件
        files = get_ruixing_files_by_date(check_date_str)
        if files:
            print(f"✅ 找到前一交易日: {check_date_str} (往前{i}天)")
            return check_date_str

    print("❌ 未找到前一交易日数据")
    return None


def get_current_trading_date(target_date=None):
    """
    获取当前交易日（如果今天没有数据，则往前找最近的交易日）

    Args:
        target_date: 目标日期，如果为None则使用今天

    Returns:
        str: 当前交易日，格式 'YYYYMMDD'
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        if len(target_date) == 8:  # YYYYMMDD格式
            target_date = datetime.strptime(target_date, '%Y%m%d').date()
        else:  # YYYY-MM-DD格式
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    # 先检查目标日期本身是否有数据
    target_date_str = target_date.strftime('%Y%m%d')
    files = get_ruixing_files_by_date(target_date_str)
    if files:
        print(f"✅ 当前交易日: {target_date_str}")
        return target_date_str

    # 如果没有，向前查找最近的交易日
    for i in range(1, 11):
        check_date = target_date - timedelta(days=i)
        check_date_str = check_date.strftime('%Y%m%d')

        files = get_ruixing_files_by_date(check_date_str)
        if files:
            print(f"✅ 最近交易日: {check_date_str} (往前{i}天)")
            return check_date_str

    print("❌ 未找到最近的交易日数据")
    return None


def get_ruixing_total_assets_with_futures(today_trading_date, yesterday_trading_date, get_latest_futures_data_by_date_func):
    """
    获取瑞幸1号今日和昨日的总资产（现货+期货）

    Args:
        today_trading_date: 当前交易日 'YYYYMMDD'
        yesterday_trading_date: 前一交易日 'YYYYMMDD'
        get_latest_futures_data_by_date_func: 期货数据读取函数

    Returns:
        tuple: (today_total_asset, yesterday_total_asset) 或 (None, None) 如果失败
    """
    print(f"🔍 获取瑞幸1号资产数据（现货+期货）:")
    print(f"  - 当前交易日: {today_trading_date}")
    print(f"  - 前一交易日: {yesterday_trading_date}")

    # 获取现货资产
    today_equity = get_ruixing_equity_asset_by_date(today_trading_date)
    yesterday_equity = get_ruixing_equity_asset_by_date(yesterday_trading_date)

    if today_equity is None or yesterday_equity is None:
        print("❌ 无法获取现货资产数据")
        return None, None

    # 获取期货资产
    today_futures = 0
    yesterday_futures = 0

    try:
        # 获取今日期货数据
        today_futures_data = get_latest_futures_data_by_date_func(today_trading_date, "实盘")
        if today_futures_data is not None:
            ruixing_futures_today = today_futures_data[today_futures_data['产品名称'] == '瑞幸1号']
            if not ruixing_futures_today.empty:
                today_futures = ruixing_futures_today['期货资产'].iloc[0]

        # 获取昨日期货数据
        yesterday_futures_data = get_latest_futures_data_by_date_func(yesterday_trading_date, "实盘")
        if yesterday_futures_data is not None:
            ruixing_futures_yesterday = yesterday_futures_data[yesterday_futures_data['产品名称'] == '瑞幸1号']
            if not ruixing_futures_yesterday.empty:
                yesterday_futures = ruixing_futures_yesterday['期货资产'].iloc[0]

        print(f"📊 期货资产:")
        print(f"  - 当前交易日期货: {today_futures:,.0f}")
        print(f"  - 前一交易日期货: {yesterday_futures:,.0f}")

    except Exception as e:
        print(f"⚠️ 获取期货数据失败，将使用0: {e}")
        today_futures = 0
        yesterday_futures = 0

    # 计算总资产
    today_total = today_equity + today_futures
    yesterday_total = yesterday_equity + yesterday_futures

    print(f"💎 瑞幸1号总资产:")
    print(f"  - 当前交易日: {today_total:,.0f} (现货 {today_equity:,.0f} + 期货 {today_futures:,.0f})")
    print(f"  - 前一交易日: {yesterday_total:,.0f} (现货 {yesterday_equity:,.0f} + 期货 {yesterday_futures:,.0f})")

    return today_total, yesterday_total