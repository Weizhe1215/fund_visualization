"""
移动端优化图表组件
使用 Chart.js 和自定义 HTML/CSS 替代 Plotly，更适合移动端
将此文件保存为：components/mobile_chart.py
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta


def render_mobile_optimized_nav_chart(nav_data, product_name):
    """渲染移动端优化的净值图表"""
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
        cutoff_date = nav_data['date'].max() - timedelta(days=days)
        filtered_data = nav_data[nav_data['date'] >= cutoff_date]
    else:
        filtered_data = nav_data

    if filtered_data.empty:
        st.warning("选定期间内无数据")
        return

    # 准备图表数据
    chart_data = prepare_chart_data(filtered_data, chart_type)

    # 渲染图表
    render_chart_js_chart(chart_data, product_name, chart_type)


def prepare_chart_data(data, chart_type):
    """准备图表数据"""
    data = data.copy()
    data['date_str'] = data['date'].dt.strftime('%Y-%m-%d')

    if chart_type == "净值走势":
        y_data = data['nav_value'].tolist()
        y_label = "净值"
    else:
        y_data = data['cumulative_return'].tolist()
        y_label = "累计收益率 (%)"

    return {
        'labels': data['date_str'].tolist(),
        'data': y_data,
        'label': y_label,
        'chart_type': chart_type
    }


def render_chart_js_chart(chart_data, product_name, chart_type):
    """使用 Chart.js 渲染移动端优化图表"""

    # 颜色配置
    if chart_type == "净值走势":
        line_color = "#1f77b4"
        fill_color = "rgba(31, 119, 180, 0.1)"
    else:
        # 收益率图表根据正负使用不同颜色
        last_value = chart_data['data'][-1] if chart_data['data'] else 0
        line_color = "#10b981" if last_value >= 0 else "#ef4444"
        fill_color = "rgba(16, 185, 129, 0.1)" if last_value >= 0 else "rgba(239, 68, 68, 0.1)"

    # 生成唯一的图表ID
    chart_id = f"chart_{hash(product_name + chart_type) % 10000}"

    # HTML + Chart.js 图表
    chart_html = f"""
    <div style="width: 100%; height: 350px; margin: 1rem 0;">
        <canvas id="{chart_id}" style="width: 100%; height: 100%;"></canvas>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/chart.js/3.9.1/chart.min.js"></script>
    <script>
    (function() {{
        const ctx = document.getElementById('{chart_id}');
        if (!ctx) return;
        
        // 销毁已存在的图表
        if (window.chartInstance_{chart_id}) {{
            window.chartInstance_{chart_id}.destroy();
        }}
        
        const data = {json.dumps(chart_data['data'])};
        const labels = {json.dumps(chart_data['labels'])};
        
        const config = {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: '{chart_data["label"]}',
                    data: data,
                    borderColor: '{line_color}',
                    backgroundColor: '{fill_color}',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.1,
                    pointRadius: 2,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '{line_color}',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                    mode: 'index'
                }},
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: '{line_color}',
                        borderWidth: 1,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {{
                            title: function(context) {{
                                return '日期: ' + context[0].label;
                            }},
                            label: function(context) {{
                                const value = context.parsed.y;
                                if ('{chart_type}' === '净值走势') {{
                                    return '净值: ' + value.toFixed(4);
                                }} else {{
                                    return '收益率: ' + value.toFixed(2) + '%';
                                }}
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        display: true,
                        grid: {{
                            color: 'rgba(0, 0, 0, 0.1)',
                            drawOnChartArea: true
                        }},
                        ticks: {{
                            maxTicksLimit: 6,
                            color: '#666666',
                            font: {{
                                size: 11
                            }}
                        }}
                    }},
                    y: {{
                        display: true,
                        grid: {{
                            color: 'rgba(0, 0, 0, 0.1)',
                            drawOnChartArea: true
                        }},
                        ticks: {{
                            color: '#666666',
                            font: {{
                                size: 11
                            }},
                            callback: function(value) {{
                                if ('{chart_type}' === '净值走势') {{
                                    return value.toFixed(3);
                                }} else {{
                                    return value.toFixed(1) + '%';
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }};
        
        window.chartInstance_{chart_id} = new Chart(ctx, config);
    }})();
    </script>
    """

    st.components.v1.html(chart_html, height=380)


def render_simple_metrics_cards(nav_data):
    """渲染简化的指标卡片（移动端优化）"""
    if nav_data.empty:
        return

    latest_data = nav_data.iloc[-1]

    # 计算指标
    current_nav = latest_data['nav_value']
    total_return = latest_data['cumulative_return']
    daily_return = latest_data['daily_return'] if not pd.isna(latest_data['daily_return']) else 0

    # 使用原生HTML渲染，避免Streamlit组件
    metrics_html = f"""
    <style>
    .metric-container {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
        margin: 1rem 0;
    }}
    
    .metric-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    
    .metric-value {{
        font-size: 1.4rem;
        font-weight: bold;
        margin: 0.5rem 0;
        line-height: 1.2;
    }}
    
    .metric-label {{
        font-size: 0.85rem;
        opacity: 0.9;
        margin-bottom: 0.25rem;
    }}
    
    .metric-change {{
        font-size: 0.75rem;
        opacity: 0.8;
        margin-top: 0.25rem;
    }}
    
    @media (max-width: 480px) {{
        .metric-container {{
            gap: 0.5rem;
        }}
        .metric-card {{
            padding: 0.75rem;
        }}
        .metric-value {{
            font-size: 1.2rem;
        }}
    }}
    </style>
    
    <div class="metric-container">
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
        
        <div class="metric-card">
            <div class="metric-label">数据天数</div>
            <div class="metric-value">{len(nav_data)}</div>
            <div class="metric-change">最新: {latest_data['date'].strftime('%m-%d')}</div>
        </div>
        
        <div class="metric-card">
            <div class="metric-label">波动率</div>
            <div class="metric-value">{nav_data['daily_return'].std():.2f}%</div>
            <div class="metric-change">日收益标准差</div>
        </div>
    </div>
    """

    st.components.v1.html(metrics_html, height=180)


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
        # 前5大持仓（移动端显示更少）
        top_holdings = holdings.nlargest(5, 'position_ratio')

        # 使用HTML表格，更适合移动端
        holdings_html = """
        <style>
        .holdings-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .holdings-table th, .holdings-table td {
            padding: 0.5rem;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        .holdings-table th {
            background-color: #f8f9fa;
            font-weight: bold;
            font-size: 0.85rem;
        }
        .position-ratio {
            font-weight: bold;
            color: #1f77b4;
        }
        </style>
        <table class="holdings-table">
            <thead>
                <tr>
                    <th>股票名称</th>
                    <th style="text-align: right;">仓位比例</th>
                </tr>
            </thead>
            <tbody>
        """

        for idx, holding in top_holdings.iterrows():
            stock_name = holding['stock_name'] or holding['stock_code']
            if len(stock_name) > 8:  # 移动端截断长名称
                stock_name = stock_name[:8] + "..."

            holdings_html += f"""
                <tr>
                    <td>{stock_name}<br><small style="color: #666;">{holding['stock_code']}</small></td>
                    <td style="text-align: right;" class="position-ratio">{holding['position_ratio']:.2f}%</td>
                </tr>
            """

        holdings_html += "</tbody></table>"

        # 汇总信息
        total_ratio = holdings['position_ratio'].sum()
        stock_count = len(holdings)

        holdings_html += f"""
        <div style="margin-top: 1rem; padding: 0.75rem; background: #f8f9fa; border-radius: 8px; text-align: center;">
            <strong>持仓汇总：</strong>{stock_count} 只股票，总仓位 {total_ratio:.1f}%
        </div>
        """

        st.components.v1.html(holdings_html, height=280)