"""
外部用户净值展示组件
专为移动端优化的简洁净值查看界面
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from components.auth import AuthManager


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
    if 'selected_product' in st.session_state and st.session_state.selected_product:
        # 验证权限
        if auth_manager.has_product_permission(st.session_state.selected_product):
            selected_product = next(
                (p for p in user_products if p['product_code'] == st.session_state.selected_product),
                None
            )
            if selected_product:
                # 返回按钮
                if st.button("⬅️ 返回产品列表", key="back_to_list"):
                    st.session_state.selected_product = None
                    st.rerun()

                st.markdown("---")
                render_product_detail(auth_manager, db, selected_product['product_code'], selected_product['product_name'])
                return

    # 直接显示产品列表，移除多余的标题
    st.markdown("### 📊 选择要查看的产品")
    render_product_list(auth_manager, db, user_products)


def render_product_list(auth_manager: AuthManager, db, user_products):
    """渲染产品列表"""

    for product in user_products:
        product_code = product['product_code']
        product_name = product['product_name']

        # 获取最新净值数据
        nav_data = db.get_nav_data(product_code)

        # 使用 expander 或简单的布局，避免多余的容器
        col1, col2 = st.columns([4, 1])

        with col1:
            st.markdown(f"**{product_name}**")
            st.caption(f"产品代码：{product_code}")

            if not nav_data.empty:
                latest_nav = nav_data.iloc[-1]
                latest_date = latest_nav['date']
                nav_value = latest_nav['nav_value']

                # 计算涨跌
                if len(nav_data) > 1:
                    prev_nav = nav_data.iloc[-2]['nav_value']
                    change = nav_value - prev_nav
                    change_pct = (change / prev_nav) * 100

                    change_color = "green" if change > 0 else "red" if change < 0 else "gray"
                    change_text = f"+{change:.4f} (+{change_pct:.2f}%)" if change > 0 else f"{change:.4f} ({change_pct:.2f}%)"

                    st.markdown(f"**净值：{nav_value:.4f}** :{change_color}[{change_text}]")
                else:
                    st.markdown(f"**最新净值：** {nav_value:.4f}")

                st.caption(f"更新时间：{latest_date}")
            else:
                st.caption("暂无净值数据")

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

    # 持仓概览（可选）
    render_mobile_holdings_summary(db, product_code)


def render_mobile_metrics_cards(nav_data):
    """渲染移动端优化的指标卡片（简化版）"""
    if nav_data.empty:
        return

    latest_data = nav_data.iloc[-1]

    # 计算指标
    current_nav = latest_data['nav_value']
    total_return = latest_data['cumulative_return']
    daily_return = latest_data['daily_return'] if not pd.isna(latest_data['daily_return']) else 0

    st.markdown("### 📊 关键指标")

    # 只保留两个核心指标卡片
    metrics_html = f"""
    <style>
    .metrics-container {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
        margin: 1rem 0;
        width: 100%;
        box-sizing: border-box;
    }}
    
    .metric-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }}
    
    .metric-value {{
        font-size: 1.5rem;
        font-weight: bold;
        margin: 0.5rem 0;
        line-height: 1.2;
    }}
    
    .metric-label {{
        font-size: 0.9rem;
        opacity: 0.9;
        margin-bottom: 0.3rem;
        line-height: 1.2;
    }}
    
    .metric-change {{
        font-size: 0.8rem;
        opacity: 0.8;
        margin-top: 0.3rem;
        line-height: 1.2;
    }}
    
    @media (max-width: 600px) {{
        .metrics-container {{
            gap: 0.75rem;
        }}
        .metric-card {{
            padding: 1.25rem;
        }}
        .metric-value {{
            font-size: 1.3rem;
        }}
    }}
    </style>
    
    <div class="metrics-container">
        <div class="metric-card">
            <div class="metric-label">最新净值</div>
            <div class="metric-value">{current_nav:.4f}</div>
            <div class="metric-change">日涨跌: {daily_return:+.2f}%</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">累计收益</div>
            <div class="metric-value">{total_return:+.2f}%</div>
            <div class="metric-change">成立以来</div>
        </div>
    </div>
    """

    st.components.v1.html(metrics_html, height=150)


def render_mobile_optimized_plotly_chart(nav_data, product_name):
    """渲染移动端优化的Plotly图表（仅周频数据）"""
    st.markdown("### 📈 净值走势")

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

    # 数据筛选
    if period != "全部":
        days_map = {"近1年": 365, "近6个月": 180, "近3个月": 90, "近1个月": 30}
        days = days_map[period]
        cutoff_date = nav_data['date'].max() - pd.Timedelta(days=days)
        filtered_data = nav_data[nav_data['date'] >= cutoff_date]
    else:
        filtered_data = nav_data

    if filtered_data.empty:
        st.warning("选定期间内无数据")
        return

    # 转换为周频数据
    chart_data = convert_to_weekly_data(filtered_data)
    if chart_data.empty:
        st.warning("周频数据不足")
        return

    # 创建移动端优化的Plotly图表
    fig = go.Figure()

    if chart_type == "净值走势":
        y_data = chart_data['nav_value']
        y_title = "净值"
        hover_template = '<b>%{x}</b><br>净值: %{y:.4f}<extra></extra>'
        line_color = '#1f77b4'
    else:
        y_data = chart_data['cumulative_return']
        y_title = "累计收益率 (%)"
        hover_template = '<b>%{x}</b><br>收益率: %{y:.2f}%<extra></extra>'
        line_color = '#10b981' if y_data.iloc[-1] >= 0 else '#ef4444'

    fig.add_trace(go.Scatter(
        x=chart_data['date'],
        y=y_data,
        mode='lines+markers',  # 周频数据显示线条+标记点
        name=chart_type,
        line=dict(color=line_color, width=3),
        marker=dict(size=6, color=line_color),
        hovertemplate=hover_template,
        fill='tonexty' if chart_type == "收益率" else None,
        fillcolor=f'rgba({",".join(map(str, [int(line_color[i:i+2], 16) for i in (1, 3, 5)]))}, 0.1)' if chart_type == "收益率" else None
    ))

    # 移动端优化的布局配置
    fig.update_layout(
        # 完全不设置 title，让图表没有标题
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            tickfont=dict(size=10),
            tickangle=0
        ),
        yaxis=dict(
            title=y_title,
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            tickfont=dict(size=10)
        ),
        height=350,
        margin=dict(l=40, r=20, t=10, b=30),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        showlegend=False,
        # 移动端优化配置
        font=dict(size=11),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Arial"
        )
    )

    # 移动端友好的配置
    config = {
        'displayModeBar': False,
        'scrollZoom': False,
        'doubleClick': 'reset',
        'showTips': False,
        'responsive': True,
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'{product_name}_{chart_type}_weekly',
            'height': 500,
            'width': 700,
            'scale': 1
        }
    }

    st.plotly_chart(fig, use_container_width=True, config=config)

    # 显示周频数据点数量信息
    st.caption(f"📊 显示 {len(chart_data)} 个周度数据点（每周最后交易日）")


def convert_to_weekly_data(daily_data):
    """将日频数据转换为周频数据（每周最后一个交易日，不超过当前日期）"""
    if daily_data.empty:
        return daily_data

    # 确保数据按日期排序
    data = daily_data.copy().sort_values('date')
    data['date'] = pd.to_datetime(data['date'])

    # 获取当前日期，不显示未来数据
    current_date = pd.Timestamp.now().normalize()
    data = data[data['date'] <= current_date]

    if data.empty:
        return data

    # 添加星期信息（0=周一, 6=周日）
    data['weekday'] = data['date'].dt.weekday

    # 添加年-周信息用于分组
    data['year_week'] = data['date'].dt.isocalendar().week.astype(str) + '-' + data['date'].dt.isocalendar().year.astype(str)

    # 按年-周分组处理
    weekly_results = []

    for week_key, week_group in data.groupby('year_week'):
        # 排序确保日期顺序
        week_group = week_group.sort_values('date')

        # 优先选择周五（weekday=4），如果没有周五则选择本周最后一个交易日
        friday_data = week_group[week_group['weekday'] == 4]  # 周五

        if not friday_data.empty:
            # 如果有周五数据，选择周五
            weekly_point = friday_data.iloc[-1]  # 如果有多个周五，取最后一个
        else:
            # 如果没有周五数据，选择本周最后一个交易日
            # 优先级：周四 > 周三 > 周二 > 周一 > 周六 > 周日
            for preferred_day in [3, 2, 1, 0, 5, 6]:  # 周四到周日
                day_data = week_group[week_group['weekday'] == preferred_day]
                if not day_data.empty:
                    weekly_point = day_data.iloc[-1]
                    break
            else:
                # 如果上面都没找到，就取本周最后一天（兜底）
                weekly_point = week_group.iloc[-1]

        weekly_results.append(weekly_point)

    # 转换为DataFrame
    if weekly_results:
        weekly_data = pd.DataFrame(weekly_results)
        weekly_data = weekly_data.drop(['weekday', 'year_week'], axis=1)

        # 重新计算累计收益率（基于周频数据）
        if 'nav_value' in weekly_data.columns:
            weekly_data['cumulative_return'] = (weekly_data['nav_value'] / weekly_data['nav_value'].iloc[0] - 1) * 100

            # 计算周收益率
            weekly_data['weekly_return'] = weekly_data['nav_value'].pct_change() * 100

        return weekly_data.reset_index(drop=True)
    else:
        return pd.DataFrame()


def render_mobile_holdings_summary(db, product_code):
    """渲染移动端优化的持仓概览"""
    available_dates = db.get_available_dates(product_code)

    if not available_dates:
        return

    latest_date = max(available_dates)
    holdings = db.get_holdings_by_date(product_code, latest_date)

    if holdings.empty:
        return

    # 使用expander，但样式优化
    with st.expander(f"📋 持仓概览 ({latest_date})", expanded=False):
        # 前8大持仓（移动端显示适中数量）
        if 'position_ratio' in holdings.columns:
            top_holdings = holdings.nlargest(8, 'position_ratio')

            # 使用更简洁的表格显示
            display_data = []
            for idx, holding in top_holdings.iterrows():
                stock_name = holding['stock_name'] or holding['stock_code']
                if len(stock_name) > 6:  # 移动端截断长名称
                    stock_name = stock_name[:6] + "..."

                display_data.append({
                    "股票": f"{stock_name}",
                    "代码": holding['stock_code'],
                    "仓位": f"{holding['position_ratio']:.2f}%"
                })

            # 创建DataFrame并显示
            df_holdings = pd.DataFrame(display_data)
            st.dataframe(df_holdings, hide_index=True, use_container_width=True)

            # 汇总信息
            total_ratio = holdings['position_ratio'].sum()
            stock_count = len(holdings)

            st.markdown(f"""
            <div style='background: #f0f2f6; padding: 0.75rem; border-radius: 8px; text-align: center; margin-top: 1rem;'>
                <strong>📊 持仓汇总：</strong>{stock_count} 只股票，总仓位 {total_ratio:.1f}%
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("持仓数据格式异常")


def render_key_metrics(nav_data):
    """渲染关键指标卡片"""
    latest_data = nav_data.iloc[-1]

    # 计算指标
    current_nav = latest_data['nav_value']
    total_return = latest_data['cumulative_return']
    daily_return = latest_data['daily_return'] if not pd.isna(latest_data['daily_return']) else 0
    volatility = nav_data['daily_return'].std()

    st.markdown("### 📊 关键指标")

    # 响应式指标卡片
    col1, col2 = st.columns(2)

    with col1:
        render_metric_card("最新净值", f"{current_nav:.4f}", f"日涨跌: {daily_return:+.2f}%")
        render_metric_card("波动率", f"{volatility:.2f}%", "日收益率标准差")

    with col2:
        render_metric_card("累计收益", f"{total_return:+.2f}%", "成立以来收益率")
        render_metric_card("数据天数", f"{len(nav_data)}", f"最新: {latest_data['date'].strftime('%Y-%m-%d')}")


def render_metric_card(title, value, subtitle):
    """渲染单个指标卡片"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def render_mobile_nav_chart(nav_data, product_name):
    """渲染移动端优化的净值图表"""
    st.markdown("### 📈 净值走势")

    # 时间范围选择器
    col1, col2 = st.columns(2)

    with col1:
        period = st.selectbox(
            "查看期间",
            ["全部", "近1年", "近6个月", "近3个月", "近1个月"],
            index=0
        )

    with col2:
        chart_type = st.selectbox(
            "图表类型",
            ["净值走势", "收益率"],
            index=0
        )

    # 根据选择的期间筛选数据
    if period != "全部":
        days_map = {"近1年": 365, "近6个月": 180, "近3个月": 90, "近1个月": 30}
        days = days_map[period]
        cutoff_date = nav_data['date'].max() - timedelta(days=days)
        filtered_data = nav_data[nav_data['date'] >= cutoff_date]
    else:
        filtered_data = nav_data

    if filtered_data.empty:
        st.warning("选定期间内无数据")
        return

    # 创建图表
    fig = go.Figure()

    if chart_type == "净值走势":
        y_data = filtered_data['nav_value']
        y_title = "净值"
        hover_template = '<b>日期</b>: %{x}<br><b>净值</b>: %{y:.4f}<extra></extra>'
    else:
        y_data = filtered_data['cumulative_return']
        y_title = "累计收益率 (%)"
        hover_template = '<b>日期</b>: %{x}<br><b>收益率</b>: %{y:.2f}%<extra></extra>'

    fig.add_trace(go.Scatter(
        x=filtered_data['date'],
        y=y_data,
        mode='lines',
        name=chart_type,
        line=dict(color='#1f77b4', width=3),
        hovertemplate=hover_template,
        fill='tonexty' if chart_type == "收益率" else None,
        fillcolor='rgba(31, 119, 180, 0.1)' if chart_type == "收益率" else None
    ))

    # 移动端优化的图表布局
    fig.update_layout(
        title=dict(
            text=f"{product_name} - {chart_type}",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)'
        ),
        yaxis=dict(
            title=y_title,
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)'
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


def render_holdings_summary(db, product_code):
    """渲染持仓概览"""
    # 获取最新持仓日期
    available_dates = db.get_available_dates(product_code)

    if not available_dates:
        return

    latest_date = max(available_dates)
    holdings = db.get_holdings_by_date(product_code, latest_date)

    if holdings.empty:
        return

    # 可展开的持仓信息
    with st.expander(f"📋 持仓概览 ({latest_date})", expanded=False):
        # 前10大持仓
        top_holdings = holdings.nlargest(10, 'position_ratio')

        st.markdown("**前10大持仓：**")

        for idx, holding in top_holdings.iterrows():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"**{holding['stock_name']}**")
                st.caption(f"{holding['stock_code']}")

            with col2:
                st.write(f"{holding['position_ratio']:.2f}%")

        # 汇总信息
        total_ratio = holdings['position_ratio'].sum()
        stock_count = len(holdings)

        st.markdown("---")
        st.markdown(f"**持仓汇总：** {stock_count} 只股票，总仓位 {total_ratio:.2f}%")


def render_refresh_button():
    """渲染刷新按钮"""
    if st.button("🔄 刷新数据", use_container_width=True):
        st.rerun()