"""
行业分析组件
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


def analyze_holdings_by_industry(db, product_code, analysis_date):
    """分析持仓在各行业中的分布"""
    # 获取该日期的持仓
    holdings = db.get_holdings_by_date(product_code, analysis_date)

    if holdings.empty:
        return None

    # 获取所有行业
    industries = db.get_all_industries()

    if not industries:
        return None

    analysis_results = {}
    total_position = holdings['position_ratio'].sum()
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

    return analysis_results


def render_industry_bar_chart(analysis_results):
    """渲染行业分布柱状图"""
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


def analyze_holdings_by_market(holdings):
    """按市场分类分析持仓"""
    market_results = {'科创板': 0, '创业板': 0, '主板': 0}

    for _, holding in holdings.iterrows():
        code = holding['stock_code'][:6]
        if code.startswith(('688', '689')):
            market_results['科创板'] += holding['position_ratio']
        elif code.startswith('300'):
            market_results['创业板'] += holding['position_ratio']
        else:
            market_results['主板'] += holding['position_ratio']

    return market_results


def render_market_pie_chart(market_results):
    """渲染市场分布饼状图"""
    labels = []
    values = []

    for market, ratio in market_results.items():
        if ratio > 0.1:
            labels.append(market)
            values.append(ratio)

    if not values:
        return

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(
            colors=px.colors.sequential.Oranges_r[2:],  # 使用橙色渐变（倒序，深色优先）
            line=dict(width=2, color='rgba(255,255,255,0.3)')
        ),
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>占比: %{percent}<extra></extra>'
    )])

    fig.update_layout(
        title="市场分布",
        height=400,
        showlegend=False,
        margin=dict(t=50, b=50, l=50, r=50)
    )

    st.plotly_chart(fig, use_container_width=True)