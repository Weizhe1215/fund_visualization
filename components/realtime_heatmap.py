"""
实时持仓热力图组件
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import glob
from datetime import datetime, timedelta
import time
import numpy as np
import plotly.figure_factory as ff
from components.product_returns import combine_assets_and_futures
from components.ruixing_data_reader import *
import json
from typing import Optional, Dict, Tuple

# 数据路径配置
DATA_PATHS = {
    "实盘": r"C:\shared_data\实盘\交易数据定频导出",
    "仿真": r"C:\shared_data\仿真\交易数据定频导出"
}


# 在你的 realtime_heatmap.py 文件顶部临时添加这段代码测试
def test_time_slot():
    from datetime import datetime, time

    def is_trading_hours(dt):
        if dt.weekday() >= 5:  # 周末
            return False
        time_now = dt.time()
        return (time(9, 30) <= time_now <= time(15, 0))

    def get_time_slot():
        now = datetime.now()
        if is_trading_hours(now):
            minutes = (now.minute // 15) * 15
            time_slot = now.replace(minute=minutes, second=0, microsecond=0)
        else:
            time_slot = now.replace(minute=0, second=0, microsecond=0)
        return time_slot.strftime('%Y-%m-%d_%H:%M')

    current_time = datetime.now()
    time_slot = get_time_slot()
    cache_key = f"测试产品_实盘_{time_slot}"

    print(f"当前时间: {current_time}")
    print(f"时间片: {time_slot}")
    print(f"缓存键: {cache_key}")
    print(f"是否交易时间: {is_trading_hours(current_time)}")


# 在 render_realtime_heatmap 函数开头调用
test_time_slot()

def get_time_slot() -> str:
    """获取15分钟时间片"""
    now = datetime.now()

    # 交易时间内使用15分钟缓存
    if is_trading_hours(now):
        minutes = (now.minute // 15) * 15
        time_slot = now.replace(minute=minutes, second=0, microsecond=0)
    else:
        # 非交易时间使用小时缓存
        time_slot = now.replace(minute=0, second=0, microsecond=0)

    return time_slot.strftime('%Y-%m-%d_%H:%M')


def is_trading_hours(dt: datetime) -> bool:
    """判断是否在交易时间"""
    if dt.weekday() >= 5:  # 周末
        return False

    from datetime import time
    time_now = dt.time()
    return (time(9, 30) <= time_now <= time(15, 0))


def get_cache_key(product_name: str, data_source: str, time_slot: str) -> str:
    """生成缓存键"""
    return f"{product_name}_{data_source}_{time_slot}"


def get_latest_data_file_time(data_source: str) -> datetime:
    """获取最新数据文件的修改时间"""
    try:
        file_info = get_latest_holding_files(data_source)

        if not file_info or not file_info.get('files'):
            return datetime.now()

        latest_time = datetime.min

        for product_id, file_path in file_info['files'].items():
            # 确保file_path是有效的文件路径
            if isinstance(file_path, str) and os.path.exists(file_path):
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time > latest_time:
                    latest_time = file_time

        return latest_time if latest_time != datetime.min else datetime.now()

    except Exception as e:
        print(f"获取文件时间失败: {e}")
        return datetime.now()


def should_use_cache(product_name: str, data_source: str, db) -> Tuple[bool, Optional[Dict]]:
    """判断是否应该使用缓存"""
    try:
        time_slot = get_time_slot()
        cache_key = get_cache_key(product_name, data_source, time_slot)

        # 获取缓存数据
        cache_result = db.get_cache_data(cache_key)
        if not cache_result:
            return False, None

        # 检查数据文件是否比缓存更新
        latest_file_time = get_latest_data_file_time(data_source)
        cache_file_time = cache_result.get('data_file_time')

        if cache_file_time and latest_file_time > cache_file_time:
            return False, None

        return True, cache_result['data']

    except Exception as e:
        return False, None


def calculate_product_data_realtime(product_name: str, data_source: str, db) -> Dict:
    """实时计算产品数据"""
    try:
        # 使用现有的文件获取逻辑
        file_info = get_latest_holding_files(data_source)

        if not file_info or not file_info.get('files'):
            return {}

        # 获取数据库中的产品列表
        db_products = db.get_products()
        db_product_names = {p['product_name']: p['product_code'] for p in db_products}

        # 读取每个产品的最新文件数据并匹配产品
        all_data = {}

        for product_id, file_path in file_info['files'].items():
            # 验证文件路径是否有效
            if not os.path.exists(file_path):
                continue

            df = read_holding_file(file_path)
            if not df.empty and 'product_name' in df.columns:
                # 获取文件中的产品名称
                file_product_names = df['product_name'].unique()

                for prod_name in file_product_names:
                    # 尝试匹配数据库中的产品
                    if prod_name in db_product_names:
                        product_data = df[df['product_name'] == prod_name].copy()
                        if not product_data.empty:
                            # 如果产品已存在，合并数据
                            if prod_name in all_data:
                                # 合并持仓数据，按股票代码分组，市值相加，涨跌幅取平均
                                existing_data = all_data[prod_name]
                                combined_data = pd.concat([existing_data, product_data], ignore_index=True)

                                # 按股票代码合并
                                merged_data = combined_data.groupby('stock_code').agg({
                                    'stock_name': 'first',  # 取第一个名称
                                    'market_value': 'sum',  # 市值相加
                                    'change_pct': 'mean',  # 涨跌幅取平均
                                    'product_name': 'first'
                                }).reset_index()

                                all_data[prod_name] = merged_data
                            else:
                                all_data[prod_name] = product_data

        if product_name not in all_data:
            return {}

        product_data = all_data[product_name]

        # 计算权重（基于市值）
        if 'weight' not in product_data.columns:
            product_data['weight'] = product_data['market_value'] / product_data['market_value'].sum() * 100

        # 计算收益率
        return_rate = get_product_return_from_holdings(product_name, data_source, db)

        # 计算统计数据
        positive_count = len(product_data[product_data['change_pct'] > 0])
        total_count = len(product_data)
        total_value = product_data['market_value'].sum()

        # 计算前5名数据
        top_gainers = []
        top_losers = []

        if not product_data.empty:
            gainers_data = product_data[product_data['change_pct'] > 0]
            if not gainers_data.empty:
                top_gainers_df = gainers_data.nlargest(5, 'change_pct')[['stock_name', 'change_pct', 'weight']]
                top_gainers = top_gainers_df.to_dict('records')

            losers_data = product_data[product_data['change_pct'] < 0]
            if not losers_data.empty:
                top_losers_df = losers_data.nsmallest(5, 'change_pct')[['stock_name', 'change_pct', 'weight']]
                top_losers = top_losers_df.to_dict('records')

        return {
            'return_rate': return_rate,
            'positive_count': positive_count,
            'total_count': total_count,
            'total_value': total_value,
            'product_data': product_data.to_dict('records'),
            'top_gainers': top_gainers,
            'top_losers': top_losers,
            'calculation_timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"计算产品数据失败: {e}")
        return {}


def get_product_data_with_cache(product_name: str, data_source: str, db) -> Dict:
    """获取产品数据（带缓存）"""
    # 检查是否使用缓存
    use_cache, cached_data = should_use_cache(product_name, data_source, db)

    if use_cache and cached_data:
        return cached_data

    # 缓存未命中，执行实时计算
    result = calculate_product_data_realtime(product_name, data_source, db)

    # 保存到缓存
    if result:
        time_slot = get_time_slot()
        cache_key = get_cache_key(product_name, data_source, time_slot)
        data_file_time = get_latest_data_file_time(data_source)

        db.save_cache_data(cache_key, product_name, data_source, time_slot, result, data_file_time)

    return result

def create_heatmap_data(df, mode='price_change'):
    """创建热力图数据"""
    if df.empty:
        return None, None, None, None

    # 计算权重（基于市值）
    df['weight'] = df['market_value'] / df['market_value'].sum() * 100

    # 分为涨跌两组
    rising_df = df[df['change_pct'] > 0].copy()
    falling_df = df[df['change_pct'] < 0].copy()

    if mode == 'price_change':
        # 模式1：纯涨跌幅，面积完全基于涨跌幅大小
        if not rising_df.empty:
            # 面积 = 涨跌幅的平方（放大差异）
            rising_df['size'] = rising_df['change_pct'] ** 2
            rising_df['color_value'] = rising_df['change_pct']

        if not falling_df.empty:
            # 面积 = 跌幅的平方
            falling_df['size'] = falling_df['change_pct'] ** 2  # 负数的平方还是正数
            falling_df['color_value'] = falling_df['change_pct']

        title_rising = "上涨股票热力图（面积=涨幅）"
        title_falling = "下跌股票热力图（面积=跌幅）"
        color_title = "涨跌幅 (%)"
    else:
        # 模式2：收益贡献，面积基于贡献度
        # 先计算所有股票的原始贡献度
        df['raw_contribution'] = df['change_pct'] * df['weight'] / 100
        total_abs_contribution = df['raw_contribution'].abs().sum()

        # 归一化贡献度
        if total_abs_contribution > 0:
            df['contribution'] = (df['raw_contribution'].abs() / total_abs_contribution) * 100
            df['contribution_signed'] = df['raw_contribution'] / total_abs_contribution * 100  # 保留正负号用于颜色
        else:
            df['contribution'] = 0
            df['contribution_signed'] = 0

        # 重新分组
        rising_df = df[df['change_pct'] > 0].copy() if not df[df['change_pct'] > 0].empty else pd.DataFrame()
        falling_df = df[df['change_pct'] < 0].copy() if not df[df['change_pct'] < 0].empty else pd.DataFrame()

        if not rising_df.empty:
            rising_df['size'] = rising_df['contribution']  # 面积 = 归一化贡献度
            rising_df['color_value'] = rising_df['contribution_signed']  # 颜色 = 带符号的贡献度

        if not falling_df.empty:
            falling_df['size'] = falling_df['contribution']  # 面积 = 归一化贡献度
            falling_df['color_value'] = falling_df['contribution_signed']  # 颜色 = 带符号的贡献度

        title_rising = "正贡献股票热力图（面积=贡献度）"
        title_falling = "负贡献股票热力图（面积=贡献度）"
        color_title = "贡献度 (%)"

    return rising_df, falling_df, (title_rising, title_falling), color_title


def render_dual_treemap_heatmap(rising_df, falling_df, titles, color_title, mode='price_change'):
    """渲染双热力图（涨跌分开）"""
    title_rising, title_falling = titles

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(title_rising)
        if rising_df is not None and not rising_df.empty:
            render_single_treemap(rising_df, color_title, 'Reds', mode)
        else:
            st.info("暂无上涨股票")

    with col2:
        st.subheader(title_falling)
        if falling_df is not None and not falling_df.empty:
            render_single_treemap(falling_df, color_title, 'Greens_r', mode)
        else:
            st.info("暂无下跌股票")


def render_single_treemap(df, color_title, colorscale, mode='price_change'):
    """渲染单个热力图"""
    # 根据模式准备不同的显示标签
    if 'contribution' in df.columns:  # 贡献度模式
        df['label'] = df.apply(lambda x: f"{x['stock_name']}<br>{x['stock_code']}<br>{x['contribution']:.3f}%", axis=1)
    else:  # 价格涨跌模式
        df['label'] = df.apply(lambda x: f"{x['stock_name']}<br>{x['stock_code']}<br>{x['change_pct']:.2f}%", axis=1)

    # 为上涨和下跌使用不同的高级配色
    if colorscale == 'Reds':
        colorscale = 'Reds'  # 保持红色系
    elif colorscale == 'Greens_r':
        colorscale = 'Greens_r'  # 改为正向绿色系

    fig = go.Figure(go.Treemap(
        labels=df['label'],
        values=df['size'],
        parents=[""] * len(df),
        marker=dict(
            colorscale=colorscale,
            colorbar=dict(title=color_title),
            colors=df['color_value'],
            line=dict(width=2, color='rgba(255,255,255,0.3)')  # 添加边框线
        ),
        textinfo="label",
        textfont_size=11,
        hovertemplate='<b>%{label}</b><br>' +
                      f'{color_title}: %{{color:.2f}}<br>' +
                      '面积权重: %{value:.2f}<br>' +
                      '<extra></extra>'
    ))

    fig.update_layout(
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(t=20, b=20, l=20, r=20)
    )

    st.plotly_chart(fig, use_container_width=True)


def get_latest_holding_files(data_source="实盘"):
    """获取每个产品最新的持仓文件"""
    try:
        base_path = DATA_PATHS[data_source]
        if not os.path.exists(base_path):
            return {}

        # 获取所有日期文件夹并排序，选择最新的
        date_folders = [f for f in os.listdir(base_path)
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(base_path, f))]

        if not date_folders:
            return {}

        latest_date_folder = max(date_folders)
        date_folder_path = os.path.join(base_path, latest_date_folder)

        # 递归查找所有持仓文件
        all_files = []
        for root, dirs, files in os.walk(date_folder_path):
            for file in files:
                # 根据数据源使用不同的匹配规则
                if data_source == "仿真":
                    # 仿真支持三种格式
                    if ((file.startswith("单元资产账户持仓导出") or
                         file.startswith("单元账户层资产资产导出") or
                         file.startswith("单元账户层资产持仓导出")) and
                            (file.endswith('.xlsx') or file.endswith('.csv'))):
                        all_files.append(os.path.join(root, file))
                else:
                    # 实盘保持原格式
                    if file.startswith("单元资产账户持仓导出") and (file.endswith('.xlsx') or file.endswith('.csv')):
                        all_files.append(os.path.join(root, file))

        # 按产品分组文件
        product_files = {}
        for file_path in all_files:
            filename = os.path.basename(file_path)
            # 解析文件名：单元资产账户持仓导出_东财EMC_普通_20250625-123500
            # 或：单元资产账户持仓导出_开源ATX_普通1_20250625-121200

            # 根据文件名前缀移除对应的前缀
            if filename.startswith("单元账户层资产持仓导出"):
                # 新持仓格式: 单元账户层资产持仓导出_资产账户1_YYYYMMDD-HHMMSS.xlsx
                name_part = filename.replace('单元账户层资产持仓导出_', '')
            elif filename.startswith("单元账户层资产资产导出"):
                # 新总资产格式: 单元账户层资产资产导出_YYYYMMDD-HHMMSS.xlsx
                name_part = filename.replace('单元账户层资产资产导出_', '')
            else:
                # 原格式
                name_part = filename.replace('单元资产账户持仓导出_', '').replace('单元资产账户持仓导出-', '')

            # 分割获取产品标识和时间
            parts = name_part.split('_')

            if len(parts) >= 2:
                # 最后一部分包含日期时间
                datetime_part = parts[-1]
                # 产品标识是除了最后一部分的其他部分
                product_identifier = '_'.join(parts[:-1])

                # 提取时间戳
                if '-' in datetime_part:
                    date_time = datetime_part.replace('.xlsx', '').replace('.csv', '')
                    try:
                        timestamp = datetime.strptime(date_time, "%Y%m%d-%H%M%S")
                    except:
                        continue
                else:
                    continue

                if product_identifier not in product_files:
                    product_files[product_identifier] = []

                product_files[product_identifier].append({
                    'file_path': file_path,
                    'timestamp': timestamp,
                    'filename': filename
                })

        # 获取每个产品最新的文件
        latest_files = {}
        for product_id, files_list in product_files.items():
            if files_list:
                latest_file = max(files_list, key=lambda x: x['timestamp'])
                latest_files[product_id] = latest_file['file_path']

        return {
            'latest_date': latest_date_folder,
            'files': latest_files,
            'file_count': sum(len(files) for files in product_files.values()),
            'data_source': data_source  # 添加数据源信息
        }

    except Exception as e:
        st.error(f"读取{data_source}文件夹失败: {e}")
        return {}


def read_holding_file(file_path):
    """读取单个持仓文件"""
    try:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, encoding='utf-8-sig')

        # 标准化列名，避免重复
        column_mapping = {}
        used_standard_names = set()

        for col in df.columns:
            if '产品名称' in col and 'product_name' not in used_standard_names:
                column_mapping[col] = 'product_name'
                used_standard_names.add('product_name')
            elif '证券代码' in col and 'stock_code' not in used_standard_names:
                column_mapping[col] = 'stock_code'
                used_standard_names.add('stock_code')
            elif '证券名称' in col and 'stock_name' not in used_standard_names:
                column_mapping[col] = 'stock_name'
                used_standard_names.add('stock_name')
            elif '持仓市值' in col and 'market_value' not in used_standard_names:
                column_mapping[col] = 'market_value'
                used_standard_names.add('market_value')
            elif ('涨跌幅' in col or '当日涨跌幅' in col) and 'change_pct' not in used_standard_names:
                column_mapping[col] = 'change_pct'
                used_standard_names.add('change_pct')
            elif '日期' in col and 'date' not in used_standard_names:
                column_mapping[col] = 'date'
                used_standard_names.add('date')

        # 应用列名映射
        df = df.rename(columns=column_mapping)

        # 检查必需列
        required_cols = ['product_name', 'stock_code', 'stock_name', 'market_value', 'change_pct']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            st.warning(f"文件 {os.path.basename(file_path)} 缺少列: {missing_cols}")
            st.write(f"实际列名: {list(df.columns)}")
            return pd.DataFrame()

        # 数据类型转换
        df['stock_code'] = df['stock_code'].astype(str).str.zfill(6)
        df['market_value'] = pd.to_numeric(df['market_value'], errors='coerce')
        df['change_pct'] = pd.to_numeric(df['change_pct'], errors='coerce')

        # 删除无效数据
        df = df.dropna(subset=['market_value', 'change_pct'])
        df = df[df['market_value'] > 0]

        return df

    except Exception as e:
        st.error(f"读取文件失败 {file_path}: {e}")
        return pd.DataFrame()


def render_realtime_heatmap(db):
    """渲染实时持仓热力图页面"""
    st.header("📊 实时持仓热力图")

    # 添加数据源选择
    col1, col2 = st.columns([1, 3])
    with col1:
        data_source = st.selectbox(
            "数据源",
            options=["实盘", "仿真"],
            key="data_source_selector"
        )

    with col2:
        st.info(f"数据路径: {DATA_PATHS[data_source]}")

    # 添加刷新按钮和自动刷新
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("🔄 手动刷新", type="primary"):
            st.rerun()

    with col2:
        auto_refresh = st.checkbox("自动刷新 (5分钟)", value=False)

    with col3:
        last_update = st.empty()

    # 获取最新文件
    file_info = get_latest_holding_files(data_source)

    if not file_info or not file_info.get('files'):
        st.error(f"未找到{data_source}持仓文件")
        return

    st.success(
        f"最新日期: {file_info['latest_date']}, 总文件数: {file_info.get('file_count', 0)}, 产品数: {len(file_info['files'])}")

    # 获取数据库中的产品列表
    db_products = db.get_products()
    db_product_names = {p['product_name']: p['product_code'] for p in db_products}

    # 读取每个产品的最新文件数据并匹配产品
    all_data = {}
    matched_products = []

    for product_id, file_path in file_info['files'].items():
        df = read_holding_file(file_path)
        if not df.empty and 'product_name' in df.columns:
            # 获取文件中的产品名称
            file_product_names = df['product_name'].unique()

            for prod_name in file_product_names:
                # 尝试匹配数据库中的产品
                if prod_name in db_product_names:
                    product_data = df[df['product_name'] == prod_name].copy()
                    if not product_data.empty:
                        # 如果产品已存在，合并数据
                        if prod_name in all_data:
                            # 合并持仓数据，按股票代码分组，市值相加，涨跌幅取平均
                            existing_data = all_data[prod_name]
                            combined_data = pd.concat([existing_data, product_data], ignore_index=True)

                            # 按股票代码合并
                            merged_data = combined_data.groupby('stock_code').agg({
                                'stock_name': 'first',  # 取第一个名称
                                'market_value': 'sum',  # 市值相加
                                'change_pct': 'mean',  # 涨跌幅取平均
                                'product_name': 'first'
                            }).reset_index()

                            all_data[prod_name] = merged_data
                        else:
                            all_data[prod_name] = product_data
                            matched_products.append(prod_name)

    if not matched_products:
        st.warning(f"未找到与数据库匹配的{data_source}产品数据")
        st.info("请确保文件中的产品名称与数据库中的产品名称一致")
        return

    # ✅ 新增：创建主要内容区域和侧边栏
    col_main, col_sidebar = st.columns([2.5, 1])

    # ✅ 新增：在侧边栏显示产品收益表现（使用缓存）
    with col_sidebar:
        st.subheader("📈 当日产品表现")

        # 计算每个产品的收益率 - 使用缓存
        product_returns = []
        for product_name in matched_products:
            # ✅ 使用缓存获取收益率
            cached_result = get_product_data_with_cache(product_name, data_source, db)
            if cached_result and 'return_rate' in cached_result:
                return_rate = cached_result['return_rate']
                if return_rate is not None:
                    product_returns.append({
                        'product_name': product_name,
                        'return_rate': return_rate
                    })

        if product_returns:
            # 创建收益率柱状图
            returns_df = pd.DataFrame(product_returns)
            returns_df = returns_df.sort_values('return_rate', ascending=True)

            # 使用plotly创建柱状图
            import plotly.graph_objects as go

            colors = ['#90EE90' if x < 0 else 'pink' for x in returns_df['return_rate']]

            fig = go.Figure(data=[
                go.Bar(
                    y=returns_df['product_name'],
                    x=returns_df['return_rate'],
                    orientation='h',
                    marker=dict(color=colors),
                    text=[f"{x:.2f}%" for x in returns_df['return_rate']],
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>收益率: %{x:.2f}%<extra></extra>'
                )
            ])

            fig.update_layout(
                title="产品收益率排行",
                xaxis_title="收益率 (%)",
                yaxis_title="产品名称",
                height=300,
                margin=dict(l=10, r=10, t=50, b=10),
                font=dict(size=10)
            )

            st.plotly_chart(fig, use_container_width=True)

            # 显示具体数值表格
            st.write("**详细数据：**")
            display_df = returns_df.copy()
            display_df['return_rate'] = display_df['return_rate'].apply(lambda x: f"{x:.2f}%")
            display_df.columns = ['产品名称', '当日收益率']
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        else:
            st.info("暂无收益率数据")

    # 主要内容区域：原有的产品选择和热力图
    with col_main:
        # 产品选择下拉框
        selected_product_name = st.selectbox(
            f"选择要分析的{data_source}产品",
            options=matched_products,
            key=f"realtime_product_selector_{data_source}"
        )

        if selected_product_name:
            # ✅ 使用缓存获取产品数据
            cached_result = get_product_data_with_cache(selected_product_name, data_source, db)

            if cached_result and 'product_data' in cached_result:
                # 从缓存恢复DataFrame
                product_data = pd.DataFrame(cached_result['product_data'])

                # 显示数据概况
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("持仓股票数", cached_result.get('total_count', 0))

                with col2:
                    total_value = cached_result.get('total_value', 0)
                    st.metric("总市值", f"{total_value:,.0f}")

                with col3:
                    return_rate = cached_result.get('return_rate')
                    if return_rate is not None:
                        st.metric("当日收益率(已调整)", f"{return_rate:.2f}%")
                    else:
                        st.metric("当日收益率", "计算失败")

                with col4:
                    positive_count = cached_result.get('positive_count', 0)
                    total_count = cached_result.get('total_count', 0)
                    st.metric("上涨股票数", f"{positive_count}/{total_count}")

                # 热力图展示
                st.divider()
                st.subheader("持仓热力图")

                # 模式切换
                col1, col2 = st.columns(2)
                with col1:
                    heatmap_mode = st.radio(
                        "热力图模式",
                        options=['price_change', 'contribution'],
                        format_func=lambda x: "价格涨跌" if x == 'price_change' else "收益贡献",
                        key=f"heatmap_mode_{data_source}"
                    )

                # 生成热力图数据
                rising_df, falling_df, titles, color_title = create_heatmap_data(product_data, heatmap_mode)

                # 渲染热力图
                if rising_df is not None or falling_df is not None:
                    render_dual_treemap_heatmap(rising_df, falling_df, titles, color_title, heatmap_mode)

                    # 显示统计信息
                    st.subheader("详细统计")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**涨幅前5名:**")
                        # 使用缓存的top_gainers数据
                        top_gainers = cached_result.get('top_gainers', [])
                        if top_gainers:
                            gainers_df = pd.DataFrame(top_gainers)
                            if 'change_pct' in gainers_df.columns and 'weight' in gainers_df.columns:
                                gainers_df['change_pct'] = gainers_df['change_pct'].apply(lambda x: f"{x:.2f}%")
                                gainers_df['weight'] = gainers_df['weight'].apply(lambda x: f"{x:.2f}%")
                                gainers_df.columns = ['股票名称', '涨跌幅', '权重']
                                st.dataframe(gainers_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("暂无上涨股票")

                    with col2:
                        st.write("**跌幅前5名:**")
                        # 使用缓存的top_losers数据
                        top_losers = cached_result.get('top_losers', [])
                        if top_losers:
                            losers_df = pd.DataFrame(top_losers)
                            if 'change_pct' in losers_df.columns and 'weight' in losers_df.columns:
                                losers_df['change_pct'] = losers_df['change_pct'].apply(lambda x: f"{x:.2f}%")
                                losers_df['weight'] = losers_df['weight'].apply(lambda x: f"{x:.2f}%")
                                losers_df.columns = ['股票名称', '涨跌幅', '权重']
                                st.dataframe(losers_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("暂无下跌股票")

                # 显示数据计算时间
                calc_time = cached_result.get('calculation_timestamp')
                if calc_time:
                    calc_dt = datetime.fromisoformat(calc_time)
                    st.caption(f"数据计算时间: {calc_dt.strftime('%Y-%m-%d %H:%M:%S')}")

            elif selected_product_name in all_data:
                # 回退到原始逻辑（缓存失败时）
                product_data = all_data[selected_product_name]

                # 显示数据概况
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("持仓股票数", len(product_data))

                with col2:
                    total_value = product_data['market_value'].sum()
                    st.metric("总市值", f"{total_value:,.0f}")

                with col3:
                    # ✅ 传入db参数，启用出入金调整
                    actual_return = get_product_return_from_holdings(selected_product_name, data_source, db)
                    if actual_return is not None:
                        st.metric("当日收益率(已调整)", f"{actual_return:.2f}%")
                    else:
                        st.metric("当日收益率", "计算失败")

                with col4:
                    positive_count = len(product_data[product_data['change_pct'] > 0])
                    st.metric("上涨股票数", f"{positive_count}/{len(product_data)}")

                # 热力图展示
                st.divider()
                st.subheader("持仓热力图")

                # 模式切换
                col1, col2 = st.columns(2)
                with col1:
                    heatmap_mode = st.radio(
                        "热力图模式",
                        options=['price_change', 'contribution'],
                        format_func=lambda x: "价格涨跌" if x == 'price_change' else "收益贡献",
                        key=f"heatmap_mode_{data_source}"
                    )

                # 生成热力图数据
                rising_df, falling_df, titles, color_title = create_heatmap_data(product_data, heatmap_mode)

                # 渲染热力图
                if rising_df is not None or falling_df is not None:
                    render_dual_treemap_heatmap(rising_df, falling_df, titles, color_title, heatmap_mode)

                    # 显示统计信息
                    st.subheader("详细统计")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**涨幅前5名:**")
                        if rising_df is not None and not rising_df.empty:
                            top_gainers = rising_df.nlargest(5, 'change_pct')[['stock_name', 'change_pct', 'weight']]
                            top_gainers['change_pct'] = top_gainers['change_pct'].apply(lambda x: f"{x:.2f}%")
                            top_gainers['weight'] = top_gainers['weight'].apply(lambda x: f"{x:.2f}%")
                            top_gainers.columns = ['股票名称', '涨跌幅', '权重']
                            st.dataframe(top_gainers, use_container_width=True, hide_index=True)
                        else:
                            st.info("暂无上涨股票")

                    with col2:
                        st.write("**跌幅前5名:**")
                        if falling_df is not None and not falling_df.empty:
                            top_losers = falling_df.nsmallest(5, 'change_pct')[['stock_name', 'change_pct', 'weight']]
                            top_losers['change_pct'] = top_losers['change_pct'].apply(lambda x: f"{x:.2f}%")
                            top_losers['weight'] = top_losers['weight'].apply(lambda x: f"{x:.2f}%")
                            top_losers.columns = ['股票名称', '涨跌幅', '权重']
                            st.dataframe(top_losers, use_container_width=True, hide_index=True)
                        else:
                            st.info("暂无下跌股票")

    # 自动刷新逻辑
    if auto_refresh:
        time.sleep(300)  # 5分钟
        st.rerun()

    last_update.write(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 只有在选择了产品之后才显示出入金管理
    if 'selected_product_name' in locals() and selected_product_name and selected_product_name in all_data:

        st.divider()
        st.subheader("💰 出入金管理")

        col_input, col_history = st.columns([1, 1])

        # 左列：录入出入金
        with col_input:
            st.write("**录入今日出入金**")

            cash_amount = st.number_input(
                "金额（万元）",
                value=0.0,
                step=1.0,
                min_value=0.0,
                key="cash_flow_amount"
            )

            flow_type = st.selectbox(
                "类型",
                ["出金", "入金"],
                key="cash_flow_type"
            )

            note = st.text_input(
                "备注",
                placeholder="可选，如：客户赎回、追加投资等",
                key="cash_flow_note"
            )

            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button("✅ 确认录入", type="primary"):
                    if cash_amount > 0:
                        # 转换为元并确定类型
                        amount_yuan = cash_amount * 10000
                        flow_type_db = "outflow" if flow_type == "出金" else "inflow"
                        today_date = datetime.now().strftime('%Y-%m-%d')

                        success = db.add_cash_flow(
                            selected_product_name,
                            today_date,
                            flow_type_db,
                            amount_yuan,
                            note
                        )

                        if success:
                            st.success(f"✅ 记录成功：{flow_type} {cash_amount}万元")
                            time.sleep(1)  # 短暂延迟让用户看到成功信息
                            st.rerun()  # 刷新页面显示最新数据
                        else:
                            st.error("❌ 记录失败，请重试")
                    else:
                        st.warning("⚠️ 请输入大于0的金额")

            with col_btn2:
                if st.button("🗑️ 清除今日"):
                    today_date = datetime.now().strftime('%Y-%m-%d')

                    # 获取今日的所有出入金记录并删除
                    today_flows = db.get_cash_flows_by_unit(selected_product_name)
                    today_flows = today_flows[today_flows['日期'] == today_date]

                    deleted_count = 0
                    for _, flow in today_flows.iterrows():
                        flow_type_db = flow['类型']
                        amount = flow['金额']
                        success = db.delete_cash_flow(selected_product_name, today_date, flow_type_db, amount)
                        if success:
                            deleted_count += 1

                    if deleted_count > 0:
                        st.success(f"✅ 已清除今日{deleted_count}条记录")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info("ℹ️ 今日暂无记录需要清除")

        # 右列：显示出入金历史
        with col_history:
            st.write("**出入金历史**")

            try:
                cash_flows = db.get_cash_flows_by_unit(selected_product_name)

                if not cash_flows.empty:
                    # 格式化显示
                    display_df = cash_flows.copy()
                    display_df['金额(万元)'] = display_df['金额'].apply(lambda x: f"{x / 10000:.1f}")
                    display_df['类型'] = display_df['类型'].map({
                        "inflow": "💰 入金",
                        "outflow": "📤 出金"
                    })

                    # 显示最近10条记录
                    st.dataframe(
                        display_df[['日期', '类型', '金额(万元)', '备注']].head(10),
                        use_container_width=True,
                        hide_index=True
                    )

                    # 显示今日汇总
                    today_date = datetime.now().strftime('%Y-%m-%d')
                    today_flows = cash_flows[cash_flows['日期'] == today_date]

                    if not today_flows.empty:
                        today_inflow = today_flows[today_flows['类型'] == 'inflow']['金额'].sum()
                        today_outflow = today_flows[today_flows['类型'] == 'outflow']['金额'].sum()
                        today_net_flow = today_inflow - today_outflow

                        # 创建三列显示今日汇总
                        col_in, col_out, col_net = st.columns(3)

                        with col_in:
                            st.metric("今日入金", f"{today_inflow / 10000:.1f}万", delta=None)

                        with col_out:
                            st.metric("今日出金", f"{today_outflow / 10000:.1f}万", delta=None)

                        with col_net:
                            net_color = "normal" if today_net_flow >= 0 else "inverse"
                            st.metric(
                                "净流入",
                                f"{today_net_flow / 10000:.1f}万",
                                delta=f"{'流入' if today_net_flow >= 0 else '流出'}",
                                delta_color=net_color
                            )
                    else:
                        st.info("📊 今日暂无出入金记录")

                else:
                    st.info("📝 暂无出入金历史记录")
                    st.caption("提示：首次使用请先录入出入金信息以获得准确的收益率")

            except Exception as e:
                st.error(f"❌ 获取出入金数据失败：{str(e)}")

def get_latest_asset_files(data_source="实盘"):
    """获取最新的资产导出文件"""
    try:
        base_path = DATA_PATHS[data_source]
        if not os.path.exists(base_path):
            return None

        # 获取最新日期文件夹
        date_folders = [f for f in os.listdir(base_path)
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(base_path, f))]

        if not date_folders:
            return None

        latest_date_folder = max(date_folders)
        date_folder_path = os.path.join(base_path, latest_date_folder)

        # 查找资产导出文件
        asset_files = []
        for root, dirs, files in os.walk(date_folder_path):
            for file in files:
                if file.startswith("单元资产账户资产导出_") and (file.endswith('.xlsx') or file.endswith('.csv')):
                    asset_files.append(os.path.join(root, file))

        # 找到最新时间的文件
        latest_asset_file = None
        latest_time = None

        for file_path in asset_files:
            filename = os.path.basename(file_path)
            # 解析时间：单元资产账户资产导出_20250626-161500
            time_part = filename.replace('单元资产账户资产导出_', '').replace('.xlsx', '').replace('.csv', '')
            try:
                file_time = datetime.strptime(time_part, "%Y%m%d-%H%M%S")
                if latest_time is None or file_time > latest_time:
                    latest_time = file_time
                    latest_asset_file = file_path
            except:
                continue

        return latest_asset_file

    except Exception as e:
        print(f"读取{data_source}资产文件失败: {e}")
        return None


def read_asset_file(file_path):
    """读取资产导出文件"""
    try:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, encoding='utf-8-sig')

        # 查找需要的列
        product_col = None
        profit_col = None
        asset_col = None

        for col in df.columns:
            if '产品名称' in col:
                product_col = col
            elif '当日盈亏' in col:
                profit_col = col
            elif '总资产' in col:
                asset_col = col

        if not all([product_col, profit_col, asset_col]):
            return pd.DataFrame()

        # 提取需要的数据
        result_df = df[[product_col, profit_col, asset_col]].copy()
        result_df.columns = ['product_name', 'daily_profit', 'total_asset']

        # 数据类型转换
        result_df['daily_profit'] = pd.to_numeric(result_df['daily_profit'], errors='coerce')
        result_df['total_asset'] = pd.to_numeric(result_df['total_asset'], errors='coerce')

        # 计算当日收益率
        result_df['daily_return'] = (result_df['daily_profit'] / result_df['total_asset'] * 100).fillna(0)

        return result_df

    except Exception as e:
        print(f"读取资产文件失败: {e}")
        return pd.DataFrame()


def get_product_return_from_holdings(product_name, data_source="实盘", db=None):
    """从资产文件获取产品收益率（包含期货）- 修正出入金调整逻辑"""
    try:
        print(f"🔍 开始计算收益率:")
        print(f"  - 产品名称: {product_name}")
        print(f"  - 数据源: {data_source}")

        if product_name == "瑞幸1号":
            return calculate_ruixing_return(product_name, db)

        base_path = DATA_PATHS[data_source]

        if not os.path.exists(base_path):
            print(f"❌ 路径不存在: {base_path}")
            return None

        # 获取所有日期文件夹并排序
        all_items = os.listdir(base_path)
        date_folders = [f for f in all_items
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(base_path, f))]

        if len(date_folders) < 2:
            print(f"❌ 日期文件夹不足2个")
            return None

        date_folders.sort(reverse=True)
        today_folder = date_folders[0]  # 如：20250708
        yesterday_folder = date_folders[1]  # 如：20250707

        print(f"  - 今日: {today_folder}, 昨日: {yesterday_folder}")

        # 获取今天的总资产（现货+期货）
        today_assets = get_latest_asset_data_by_folder(base_path, today_folder)
        today_futures = get_latest_futures_data_by_date(today_folder, data_source)
        today_combined = combine_assets_and_futures(today_assets, today_futures)

        # 获取昨天的总资产（现货+期货）
        yesterday_assets = get_latest_asset_data_by_folder(base_path, yesterday_folder)
        yesterday_futures = get_latest_futures_data_by_date(yesterday_folder, data_source)
        yesterday_combined = combine_assets_and_futures(yesterday_assets, yesterday_futures)

        if today_combined is None or yesterday_combined is None:
            print("❌ 合并数据失败")
            return None

        # 查找具体产品的资产
        today_product = today_combined[today_combined['产品名称'] == product_name]
        yesterday_product = yesterday_combined[yesterday_combined['产品名称'] == product_name]

        if today_product.empty or yesterday_product.empty:
            print(f"❌ 产品匹配失败")
            print(f"  - 今日可用产品: {today_combined['产品名称'].tolist()}")
            print(f"  - 昨日可用产品: {yesterday_combined['产品名称'].tolist()}")
            return None

        # 获取今日和昨日的总资产
        today_total_asset = today_product['真实总资产'].iloc[0]
        yesterday_total_asset = yesterday_product['真实总资产'].iloc[0]

        print(f"💰 资产数据:")
        print(f"  - 今日总资产: {today_total_asset:,.0f}")
        print(f"  - 昨日总资产: {yesterday_total_asset:,.0f}")

        # 获取今日出入金数据
        total_outflow = 0  # 出金总额
        total_inflow = 0  # 入金总额

        if db is not None:
            today_date_str = f"{today_folder[:4]}-{today_folder[4:6]}-{today_folder[6:8]}"
            print(f"📅 查询出入金日期: {today_date_str}")

            try:
                # 获取今日的所有出入金记录
                cash_flows = db.get_cash_flows_by_unit(product_name)
                today_flows = cash_flows[cash_flows['日期'] == today_date_str]

                if not today_flows.empty:
                    total_inflow = today_flows[today_flows['类型'] == 'inflow']['金额'].sum()
                    total_outflow = today_flows[today_flows['类型'] == 'outflow']['金额'].sum()

                print(f"💸 出入金数据:")
                print(f"  - 今日入金: {total_inflow:,.0f}")
                print(f"  - 今日出金: {total_outflow:,.0f}")

            except Exception as e:
                print(f"❌ 获取出入金失败: {e}")
                total_inflow = 0
                total_outflow = 0
        else:
            print("⚠️ 未提供DB对象，跳过出入金调整")

        # ✅ 修正的收益率计算逻辑
        # 原始收益 = 今日总资产 - 昨日总资产
        raw_return = today_total_asset - yesterday_total_asset

        # 调整逻辑：
        # 如果今天出金，说明资产减少不是因为亏损，需要加回来
        # 如果今天入金，说明资产增加不是因为盈利，需要减去
        # 调整后收益 = 原始收益 + 出金 - 入金
        adjusted_return = raw_return + total_outflow - total_inflow

        print(f"📈 收益率计算:")
        print(f"  - 原始收益: {raw_return:,.0f}")
        print(f"  - 出金调整: +{total_outflow:,.0f}")
        print(f"  - 入金调整: -{total_inflow:,.0f}")
        print(f"  - 调整后收益: {adjusted_return:,.0f}")

        if yesterday_total_asset <= 0:
            print("❌ 昨日总资产为0或负数")
            return None

        return_rate = (adjusted_return / (yesterday_total_asset - total_outflow + total_inflow)) * 100
        print(f"  - 最终收益率: {return_rate:.4f}%")

        return return_rate

    except Exception as e:
        print(f"❌ 计算收益率异常: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return None


def get_latest_asset_data_by_folder(base_path, date_folder,data_source="实盘"):
    """获取指定日期文件夹中最新的资产数据"""
    try:
        folder_path = os.path.join(base_path, date_folder)
        asset_files = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 根据数据源匹配不同的文件名
                file_matched = False
                time_part = ""

                if data_source == "仿真":
                    # 仿真支持两种资产文件格式
                    if file.startswith("单元账户层资产资产导出") and file.endswith('.xlsx'):
                        time_part = file.replace('单元账户层资产资产导出_', '').replace('.xlsx', '')
                        file_matched = True
                    elif file.startswith("单元资产账户资产导出") and file.endswith('.xlsx'):
                        time_part = file.replace('单元资产账户资产导出_', '').replace('.xlsx', '')
                        file_matched = True
                else:
                    # 实盘保持原格式
                    if file.startswith("单元资产账户资产导出") and file.endswith('.xlsx'):
                        time_part = file.replace('单元资产账户资产导出_', '').replace('.xlsx', '')
                        file_matched = True

                if file_matched:
                    file_path = os.path.join(root, file)
                    try:
                        timestamp = datetime.strptime(time_part, "%Y%m%d-%H%M%S")
                        asset_files.append({'file_path': file_path, 'timestamp': timestamp})
                    except:
                        continue

        if not asset_files:
            return None

        # 选择最新的文件
        latest_file = max(asset_files, key=lambda x: x['timestamp'])

        # 读取数据
        from components.product_returns import read_total_assets_from_holding_file
        return read_total_assets_from_holding_file(latest_file['file_path'])

    except:
        return None


def get_latest_futures_data_by_date(target_date, data_source="实盘"):
    """获取指定日期的最新期货数据"""
    try:
        # 仿真不需要期货数据，直接返回None
        if data_source == "仿真":
            return None

        futures_dir = r"C:\shared_data\期货"

        if not os.path.exists(futures_dir):
            return None

        # 解析所有期货文件
        all_futures_files = []

        for file in os.listdir(futures_dir):
            if file.startswith("期货资产导出_") and file.endswith('.xls'):
                try:
                    # 解析文件名中的日期和时间
                    time_part = file.replace('期货资产导出_', '').replace('.xls', '')
                    timestamp = datetime.strptime(time_part, '%Y%m%d-%H%M%S')
                    file_date = timestamp.strftime('%Y%m%d')

                    all_futures_files.append({
                        'file_path': os.path.join(futures_dir, file),
                        'timestamp': timestamp,
                        'file_date': file_date,
                        'filename': file
                    })
                except:
                    continue

        if not all_futures_files:
            return None

        if target_date == max([f['file_date'] for f in all_futures_files]):
            # 如果是最新日期，选择所有文件中时间最新的
            latest_file = max(all_futures_files, key=lambda x: x['timestamp'])
        else:
            # 如果是历史日期，选择该日期最晚的文件
            target_date_files = [f for f in all_futures_files if f['file_date'] == target_date]

            if not target_date_files:
                # 如果今天没有期货文件，用最新的期货文件
                latest_file = max(all_futures_files, key=lambda x: x['timestamp'])
            else:
                latest_file = max(target_date_files, key=lambda x: x['timestamp'])

        # 读取数据
        from components.product_returns import read_futures_assets_from_file
        return read_futures_assets_from_file(latest_file['file_path'])

    except Exception as e:
        return None

# 在 realtime_heatmap.py 中添加出入金获取功能
def get_cash_flow_for_date(unit_name, date, db):
    """获取指定单元和日期的净出入金"""
    return db.get_cash_flow_by_date(unit_name, date)


def get_product_return_with_cash_flow_adjustment(product_name, data_source="实盘", db=None):
    """计算调整出入金后的收益率"""
    # 1. 获取今日和昨日的总资产（股票+期货）
    today_total_asset = get_today_total_asset(product_name, data_source)
    yesterday_total_asset = get_yesterday_total_asset(product_name, data_source)

    # 2. 获取今日净出入金
    today_date = datetime.now().strftime('%Y%m%d')
    net_cash_flow = db.get_cash_flow_by_date(product_name, today_date) if db else 0

    # 3. 计算调整后收益
    adjusted_return = today_total_asset - yesterday_total_asset + net_cash_flow

    # 4. 计算收益率
    if yesterday_total_asset > 0:
        return_rate = (adjusted_return / yesterday_total_asset) * 100
    else:
        return_rate = 0

    return return_rate


def calculate_ruixing_return(product_name, db=None):
    """
    瑞幸1号专用收益率计算函数（包含期货）
    """
    try:
        print(f"🎯 开始计算瑞幸1号收益率（包含期货）...")

        # 导入瑞幸1号数据读取器
        from .ruixing_data_reader import (
            get_current_trading_date,
            get_previous_trading_date,
            get_ruixing_total_assets_with_futures
        )

        # 获取交易日
        today_trading_date = get_current_trading_date()
        if not today_trading_date:
            print("❌ 无法确定当前交易日")
            return None

        yesterday_trading_date = get_previous_trading_date(today_trading_date)
        if not yesterday_trading_date:
            print("❌ 无法确定前一交易日")
            return None

        # 🎯 获取总资产（现货+期货），传入期货数据读取函数
        today_total_asset, yesterday_total_asset = get_ruixing_total_assets_with_futures(
            today_trading_date,
            yesterday_trading_date,
            get_latest_futures_data_by_date  # 使用现有的期货数据读取函数
        )

        if today_total_asset is None or yesterday_total_asset is None:
            print("❌ 无法获取瑞幸1号总资产数据")
            return None

        # 获取今日出入金数据（与其他产品逻辑相同）
        total_outflow = 0
        total_inflow = 0

        if db is not None:
            # 注意：这里使用实际的今天日期来查询出入金，而不是交易日
            # 因为出入金可能在非交易日发生
            today_date = datetime.now().strftime('%Y-%m-%d')
            print(f"📅 查询出入金日期: {today_date}")

            try:
                cash_flows = db.get_cash_flows_by_unit(product_name)
                today_flows = cash_flows[cash_flows['日期'] == today_date]

                if not today_flows.empty:
                    total_inflow = today_flows[today_flows['类型'] == 'inflow']['金额'].sum()
                    total_outflow = today_flows[today_flows['类型'] == 'outflow']['金额'].sum()

                print(f"💸 出入金数据:")
                print(f"  - 今日入金: {total_inflow:,.0f}")
                print(f"  - 今日出金: {total_outflow:,.0f}")

            except Exception as e:
                print(f"❌ 获取出入金失败: {e}")
                total_inflow = 0
                total_outflow = 0
        else:
            print("⚠️ 未提供DB对象，跳过出入金调整")

        # 收益率计算逻辑（与其他产品相同）
        raw_return = today_total_asset - yesterday_total_asset
        adjusted_return = raw_return + total_outflow - total_inflow

        print(f"📈 收益率计算:")
        print(f"  - 原始收益: {raw_return:,.0f}")
        print(f"  - 出金调整: +{total_outflow:,.0f}")
        print(f"  - 入金调整: -{total_inflow:,.0f}")
        print(f"  - 调整后收益: {adjusted_return:,.0f}")

        if yesterday_total_asset <= 0:
            print("❌ 前一交易日总资产为0或负数")
            return None

        return_rate = (adjusted_return / yesterday_total_asset) * 100
        print(f"  - 最终收益率: {return_rate:.4f}%")

        return return_rate

    except Exception as e:
        print(f"❌ 计算瑞幸1号收益率异常: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return None