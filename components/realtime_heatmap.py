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

# 固定数据路径
BASE_DATA_PATH = r"C:\shared_data\实盘\交易数据定频导出"


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
        colorscale = 'Greens'  # 改为正向绿色系

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


def get_latest_holding_files():
    """获取每个产品最新的持仓文件"""
    try:
        if not os.path.exists(BASE_DATA_PATH):
            return {}

        # 获取所有日期文件夹并排序，选择最新的
        date_folders = [f for f in os.listdir(BASE_DATA_PATH)
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(BASE_DATA_PATH, f))]

        if not date_folders:
            return {}

        latest_date_folder = max(date_folders)
        date_folder_path = os.path.join(BASE_DATA_PATH, latest_date_folder)

        # 递归查找所有持仓文件
        all_files = []
        for root, dirs, files in os.walk(date_folder_path):
            for file in files:
                if file.startswith("单元资产账户持仓导出") and (file.endswith('.xlsx') or file.endswith('.csv')):
                    all_files.append(os.path.join(root, file))

        # 按产品分组文件
        product_files = {}
        for file_path in all_files:
            filename = os.path.basename(file_path)
            # 解析文件名：单元资产账户持仓导出_东财EMC_普通_20250625-123500
            # 或：单元资产账户持仓导出_开源ATX_普通1_20250625-121200

            # 移除前缀
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
            'file_count': sum(len(files) for files in product_files.values())
        }

    except Exception as e:
        st.error(f"读取文件夹失败: {e}")
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

    # 显示数据路径
    st.info(f"数据路径: {BASE_DATA_PATH}")

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
    file_info = get_latest_holding_files()

    if not file_info or not file_info.get('files'):
        st.error("未找到持仓文件")
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
        st.warning("未找到与数据库匹配的产品数据")
        st.info("请确保文件中的产品名称与数据库中的产品名称一致")
        return

    # 产品选择下拉框
    selected_product_name = st.selectbox(
        "选择要分析的产品",
        options=matched_products,
        key="realtime_product_selector"
    )

    if selected_product_name and selected_product_name in all_data:
        product_data = all_data[selected_product_name]

        # 显示数据概况
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("持仓股票数", len(product_data))

        with col2:
            total_value = product_data['market_value'].sum()
            st.metric("总市值", f"{total_value:,.0f}")

        with col3:
            # 使用持仓文件计算准确的当日收益率
            actual_return = get_product_return_from_holdings(selected_product_name)
            if actual_return is not None:
                st.metric("当日收益率", f"{actual_return:.2f}%")
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
                key="heatmap_mode"
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

            # 数据预览表格（移到最后）
            st.divider()
            st.subheader("数据预览")
            display_df = product_data[['stock_name', 'stock_code', 'change_pct', 'market_value']].copy()
            display_df['change_pct'] = display_df['change_pct'].apply(lambda x: f"{x:.2f}%")
            display_df['market_value'] = display_df['market_value'].apply(lambda x: f"{x:,.0f}")
            display_df.columns = ['股票名称', '股票代码', '涨跌幅', '市值']
            #st.dataframe(display_df, use_container_width=True, hide_index=True)

    # 自动刷新逻辑
    if auto_refresh:
        time.sleep(300)  # 5分钟
        st.rerun()

    last_update.write(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def get_latest_asset_files():
    """获取最新的资产导出文件"""
    try:
        if not os.path.exists(BASE_DATA_PATH):
            return {}

        # 获取最新日期文件夹
        date_folders = [f for f in os.listdir(BASE_DATA_PATH)
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(BASE_DATA_PATH, f))]

        if not date_folders:
            return {}

        latest_date_folder = max(date_folders)
        date_folder_path = os.path.join(BASE_DATA_PATH, latest_date_folder)

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
        print(f"读取资产文件失败: {e}")
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


def get_product_return_from_holdings(product_name):
    """从资产文件获取产品收益率（包含期货）"""
    try:
        base_path = r"C:\shared_data\实盘\交易数据定频导出"

        if not os.path.exists(base_path):
            return None

        # 获取所有日期文件夹并排序
        all_items = os.listdir(base_path)
        date_folders = [f for f in all_items
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(base_path, f))]

        if len(date_folders) < 2:
            return None

        date_folders.sort(reverse=True)
        today_folder = date_folders[0]
        yesterday_folder = date_folders[1]

        # 获取今天的数据
        today_assets = get_latest_asset_data_by_folder(base_path, today_folder)
        today_futures = get_latest_futures_data_by_date(today_folder)

        # 获取昨天的数据
        yesterday_assets = get_latest_asset_data_by_folder(base_path, yesterday_folder)
        yesterday_futures = get_latest_futures_data_by_date(yesterday_folder)

        # 合并现货和期货数据
        from components.product_returns import combine_assets_and_futures

        today_combined = combine_assets_and_futures(today_assets, today_futures)
        yesterday_combined = combine_assets_and_futures(yesterday_assets, yesterday_futures)

        if today_combined is None or yesterday_combined is None:
            return None

        # 查找产品
        today_product = today_combined[today_combined['产品名称'] == product_name]
        yesterday_product = yesterday_combined[yesterday_combined['产品名称'] == product_name]

        if today_product.empty or yesterday_product.empty:
            return None

        # 计算收益率
        today_asset = today_product['真实总资产'].iloc[0]
        yesterday_asset = yesterday_product['真实总资产'].iloc[0]

        return (today_asset / yesterday_asset - 1) * 100

    except Exception as e:
        return None


def get_latest_asset_data_by_folder(base_path, date_folder):
    """获取指定日期文件夹中最新的资产数据"""
    try:
        folder_path = os.path.join(base_path, date_folder)
        asset_files = []

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.startswith("单元资产账户资产导出") and file.endswith('.xlsx'):
                    file_path = os.path.join(root, file)
                    try:
                        time_part = file.replace('单元资产账户资产导出_', '').replace('.xlsx', '')
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


def get_latest_futures_data_by_date(target_date):
    """获取指定日期的最新期货数据"""
    try:
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
                return None

            latest_file = max(target_date_files, key=lambda x: x['timestamp'])

        # 读取数据
        from components.product_returns import read_futures_assets_from_file
        return read_futures_assets_from_file(latest_file['file_path'])

    except Exception as e:
        return None