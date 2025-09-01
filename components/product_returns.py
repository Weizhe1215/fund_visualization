"""
产品收益率计算（简化版）
"""
import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta


def get_latest_holding_files_with_total_assets():
    """获取包含总资产的最新持仓文件"""
    base_path = r"C:\shared_data\实盘\交易数据定频导出"

    if not os.path.exists(base_path):
        return []

    # 获取所有日期文件夹并排序
    date_folders = [f for f in os.listdir(base_path)
                    if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(base_path, f))]

    all_files = []
    for date_folder in sorted(date_folders, reverse=True)[:3]:  # 取最近3天，确保能找到不同日期
        date_folder_path = os.path.join(base_path, date_folder)

        for root, dirs, files in os.walk(date_folder_path):
            for file in files:
                # 这个函数主要用于实盘数据，但如果需要支持仿真，可以添加
                if file.startswith("单元资产账户持仓导出") and (file.endswith('.xlsx') or file.endswith('.csv')):
                    file_path = os.path.join(root, file)

                    # 解析时间
                    try:
                        filename = os.path.basename(file_path)
                        name_part = filename.replace('单元资产账户持仓导出_', '').replace('单元资产账户持仓导出-', '')
                        parts = name_part.split('_')
                        if len(parts) >= 2:
                            datetime_part = parts[-1]
                            if '-' in datetime_part:
                                date_time = datetime_part.replace('.xlsx', '').replace('.csv', '')
                                timestamp = datetime.strptime(date_time, "%Y%m%d-%H%M%S")

                                all_files.append({
                                    'file_path': file_path,
                                    'timestamp': timestamp,
                                    'date': date_folder,
                                    'filename': filename
                                })
                    except:
                        continue

    return sorted(all_files, key=lambda x: x['timestamp'], reverse=True)


def read_total_assets_from_holding_file(file_path):
    """从资产文件中读取总资产信息"""
    try:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, encoding='utf-8-sig')

        # 查找必要的列
        product_col = None
        total_asset_col = None

        for col in df.columns:
            if '产品名称' in col:
                product_col = col
            elif col == '总资产':  # 精确匹配
                total_asset_col = col

        if not product_col or not total_asset_col:
            return None

        # 提取数据
        result_df = df[[product_col, total_asset_col]].copy()
        result_df.columns = ['产品名称', '总资产']

        # 数据清理
        result_df['产品名称'] = result_df['产品名称'].astype(str)
        result_df['总资产'] = pd.to_numeric(result_df['总资产'], errors='coerce')
        result_df = result_df.dropna(subset=['产品名称', '总资产'])
        result_df = result_df[result_df['产品名称'] != '']
        result_df = result_df.groupby('产品名称').agg({'总资产': 'sum'}).reset_index()

        return result_df

    except Exception as e:
        return None

def calculate_simple_returns():
    """简化的收益率计算"""
    st.subheader("📈 产品收益率计算")

    # 获取最新的持仓文件
    files = get_latest_holding_files_with_total_assets()

    if len(files) < 2:
        st.error("需要至少2个不同日期的文件来计算收益率")
        return

    # 取最新的两个不同日期的文件
    latest_file = files[0]
    previous_file = None

    # 找到不同日期的文件
    for file in files[1:]:
        if file['date'] != latest_file['date']:
            previous_file = file
            break

    if not previous_file:
        st.error("未找到不同日期的文件")
        return

    # 读取数据
    latest_data = read_total_assets_from_holding_file(latest_file['file_path'])
    previous_data = read_total_assets_from_holding_file(previous_file['file_path'])

    if latest_data is None or previous_data is None:
        st.error("数据读取失败")
        return

    # 计算收益率
    merged = pd.merge(
        previous_data.rename(columns={'总资产': '历史总资产'}),
        latest_data.rename(columns={'总资产': '最新总资产'}),
        on='产品名称',
        how='inner'
    )

    if merged.empty:
        st.error("没有匹配的产品")
        return

    # 计算收益率
    merged['收益率'] = (merged['最新总资产'] / merged['历史总资产'] - 1) * 100

    st.dataframe(merged)

    # 统计信息
    col1, col2, col3 = st.columns(3)
    with col1:
        avg_return = merged['收益率'].mean()
        st.metric("平均收益率", f"{avg_return:.2f}%")

    with col2:
        max_return = merged['收益率'].max()
        st.metric("最高收益率", f"{max_return:.2f}%")

    with col3:
        min_return = merged['收益率'].min()
        st.metric("最低收益率", f"{min_return:.2f}%")


def read_futures_assets_from_file(file_path):
    """从期货文件中读取市值权益信息"""
    try:
        df = pd.read_excel(file_path)

        # 查找必要的列
        product_col = None
        market_value_col = None

        for col in df.columns:
            if '产品名称' in col:
                product_col = col
            elif col == '市值权益':
                market_value_col = col

        if not product_col or not market_value_col:
            return None

        # 提取数据
        result_df = df[[product_col, market_value_col]].copy()
        result_df.columns = ['产品名称', '期货资产']

        # 数据清理
        result_df['产品名称'] = result_df['产品名称'].astype(str)
        result_df['期货资产'] = pd.to_numeric(result_df['期货资产'], errors='coerce')
        result_df = result_df.dropna(subset=['产品名称', '期货资产'])
        result_df = result_df[result_df['产品名称'] != '']
        result_df = result_df.groupby('产品名称').agg({'期货资产': 'sum'}).reset_index()

        return result_df

    except Exception as e:
        return None


def get_latest_futures_file_by_date(target_date):
    """获取指定日期的最新期货文件"""
    futures_dir = r"C:\shared_data\期货"

    if not os.path.exists(futures_dir):
        return None

    # 查找期货文件
    futures_files = []
    for file in os.listdir(futures_dir):
        if file.startswith("期货资产导出_") and file.endswith('.xls'):
            try:
                time_part = file.replace('期货资产导出_', '').replace('.xls', '')
                timestamp = datetime.strptime(time_part, '%Y%m%d-%H%M%S')
                file_date = timestamp.strftime('%Y%m%d')

                # 匹配目标日期
                if file_date == target_date:
                    futures_files.append({
                        'file_path': os.path.join(futures_dir, file),
                        'timestamp': timestamp
                    })
            except:
                continue

    # 如果找不到精确匹配的日期，找最接近的历史文件
    if not futures_files:
        all_futures_files = []
        for file in os.listdir(futures_dir):
            if file.startswith("期货资产导出_") and file.endswith('.xls'):
                try:
                    time_part = file.replace('期货资产导出_', '').replace('.xls', '')
                    timestamp = datetime.strptime(time_part, '%Y%m%d-%H%M%S')
                    file_date = timestamp.strftime('%Y%m%d')

                    # 只要日期小于等于目标日期就可以
                    if file_date <= target_date:
                        all_futures_files.append({
                            'file_path': os.path.join(futures_dir, file),
                            'timestamp': timestamp,
                            'date': file_date
                        })
                except:
                    continue

        if all_futures_files:
            # 选择最接近且不超过目标日期的文件
            latest_futures = max(all_futures_files, key=lambda x: x['timestamp'])
            return latest_futures['file_path']
        else:
            return None
    else:
        # 返回该日期最新的期货文件
        latest_futures = max(futures_files, key=lambda x: x['timestamp'])
        return latest_futures['file_path']


def combine_assets_and_futures(assets_data, futures_data, custody_data=None):
    """合并现货资产、期货资产和托管户资金"""
    if assets_data is None:
        assets_data = pd.DataFrame(columns=['产品名称', '总资产'])
    if futures_data is None:
        futures_data = pd.DataFrame(columns=['产品名称', '期货资产'])
    if custody_data is None:
        custody_data = pd.DataFrame(columns=['产品名称', '托管资金'])

    # 外连接合并
    combined = pd.merge(assets_data, futures_data, on='产品名称', how='outer')
    combined = pd.merge(combined, custody_data, on='产品名称', how='outer')
    combined = combined.fillna(0)

    # 计算真实总资产 = 现货 + 期货 + 托管
    combined['真实总资产'] = combined['总资产'] + combined['期货资产'] + combined['托管资金']

    return combined[['产品名称', '真实总资产']]

def combine_assets_and_futures_without_custody(assets_data, futures_data):
    """合并现货资产、期货资产和托管户资金"""
    if assets_data is None:
        assets_data = pd.DataFrame(columns=['产品名称', '总资产'])
    if futures_data is None:
        futures_data = pd.DataFrame(columns=['产品名称', '期货资产'])

    # 外连接合并
    combined = pd.merge(assets_data, futures_data, on='产品名称', how='outer')
    combined = combined.fillna(0)

    # 计算真实总资产 = 现货 + 期货 + 托管
    combined['真实总资产'] = combined['总资产'] + combined['期货资产']

    return combined[['产品名称', '真实总资产']]

