"""
可转债分析组件
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import glob
from datetime import datetime


def get_latest_conv_bond_files():
    """获取最新的可转债分析文件"""
    conv_bond_dir = "data/conv_bond"

    if not os.path.exists(conv_bond_dir):
        return None, None

    # 查找关联文件
    relation_files = glob.glob(os.path.join(conv_bond_dir, "可转债正股关联_*.csv"))
    analysis_files = glob.glob(os.path.join(conv_bond_dir, "可转债分析数据_*.csv"))

    if not relation_files or not analysis_files:
        return None, None

    # 按日期排序，选择最新的
    def extract_date(filename):
        try:
            date_part = filename.split('_')[-1].replace('.csv', '')
            return datetime.strptime(date_part, '%Y%m%d')
        except:
            return datetime.min

    latest_relation = max(relation_files, key=extract_date)
    latest_analysis = max(analysis_files, key=extract_date)

    return latest_relation, latest_analysis


def load_conv_bond_data():
    """加载可转债数据"""
    relation_file, analysis_file = get_latest_conv_bond_files()

    if not relation_file or not analysis_file:
        return None, None

    try:
        # 读取关联数据 - 尝试多种编码和分隔符
        encodings = ['gbk', 'gb2312', 'utf-8-sig', 'utf-8']
        separators = [',', '\t', ';', '|']
        relation_df = None
        analysis_df = None

        # 读取关联文件
        for encoding in encodings:
            for sep in separators:
                try:
                    relation_df = pd.read_csv(relation_file, encoding=encoding, sep=sep)
                    if relation_df.shape[1] > 1:
                        break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            if relation_df is not None and relation_df.shape[1] > 1:
                break

        if relation_df is None or relation_df.shape[1] <= 1:
            raise Exception(f"无法正确解析关联文件: {relation_file}")

        # 读取分析文件
        for encoding in encodings:
            for sep in separators:
                try:
                    analysis_df = pd.read_csv(analysis_file, encoding=encoding, sep=sep)
                    if analysis_df.shape[1] > 1:
                        break
                except (UnicodeDecodeError, pd.errors.ParserError):
                    continue
            if analysis_df is not None and analysis_df.shape[1] > 1:
                break

        if analysis_df is None or analysis_df.shape[1] <= 1:
            raise Exception(f"无法正确解析分析文件: {analysis_file}")

        return relation_df, analysis_df
    except Exception as e:
        st.error(f"读取可转债数据失败: {e}")
        return None, None


def analyze_conv_bond_holdings(holdings_data, relation_df, analysis_df, industry_db):
    """分析持仓中的可转债"""
    # 筛选出1开头的股票代码（可转债）
    conv_bond_holdings = holdings_data[holdings_data['stock_code'].str.startswith('1')].copy()

    if conv_bond_holdings.empty:
        return None

    # 提取6位数字代码进行匹配
    conv_bond_holdings['code_6digit'] = conv_bond_holdings['stock_code'].str[:6]

    # 动态找到正确的列名
    relation_code_col = None
    analysis_code_col = None

    # 查找转债代码列
    for col in relation_df.columns:
        if '转债代码' in col or '债券代码' in col or '代码' in col:
            relation_code_col = col
            break

    for col in analysis_df.columns:
        if '转债代码' in col or '债券代码' in col or '代码' in col:
            analysis_code_col = col
            break

    if relation_code_col is None or analysis_code_col is None:
        return None

    # 标准化代码格式
    relation_df[relation_code_col] = relation_df[relation_code_col].astype(str).str.replace(r'\D', '',
                                                                                            regex=True).str.zfill(6)
    analysis_df[analysis_code_col] = analysis_df[analysis_code_col].astype(str).str.replace(r'\D', '',
                                                                                            regex=True).str.zfill(6)

    # 与关联表匹配
    merged_df = conv_bond_holdings.merge(
        relation_df,
        left_on='code_6digit',
        right_on=relation_code_col,
        how='left'
    )

    # 与分析数据匹配
    final_df = merged_df.merge(
        analysis_df,
        left_on='code_6digit',
        right_on=analysis_code_col,
        how='left',
        suffixes=('', '_analysis')
    )

    return final_df


def analyze_conv_bond_by_industry(conv_bond_df, industry_db):
    """分析可转债按行业分布"""
    if conv_bond_df is None or conv_bond_df.empty:
        return None

    # 获取所有行业
    industries = industry_db.get_all_industries()
    if not industries:
        return None

    analysis_results = {}
    total_position = conv_bond_df['position_ratio'].sum()
    matched_bonds = set()

    # 分析各行业
    for industry_name in industries:
        # 获取该行业的股票代码（6位数字）
        industry_stocks_6digit = industry_db.get_industry_stocks(industry_name)

        # 通过正股代码匹配
        # 通过正股代码匹配
        matched_holdings = []
        for _, holding in conv_bond_df.iterrows():
            underlying_stock_code = str(holding.get('正股代码', ''))
            if pd.notna(underlying_stock_code) and underlying_stock_code != '':
                # 提取6位数字代码
                underlying_stock_6digit = underlying_stock_code.zfill(6)[:6]
                if underlying_stock_6digit in industry_stocks_6digit:
                    matched_holdings.append(holding)
                    matched_bonds.add(holding['stock_code'])

        if matched_holdings:
            matched_df = pd.DataFrame(matched_holdings)
            industry_ratio = matched_df['position_ratio'].sum()

            analysis_results[industry_name] = {
                'ratio': industry_ratio,
                'bond_count': len(matched_holdings),
                'bonds': matched_df['stock_code'].tolist()
            }

    # 计算"其他"部分
    unmatched_holdings = conv_bond_df[~conv_bond_df['stock_code'].isin(matched_bonds)]
    other_ratio = unmatched_holdings['position_ratio'].sum() if not unmatched_holdings.empty else 0

    if other_ratio > 0:
        analysis_results['其他'] = {
            'ratio': other_ratio,
            'bond_count': len(unmatched_holdings),
            'bonds': unmatched_holdings['stock_code'].tolist()
        }

    return analysis_results


def analyze_conv_bond_characteristics(conv_bond_df):
    """分析可转债股性/债性特征"""
    if conv_bond_df is None or conv_bond_df.empty:
        return None

    # 查找转股溢价率列
    premium_col = None
    for col in conv_bond_df.columns:
        if '转股溢价率' in col or '溢价率' in col:
            premium_col = col
            break

    if premium_col is None:
        st.error("找不到转股溢价率列")
        return None

    # 转股溢价率分类
    def classify_premium(premium_str):
        try:
            # 清理数据，移除%符号并转换为数值
            premium = float(str(premium_str).replace('%', '').strip())
            if premium <= 10:
                return "强股性转债(≤10%)"
            elif premium <= 30:
                return "偏股性转债(10%-30%)"
            elif premium <= 60:
                return "平衡性转债(30%-60%)"
            elif premium <= 100:
                return "偏债性转债(60%-100%)"
            else:
                return "强债性转债(>100%)"
        except:
            return "无数据"

    conv_bond_df['股债特性'] = conv_bond_df[premium_col].apply(classify_premium)

    # 按分类统计
    characteristics = conv_bond_df.groupby('股债特性').agg({
        'position_ratio': 'sum',
        'stock_code': 'count'
    }).reset_index()
    characteristics.columns = ['特性分类', '占比', '债券数量']

    return characteristics


def analyze_conv_bond_ratings(conv_bond_df):
    """分析可转债外部评级分布"""
    if conv_bond_df is None or conv_bond_df.empty:
        return None

    # 按评级统计
    ratings = conv_bond_df.groupby('外部评级').agg({
        'position_ratio': 'sum',
        'stock_code': 'count'
    }).reset_index()
    ratings.columns = ['评级', '占比', '债券数量']

    # 排序（按评级优先级）
    rating_order = ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-']
    ratings['排序'] = ratings['评级'].apply(lambda x: rating_order.index(x) if x in rating_order else 999)
    ratings = ratings.sort_values('排序')

    return ratings


def render_conv_bond_characteristics_chart(characteristics_df):
    """渲染股性/债性分布柱状图"""
    if characteristics_df is None or characteristics_df.empty:
        st.info("暂无可转债特性分析数据")
        return

    # 创建柱状图
    fig = go.Figure(data=[
        go.Bar(
            x=characteristics_df['特性分类'],
            y=characteristics_df['占比'],
            marker=dict(
                color=characteristics_df['占比'],
                colorscale='Oranges',  # 橙色渐变
                showscale=True,
                colorbar=dict(title="占比 (%)")
            ),
            text=[f"{ratio:.1f}%" for ratio in characteristics_df['占比']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>占比: %{y:.1f}%<br>债券数量: %{customdata}<extra></extra>',
            customdata=characteristics_df['债券数量']
        )
    ])

    fig.update_layout(
        title=dict(
            text="可转债股性/债性分布",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="特性分类",
            tickangle=45
        ),
        yaxis=dict(
            title="占比 (%)",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)'
        ),
        height=450,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=50, t=80, b=100)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_conv_bond_ratings_chart(ratings_df):
    """渲染外部评级分布柱状图"""
    if ratings_df is None or ratings_df.empty:
        st.info("暂无可转债评级分析数据")
        return

    # 创建柱状图
    fig = go.Figure(data=[
        go.Bar(
            x=ratings_df['评级'],
            y=ratings_df['占比'],
            marker=dict(
                color=ratings_df['占比'],
                colorscale='Greens',  # 绿色渐变
                showscale=True,
                colorbar=dict(title="占比 (%)")
            ),
            text=[f"{ratio:.1f}%" for ratio in ratings_df['占比']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>占比: %{y:.1f}%<br>债券数量: %{customdata}<extra></extra>',
            customdata=ratings_df['债券数量']
        )
    ])

    fig.update_layout(
        title=dict(
            text="可转债外部评级分布",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="外部评级"
        ),
        yaxis=dict(
            title="占比 (%)",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)'
        ),
        height=450,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=50, t=80, b=100)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_conv_bond_industry_chart(industry_results):
    """渲染可转债行业分布柱状图"""
    if not industry_results:
        st.info("暂无可转债行业分析数据")
        return

    # 准备数据，只显示占比大于0.1%的行业
    industries = []
    ratios = []

    for industry_name, data in industry_results.items():
        if data['ratio'] > 0.1:
            industries.append(industry_name)
            ratios.append(data['ratio'])

    if not industries:
        st.info("没有足够的数据绘制图表")
        return

    # 按比例排序
    sorted_data = sorted(zip(industries, ratios), key=lambda x: x[1], reverse=True)
    industries_sorted = [x[0] for x in sorted_data]
    ratios_sorted = [x[1] for x in sorted_data]

    # 创建柱状图
    # 创建柱状图
    fig = go.Figure(data=[
        go.Bar(
            x=industries_sorted,
            y=ratios_sorted,
            marker=dict(
                color=ratios_sorted,
                colorscale='Blues',  # 蓝色渐变（保持原样）
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
            text="可转债行业分布",
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
        height=450,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=50, t=80, b=100)
    )

    st.plotly_chart(fig, use_container_width=True)


def analyze_conv_bond_market_cap(conv_bond_df):
    """分析可转债正股市值分布"""
    if conv_bond_df is None or conv_bond_df.empty:
        return None

    # 查找正股流通市值列
    market_cap_col = None
    for col in conv_bond_df.columns:
        if '正股流通市值' in col or '流通市值' in col:
            market_cap_col = col
            break

    if market_cap_col is None:
        return None

    # 市值分类（基于A股实际情况）
    def classify_market_cap(market_cap):
        try:
            cap = float(str(market_cap).replace('亿', '').strip())
            if cap < 50:
                return "小盘股(<50亿)"
            elif cap < 100:
                return "中小盘股(50-100亿)"
            elif cap < 300:
                return "中盘股(100-300亿)"
            elif cap < 1000:
                return "大盘股(300-1000亿)"
            else:
                return "超大盘股(≥1000亿)"
        except:
            return "无数据"

    conv_bond_df['市值分类'] = conv_bond_df[market_cap_col].apply(classify_market_cap)

    # 按分类统计
    market_cap_analysis = conv_bond_df.groupby('市值分类').agg({
        'position_ratio': 'sum',
        'stock_code': 'count'
    }).reset_index()
    market_cap_analysis.columns = ['市值分类', '占比', '债券数量']

    # 按市值大小排序
    cap_order = ["小盘股(<50亿)", "中小盘股(50-100亿)", "中盘股(100-300亿)", "大盘股(300-1000亿)", "超大盘股(≥1000亿)",
                 "无数据"]
    market_cap_analysis['排序'] = market_cap_analysis['市值分类'].apply(
        lambda x: cap_order.index(x) if x in cap_order else 999)
    market_cap_analysis = market_cap_analysis.sort_values('排序')

    return market_cap_analysis


def render_conv_bond_market_cap_chart(market_cap_df):
    """渲染正股市值分布柱状图"""
    if market_cap_df is None or market_cap_df.empty:
        st.info("暂无正股市值分析数据")
        return

    # 创建柱状图
    fig = go.Figure(data=[
        go.Bar(
            x=market_cap_df['市值分类'],
            y=market_cap_df['占比'],
            marker=dict(
                color=market_cap_df['占比'],
                colorscale='Purples',  # 紫色渐变
                showscale=True,
                colorbar=dict(title="占比 (%)")
            ),
            text=[f"{ratio:.1f}%" for ratio in market_cap_df['占比']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>占比: %{y:.1f}%<br>债券数量: %{customdata}<extra></extra>',
            customdata=market_cap_df['债券数量']
        )
    ])

    fig.update_layout(
        title=dict(
            text="可转债正股市值分布",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis=dict(
            title="市值分类",
            tickangle=45
        ),
        yaxis=dict(
            title="占比 (%)",
            showgrid=True,
            gridcolor='rgba(128,128,128,0.3)'
        ),
        height=450,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=50, t=80, b=100)
    )

    st.plotly_chart(fig, use_container_width=True)