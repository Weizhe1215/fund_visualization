"""
周度汇总组件 (改进版)
计算自定义日期范围内仿真+实盘产品的收益率并进行可视化对比
"""
import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta, date
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_custom_date_range(start_date=None, end_date=None):
    """
    获取自定义日期范围内的交易日期范围

    Args:
        start_date: 开始日期，如果为None则使用本周一
        end_date: 结束日期，如果为None则使用本周五

    Returns:
        tuple: (period_start, period_end, trading_dates_list)
    """
    # 如果没有提供日期，则默认使用本周
    if start_date is None or end_date is None:
        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=4)  # 周五

        if start_date is None:
            start_date = week_start
        if end_date is None:
            end_date = week_end

    # 确保日期格式正确
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # 生成日期范围内的所有日期（只包括工作日）
    trading_dates = []
    current_date = start_date
    while current_date <= end_date:
        # 只包括周一到周五的工作日
        if current_date.weekday() < 5:  # 0-4 表示周一到周五
            trading_dates.append(current_date)
        current_date += timedelta(days=1)

    return start_date, end_date, trading_dates


def get_available_asset_files_for_period(trading_dates, data_sources=["实盘", "仿真"]):
    """
    获取指定日期范围内交易日的可用资产文件（自动跳过节假日）

    Args:
        trading_dates: 交易日期列表
        data_sources: 数据源列表

    Returns:
        dict: {date_str: {source: file_path}} - 只包含有数据的日期
    """
    # 数据路径配置
    data_paths = {
        "实盘": r"C:\shared_data\实盘\交易数据定频导出",
        "仿真": r"C:\shared_data\仿真\交易数据定频导出"
    }

    available_files = {}

    for date_obj in trading_dates:
        date_str = date_obj.strftime('%Y%m%d')
        date_key = date_obj.strftime('%Y-%m-%d')

        # 检查这一天是否有任何数据源的文件
        day_has_data = False
        day_files = {}

        for source in data_sources:
            base_path = data_paths.get(source)
            if not base_path or not os.path.exists(base_path):
                continue

            # 检查该日期的文件夹是否存在
            date_folder = os.path.join(base_path, date_str)
            if not os.path.exists(date_folder):
                continue

            # 查找最新的资产导出文件
            asset_files = []
            for root, dirs, files in os.walk(date_folder):
                for file in files:
                    # 根据数据源匹配文件 - 使用与realtime_heatmap相同的规则
                    file_matched = False
                    if source == "仿真":
                        # 仿真支持两种资产文件格式（与realtime_heatmap一致）
                        if (file.startswith("单元账户层资产资产导出") and file.endswith('.xlsx')) or \
                           (file.startswith("单元资产账户资产导出") and (file.endswith('.xlsx') or file.endswith('.csv'))):
                            file_matched = True
                    else:
                        # 实盘保持原格式
                        if file.startswith("单元资产账户资产导出") and (file.endswith('.xlsx') or file.endswith('.csv')):
                            file_matched = True

                    if file_matched:
                        file_path = os.path.join(root, file)

                        # 解析时间戳 - 支持两种仿真格式
                        try:
                            filename = os.path.basename(file_path)
                            if source == "仿真" and filename.startswith("单元账户层资产资产导出"):
                                time_part = filename.replace('单元账户层资产资产导出_', '').replace('.xlsx', '').replace('.csv', '')
                            else:
                                time_part = filename.replace('单元资产账户资产导出_', '').replace('.xlsx', '').replace('.csv', '')

                            timestamp = datetime.strptime(time_part, "%Y%m%d-%H%M%S")
                            asset_files.append({
                                'file_path': file_path,
                                'timestamp': timestamp
                            })
                        except Exception as e:
                            print(f"解析文件时间戳失败 {filename}: {e}")
                            continue

            # 选择最新的文件
            if asset_files:
                latest_file = max(asset_files, key=lambda x: x['timestamp'])
                day_files[source] = latest_file['file_path']
                day_has_data = True

        # 只有当这一天有数据时才添加到结果中
        if day_has_data:
            available_files[date_key] = day_files

    return available_files


def read_asset_file_for_period_analysis(file_path):
    """
    读取资产文件并提取周期分析需要的数据
    支持实盘和仿真的不同文件格式

    Args:
        file_path: 资产文件路径

    Returns:
        pd.DataFrame: 包含产品名称、总资产、当日盈亏的数据
    """
    try:
        if file_path.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path, encoding='utf-8-sig')

        print(f"读取文件: {os.path.basename(file_path)}")
        print(f"文件列名: {list(df.columns)}")

        # 查找需要的列 - 适配不同的列名格式
        product_col = None
        total_asset_col = None
        daily_profit_col = None

        for col in df.columns:
            col_str = str(col)
            if '产品名称' in col_str:
                product_col = col
            elif col_str == '总资产':  # 精确匹配避免"昨日总资产"等
                total_asset_col = col
            elif '当日盈亏' in col_str:
                daily_profit_col = col

        if not product_col or not total_asset_col:
            print(f"缺少必要列: product_col={product_col}, total_asset_col={total_asset_col}")
            print(f"可用列: {list(df.columns)}")
            return pd.DataFrame()

        # 提取需要的列
        columns_to_extract = [product_col, total_asset_col]
        column_names = ['product_name', 'total_asset']

        if daily_profit_col:
            columns_to_extract.append(daily_profit_col)
            column_names.append('daily_profit')

        result_df = df[columns_to_extract].copy()
        result_df.columns = column_names

        # 数据清理
        result_df['product_name'] = result_df['product_name'].astype(str)
        result_df['total_asset'] = pd.to_numeric(result_df['total_asset'], errors='coerce')

        if 'daily_profit' in result_df.columns:
            result_df['daily_profit'] = pd.to_numeric(result_df['daily_profit'], errors='coerce')
        else:
            result_df['daily_profit'] = 0  # 如果没有当日盈亏列，设为0

        # 删除无效数据
        result_df = result_df.dropna(subset=['product_name', 'total_asset'])
        result_df = result_df[result_df['product_name'] != '']
        result_df = result_df[result_df['total_asset'] > 0]

        # 按产品名称分组，合并多个账户的数据
        result_df = result_df.groupby('product_name').agg({
            'total_asset': 'sum',
            'daily_profit': 'sum'
        }).reset_index()

        print(f"成功读取产品: {result_df['product_name'].tolist()}")

        return result_df

    except Exception as e:
        print(f"读取文件失败 {os.path.basename(file_path)}: {e}")
        st.error(f"读取文件失败 {os.path.basename(file_path)}: {e}")
        return pd.DataFrame()


def calculate_period_returns_from_nav(period_files, db, period_start, period_end):
    """
    直接从净值数据计算指定周期内各产品的收益率
    重新设计：分别从实盘和仿真文件夹读取，生成不同的display_name

    Args:
        period_files: 周期内可用文件字典
        db: 数据库对象
        period_start: 周期开始日期
        period_end: 周期结束日期

    Returns:
        dict: {display_name: {date: {nav_value, daily_return, cumulative_return, source}}}
    """
    period_data = {}

    # 获取所有产品
    products = db.get_products()
    if not products:
        return period_data

    # 为每个产品和数据源组合计算收益率
    for product in products:
        product_code = product['product_code']
        product_name = product['product_name']

        # 读取该产品的净值数据
        nav_data = db.get_nav_data(product_code)

        if nav_data.empty:
            continue

        # 转换日期格式并排序
        nav_data['date'] = pd.to_datetime(nav_data['date'])
        nav_data = nav_data.sort_values('date')

        # 获取指定周期及前一个交易日的净值数据（用于计算收益率）
        period_start_dt = pd.to_datetime(period_start)
        period_end_dt = pd.to_datetime(period_end)

        # 包含期间开始前一个交易日，用于计算基准点
        extended_start = period_start_dt - pd.Timedelta(days=7)  # 向前扩展7天确保包含基准点

        # 筛选相关日期的数据
        relevant_data = nav_data[
            (nav_data['date'] >= extended_start) &
            (nav_data['date'] <= period_end_dt)
        ].copy()

        if relevant_data.empty:
            continue

        # 分别处理实盘和仿真数据源
        for data_source in ["实盘", "仿真"]:
            # 检查该产品是否在当前数据源中有数据
            product_found_in_source = False

            for date_key, files in period_files.items():
                if data_source in files:
                    try:
                        asset_data = read_asset_file_for_period_analysis(files[data_source])
                        if not asset_data.empty and product_name in asset_data['product_name'].values:
                            product_found_in_source = True
                            break
                    except:
                        continue

            # 如果该产品在此数据源中没有数据，跳过
            if not product_found_in_source:
                continue

            # 设置显示名称
            if data_source == "仿真":
                display_name = f"{product_name}(仿真)"
            else:
                display_name = product_name

            # 先获取所有相关数据
            all_nav_data = {}

            for i, row in relevant_data.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                nav_value = row['nav_value']

                # 计算日收益率（相对于前一个净值）
                if i == 0:
                    daily_return = 0
                else:
                    prev_nav = list(all_nav_data.values())[-1]['nav_value'] if all_nav_data else nav_value
                    if prev_nav > 0:
                        daily_return = (nav_value / prev_nav - 1) * 100
                    else:
                        daily_return = 0

                all_nav_data[date_str] = {
                    'nav_value': nav_value,
                    'daily_return': daily_return,
                    'source': data_source
                }

            # 只保留指定周期内的数据
            period_data_filtered = {}
            period_dates = []

            for date_str, data in all_nav_data.items():
                date_obj = pd.to_datetime(date_str).date()
                if period_start <= date_obj <= period_end:
                    period_data_filtered[date_str] = data
                    period_dates.append(date_str)

            # 重新计算累积收益率 - 从周期第一天开始归一化为0
            if period_data_filtered and period_dates:
                # 按日期排序
                sorted_period_dates = sorted(period_dates)

                # 获取周期第一天的净值作为基准
                first_date = sorted_period_dates[0]
                base_nav = period_data_filtered[first_date]['nav_value']

                # 重新计算每一天的累积收益率（相对于周期第一天）
                for date_str in sorted_period_dates:
                    current_nav = period_data_filtered[date_str]['nav_value']

                    if base_nav > 0:
                        # 从周期开始日归一化计算累积收益率
                        period_data_filtered[date_str]['cumulative_return'] = (current_nav / base_nav - 1) * 100
                    else:
                        period_data_filtered[date_str]['cumulative_return'] = 0

                period_data[display_name] = period_data_filtered

    return period_data


def filter_products_with_complete_data(period_data, min_days=1):
    """
    筛选有足够数据的产品（至少有min_days天的数据，考虑节假日）

    Args:
        period_data: 周期数据字典
        min_days: 最少天数要求（默认1天，因为要考虑节假日）

    Returns:
        dict: 筛选后的周期数据
    """
    filtered_data = {}

    for product_name, product_data in period_data.items():
        # 检查该产品有多少天的数据
        valid_days = len([d for d, data in product_data.items()
                         if data['nav_value'] > 0])

        if valid_days >= min_days:
            filtered_data[product_name] = product_data
        else:
            print(f"产品 {product_name} 数据不足，只有 {valid_days} 天，需要至少 {min_days} 天")

    return filtered_data


def render_date_range_selector():
    """
    渲染日期范围选择器

    Returns:
        tuple: (start_date, end_date, period_type_name)
    """
    st.subheader("📅 选择对比周期")

    # 创建两列：快速选择和自定义选择
    col_quick, col_custom = st.columns([1, 1])

    with col_quick:
        st.write("**快速选择**")

        # 预设周期选项
        quick_options = {
            "本周": "this_week",
            "上周": "last_week",
            "上上周": "two_weeks_ago",
            "最近3天": "last_3_days",
            "最近5天": "last_5_days",
            "自定义周期": "custom"
        }

        selected_option = st.selectbox(
            "选择周期",
            options=list(quick_options.keys()),
            key="period_selector"
        )

        # 根据选择计算日期范围
        today = datetime.now().date()

        if selected_option == "本周":
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            # 本周从上周五开始，到本周五结束
            start_date = this_monday - timedelta(days=3)  # 上周五
            end_date = this_monday + timedelta(days=4)    # 本周五
            period_name = "本周"

        elif selected_option == "上周":
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            last_monday = this_monday - timedelta(days=7)
            # 上周从上上周五开始，到上周五结束
            start_date = last_monday - timedelta(days=3)  # 上上周五
            end_date = last_monday + timedelta(days=4)    # 上周五
            period_name = "上周"

        elif selected_option == "上上周":
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            two_weeks_ago_monday = this_monday - timedelta(days=14)
            # 上上周从三周前的周五开始，到上上周五结束
            start_date = two_weeks_ago_monday - timedelta(days=3)  # 三周前周五
            end_date = two_weeks_ago_monday + timedelta(days=4)    # 上上周五
            period_name = "上上周"

        elif selected_option == "最近3天":
            end_date = today
            start_date = today - timedelta(days=2)
            period_name = "最近3天"

        elif selected_option == "最近5天":
            end_date = today
            start_date = today - timedelta(days=4)
            period_name = "最近5天"

        else:  # 自定义周期
            start_date = None
            end_date = None
            period_name = "自定义周期"

    with col_custom:
        st.write("**自定义日期范围**")

        # 自定义日期选择器
        if selected_option == "自定义周期":
            # 默认值设为本周
            days_since_monday = today.weekday()
            default_start = today - timedelta(days=days_since_monday)
            default_end = default_start + timedelta(days=4)

            custom_start = st.date_input(
                "开始日期",
                value=default_start,
                key="custom_start_date"
            )

            custom_end = st.date_input(
                "结束日期",
                value=default_end,
                key="custom_end_date"
            )

            # 验证日期范围
            if custom_start <= custom_end:
                start_date = custom_start
                end_date = custom_end
                period_name = f"{start_date.strftime('%m-%d')} 至 {end_date.strftime('%m-%d')}"
            else:
                st.error("开始日期不能晚于结束日期")
                start_date = custom_end
                end_date = custom_start
                period_name = "日期错误"
        else:
            # 显示当前选择的日期范围
            if start_date and end_date:
                st.info(f"📅 {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")

                # 显示包含的交易日数量
                _, _, trading_dates = get_custom_date_range(start_date, end_date)
                st.info(f"📊 包含 {len(trading_dates)} 个交易日")

    return start_date, end_date, period_name


def classify_products_by_source(filtered_period_data, period_files):
    """
    根据数据实际来源分类产品为实盘/仿真
    逻辑：检查产品实际出现在实盘文件夹还是仿真文件夹的文件中

    Args:
        filtered_period_data: 筛选后的周期数据
        period_files: 周期文件字典 {date: {"实盘": file_path, "仿真": file_path}}

    Returns:
        tuple: (real_products, simulation_products)
    """
    real_products = []
    simulation_products = []

    # 分析每个产品在filtered_period_data中的数据来源
    for product_display_name, product_data in filtered_period_data.items():
        # 去除可能的仿真标识，获取基础产品名
        if product_display_name.endswith("(仿真)"):
            base_product_name = product_display_name.replace("(仿真)", "")
            expected_source = "仿真"
        else:
            base_product_name = product_display_name
            expected_source = "实盘"

        # 根据数据源记录的信息确定分类
        # 从product_data中获取source信息
        sample_date = list(product_data.keys())[0]
        actual_source = product_data[sample_date]['source']

        product_info = {
            'base_name': base_product_name,
            'display_name': product_display_name,
            'source': actual_source
        }

        if actual_source == "实盘":
            real_products.append(product_info)
        else:  # 仿真
            simulation_products.append(product_info)

    return real_products, simulation_products


def render_smart_product_selection(db, filtered_period_data, period_name, period_files):
    """
    智能产品选择界面 - 支持标签筛选、实盘/仿真分类、已选择管理

    Args:
        db: 数据库对象
        filtered_period_data: 筛选后的周期数据
        period_name: 周期名称
        period_files: 周期文件字典，用于判断产品来源

    Returns:
        list: 选中的产品列表
    """
    if not filtered_period_data:
        st.warning(f"{period_name}暂无可用的产品数据")
        return []

    st.subheader("🏷️ 智能产品选择")

    # 初始化已选择产品的session state
    selected_products_key = f"selected_products_{period_name}"
    if selected_products_key not in st.session_state:
        st.session_state[selected_products_key] = []

    # 第一行：标签筛选
    col_tag, col_info = st.columns([2, 1])

    with col_tag:
        from components.product_tags import render_tag_filter
        selected_tag = render_tag_filter(db, f"period_selection_{period_name}")

    with col_info:
        st.info(f"📊 {period_name} 可用产品: {len(filtered_period_data)}")

    # 根据文件来源分类产品
    real_products, simulation_products = classify_products_by_source(filtered_period_data, period_files)

    # 根据标签进一步筛选产品
    if selected_tag != "全部":
        # 获取该标签下的产品
        tagged_products = db.get_products_by_tag(selected_tag)
        tagged_product_names = [p['product_name'] for p in tagged_products]

        # 筛选实盘产品
        real_products = [p for p in real_products if p['base_name'] in tagged_product_names]
        # 筛选仿真产品
        simulation_products = [p for p in simulation_products if p['base_name'] in tagged_product_names]

    # 第二行：实盘/仿真产品选择
    col_real, col_sim = st.columns(2)

    with col_real:
        st.write("**🔴 实盘产品**")
        if real_products:
            for product in real_products:
                # 检查是否已选择
                is_selected = product['display_name'] in st.session_state[selected_products_key]

                if st.checkbox(
                    product['base_name'],
                    value=is_selected,
                    key=f"real_{product['base_name']}_{period_name}"
                ):
                    if product['display_name'] not in st.session_state[selected_products_key]:
                        st.session_state[selected_products_key].append(product['display_name'])
                else:
                    if product['display_name'] in st.session_state[selected_products_key]:
                        st.session_state[selected_products_key].remove(product['display_name'])

                # 显示收益率预览
                if product['display_name'] in filtered_period_data:
                    product_data = filtered_period_data[product['display_name']]
                    latest_date = max(product_data.keys())
                    latest_data = product_data[latest_date]
                    cumulative_return = latest_data['cumulative_return']

                    if cumulative_return > 0:
                        st.markdown(f"<small style='color: red'>📈 +{cumulative_return:.2f}%</small>",
                                   unsafe_allow_html=True)
                    elif cumulative_return < 0:
                        st.markdown(f"<small style='color: green'>📉 {cumulative_return:.2f}%</small>",
                                   unsafe_allow_html=True)
                    else:
                        st.markdown(f"<small style='color: gray'>➡️ {cumulative_return:.2f}%</small>",
                                   unsafe_allow_html=True)
        else:
            if selected_tag == "全部":
                st.info("该期间暂无实盘产品数据")
            else:
                st.info(f"标签 '{selected_tag}' 下暂无实盘产品")

    with col_sim:
        st.write("**🔵 仿真产品**")
        if simulation_products:
            for product in simulation_products:
                # 检查是否已选择
                is_selected = product['display_name'] in st.session_state[selected_products_key]

                if st.checkbox(
                    product['base_name'],
                    value=is_selected,
                    key=f"sim_{product['base_name']}_{period_name}"
                ):
                    if product['display_name'] not in st.session_state[selected_products_key]:
                        st.session_state[selected_products_key].append(product['display_name'])
                else:
                    if product['display_name'] in st.session_state[selected_products_key]:
                        st.session_state[selected_products_key].remove(product['display_name'])

                # 显示收益率预览
                if product['display_name'] in filtered_period_data:
                    product_data = filtered_period_data[product['display_name']]
                    latest_date = max(product_data.keys())
                    latest_data = product_data[latest_date]
                    cumulative_return = latest_data['cumulative_return']

                    if cumulative_return > 0:
                        st.markdown(f"<small style='color: red'>📈 +{cumulative_return:.2f}%</small>",
                                   unsafe_allow_html=True)
                    elif cumulative_return < 0:
                        st.markdown(f"<small style='color: green'>📉 {cumulative_return:.2f}%</small>",
                                   unsafe_allow_html=True)
                    else:
                        st.markdown(f"<small style='color: gray'>➡️ {cumulative_return:.2f}%</small>",
                                   unsafe_allow_html=True)
        else:
            if selected_tag == "全部":
                st.info("该期间暂无仿真产品数据")
            else:
                st.info(f"标签 '{selected_tag}' 下暂无仿真产品")

    # 第三行：已选择产品管理
    if st.session_state[selected_products_key]:
        st.write("**✅ 已选择的产品**")

        # 创建已选择产品的标签列表
        selected_cols = st.columns(min(len(st.session_state[selected_products_key]), 4))

        products_to_remove = []
        for i, selected_product in enumerate(st.session_state[selected_products_key]):
            col_index = i % len(selected_cols)

            with selected_cols[col_index]:
                # 判断产品类型并设置颜色
                if "(仿真)" in selected_product:
                    bg_color = "#e3f2fd"  # 浅蓝色
                    icon = "🔵"
                    clean_name = selected_product.replace("(仿真)", "")
                else:
                    bg_color = "#ffebee"  # 浅红色
                    icon = "🔴"
                    clean_name = selected_product

                # 显示已选择的产品标签
                st.markdown(
                    f'<div style="background-color: {bg_color}; '
                    f'padding: 8px; border-radius: 8px; margin: 2px 0; '
                    f'border: 1px solid #ddd;">'
                    f'<span style="font-size: 12px;">{icon} {clean_name}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # 移除按钮
                if st.button("❌", key=f"remove_{selected_product}_{period_name}",
                            help="移除该产品"):
                    products_to_remove.append(selected_product)

        # 移除被点击的产品
        for product_to_remove in products_to_remove:
            st.session_state[selected_products_key].remove(product_to_remove)
            st.rerun()

        # 快速操作按钮
        col_clear, col_count = st.columns([1, 2])

        with col_clear:
            if st.button("🗑️ 清空选择", key=f"clear_all_{period_name}"):
                st.session_state[selected_products_key] = []
                st.rerun()

        with col_count:
            st.info(f"已选择 {len(st.session_state[selected_products_key])} 个产品")

    else:
        st.info("💡 请选择要对比的产品")

    return st.session_state[selected_products_key]


def render_product_selection_checkboxes(filtered_weekly_data, period_name, period_files=None):
    """
    旧版产品选择界面（保持向后兼容）

    Args:
        filtered_weekly_data: 筛选后的周期数据
        period_name: 周期名称
        period_files: 周期文件字典（可选，用于兼容性）

    Returns:
        list: 选中的产品列表
    """
    # 直接调用新的智能产品选择界面
    if period_files is None:
        period_files = {}
    return render_smart_product_selection(st.session_state.db, filtered_weekly_data, period_name, period_files)


def create_period_comparison_chart(selected_products, filtered_period_data, period_start, period_end):
    """
    创建周期收益率对比图表

    Args:
        selected_products: 选中的产品列表
        filtered_period_data: 筛选后的周期数据
        period_start: 周期开始日期
        period_end: 周期结束日期

    Returns:
        plotly.graph_objects.Figure: 图表对象
    """
    if not selected_products:
        return None

    # 创建图表
    fig = go.Figure()

    # 获取所有产品共同的交易日期（有数据的日期）
    all_trading_dates = set()
    for product_name in selected_products:
        product_data = filtered_period_data[product_name]
        all_trading_dates.update(product_data.keys())

    # 按日期排序，作为横轴的交易日序列
    sorted_trading_dates = sorted(all_trading_dates)

    # 为每个选中的产品添加线条
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

    for i, product_name in enumerate(selected_products):
        product_data = filtered_period_data[product_name]

        # 准备数据 - 使用交易日索引而不是实际日期
        trading_day_indices = []  # 交易日序号 (第1天、第2天...)
        trading_day_labels = []   # 交易日标签 (用于悬停显示)
        cumulative_returns = []
        daily_returns = []
        nav_values = []

        for idx, date_key in enumerate(sorted_trading_dates):
            if date_key in product_data:
                data = product_data[date_key]

                # 交易日序号从1开始
                trading_day_indices.append(idx + 1)

                # 格式化日期标签（添加星期）
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][date_obj.weekday()]
                trading_day_labels.append(f"{date_key}<br>({weekday_name})")

                cumulative_returns.append(data['cumulative_return'])
                daily_returns.append(data['daily_return'])
                nav_values.append(data['nav_value'])

        # 添加线条 - 横轴使用交易日序号
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=trading_day_indices,
            y=cumulative_returns,
            mode='lines+markers',
            name=product_name,
            line=dict(color=color, width=2),
            marker=dict(size=6),
            customdata=list(zip(trading_day_labels, daily_returns, nav_values)),
            hovertemplate=(
                f"<b>{product_name}</b><br>" +
                "日期: %{customdata[0]}<br>" +
                "累积收益率: %{y:.2f}%<br>" +
                "当日收益率: %{customdata[1]:.2f}%<br>" +
                "净值: %{customdata[2]:.4f}<br>" +
                "<extra></extra>"
            )
        ))

    # 更新图表布局
    fig.update_layout(
        title=f"📊 收益率对比图表 ({period_start.strftime('%Y-%m-%d')} 至 {period_end.strftime('%Y-%m-%d')})",
        hovermode='closest',
        height=500,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Arial, sans-serif", size=12),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='rgba(128,128,128,0.5)',
            borderwidth=1
        ),
        margin=dict(l=50, r=150, t=80, b=50)
    )

    # 更新X轴配置 - 设置交易日标签
    fig.update_xaxes(
        title="交易日",
        showgrid=True,
        gridcolor='rgba(128,128,128,0.3)',
        tickmode='array',
        tickvals=list(range(1, len(sorted_trading_dates) + 1)),
        ticktext=[f"T{i}" for i in range(1, len(sorted_trading_dates) + 1)],  # T1, T2, T3...
        tickangle=0
    )

    # 更新Y轴配置
    fig.update_yaxes(
        title="累积收益率 (%)",
        showgrid=True,
        gridcolor='rgba(128,128,128,0.3)',
        zeroline=True,
        zerolinecolor='rgba(128,128,128,0.8)',
        zerolinewidth=2
    )

    fig.update_layout(
        hovermode='closest',
        height=500,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Arial, sans-serif", size=12),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='rgba(128,128,128,0.5)',
            borderwidth=1
        ),
        margin=dict(l=50, r=150, t=80, b=50)
    )

    return fig


def render_period_summary_page(db):
    """
    渲染改进版周期汇总主页面

    Args:
        db: 数据库对象
    """
    st.header("📊 周期收益对比")
    st.markdown("*选择任意日期范围，分析产品收益率表现*")

    # 渲染日期选择器
    period_start, period_end, period_name = render_date_range_selector()

    if not period_start or not period_end:
        st.warning("请选择有效的日期范围")
        return

    # 显示选择的周期信息
    st.divider()

    # 获取交易日期和数据文件
    _, _, trading_dates = get_custom_date_range(period_start, period_end)

    # 显示周期信息
    col_info1, col_info2, col_refresh = st.columns([1, 1, 1])

    with col_info1:
        st.info(f"📅 分析周期: {period_start.strftime('%Y-%m-%d')} ~ {period_end.strftime('%Y-%m-%d')}")

    with col_info2:
        st.info(f"📊 交易日: {len(trading_dates)} 天")

    with col_refresh:
        if st.button("🔄 刷新数据", type="primary"):
            # 清除缓存，强制重新计算
            keys_to_remove = [k for k in st.session_state.keys() if k.startswith('period_nav_data_')]
            for key in keys_to_remove:
                del st.session_state[key]
            st.rerun()

    # 显示数据获取进度
    with st.spinner(f"正在扫描{period_name}交易数据文件..."):
        period_files = get_available_asset_files_for_period(trading_dates)

    # 显示数据可用性统计
    st.subheader("📈 数据可用性")

    data_summary = []
    for date_obj in trading_dates:  # 遍历所有交易日
        date_key = date_obj.strftime('%Y-%m-%d')
        weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][date_obj.weekday()]

        files = period_files.get(date_key, {})
        has_shiPan = '实盘' in files
        has_fangzhen = '仿真' in files

        # 判断状态
        if has_shiPan and has_fangzhen:
            status = "✅ 完整"
        elif has_shiPan or has_fangzhen:
            status = "⚠️ 部分"
        else:
            status = "❌ 无数据 (节假日?)"

        data_summary.append({
            '日期': f"{date_key} ({weekday_name})",
            '实盘': "✅" if has_shiPan else "❌",
            '仿真': "✅" if has_fangzhen else "❌",
            '状态': status
        })

    if data_summary:
        summary_df = pd.DataFrame(data_summary)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # 显示数据统计
        available_days = len([d for d in period_files.keys()])
        total_trading_days = len(trading_dates)

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("可用交易日", f"{available_days}/{total_trading_days}")
        with col_stat2:
            coverage_rate = (available_days / total_trading_days * 100) if total_trading_days > 0 else 0
            st.metric("数据覆盖率", f"{coverage_rate:.1f}%")
        with col_stat3:
            if available_days == 0:
                st.metric("状态", f"❌ {period_name}无数据")
            elif available_days < total_trading_days:
                st.metric("状态", "⚠️ 数据不完整")
            else:
                st.metric("状态", "✅ 数据完整")

    # 计算周期收益率
    if not period_files:
        st.error(f"❌ {period_name}暂无可用交易数据文件，可能原因：")
        st.write(f"- {period_name}都是节假日")
        st.write("- 数据目录不存在或无权限访问")
        st.write("- 文件命名格式不正确")
        return

    with st.spinner(f"正在从净值数据计算{period_name}收益率..."):
        # 使用缓存避免重复计算
        cache_key = f"period_nav_data_{period_start}_{period_end}"

        if cache_key not in st.session_state:
            period_data = calculate_period_returns_from_nav(period_files, db, period_start, period_end)
            filtered_data = filter_products_with_complete_data(period_data, min_days=1)
            st.session_state[cache_key] = filtered_data
        else:
            filtered_data = st.session_state[cache_key]

    if not filtered_data:
        st.error(f"❌ {period_name}暂无有效的产品收益数据")
        st.info("💡 提示：即使有节假日，只要有1天的数据就可以显示")
        return

    st.success(f"✅ 成功获取 {len(filtered_data)} 个产品的{period_name}数据")

    # 渲染产品选择界面
    selected_products = render_smart_product_selection(db, filtered_data, period_name, period_files)

    # 如果有选中的产品，创建对比图表
    if selected_products:
        st.divider()
        st.subheader("📊 收益率对比图表")

        # 创建图表
        fig = create_period_comparison_chart(selected_products, filtered_data, period_start, period_end)

        if fig:
            st.plotly_chart(fig, use_container_width=True)

            # 显示详细统计表
            st.subheader("📋 详细统计")

            # 为每个选中的产品创建详细的每日涨跌表格
            for product_name in selected_products:
                product_data = filtered_data[product_name]

                with st.expander(f"📊 {product_name} - 每日详情", expanded=True):
                    # 准备详细数据
                    detail_data = []

                    for date_key in sorted(product_data.keys()):
                        data = product_data[date_key]

                        # 格式化日期显示（添加星期）
                        date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                        weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][date_obj.weekday()]
                        formatted_date = f"{date_key} ({weekday_name})"

                        # 格式化收益率显示（添加颜色标识）
                        daily_return = data['daily_return']
                        cumulative_return = data['cumulative_return']

                        if daily_return > 0:
                            daily_return_str = f"📈 +{daily_return:.2f}%"
                        elif daily_return < 0:
                            daily_return_str = f"📉 {daily_return:.2f}%"
                        else:
                            daily_return_str = f"➡️ {daily_return:.2f}%"

                        if cumulative_return > 0:
                            cumulative_return_str = f"📈 +{cumulative_return:.2f}%"
                        elif cumulative_return < 0:
                            cumulative_return_str = f"📉 {cumulative_return:.2f}%"
                        else:
                            cumulative_return_str = f"➡️ {cumulative_return:.2f}%"

                        detail_data.append({
                            '日期': formatted_date,
                            '净值': f"{data['nav_value']:.4f}",
                            '日收益率': daily_return_str,
                            '累积收益率': cumulative_return_str,
                            '数据源': data['source']
                        })

                    if detail_data:
                        detail_df = pd.DataFrame(detail_data)
                        st.dataframe(detail_df, use_container_width=True, hide_index=True)

                        # 显示产品统计指标
                        daily_returns = [data['daily_return'] for data in product_data.values()]

                        col_summary1, col_summary2, col_summary3, col_summary4 = st.columns(4)

                        with col_summary1:
                            period_return = list(product_data.values())[-1]['cumulative_return']
                            st.metric("周期收益率", f"{period_return:.2f}%")

                        with col_summary2:
                            avg_daily = sum(daily_returns)/len(daily_returns) if daily_returns else 0
                            st.metric("平均日收益", f"{avg_daily:.3f}%")

                        with col_summary3:
                            max_daily = max(daily_returns) if daily_returns else 0
                            st.metric("最大单日涨幅", f"{max_daily:.2f}%")

                        with col_summary4:
                            min_daily = min(daily_returns) if daily_returns else 0
                            st.metric("最大单日跌幅", f"{min_daily:.2f}%")
                    else:
                        st.info("该产品暂无详细数据")

            # 添加对比汇总表
            st.subheader("📋 产品对比汇总")

            comparison_data = []
            for product_name in selected_products:
                product_data = filtered_data[product_name]

                # 获取最新数据
                latest_date = max(product_data.keys())
                latest_data = product_data[latest_date]

                # 计算统计指标
                daily_returns = [data['daily_return'] for data in product_data.values()]

                comparison_data.append({
                    '产品名称': product_name,
                    '周期收益率': f"{latest_data['cumulative_return']:.2f}%",
                    '最新净值': f"{latest_data['nav_value']:.4f}",
                    '数据天数': len(product_data),
                    '平均日收益': f"{sum(daily_returns)/len(daily_returns):.3f}%" if daily_returns else "0.000%",
                    '最大单日涨幅': f"{max(daily_returns):.2f}%" if daily_returns else "0.00%",
                    '最大单日跌幅': f"{min(daily_returns):.2f}%" if daily_returns else "0.00%",
                    '波动率': f"{pd.Series(daily_returns).std():.3f}%" if len(daily_returns) > 1 else "0.000%"
                })

            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    else:
        st.info("💡 请至少选择一个产品进行对比分析")


# 保持向后兼容的函数别名
def get_week_date_range(target_date=None):
    """
    向后兼容的函数，但现在本周从上周五开始计算

    Args:
        target_date: 目标日期，如果为None则使用今天

    Returns:
        tuple: (week_start, week_end, week_trading_dates_list)
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    # 获取本周一
    days_since_monday = target_date.weekday()
    this_monday = target_date - timedelta(days=days_since_monday)

    # 本周从上周五开始，到本周五结束
    week_start = this_monday - timedelta(days=3)  # 上周五
    week_end = this_monday + timedelta(days=4)    # 本周五

    # 生成交易日期范围（包括上周五和本周一到五）
    trading_dates = []
    current_date = week_start
    while current_date <= week_end:
        # 只包括周一到周五的工作日
        if current_date.weekday() < 5:  # 0-4 表示周一到周五
            trading_dates.append(current_date)
        current_date += timedelta(days=1)

    return week_start, week_end, trading_dates

def render_weekly_summary_page(db):
    """向后兼容的函数，调用新的render_period_summary_page"""
    return render_period_summary_page(db)