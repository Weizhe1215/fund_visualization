"""
持仓分析组件
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from config import MAJOR_INDICES
import sqlite3
import sqlite3
import plotly.express as px


def analyze_holdings_by_index(db, product_code, analysis_date):
    """分析持仓在各指数中的分布"""
    # 获取该日期的持仓
    holdings = db.get_holdings_by_date(product_code, analysis_date)

    if holdings.empty:
        return None

    analysis_results = {}
    total_position = holdings['position_ratio'].sum()

    # 分析各主要指数
    for index_name, index_code in MAJOR_INDICES.items():

        # 获取该指数在该日期（或最近日期）的成分股
        index_components = db.get_index_components_by_date(index_code, analysis_date)

        if not index_components.empty:
            # 取最近日期的数据
            latest_date = index_components['date'].max()
            index_stocks = index_components[index_components['date'] == latest_date]['stock_code'].tolist()

            # 计算持仓中属于该指数的比例
            index_holdings = holdings[holdings['stock_code'].isin(index_stocks)]
            index_ratio = index_holdings['position_ratio'].sum()

            analysis_results[index_name] = {
                'ratio': index_ratio,
                'stock_count': len(index_holdings),
                'reference_date': latest_date
            }
        else:
            analysis_results[index_name] = {
                'ratio': 0.0,
                'stock_count': 0,
                'reference_date': None
            }


    # 计算"其他"部分
    total_index_ratio = sum([result['ratio'] for result in analysis_results.values()])
    other_ratio = max(0, total_position - total_index_ratio)

    analysis_results['微盘⚠️⚠️'] = {
        'ratio': other_ratio,
        'stock_count': len(holdings) - sum([result['stock_count'] for result in analysis_results.values()]),
        'reference_date': analysis_date
    }

    return analysis_results


def render_holdings_pie_chart(analysis_results):
    """渲染持仓分布饼状图"""
    if not analysis_results:
        return

    # 准备饼状图数据
    labels = []
    values = []
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3']

    for i, (index_name, data) in enumerate(analysis_results.items()):
        if data['ratio'] > 0.1:  # 只显示占比超过0.1%的部分
            labels.append(index_name)
            values.append(data['ratio'])

    if not values:
        st.warning("没有足够的数据绘制饼状图")
        return

    # 创建饼状图
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(
            colors=px.colors.sequential.Blues_r[2:],  # 使用蓝色渐变（倒序，深色优先）
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
            font=dict(size=16, color='#2c3e50')
        ),
        height=400,
        showlegend=False,
        margin=dict(t=50, b=50, l=50, r=50)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_analysis(db, product_code):
    """渲染持仓分析页面"""
    st.header("📊 持仓分析")

    if not product_code:
        st.warning("请先在左侧选择一个产品")
        return

    # 获取可用日期
    available_dates = db.get_available_dates(product_code)

    if not available_dates:
        st.warning("该产品暂无持仓数据")
        return

    # 日期选择
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_date = st.selectbox(
            "分析日期",
            options=available_dates,
            key="analysis_date_selector"
        )

    # 进行分析
    analysis_results = analyze_holdings_by_index(db, product_code, selected_date)

    if not analysis_results:
        st.error("分析失败，请检查数据")
        return

    # 显示分析结果
    col1, col2 = st.columns([1, 1])

    with col1:
        # 饼状图
        render_holdings_pie_chart(analysis_results)

    with col2:
        # 详细数据表
        st.subheader("详细分布")

        # 准备表格数据
        table_data = []
        for index_name, data in analysis_results.items():
            table_data.append({
                '指数': index_name,
                '占比': f"{data['ratio']:.2f}%",
                '股票数': data['stock_count'],
                '参考日期': data['reference_date'] or '无数据'
            })

        # 按占比排序
        table_df = pd.DataFrame(table_data)
        table_df['占比_num'] = table_df['占比'].str.replace('%', '').astype(float)
        table_df = table_df.sort_values('占比_num', ascending=False)
        table_df = table_df.drop('占比_num', axis=1)

        st.dataframe(table_df, use_container_width=True, hide_index=True)

        # 显示总计
        total_ratio = sum([data['ratio'] for data in analysis_results.values()])
        st.metric("总持仓比例", f"{total_ratio:.2f}%")

    # 警告信息
    st.info("💡 **说明：** 分析基于指数成分股数据库中离选定日期最近的数据进行匹配")

    # 显示缺失的指数数据
    missing_indices = []
    for index_name, data in analysis_results.items():
        if index_name != '其他' and data['reference_date'] is None:
            missing_indices.append(index_name)

    if missing_indices:
        st.warning(f"⚠️ 以下指数缺少成分股数据：{', '.join(missing_indices)}")
        st.info("请在'指数成分股管理'页面导入相关数据以获得更准确的分析结果")
