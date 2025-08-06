"""
周度汇总组件
计算本周仿真+实盘产品的收益率并进行可视化对比
"""
import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_week_date_range(target_date=None):
    """
    获取本周的交易日期范围（周一到周五）

    Args:
        target_date: 目标日期，如果为None则使用今天

    Returns:
        tuple: (week_start, week_end, week_trading_dates_list)
    """
    if target_date is None:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()

    # 获取本周一（weekday()返回0-6，0是周一）
    days_since_monday = target_date.weekday()
    week_start = target_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=4)  # 周五

    # 生成本周交易日期（周一到周五）
    week_trading_dates = []
    current_date = week_start
    while current_date <= week_end:
        week_trading_dates.append(current_date)
        current_date += timedelta(days=1)

    return week_start, week_end, week_trading_dates


def get_available_asset_files_for_week(week_trading_dates, data_sources=["实盘", "仿真"]):
    """
    获取本周交易日的可用资产文件（自动跳过节假日）

    Args:
        week_trading_dates: 本周交易日期列表（周一到周五）
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

    for date_obj in week_trading_dates:
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
                    if (file.startswith("单元资产账户资产导出") and
                        (file.endswith('.xlsx') or file.endswith('.csv'))):
                        file_path = os.path.join(root, file)

                        # 解析时间戳
                        try:
                            filename = os.path.basename(file_path)
                            time_part = filename.replace('单元资产账户资产导出_', '').replace('.xlsx', '').replace('.csv', '')
                            timestamp = datetime.strptime(time_part, "%Y%m%d-%H%M%S")
                            asset_files.append({
                                'file_path': file_path,
                                'timestamp': timestamp
                            })
                        except:
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


def read_asset_file_for_weekly(file_path):
    """
    读取资产文件并提取周度汇总需要的数据

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

        # 查找需要的列
        product_col = None
        total_asset_col = None
        daily_profit_col = None

        for col in df.columns:
            col_lower = str(col).lower()
            if '产品名称' in col:
                product_col = col
            elif col == '总资产':  # 精确匹配避免"昨日总资产"等
                total_asset_col = col
            elif '当日盈亏' in col:
                daily_profit_col = col

        if not product_col or not total_asset_col:
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

        return result_df

    except Exception as e:
        st.error(f"读取文件失败 {os.path.basename(file_path)}: {e}")
        return pd.DataFrame()


def calculate_weekly_returns_from_nav(week_files, db):
    """
    直接从净值数据计算本周各产品的收益率

    Args:
        week_files: 本周可用文件字典 (用于确定产品列表)
        db: 数据库对象

    Returns:
        dict: {product_name: {date: {nav_value, daily_return, cumulative_return}}}
    """
    weekly_data = {}

    # 获取所有产品
    products = db.get_products()
    if not products:
        return weekly_data

    # 获取本周日期范围
    week_start, week_end, week_trading_dates = get_week_date_range()

    # 为每个产品读取净值数据
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

        # 获取本周及上周五的净值数据
        week_start_dt = pd.to_datetime(week_start)
        week_end_dt = pd.to_datetime(week_end)

        # 包含上周五到本周五的数据
        last_friday = week_start_dt - pd.Timedelta(days=3)  # 本周一往前3天是上周五

        # 筛选相关日期的数据
        relevant_data = nav_data[
            (nav_data['date'] >= last_friday) &
            (nav_data['date'] <= week_end_dt)
        ].copy()

        if relevant_data.empty:
            continue

        # 检查是否为仿真产品
        is_simulation = False
        for date_key, files in week_files.items():
            for source, file_path in files.items():
                if source == "仿真":
                    # 简单检查：如果文件路径包含仿真数据，就认为是仿真产品
                    asset_data = read_asset_file_for_weekly(file_path)
                    if not asset_data.empty and product_name in asset_data['product_name'].values:
                        is_simulation = True
                        break
            if is_simulation:
                break

        # 设置显示名称
        if is_simulation:
            display_name = f"{product_name}(仿真)"
        else:
            display_name = product_name

        # 计算收益率
        product_nav_data = {}

        for i, row in relevant_data.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d')
            nav_value = row['nav_value']

            # 计算日收益率
            if i == 0 or len(product_nav_data) == 0:
                # 第一个数据点，日收益率为0
                daily_return = 0
                cumulative_return = 0
            else:
                # 相对于前一个净值计算日收益率
                prev_nav = list(product_nav_data.values())[-1]['nav_value']
                if prev_nav > 0:
                    daily_return = (nav_value / prev_nav - 1) * 100
                else:
                    daily_return = 0

                # 累积收益率：相对于第一个净值
                first_nav = list(product_nav_data.values())[0]['nav_value']
                if first_nav > 0:
                    cumulative_return = (nav_value / first_nav - 1) * 100
                else:
                    cumulative_return = 0

            product_nav_data[date_str] = {
                'nav_value': nav_value,
                'daily_return': daily_return,
                'cumulative_return': cumulative_return,
                'source': '仿真' if is_simulation else '实盘'
            }

        # 只保留本周的数据（不包括上周五基准点）
        week_data = {}
        for date_str, data in product_nav_data.items():
            date_obj = pd.to_datetime(date_str).date()
            if week_start <= date_obj <= week_end:
                week_data[date_str] = data

        if week_data:
            weekly_data[display_name] = week_data

    return weekly_data


def filter_products_with_complete_data(weekly_data, min_days=1):
    """
    筛选有足够数据的产品（至少有min_days天的数据，考虑节假日）

    Args:
        weekly_data: 周度数据字典
        min_days: 最少天数要求（默认1天，因为要考虑节假日）

    Returns:
        dict: 筛选后的周度数据
    """
    filtered_data = {}

    for product_name, product_data in weekly_data.items():
        # 检查该产品有多少天的数据
        valid_days = len([d for d, data in product_data.items()
                         if data['nav_value'] > 0])

        if valid_days >= min_days:
            filtered_data[product_name] = product_data
        else:
            print(f"产品 {product_name} 数据不足，只有 {valid_days} 天，需要至少 {min_days} 天")

    return filtered_data


def render_product_selection_checkboxes(filtered_weekly_data):
    """
    渲染产品选择复选框界面

    Args:
        filtered_weekly_data: 筛选后的周度数据

    Returns:
        list: 选中的产品列表
    """
    if not filtered_weekly_data:
        st.warning("本周暂无可用的产品数据")
        return []

    st.subheader("📊 选择要对比的产品")

    # 创建多列布局来显示复选框
    products = list(filtered_weekly_data.keys())

    # 根据产品数量决定列数
    if len(products) <= 4:
        cols = st.columns(len(products))
    elif len(products) <= 8:
        cols = st.columns(4)
    else:
        cols = st.columns(5)

    selected_products = []

    # 添加全选/全不选按钮
    col_select_all, col_select_none, col_info = st.columns([1, 1, 2])

    with col_select_all:
        if st.button("✅ 全选", key="select_all_weekly"):
            for product in products:
                st.session_state[f"weekly_checkbox_{product}"] = True
            st.rerun()

    with col_select_none:
        if st.button("❌ 全不选", key="select_none_weekly"):
            for product in products:
                st.session_state[f"weekly_checkbox_{product}"] = False
            st.rerun()

    with col_info:
        st.info(f"共 {len(products)} 个产品可选")

    # 渲染复选框
    for i, product in enumerate(products):
        col_index = i % len(cols)

        with cols[col_index]:
            # 默认选中前3个产品
            default_checked = i < 3

            # 检查session state中是否有保存的状态
            checkbox_key = f"weekly_checkbox_{product}"
            if checkbox_key not in st.session_state:
                st.session_state[checkbox_key] = default_checked

            is_checked = st.checkbox(
                product,
                key=checkbox_key,
                value=st.session_state[checkbox_key]
            )

            if is_checked:
                selected_products.append(product)

                # 显示该产品的基本信息
                product_data = filtered_weekly_data[product]
                latest_date = max(product_data.keys())
                latest_data = product_data[latest_date]

                # 计算本周累积收益率
                cumulative_return = latest_data['cumulative_return']

                # 用不同颜色显示收益率
                if cumulative_return > 0:
                    st.markdown(f"<small style='color: red'>📈 +{cumulative_return:.2f}%</small>",
                               unsafe_allow_html=True)
                elif cumulative_return < 0:
                    st.markdown(f"<small style='color: green'>📉 {cumulative_return:.2f}%</small>",
                               unsafe_allow_html=True)
                else:
                    st.markdown(f"<small style='color: gray'>➡️ {cumulative_return:.2f}%</small>",
                               unsafe_allow_html=True)

    return selected_products


def create_weekly_comparison_chart(selected_products, filtered_weekly_data, week_start, week_end):
    """
    创建周度收益率对比图表

    Args:
        selected_products: 选中的产品列表
        filtered_weekly_data: 筛选后的周度数据
        week_start: 周开始日期
        week_end: 周结束日期

    Returns:
        plotly.graph_objects.Figure: 图表对象
    """
    if not selected_products:
        return None

    # 创建图表
    fig = go.Figure()

    # 为每个产品添加一条线
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57',
              '#FF9FF3', '#54A0FF', '#5F27CD', '#00D2D3', '#FF9F43']

    for i, product_name in enumerate(selected_products):
        product_data = filtered_weekly_data[product_name]

        # 准备数据
        dates = []
        cumulative_returns = []
        daily_returns = []
        nav_values = []

        # 添加起始点（基准点），确保不与实际数据重复
        actual_dates = sorted(product_data.keys())
        if actual_dates:
            # 使用实际第一个交易日的前一天作为基准点
            first_actual_date = datetime.strptime(actual_dates[0], '%Y-%m-%d').date()
            baseline_date = (first_actual_date - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            baseline_date = (week_start - timedelta(days=1)).strftime('%Y-%m-%d')

        dates.append(baseline_date)
        cumulative_returns.append(0)  # 起始点为0%
        daily_returns.append(0)
        nav_values.append(0)

        # 按日期排序添加实际数据
        for date_key in actual_dates:
            data = product_data[date_key]
            dates.append(date_key)
            cumulative_returns.append(data['cumulative_return'])
            daily_returns.append(data['daily_return'])
            nav_values.append(data['nav_value'])

        # 确定线条样式
        line_style = 'solid'
        line_width = 3

        # 如果是仿真产品，使用虚线
        if '(仿真)' in product_name:
            line_style = 'dash'
            line_width = 2

        # 准备悬停信息
        hover_text = []
        for j, (date, cum_ret, daily_ret, nav_val) in enumerate(zip(dates, cumulative_returns, daily_returns, nav_values)):
            if j == 0:  # 起始点
                hover_text.append(f'<b>{product_name}</b><br>' +
                                f'基准点 (上周五收盘)<br>' +
                                f'累积收益率: 0.00%<br>' +
                                f'起始基准')
            else:
                hover_text.append(f'<b>{product_name}</b><br>' +
                                f'日期: {date}<br>' +
                                f'累积收益率: {cum_ret:.2f}%<br>' +
                                f'当日收益率: {daily_ret:.2f}%<br>' +
                                f'净值: {nav_val:.4f}')

        # 添加累积收益率线
        fig.add_trace(go.Scatter(
            x=dates,
            y=cumulative_returns,
            mode='lines+markers',
            name=product_name,
            line=dict(
                color=colors[i % len(colors)],
                width=line_width,
                dash=line_style
            ),
            marker=dict(
                size=[4 if j == 0 else 6 for j in range(len(dates))],  # 起始点稍小
                color=colors[i % len(colors)],
                symbol=['circle-open' if j == 0 else 'circle' for j in range(len(dates))]  # 起始点空心
            ),
            hovertemplate='%{text}<extra></extra>',
            text=hover_text
        ))

    # 计算X轴范围，确保不重复
    if selected_products and filtered_weekly_data:
        # 获取所有产品的实际日期范围
        all_actual_dates = []
        for product_name in selected_products:
            all_actual_dates.extend(filtered_weekly_data[product_name].keys())

        if all_actual_dates:
            earliest_date = min(all_actual_dates)
            latest_date = max(all_actual_dates)

            # 基准点日期（第一个实际交易日的前一天）
            first_date = datetime.strptime(earliest_date, '%Y-%m-%d').date()
            x_axis_start = (first_date - timedelta(days=1)).strftime('%Y-%m-%d')
            x_axis_end = latest_date
        else:
            x_axis_start = (week_start - timedelta(days=1)).strftime('%Y-%m-%d')
            x_axis_end = week_end.strftime('%Y-%m-%d')
    else:
        x_axis_start = (week_start - timedelta(days=1)).strftime('%Y-%m-%d')
        x_axis_end = week_end.strftime('%Y-%m-%d')

    # 设置图表布局
    fig.update_layout(
        title=dict(
            text=f"本周产品收益率对比 ({week_start.strftime('%m-%d')} ~ {week_end.strftime('%m-%d')})",
            x=0.5,
            font=dict(size=18, color='#2c3e50')
        ),
        xaxis=dict(
            title="日期",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            tickformat='%m-%d',
            range=[x_axis_start, x_axis_end],
            type='date',
            dtick='D1',  # 每天显示一个刻度
            tickmode='linear'  # 线性刻度模式
        ),
        yaxis=dict(
            title="累积收益率 (%)",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            zeroline=True,
            zerolinecolor='rgba(128,128,128,0.8)',
            zerolinewidth=2
        ),
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


def render_weekly_summary_page(db):
    """
    渲染周度汇总主页面

    Args:
        db: 数据库对象
    """
    st.header("📅 周度汇总")

    # 获取本周交易日期范围
    week_start, week_end, week_trading_dates = get_week_date_range()

    # 显示周度信息
    col_info1, col_info2, col_refresh = st.columns([1, 1, 1])

    with col_info1:
        st.info(f"📅 本周范围: {week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')}")

    with col_info2:
        st.info(f"📊 交易日: {len(week_trading_dates)} 天 (周一至周五)")

    with col_refresh:
        if st.button("🔄 刷新数据", type="primary"):
            # 清除缓存，强制重新计算
            keys_to_remove = [k for k in st.session_state.keys() if k.startswith('weekly_nav_data_')]
            for key in keys_to_remove:
                del st.session_state[key]
            st.rerun()

    # 显示数据获取进度
    with st.spinner("正在扫描本周交易数据文件..."):
        week_files = get_available_asset_files_for_week(week_trading_dates)

    # 显示数据可用性统计
    st.subheader("📈 数据可用性")

    data_summary = []
    for date_obj in week_trading_dates:  # 遍历所有交易日
        date_key = date_obj.strftime('%Y-%m-%d')
        weekday_name = ['周一', '周二', '周三', '周四', '周五'][date_obj.weekday()]

        files = week_files.get(date_key, {})
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
        available_days = len([d for d in week_files.keys()])
        total_trading_days = len(week_trading_dates)

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("可用交易日", f"{available_days}/{total_trading_days}")
        with col_stat2:
            coverage_rate = (available_days / total_trading_days * 100) if total_trading_days > 0 else 0
            st.metric("数据覆盖率", f"{coverage_rate:.1f}%")
        with col_stat3:
            if available_days == 0:
                st.metric("状态", "❌ 本周无数据")
            elif available_days < total_trading_days:
                st.metric("状态", "⚠️ 数据不完整")
            else:
                st.metric("状态", "✅ 数据完整")

    # 计算周度收益率
    if not week_files:
        st.error("❌ 本周暂无可用交易数据文件，可能原因：")
        st.write("- 本周都是节假日")
        st.write("- 数据目录不存在或无权限访问")
        st.write("- 文件命名格式不正确")
        return

    with st.spinner("正在从净值数据计算本周收益率..."):
        # 使用缓存避免重复计算
        cache_key = f"weekly_nav_data_{week_start}_{week_end}"

        if cache_key not in st.session_state:
            weekly_data = calculate_weekly_returns_from_nav(week_files, db)
            filtered_data = filter_products_with_complete_data(weekly_data, min_days=1)
            st.session_state[cache_key] = filtered_data
        else:
            filtered_data = st.session_state[cache_key]

    if not filtered_data:
        st.error("❌ 本周暂无有效的产品收益数据")
        st.info("💡 提示：即使有节假日，只要有1天的数据就可以显示")
        return

    st.success(f"✅ 成功获取 {len(filtered_data)} 个产品的周度数据")

    # 渲染产品选择界面
    selected_products = render_product_selection_checkboxes(filtered_data)

    # 如果有选中的产品，创建对比图表
    if selected_products:
        st.divider()
        st.subheader("📊 收益率对比图表")

        # 创建图表
        fig = create_weekly_comparison_chart(selected_products, filtered_data, week_start, week_end)

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
                        weekday_name = ['周一', '周二', '周三', '周四', '周五'][date_obj.weekday()]
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
                            '当日收益率': daily_return_str,
                            '累积收益率': cumulative_return_str,
                            '净值': f"{data['nav_value']:.4f}",
                            '数据源': '🎮 仿真' if data['source'] == '仿真' else '💼 实盘'
                        })

                    # 显示表格
                    if detail_data:
                        detail_df = pd.DataFrame(detail_data)
                        st.dataframe(detail_df, use_container_width=True, hide_index=True)

                        # 显示该产品的汇总统计
                        col_summary1, col_summary2, col_summary3, col_summary4 = st.columns(4)

                        # 计算统计指标
                        daily_returns = [data['daily_return'] for data in product_data.values()]
                        latest_data = product_data[max(product_data.keys())]

                        with col_summary1:
                            st.metric("本周总收益", f"{latest_data['cumulative_return']:.2f}%")

                        with col_summary2:
                            avg_daily = sum(daily_returns) / len(daily_returns) if daily_returns else 0
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
                    '本周收益率': f"{latest_data['cumulative_return']:.2f}%",
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