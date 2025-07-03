"""
交互式净值曲线图表组件
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import sqlite3
from datetime import datetime

def render_nav_chart(db, product_code):
    """渲染交互式净值曲线图表"""
    st.subheader("📈 净值走势图")

    # 获取净值数据
    nav_data = db.get_nav_data(product_code)

    if nav_data.empty:
        st.warning("该产品暂无净值数据")
        return None

    # 数据预处理
    nav_data['date'] = pd.to_datetime(nav_data['date'])
    nav_data = nav_data.sort_values('date')

    # 计算收益率
    nav_data['daily_return'] = nav_data['nav_value'].pct_change() * 100
    nav_data['cumulative_return'] = (nav_data['nav_value'] / nav_data['nav_value'].iloc[0] - 1) * 100

    # 创建图表
    fig = go.Figure()

    # 添加单位净值线
    fig.add_trace(go.Scatter(
        x=nav_data['date'],
        y=nav_data['nav_value'],
        mode='lines+markers',
        name='单位净值',
        line=dict(color='#2E86AB', width=3),  # 高级蓝色，更粗的线条
        marker=dict(size=5, color='#2E86AB'),
        hovertemplate='<b>日期</b>: %{x}<br>' +
                      '<b>单位净值</b>: %{y:.4f}<br>' +
                      '<extra></extra>',
        connectgaps=True
    ))

    # 如果有累计净值数据
    if 'cumulative_nav' in nav_data.columns and not nav_data['cumulative_nav'].isna().all():
        fig.add_trace(go.Scatter(
            x=nav_data['date'],
            y=nav_data['cumulative_nav'],
            mode='lines+markers',
            name='累计净值',
            line=dict(color='#E76F51', width=3),  # 高级橙红色
            marker=dict(size=5, color='#E76F51'),
            hovertemplate='<b>日期</b>: %{x}<br>' +
                          '<b>累计净值</b>: %{y:.4f}<br>' +
                          '<extra></extra>',
            connectgaps=True,
            yaxis='y2'
        ))

        # 添加第二个Y轴
        fig.update_layout(
            yaxis2=dict(
                title="累计净值",
                overlaying='y',
                side='right',
                showgrid=False
            )
        )

    # 获取持仓日期，在图上标记
    available_dates = db.get_available_dates(product_code)
    if available_dates:
        # 在图表标题中提示有持仓数据的日期
        holding_dates_str = f"（共{len(available_dates)}个持仓日期）"
    else:
        holding_dates_str = ""

    # 设置图表布局
    fig.update_layout(
        title=dict(
            text=f"{product_code} 净值走势{holding_dates_str}",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="日期",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            showline=True,
            linecolor='rgba(128,128,128,0.5)'
        ),
        yaxis=dict(
            title="单位净值",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)',
            showline=True,
            linecolor='rgba(128,128,128,0.5)'
        ),
        hovermode='x unified',
        height=450,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Arial, sans-serif", size=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=80, b=50)
    )

    # 显示图表
    st.plotly_chart(fig, use_container_width=True, key=f"nav_chart_{product_code}")

    # 添加提示信息
    if available_dates:
        st.info(f"💡 提示：该产品共有 {len(available_dates)} 个持仓日期，请使用右侧的日期选择器查看具体持仓")

    return None