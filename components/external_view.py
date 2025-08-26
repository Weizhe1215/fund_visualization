"""
外部用户净值展示组件
专为移动端优化的简洁净值查看界面
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
from components.auth import AuthManager
from components.analysis import analyze_holdings_by_index
from components.industry_analysis import analyze_holdings_by_market
from config import MAJOR_INDICES


def render_external_main_page(auth_manager: AuthManager, db):
    """渲染外部用户主页面"""
    # 移动端优化样式
    st.markdown("""
    <style>
    .main-container {
        padding: 0.5rem;
    }
    .product-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-up { background-color: #10b981; }
    .status-down { background-color: #ef4444; }
    .status-neutral { background-color: #6b7280; }
    
    /* 移动端响应式 */
    @media (max-width: 768px) {
        .main-container {
            padding: 0.25rem;
        }
        .metric-value {
            font-size: 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # 获取用户权限的产品
    permissions = auth_manager.get_user_permissions()
    if not permissions:
        render_no_permissions_page()
        return

    # 获取用户有权限的产品
    products = db.get_products()
    user_products = [p for p in products if p['product_code'] in permissions]

    if not user_products:
        render_no_products_page()
        return

    # 如果只有一个产品，直接显示
    if len(user_products) == 1:
        render_single_product_view(auth_manager, db, user_products[0])
    else:
        render_multi_product_view(auth_manager, db, user_products)


def render_no_permissions_page():
    """渲染无权限页面"""
    st.markdown("""
    <div style='text-align: center; padding: 3rem 1rem;'>
        <h2>🔒 暂无权限</h2>
        <p style='font-size: 1.1rem; color: #666; line-height: 1.6;'>
            您的账户暂未开通任何产品的查看权限<br>
            请联系管理员为您分配相关权限
        </p>
        <div style='margin-top: 2rem; padding: 1rem; background: #f8f9fa; border-radius: 8px;'>
            💡 <strong>提示：</strong>账户激活后，您将能够查看被授权的产品净值信息
        </div>
    </div>
    """, unsafe_allow_html=True)

def convert_to_weekly_data(nav_data):
    """将日频数据转换为周频数据"""
    if nav_data.empty:
        return pd.DataFrame()

    try:
        # 确保数据按日期排序
        nav_data_sorted = nav_data.sort_values('date').copy()

        # 设置星期一为一周的开始
        nav_data_sorted['week'] = nav_data_sorted['date'].dt.to_period('W-MON')

        # 按周分组，取每周最后一个交易日的数据
        weekly_data = nav_data_sorted.groupby('week').last().reset_index()

        # 重新计算周度收益率
        if len(weekly_data) > 1:
            weekly_data['daily_return'] = weekly_data['nav_value'].pct_change() * 100
            weekly_data['cumulative_return'] = (weekly_data['nav_value'] / weekly_data['nav_value'].iloc[0] - 1) * 100

            # 重命名为周度收益率
            weekly_data = weekly_data.rename(columns={'daily_return': 'weekly_return'})

        # 删除week列，保持数据结构一致
        weekly_data = weekly_data.drop(['week'], axis=1)

        return weekly_data.reset_index(drop=True)

    except Exception as e:
        print(f"转换周频数据时出错: {str(e)}")
        return pd.DataFrame()

def render_no_products_page():
    """渲染无产品页面"""
    st.markdown("""
    <div style='text-align: center; padding: 3rem 1rem;'>
        <h2>📊 暂无产品</h2>
        <p style='font-size: 1.1rem; color: #666; line-height: 1.6;'>
            系统中暂无可查看的产品数据<br>
            请稍后再试或联系管理员
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_single_product_view(auth_manager: AuthManager, db, product):
    """渲染单产品视图"""
    product_code = product['product_code']
    product_name = product['product_name']

    # 获取净值数据用于日期范围显示
    nav_data = db.get_nav_data(product_code)

    # 页面标题（优化高度）
    st.markdown(f"""
    <div style='text-align: center; margin: 0.5rem 0 1rem 0; padding: 1rem; background: linear-gradient(90deg, #f8f9fa, #e9ecef); border-radius: 12px;'>
        <h2 style='color: #1f77b4; margin: 0; font-size: 1.4rem; line-height: 1.3;'>📈 {product_name}</h2>
        <p style='color: #666; font-size: 0.85rem; margin: 0.3rem 0 0 0;'>{product_code}</p>
    </div>
    """, unsafe_allow_html=True)

    # 显示净值日期范围
    if not nav_data.empty:
        nav_data['date'] = pd.to_datetime(nav_data['date'])
        start_date = nav_data['date'].min().strftime('%Y/%m/%d')
        end_date = nav_data['date'].max().strftime('%Y/%m/%d')

        st.markdown(f"""
        <div style='text-align: center; margin: 0 0 1rem 0; padding: 0.5rem; background: #f0f2f6; border-radius: 8px;'>
            <span style='color: #666; font-size: 0.9rem;'>📅 净值数据期间：{start_date} - {end_date}</span>
        </div>
        """, unsafe_allow_html=True)

    # 渲染产品详细信息
    render_product_detail(auth_manager, db, product_code, product_name)


def render_multi_product_view(auth_manager: AuthManager, db, user_products):
    """渲染多产品选择视图"""
    # 检查是否有选中的产品
    if 'selected_product' not in st.session_state:
        st.session_state.selected_product = None

    # 如果有选中的产品，显示该产品详情
    if st.session_state.selected_product:
        selected_product = None
        for product in user_products:
            if product['product_code'] == st.session_state.selected_product:
                selected_product = product
                break

        if selected_product:
            # 添加返回按钮
            if st.button("← 返回产品列表", key="back_to_list"):
                st.session_state.selected_product = None
                st.rerun()

            render_single_product_view(auth_manager, db, selected_product)
            return

    # 显示产品列表
    st.markdown("### 📋 选择产品")

    for product in user_products:
        product_code = product['product_code']
        product_name = product['product_name']

        # 获取最新净值用于预览
        nav_data = db.get_nav_data(product_code)
        latest_nav = "暂无数据"
        nav_change = 0

        if not nav_data.empty:
            nav_data = nav_data.sort_values('date')
            latest_nav = f"{nav_data.iloc[-1]['nav_value']:.4f}"
            if len(nav_data) > 1:
                nav_change = nav_data.iloc[-1]['nav_value'] - nav_data.iloc[-2]['nav_value']

        # 产品卡片
        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{product_name}**")
                st.caption(f"{product_code}")

                # 显示净值信息
                color = "green" if nav_change >= 0 else "red"
                change_symbol = "+" if nav_change >= 0 else ""
                st.markdown(f"净值: **{latest_nav}** "
                           f"<span style='color: {color}'>({change_symbol}{nav_change:.4f})</span>",
                           unsafe_allow_html=True)

            with col2:
                if st.button(
                    "查看详情",
                    key=f"view_{product_code}",
                    type="primary",
                    use_container_width=True
                ):
                    st.session_state.selected_product = product_code
                    st.rerun()

            # 添加分隔线
            st.markdown("---")


def render_product_detail(auth_manager: AuthManager, db, product_code, product_name):
    """渲染产品详细信息"""
    # 获取净值数据
    nav_data = db.get_nav_data(product_code)

    if nav_data.empty:
        st.warning("该产品暂无净值数据")
        return

    # 数据处理
    nav_data['date'] = pd.to_datetime(nav_data['date'])
    nav_data = nav_data.sort_values('date')
    nav_data['daily_return'] = nav_data['nav_value'].pct_change() * 100
    nav_data['cumulative_return'] = (nav_data['nav_value'] / nav_data['nav_value'].iloc[0] - 1) * 100

    # 关键指标卡片（移动端优化）
    render_mobile_metrics_cards(nav_data)

    # 净值走势图（移动端优化的Plotly）
    render_mobile_optimized_plotly_chart(nav_data, product_name)

    # 持仓分析概览（取代原有的持仓概览下拉框）
    render_holdings_analysis_overview(db, product_code)


def render_mobile_metrics_cards(nav_data):
    """渲染移动端优化的指标卡片（包含夏普比率和卡玛比率）"""
    if nav_data.empty:
        return

    latest_data = nav_data.iloc[-1]

    # 计算指标
    current_nav = latest_data['nav_value']
    total_return = latest_data['cumulative_return']
    daily_return = latest_data['daily_return'] if not pd.isna(latest_data['daily_return']) else 0

    # 计算夏普比率和卡玛比率
    sharpe_ratio = calculate_sharpe_ratio(nav_data)
    calmar_ratio = calculate_calmar_ratio(nav_data)

    st.markdown("### 📊 关键指标")

    # 四个指标卡片，两行两列排列
    metrics_html = f"""
    <style>
    .metrics-container {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.8rem;
        margin: 1rem 0;
        width: 100%;
        box-sizing: border-box;
    }}
    
    .metric-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        min-height: 90px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }}
    
    .metric-value {{
        font-size: 1.3rem;
        font-weight: bold;
        margin: 0.3rem 0;
    }}
    
    .metric-label {{
        font-size: 0.8rem;
        opacity: 0.9;
        margin: 0;
    }}
    
    @media (max-width: 768px) {{
        .metrics-container {{
            gap: 0.6rem;
        }}
        .metric-card {{
            min-height: 80px;
            padding: 1rem;
        }}
        .metric-value {{
            font-size: 1.2rem;
        }}
    }}
    </style>
    
    <div class='metrics-container'>
        <div class='metric-card'>
            <div class='metric-value'>{current_nav:.4f}</div>
            <div class='metric-label'>最新净值</div>
        </div>
        <div class='metric-card'>
            <div class='metric-value'>{total_return:+.2f}%</div>
            <div class='metric-label'>累计收益率</div>
        </div>
        <div class='metric-card'>
            <div class='metric-value'>{sharpe_ratio:.2f}</div>
            <div class='metric-label'>夏普比率</div>
        </div>
        <div class='metric-card'>
            <div class='metric-value'>{calmar_ratio:.2f}</div>
            <div class='metric-label'>卡玛比率</div>
        </div>
    </div>
    """

    st.markdown(metrics_html, unsafe_allow_html=True)


def calculate_sharpe_ratio(nav_data, risk_free_rate=0.01):
    """
    计算夏普比率

    Parameters:
    nav_data: 净值数据，包含日期和净值
    risk_free_rate: 无风险收益率，默认1%年化

    Returns:
    float: 夏普比率
    """
    try:
        if len(nav_data) < 2:
            return 0.0

        # 确保数据按日期排序
        nav_data_sorted = nav_data.sort_values('date')

        # 计算日收益率
        nav_data_sorted = nav_data_sorted.copy()
        nav_data_sorted['daily_return'] = nav_data_sorted['nav_value'].pct_change()

        # 去除NaN值
        daily_returns = nav_data_sorted['daily_return'].dropna()

        if len(daily_returns) < 2:
            return 0.0

        # 计算数据期间（天数）
        start_date = nav_data_sorted['date'].min()
        end_date = nav_data_sorted['date'].max()
        total_days = (end_date - start_date).days

        if total_days <= 0:
            return 0.0

        # 计算年化收益率
        total_return = (nav_data_sorted['nav_value'].iloc[-1] / nav_data_sorted['nav_value'].iloc[0]) - 1
        annualized_return = (1 + total_return) ** (365.25 / total_days) - 1

        # 计算年化波动率
        daily_vol = daily_returns.std()
        annualized_vol = daily_vol * (365.25 ** 0.5)

        # 计算夏普比率
        if annualized_vol == 0:
            return 0.0

        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_vol

        return sharpe_ratio

    except Exception as e:
        print(f"计算夏普比率时出错: {str(e)}")
        return 0.0


def calculate_calmar_ratio(nav_data):
    """
    计算卡玛比率 (Calmar Ratio)
    卡玛比率 = 年化收益率 / 最大回撤

    Parameters:
    nav_data: 净值数据，包含日期和净值

    Returns:
    float: 卡玛比率
    """
    try:
        if len(nav_data) < 2:
            return 0.0

        # 确保数据按日期排序
        nav_data_sorted = nav_data.sort_values('date')

        # 计算数据期间（天数）
        start_date = nav_data_sorted['date'].min()
        end_date = nav_data_sorted['date'].max()
        total_days = (end_date - start_date).days

        if total_days <= 0:
            return 0.0

        # 计算年化收益率
        total_return = (nav_data_sorted['nav_value'].iloc[-1] / nav_data_sorted['nav_value'].iloc[0]) - 1
        annualized_return = (1 + total_return) ** (365.25 / total_days) - 1

        # 计算最大回撤
        nav_values = nav_data_sorted['nav_value'].values
        peak = nav_values[0]
        max_drawdown = 0

        for value in nav_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算卡玛比率
        if max_drawdown == 0:
            return float('inf') if annualized_return > 0 else 0.0

        calmar_ratio = annualized_return / max_drawdown

        return calmar_ratio

    except Exception as e:
        print(f"计算卡玛比率时出错: {str(e)}")
        return 0.0


def render_mobile_optimized_plotly_chart(nav_data, product_name):
    """渲染移动端优化的Plotly图表（仅显示周度频率数据）"""
    if nav_data.empty:
        return

    st.markdown("### 📈 净值走势")

    # 首先将日频数据转换为周频数据
    weekly_data = convert_to_weekly_data(nav_data)

    if weekly_data.empty:
        st.warning("暂无可用的周度数据")
        return

    # 时间范围和图表类型选择器
    col1, col2 = st.columns(2)

    with col1:
        period = st.selectbox(
            "查看期间",
            ["全部", "近1年", "近6个月", "近3个月", "近1个月"],
            index=0,
            key="chart_period"
        )

    with col2:
        chart_type = st.selectbox(
            "图表类型",
            ["净值走势", "收益率"],
            index=0,
            key="chart_type"
        )

    # 使用周度数据进行时间筛选
    filtered_data = weekly_data.copy()
    if period != "全部":
        days_map = {"近1年": 365, "近6个月": 180, "近3个月": 90, "近1个月": 30}
        days = days_map[period]
        cutoff_date = weekly_data['date'].max() - pd.Timedelta(days=days)
        filtered_data = weekly_data[weekly_data['date'] >= cutoff_date]

    if filtered_data.empty:
        st.warning("选定期间内无数据")
        return

    # 重新计算净值和收益率，让选定区间从1开始
    filtered_data = filtered_data.sort_values('date').copy()

    if len(filtered_data) > 0:
        # 获取选定区间的第一个净值作为基准
        first_nav = filtered_data.iloc[0]['nav_value']

        # 重新计算净值（标准化到从1开始）
        filtered_data['adjusted_nav_value'] = filtered_data['nav_value'] / first_nav

        # 重新计算累计收益率（基于选定区间）
        filtered_data['adjusted_cumulative_return'] = (filtered_data['adjusted_nav_value'] - 1) * 100

    # 根据图表类型准备数据（使用调整后的数据）
    if chart_type == "收益率":
        y_values = filtered_data['adjusted_cumulative_return']
        y_title = "累计收益率 (%)"
        hover_template = '<b>%{x}</b><br>收益率: %{y:.2f}%<extra></extra>'
        line_color = '#10b981' if y_values.iloc[-1] >= 0 else '#ef4444'
        # 正确的RGBA颜色格式
        fill_color = 'rgba(16, 185, 129, 0.1)' if y_values.iloc[-1] >= 0 else 'rgba(239, 68, 68, 0.1)'
    else:  # 净值走势
        y_values = filtered_data['adjusted_nav_value']
        y_title = "净值"
        hover_template = '<b>%{x}</b><br>净值: %{y:.4f}<extra></extra>'
        line_color = '#1f77b4'
        fill_color = None

    # 创建图表
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=filtered_data['date'],
        y=y_values,
        mode='lines+markers',  # 周度数据显示线条和标记点
        name=chart_type,
        line=dict(color=line_color, width=2),
        marker=dict(size=4, color=line_color),  # 添加标记点以突出周度数据点
        hovertemplate=hover_template,
        fill='tonexty' if chart_type == "收益率" else None,
        fillcolor=fill_color
    ))

    # 移动端优化的图表布局
    fig.update_layout(
        title=dict(
            text=f"{product_name} - {chart_type} (周度)",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            title=y_title,
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            tickfont=dict(size=10)
        ),
        height=400,
        margin=dict(l=50, r=20, t=50, b=30),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=False
    )

    # 移动端触摸优化
    config = {
        'displayModeBar': False,
        'scrollZoom': True,
        'doubleClick': 'reset',
        'showTips': False,
        'responsive': True
    }

    st.plotly_chart(fig, use_container_width=True, config=config)

    # 显示数据点数量信息 - 更新为周度数据提示
    st.caption(f"📊 数据点数: {len(filtered_data)} 个周度数据点")

    # 添加说明信息
    st.caption("💡 图表显示周度数据，每周取最后一个交易日的净值")


def convert_to_weekly_data(nav_data):
    """将日频数据转换为周频数据"""
    if nav_data.empty:
        return pd.DataFrame()

    try:
        # 确保数据按日期排序
        nav_data_sorted = nav_data.sort_values('date').copy()

        # 设置星期一为一周的开始
        nav_data_sorted['week'] = nav_data_sorted['date'].dt.to_period('W-MON')

        # 按周分组，取每周最后一个交易日的数据
        weekly_data = nav_data_sorted.groupby('week').last().reset_index()

        # 重新计算周度收益率
        if len(weekly_data) > 1:
            weekly_data['daily_return'] = weekly_data['nav_value'].pct_change() * 100
            weekly_data['cumulative_return'] = (weekly_data['nav_value'] / weekly_data['nav_value'].iloc[0] - 1) * 100

            # 重命名为周度收益率
            weekly_data = weekly_data.rename(columns={'daily_return': 'weekly_return'})

        # 删除week列，保持数据结构一致
        weekly_data = weekly_data.drop(['week'], axis=1)

        return weekly_data.reset_index(drop=True)

    except Exception as e:
        print(f"转换周频数据时出错: {str(e)}")
        return pd.DataFrame()

def render_holdings_analysis_overview(db, product_code):
    """渲染持仓分析概览（指数成分股占比、板块占比、行业分布）"""
    # 获取最新持仓日期
    available_dates = db.get_available_dates(product_code)

    if not available_dates:
        st.info("暂无持仓数据")
        return

    latest_date = max(available_dates)
    holdings = db.get_holdings_by_date(product_code, latest_date)

    if holdings.empty:
        st.info("暂无持仓数据")
        return

    st.markdown("### 📊 持仓分析概览")
    st.markdown(f"*数据日期: {latest_date}*")

    # 创建三个标签页
    tab1, tab2, tab3 = st.tabs(["指数成分股占比", "板块占比", "行业分布"])

    with tab1:
        render_index_components_analysis(db, product_code, latest_date)

    with tab2:
        render_market_analysis(holdings)

    with tab3:
        render_industry_analysis_custom(db, product_code, latest_date)


def render_index_components_analysis(db, product_code, analysis_date):
    """渲染指数成分股占比分析"""
    try:
        analysis_results = analyze_holdings_by_index(db, product_code, analysis_date)

        if not analysis_results:
            st.info("暂无指数分析数据")
            return

        # 准备饼状图数据
        labels = []
        values = []

        for index_name, data in analysis_results.items():
            if data['ratio'] > 0.1:  # 只显示占比超过0.1%的部分
                labels.append(index_name)
                values.append(data['ratio'])

        if not values:
            st.warning("没有足够的数据绘制图表")
            return

        # 创建饼状图
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(
                colors=px.colors.sequential.Blues_r[2:],
                line=dict(width=2, color='rgba(255,255,255,0.3)')
            ),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>占比: %{percent}<extra></extra>'
        )])

        fig.update_layout(
            title=dict(
                text="持仓指数分布",
                x=0.5,
                font=dict(size=14, color='#2c3e50')
            ),
            height=350,
            showlegend=False,
            margin=dict(t=40, b=40, l=40, r=40)
        )

        st.plotly_chart(fig, use_container_width=True)

        # 详细数据表
        st.markdown("**详细分布:**")
        table_data = []
        for index_name, data in analysis_results.items():
            if data['ratio'] > 0.1:
                table_data.append({
                    '指数': index_name,
                    '占比': f"{data['ratio']:.2f}%",
                    '股票数': data['stock_count']
                })

        if table_data:
            table_df = pd.DataFrame(table_data)
            table_df['占比_num'] = table_df['占比'].str.replace('%', '').astype(float)
            table_df = table_df.sort_values('占比_num', ascending=False)
            table_df = table_df.drop('占比_num', axis=1)
            st.dataframe(table_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"指数分析出现错误: {str(e)}")


def render_market_analysis(holdings):
    """渲染市场分布分析（板块占比）"""
    try:
        market_results = analyze_holdings_by_market(holdings)

        # 准备数据
        labels = []
        values = []

        for market, ratio in market_results.items():
            if ratio > 0.1:
                labels.append(market)
                values.append(ratio)

        if not values:
            st.info("没有足够的数据绘制图表")
            return

        # 创建饼状图
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(
                colors=px.colors.sequential.Oranges_r[2:],
                line=dict(width=2, color='rgba(255,255,255,0.3)')
            ),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>占比: %{percent}<extra></extra>'
        )])

        fig.update_layout(
            title=dict(
                text="市场分布",
                x=0.5,
                font=dict(size=14, color='#2c3e50')
            ),
            height=350,
            showlegend=False,
            margin=dict(t=40, b=40, l=40, r=40)
        )

        st.plotly_chart(fig, use_container_width=True)

        # 详细数据表
        st.markdown("**详细分布:**")
        table_data = []
        for market, ratio in market_results.items():
            if ratio > 0.1:
                table_data.append({
                    '板块': market,
                    '占比': f"{ratio:.2f}%"
                })

        if table_data:
            table_df = pd.DataFrame(table_data)
            table_df['占比_num'] = table_df['占比'].str.replace('%', '').astype(float)
            table_df = table_df.sort_values('占比_num', ascending=False)
            table_df = table_df.drop('占比_num', axis=1)
            st.dataframe(table_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"市场分析出现错误: {str(e)}")


def render_industry_analysis_custom(db, product_code, analysis_date):
    """渲染行业分布分析（自定义实现，使用饼图显示前10大，表格显示全部）"""
    try:
        # 直接在这里实现行业分析逻辑，不调用其他模块
        holdings = db.get_holdings_by_date(product_code, analysis_date)

        if holdings.empty:
            st.info("暂无持仓数据")
            return

        # 获取所有行业
        industries = db.get_all_industries()
        if not industries:
            st.info("暂无行业分类数据，请先在'指数成分股管理'页面导入行业分类")
            return

        # 分析各行业分布
        analysis_results = {}
        matched_stocks = set()

        # 分析各行业
        for industry_name in industries:
            # 获取该行业的股票代码（6位数字）
            industry_stocks_6digit = db.get_industry_stocks(industry_name)

            # 匹配持仓股票（提取前6位数字）
            matched_holdings = []
            for _, holding in holdings.iterrows():
                stock_code_6digit = holding['stock_code'][:6]  # 提取前6位
                if stock_code_6digit in industry_stocks_6digit:
                    matched_holdings.append(holding)
                    matched_stocks.add(holding['stock_code'])

            if matched_holdings:
                matched_df = pd.DataFrame(matched_holdings)
                industry_ratio = matched_df['position_ratio'].sum()

                analysis_results[industry_name] = {
                    'ratio': industry_ratio,
                    'stock_count': len(matched_holdings),
                    'stocks': matched_df['stock_code'].tolist()
                }

        # 计算"其他"部分（未匹配到行业的股票）
        unmatched_holdings = holdings[~holdings['stock_code'].isin(matched_stocks)]
        other_ratio = unmatched_holdings['position_ratio'].sum() if not unmatched_holdings.empty else 0

        if other_ratio > 0:
            analysis_results['其他'] = {
                'ratio': other_ratio,
                'stock_count': len(unmatched_holdings),
                'stocks': unmatched_holdings['stock_code'].tolist()
            }

        if not analysis_results:
            st.info("暂无行业分析数据")
            return

        # 准备饼图数据，只显示占比大于0.1%的行业
        all_data = [(industry, data['ratio'], data['stock_count'])
                    for industry, data in analysis_results.items()
                    if data['ratio'] > 0.1]

        if not all_data:
            st.warning("没有足够的数据绘制图表")
            return

        # 按占比排序
        all_data_sorted = sorted(all_data, key=lambda x: x[1], reverse=True)

        # 准备饼图显示的数据（取前10大行业）
        chart_data = all_data_sorted[:10]  # 只显示前10大行业

        # 如果有超过10个行业，将其他小行业合并为"其他行业"
        if len(all_data_sorted) > 10:
            other_industries_ratio = sum([x[1] for x in all_data_sorted[10:]])
            other_industries_count = sum([x[2] for x in all_data_sorted[10:]])
            chart_data.append(("其他行业", other_industries_ratio, other_industries_count))

        # 准备饼图数据
        labels = [x[0] for x in chart_data]
        values = [x[1] for x in chart_data]

        # 创建同色系的颜色序列（从浅到深的蓝色系）
        def generate_blue_palette(n):
            """生成n种深浅不同的蓝色"""
            # 基础蓝色HSL值：色调=220, 饱和度=70%
            colors = []
            for i in range(n):
                # 明度从85%逐渐降到25%，形成从浅到深的渐变
                lightness = 85 - (60 * i / max(1, n - 1))  # 避免除零
                # 饱和度也稍作变化，增加层次感
                saturation = 60 + (20 * i / max(1, n - 1))
                color = f"hsl(220, {saturation:.1f}%, {lightness:.1f}%)"
                colors.append(color)
            return colors

        # 生成颜色序列
        pie_colors = generate_blue_palette(len(labels))

        # 创建饼图
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,  # 创建圆环图
            marker=dict(
                colors=pie_colors,  # 使用同色系深浅变化
                line=dict(width=2, color='rgba(255,255,255,0.8)')
            ),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>占比: %{percent}<br>股票数: %{customdata}<extra></extra>',
            customdata=[x[2] for x in chart_data]  # 添加股票数信息到hover
        )])

        fig.update_layout(
            title=dict(
                text="持仓行业分布",
                x=0.5,
                font=dict(size=16, color='#2c3e50')
            ),
            height=500,  # 增加高度以容纳底部图例
            showlegend=True,
            legend=dict(
                orientation="h",  # 水平布局
                yanchor="top",
                y=-0.1,  # 放在图表下方
                xanchor="center",
                x=0.5,  # 居中对齐
                font=dict(size=10)
            ),
            margin=dict(t=60, b=120, l=50, r=50)  # 底部留更多空间给图例
        )

        st.plotly_chart(fig, use_container_width=True)

        # 详细数据表格（显示所有行业，不仅仅是图表中的前10个）
        st.markdown("**详细分布（完整列表）:**")
        table_data = []
        for industry_name, ratio, stock_count in all_data_sorted:
            table_data.append({
                '行业': industry_name,
                '占比': f"{ratio:.2f}%",
                '股票数': stock_count
            })

        if table_data:
            table_df = pd.DataFrame(table_data)

            # 添加排名
            table_df.reset_index(drop=True, inplace=True)
            table_df.index += 1
            table_df.index.name = '排名'

            st.dataframe(table_df, use_container_width=True)

            # 添加汇总信息
            total_industries = len(table_df)
            total_coverage = sum([float(row['占比'].replace('%', '')) for _, row in table_df.iterrows()])

            col1, col2 = st.columns(2)
            with col1:
                st.metric("行业总数", f"{total_industries}个")
            with col2:
                st.metric("覆盖仓位", f"{total_coverage:.1f}%")

    except Exception as e:
        st.error(f"行业分析出现错误: {str(e)}")


# 同时也修改industry_analysis.py中的函数，为其他地方提供饼图选项
def render_industry_pie_chart(analysis_results):
    """渲染行业分布饼图（新增函数）"""
    if not analysis_results:
        st.warning("没有行业分析数据")
        return

    # 准备数据，只显示占比大于0.1%的行业
    industries = []
    ratios = []
    stock_counts = []

    for industry_name, data in analysis_results.items():
        if data['ratio'] > 0.1:  # 只显示占比超过0.1%的
            industries.append(industry_name)
            ratios.append(data['ratio'])
            stock_counts.append(data['stock_count'])

    if not industries:
        st.warning("没有足够的数据绘制图表")
        return

    # 按比例排序
    sorted_data = sorted(zip(industries, ratios, stock_counts), key=lambda x: x[1], reverse=True)

    # 只显示前12个行业，其余合并为"其他"
    if len(sorted_data) > 12:
        main_data = sorted_data[:12]
        other_ratio = sum([x[1] for x in sorted_data[12:]])
        other_count = sum([x[2] for x in sorted_data[12:]])
        main_data.append(("其他", other_ratio, other_count))
    else:
        main_data = sorted_data

    industries_final = [x[0] for x in main_data]
    ratios_final = [x[1] for x in main_data]
    counts_final = [x[2] for x in main_data]

    # 生成同色系的颜色序列（蓝色系，从浅到深）
    def generate_blue_gradient(n):
        """生成n种深浅不同的蓝色"""
        colors = []
        for i in range(n):
            # 明度从80%逐渐降到30%
            lightness = 80 - (50 * i / max(1, n - 1))
            # 饱和度稍作变化
            saturation = 65 + (15 * i / max(1, n - 1))
            color = f"hsl(210, {saturation:.1f}%, {lightness:.1f}%)"
            colors.append(color)
        return colors

    # 创建饼图
    fig = go.Figure(data=[go.Pie(
        labels=industries_final,
        values=ratios_final,
        hole=0.3,
        marker=dict(
            colors=generate_blue_gradient(len(industries_final)),  # 使用同色系渐变
            line=dict(width=1.5, color='rgba(255,255,255,0.8)')
        ),
        textinfo='label+percent',
        textposition='outside',
        hovertemplate='<b>%{label}</b><br>占比: %{percent}<br>股票数: %{customdata}<extra></extra>',
        customdata=counts_final
    )])

    fig.update_layout(
        title=dict(
            text="持仓行业分布",
            x=0.5,
            font=dict(size=16)
        ),
        height=550,  # 增加高度以容纳底部图例
        showlegend=True,
        legend=dict(
            orientation="h",  # 水平布局
            yanchor="top",
            y=-0.1,  # 放在图表下方
            xanchor="center",
            x=0.5,  # 居中对齐
            font=dict(size=9)
        ),
        margin=dict(t=60, b=150, l=50, r=50)  # 为底部图例留出充足空间
    )

    st.plotly_chart(fig, use_container_width=True)


def render_industry_bar_chart(analysis_results):
    """渲染行业分布柱状图（保留原有函数作为备选）"""
    if not analysis_results:
        st.warning("没有行业分析数据")
        return

    # 准备数据，只显示占比大于0.1%的行业
    industries = []
    ratios = []

    for industry_name, data in analysis_results.items():
        if data['ratio'] > 0.1:  # 只显示占比超过0.1%的
            industries.append(industry_name)
            ratios.append(data['ratio'])

    if not industries:
        st.warning("没有足够的数据绘制图表")
        return

    # 按比例排序
    sorted_data = sorted(zip(industries, ratios), key=lambda x: x[1], reverse=True)
    industries_sorted = [x[0] for x in sorted_data]
    ratios_sorted = [x[1] for x in sorted_data]

    # 创建柱状图
    fig = go.Figure(data=[
        go.Bar(
            x=industries_sorted,
            y=ratios_sorted,
            marker=dict(
                color=ratios_sorted,
                colorscale='Reds',  # 红色渐变
                showscale=True,
                colorbar=dict(title="占比 (%)")
            ),
            text=[f"{ratio:.1f}%" for ratio in ratios_sorted],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>占比: %{y:.1f}%<extra></extra>'
        )
    ])

    fig.update_layout(
        title=dict(
            text="持仓行业分布",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="行业",
            tickangle=45 if len(industries_sorted) > 5 else 0
        ),
        yaxis=dict(
            title="占比 (%)",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)'
        ),
        height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=50, t=60, b=100)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_refresh_button():
    """渲染刷新按钮"""
    if st.button("🔄 刷新数据", use_container_width=True):
        st.rerun()


# 获取周度数据的辅助函数（保持原有功能）
def get_weekly_nav_data(nav_data):
    """获取周度净值数据"""
    if not nav_data.empty:
        nav_data['date'] = pd.to_datetime(nav_data['date'])
        nav_data = nav_data.sort_values('date')

        # 按周分组（周一为一周的开始）
        nav_data['week'] = nav_data['date'].dt.to_period('W-MON')

        # 每周取最后一个交易日的数据
        weekly_data = nav_data.groupby('week').last().reset_index()

        # 计算周度收益率
        if len(weekly_data) > 1:
            weekly_data['weekly_return'] = weekly_data['nav_value'].pct_change() * 100

        return weekly_data.reset_index(drop=True)
    else:
        return pd.DataFrame()