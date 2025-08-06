"""
基金可视化系统主应用
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from components.holdings_updater import render_holdings_update_section, update_holdings_from_source
from datetime import datetime, timedelta, date
from components.product_tags import render_tag_management, get_product_options_by_tag, render_tag_filter
from components.weekly_summary import render_weekly_summary_page

# 添加项目路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from config import PAGE_CONFIG, APP_TITLE
from database.database import DatabaseManager


def initialize_app():
    """初始化应用"""
    # 页面配置
    st.set_page_config(**PAGE_CONFIG)

    # 初始化数据库
    if 'db' not in st.session_state:
        st.session_state.db = DatabaseManager()

        # 强制重新初始化数据库表（包含新的标签表）
        st.session_state.db.init_database()

    # 初始化其他session state
    if 'selected_product' not in st.session_state:
        st.session_state.selected_product = None
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = None


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.header("🧭 功能导航")

        # 页面选择 - 使用单选按钮而不是下拉框
        page = st.radio(
            "选择功能",
            [ "实时持仓热力图","周度汇总","数据概览", "产品标签管理" ,"数据导入", "指数成分股管理"],
            #["数据概览", "实时持仓热力图", "每日交易统计", "数据导入", "持仓分析", "指数成分股管理"],
            key="page_selector"
        )

        return page


def render_product_selector():
    """渲染产品选择器"""
    st.subheader("📊 选择产品")

    products = st.session_state.db.get_products()

    if not products:
        st.warning("暂无产品数据，请先在'数据导入'页面添加产品")
        return None

    # 创建产品选项字典
    product_options = {f"{p['product_name']} ({p['product_code']})": p['product_code']
                      for p in products}

    # 如果当前选择的产品不在选项中，重置为None
    if (st.session_state.selected_product and
        st.session_state.selected_product not in product_options.values()):
        st.session_state.selected_product = None

    # 确定默认索引
    default_index = 0
    if st.session_state.selected_product:
        for i, (display, code) in enumerate(product_options.items()):
            if code == st.session_state.selected_product:
                default_index = i
                break

    # 产品选择下拉框
    selected_product_display = st.selectbox(
        "产品列表",
        options=list(product_options.keys()),
        index=default_index,
        key="main_product_selector"
    )

    # 更新session state
    new_selected_product = product_options[selected_product_display]
    if st.session_state.selected_product != new_selected_product:
        st.session_state.selected_product = new_selected_product
        # 重置选择的日期，因为不同产品可能有不同的可用日期
        st.session_state.selected_date = None

    return st.session_state.selected_product


def render_data_overview():
    """渲染数据概览页面"""
    from datetime import datetime as dt  # 重新导入避免冲突

    st.header("📈 数据概览")

    # 创建产品选择和持仓更新的同行布局
    col_product, col_update = st.columns([1, 1])

    with col_product:
        st.subheader("📊 选择产品")

        # 添加标签筛选
        selected_tag = render_tag_filter(st.session_state.db, "overview")

        # 根据标签获取产品选项
        product_options = get_product_options_by_tag(st.session_state.db, selected_tag)

        if not product_options:
            if selected_tag == "全部":
                st.warning("暂无产品数据，请先在'数据导入'页面添加产品")
            else:
                st.warning(f"标签 '{selected_tag}' 下暂无产品")
            return

        # 如果当前选择的产品不在筛选后的选项中，重置为None
        if (st.session_state.selected_product and
                st.session_state.selected_product not in product_options.values()):
            st.session_state.selected_product = None

        # 确定默认索引
        default_index = 0
        if st.session_state.selected_product:
            for i, (display, code) in enumerate(product_options.items()):
                if code == st.session_state.selected_product:
                    default_index = i
                    break

        # 产品选择下拉框
        selected_product_display = st.selectbox(
            "产品列表",
            options=list(product_options.keys()),
            index=default_index,
            key="main_product_selector"
        )

        # 更新session state
        new_selected_product = product_options[selected_product_display]
        if st.session_state.selected_product != new_selected_product:
            st.session_state.selected_product = new_selected_product
            # 重置选择的日期，因为不同产品可能有不同的可用日期
            st.session_state.selected_date = None

        selected_product = st.session_state.selected_product

    with col_update:
        render_holdings_update_section(st.session_state.db)

    if not selected_product:
        return

    product_code = selected_product
    st.divider()

    # 获取净值数据
    nav_data = st.session_state.db.get_nav_data(product_code)

    if nav_data.empty:
        st.error(f"产品 {product_code} 暂无净值数据，请先在'数据导入'页面导入净值数据")
        return

    # 创建两列布局
    col1, col2 = st.columns([2, 1])

    with col1:
        # 导入新的图表组件
        from components.nav_chart import render_nav_chart

        # 先显示统计信息
        nav_data = st.session_state.db.get_nav_data(product_code)
        if not nav_data.empty:
            # 计算统计指标
            nav_data['date'] = pd.to_datetime(nav_data['date'])
            nav_data = nav_data.sort_values('date')
            nav_data['daily_return'] = nav_data['nav_value'].pct_change() * 100
            nav_data['cumulative_return'] = (nav_data['nav_value'] / nav_data['nav_value'].iloc[0] - 1) * 100

            # 显示统计信息
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

            with col_stat1:
                total_return = nav_data['cumulative_return'].iloc[-1]
                daily_return = nav_data['daily_return'].iloc[-1] if not pd.isna(
                    nav_data['daily_return'].iloc[-1]) else 0
                st.metric(
                    "总收益率",
                    f"{total_return:.2f}%",
                    delta=f"{daily_return:.2f}%"
                )

            with col_stat2:
                volatility = nav_data['daily_return'].std()
                st.metric("波动率(日)", f"{volatility:.2f}%")

            with col_stat3:
                max_nav = nav_data['nav_value'].max()
                st.metric("最高净值", f"{max_nav:.4f}")

            with col_stat4:
                min_nav = nav_data['nav_value'].min()
                st.metric("最低净值", f"{min_nav:.4f}")

            st.divider()

        # 渲染交互式净值图表
        render_nav_chart(st.session_state.db, product_code)

    with col2:
        # 添加日期选择器（右上角）
        st.subheader("📅 选择查看日期")
        available_dates = st.session_state.db.get_available_dates(product_code)

        if available_dates:
            # 将字符串日期转换为日期对象
            # 智能解析日期格式
            date_objects = []
            for d in available_dates:
                try:
                    d_str = str(d)
                    if len(d_str) == 8 and d_str.isdigit():  # YYYYMMDD格式
                        date_obj = datetime.strptime(d_str, '%Y%m%d').date()
                    else:  # YYYY-MM-DD格式
                        date_obj = datetime.strptime(d_str, '%Y-%m-%d').date()
                    date_objects.append(date_obj)
                except Exception as e:
                    st.warning(f"日期解析失败: {d} - {e}")
                    continue

            # 如果session_state中有选中的日期且在可用日期中，使用它作为默认值
            default_date = date_objects[0]  # 默认最新日期
            if (st.session_state.selected_date and
                    st.session_state.selected_date in available_dates):
                default_date = datetime.strptime(st.session_state.selected_date, '%Y-%m-%d').date()

            selected_date_obj = st.date_input(
                "持仓日期",
                value=default_date,
                min_value=min(date_objects),
                max_value=max(date_objects),
                key="date_selector"
            )
            new_selected_date = selected_date_obj.strftime('%Y-%m-%d')
            st.session_state.selected_date = new_selected_date

            # 如果日期发生变化，重新运行页面
            if 'previous_selected_date' not in st.session_state:
                st.session_state.previous_selected_date = new_selected_date
            elif st.session_state.previous_selected_date != new_selected_date:
                st.session_state.previous_selected_date = new_selected_date
                st.rerun()

        else:
            st.warning("该产品暂无持仓数据，请先在'数据导入'页面导入持仓数据")

        # 持仓明细
        st.subheader("持仓明细")

        if st.session_state.selected_date:
            holdings_data = st.session_state.db.get_holdings_by_date(
                product_code, st.session_state.selected_date
            )

            if not holdings_data.empty:
                st.write(f"**{st.session_state.selected_date}** 持仓情况：")

                # 格式化显示持仓数据
                display_data = holdings_data[['stock_code', 'position_ratio']].copy()
                display_data['position_ratio'] = display_data['position_ratio'].apply(lambda x: f"{x:.2f}%")
                display_data.columns = ['股票代码', '持仓占比']

                st.dataframe(display_data, use_container_width=True)

                # 显示总持仓比例
                total_ratio = holdings_data['position_ratio'].sum()
                st.metric("总持仓比例", f"{total_ratio:.2f}%")
            else:
                st.info("该日期暂无持仓数据")
        else:
            st.info("请选择一个日期查看持仓")

    # 根据持仓类型进行分析
    if st.session_state.selected_date:
        holdings_data = st.session_state.db.get_holdings_by_date(product_code, st.session_state.selected_date)

        # 判断持仓类型
        has_stocks = False
        has_conv_bonds = False

        if not holdings_data.empty:
            has_conv_bonds = any(holdings_data['stock_code'].str.startswith('1'))
            has_stocks = any(~holdings_data['stock_code'].str.startswith('1'))

        # 只有股票时的分析
        if has_stocks and not has_conv_bonds:
            st.divider()

            # 创建两列布局，均分整行
            col_index, col_industry = st.columns(2)

            with col_index:
                st.subheader("指数分布")
                from components.analysis import analyze_holdings_by_index, render_holdings_pie_chart
                analysis_results = analyze_holdings_by_index(st.session_state.db, product_code,
                                                             st.session_state.selected_date)

                if analysis_results:
                    render_holdings_pie_chart(analysis_results)

                    # 简化的分布表格
                    table_data = []
                    for index_name, data in analysis_results.items():
                        if data['ratio'] > 0.1:
                            table_data.append({
                                '指数': index_name,
                                '占比': f"{data['ratio']:.1f}%"
                            })

                    if table_data:
                        table_df = pd.DataFrame(table_data)
                        st.dataframe(table_df, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无指数分析数据")

            with col_industry:
                st.subheader("行业分布")
                from components.industry_analysis import analyze_holdings_by_industry, render_industry_bar_chart
                industry_results = analyze_holdings_by_industry(st.session_state.db, product_code,
                                                                st.session_state.selected_date)

                if industry_results:
                    render_industry_bar_chart(industry_results)

                    # 行业分布表格
                    industry_table_data = []
                    for industry_name, data in industry_results.items():
                        if data['ratio'] > 0.1:
                            industry_table_data.append({
                                '行业': industry_name,
                                '占比': f"{data['ratio']:.1f}%",
                                '股票数': data['stock_count']
                            })

                    if industry_table_data:
                        industry_df = pd.DataFrame(industry_table_data)
                        industry_df = industry_df.sort_values('占比',
                                                              key=lambda x: x.str.replace('%', '').astype(float),
                                                              ascending=False)
                        st.dataframe(industry_df, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无行业分析数据，请先在'指数成分股管理'页面导入行业分类")

            # 市场分布
            st.divider()
            col_market, col_empty = st.columns(2)

            with col_market:
                st.subheader("市场分布")

                from components.industry_analysis import analyze_holdings_by_market, render_market_pie_chart
                holdings_data = st.session_state.db.get_holdings_by_date(product_code, st.session_state.selected_date)

                if not holdings_data.empty:
                    market_results = analyze_holdings_by_market(holdings_data)
                    render_market_pie_chart(market_results)
                else:
                    st.info("暂无持仓数据")

            with col_empty:
                pass  # 右侧留空

        # 只有可转债时的分析
        elif has_conv_bonds and not has_stocks:
            st.divider()
            st.subheader("📋 可转债分析")

            # 导入可转债分析组件
            from components.conv_bond_analysis import (
                load_conv_bond_data, analyze_conv_bond_holdings,
                analyze_conv_bond_by_industry, analyze_conv_bond_characteristics,
                analyze_conv_bond_ratings, render_conv_bond_industry_chart,
                render_conv_bond_characteristics_chart, render_conv_bond_ratings_chart
            )

            # 加载可转债数据
            relation_df, analysis_df = load_conv_bond_data()

            if relation_df is not None and analysis_df is not None:
                # 分析可转债持仓
                conv_bond_df = analyze_conv_bond_holdings(holdings_data, relation_df, analysis_df, st.session_state.db)

                if conv_bond_df is not None and not conv_bond_df.empty:
                    # 显示可转债基本信息
                    col_info1, col_info2, col_info3 = st.columns(3)

                    with col_info1:
                        conv_count = len(conv_bond_df)
                        st.metric("可转债数量", f"{conv_count}只")

                    with col_info2:
                        conv_ratio = conv_bond_df['position_ratio'].sum()
                        st.metric("可转债总占比", f"{conv_ratio:.2f}%")

                    with col_info3:
                        try:
                            # 查找转股溢价率列
                            premium_col = None
                            for col in conv_bond_df.columns:
                                if '转股溢价率' in col or '溢价率' in col:
                                    premium_col = col
                                    break

                            if premium_col and premium_col in conv_bond_df.columns:
                                # 尝试转换为数值
                                premium_data = pd.to_numeric(conv_bond_df[premium_col].astype(str).str.replace('%', ''),
                                                             errors='coerce')
                                avg_premium = premium_data.mean()
                                if not pd.isna(avg_premium):
                                    st.metric("平均转股溢价率", f"{avg_premium:.2f}%")
                                else:
                                    st.metric("平均转股溢价率", "无数据")
                            else:
                                st.metric("平均转股溢价率", "无数据")
                        except Exception as e:
                            st.metric("平均转股溢价率", "计算错误")

                    st.divider()

                    # 创建三列布局展示分析结果
                    # 创建2x2布局展示分析结果
                    col_industry, col_characteristics = st.columns(2)

                    with col_industry:
                        st.write("**可转债行业分布**")
                        industry_results = analyze_conv_bond_by_industry(conv_bond_df, st.session_state.db)
                        if industry_results:
                            render_conv_bond_industry_chart(industry_results)
                        else:
                            st.info("暂无行业数据，请先导入行业分类")

                    with col_characteristics:
                        st.write("**股性/债性分布**")
                        characteristics_df = analyze_conv_bond_characteristics(conv_bond_df)
                        render_conv_bond_characteristics_chart(characteristics_df)

                    # 第二行
                    col_ratings, col_market_cap = st.columns(2)

                    with col_ratings:
                        st.write("**外部评级分布**")
                        ratings_df = analyze_conv_bond_ratings(conv_bond_df)
                        render_conv_bond_ratings_chart(ratings_df)

                    with col_market_cap:
                        st.write("**正股市值分布**")
                        from components.conv_bond_analysis import analyze_conv_bond_market_cap, \
                            render_conv_bond_market_cap_chart
                        market_cap_df = analyze_conv_bond_market_cap(conv_bond_df)
                        render_conv_bond_market_cap_chart(market_cap_df)

                else:
                    st.info("可转债数据匹配失败，请检查数据文件格式")
            else:
                st.warning("未找到可转债分析数据，请确保 data/conv_bond/ 目录下有相关CSV文件")

        # 既有股票又有可转债时的分析
        elif has_stocks and has_conv_bonds:
            st.divider()

            # 股票分析部分
            st.subheader("📈 股票分析")
            col_index, col_industry = st.columns(2)

            with col_index:
                st.write("**指数分布**")
                from components.analysis import analyze_holdings_by_index, render_holdings_pie_chart
                # 只分析非1开头的股票
                stock_holdings = holdings_data[~holdings_data['stock_code'].str.startswith('1')]
                if not stock_holdings.empty:
                    analysis_results = analyze_holdings_by_index(st.session_state.db, product_code,
                                                                 st.session_state.selected_date)
                    if analysis_results:
                        render_holdings_pie_chart(analysis_results)
                else:
                    st.info("暂无股票持仓")

            with col_industry:
                st.write("**行业分布**")
                from components.industry_analysis import analyze_holdings_by_industry, render_industry_bar_chart
                if not stock_holdings.empty:
                    industry_results = analyze_holdings_by_industry(st.session_state.db, product_code,
                                                                    st.session_state.selected_date)
                    if industry_results:
                        render_industry_bar_chart(industry_results)
                else:
                    st.info("暂无股票持仓")

            # 可转债分析部分
            st.divider()
            st.subheader("📋 可转债分析")

            # 导入可转债分析组件
            from components.conv_bond_analysis import (
                load_conv_bond_data, analyze_conv_bond_holdings,
                analyze_conv_bond_by_industry, analyze_conv_bond_characteristics,
                analyze_conv_bond_ratings, render_conv_bond_industry_chart,
                render_conv_bond_characteristics_chart, render_conv_bond_ratings_chart
            )

            # 加载可转债数据
            relation_df, analysis_df = load_conv_bond_data()

            if relation_df is not None and analysis_df is not None:
                # 分析可转债持仓
                conv_bond_df = analyze_conv_bond_holdings(holdings_data, relation_df, analysis_df, st.session_state.db)

                if conv_bond_df is not None and not conv_bond_df.empty:
                    # 显示可转债基本信息
                    col_info1, col_info2, col_info3 = st.columns(3)

                    with col_info1:
                        conv_count = len(conv_bond_df)
                        st.metric("可转债数量", f"{conv_count}只")

                    with col_info2:
                        conv_ratio = conv_bond_df['position_ratio'].sum()
                        st.metric("可转债总占比", f"{conv_ratio:.2f}%")

                    with col_info3:
                        # 临时注释掉，先看数据结构
                        st.metric("平均转股溢价率", "待修复")
                        # 显示数据结构用于调试
                        st.write("Debug: conv_bond_df 的列名:")
                        st.write(list(conv_bond_df.columns))
                        if '转股溢价率' in conv_bond_df.columns:
                            st.write("Debug: 转股溢价率列的前几个值:")
                            st.write(conv_bond_df['转股溢价率'].head())

                    st.divider()

                    # 创建三列布局展示分析结果
                    col_industry_cb, col_characteristics, col_ratings = st.columns(3)

                    with col_industry_cb:
                        st.write("**可转债行业分布**")
                        industry_results = analyze_conv_bond_by_industry(conv_bond_df, st.session_state.db)
                        if industry_results:
                            render_conv_bond_industry_chart(industry_results)
                        else:
                            st.info("暂无行业数据，请先导入行业分类")

                    with col_characteristics:
                        st.write("**股性/债性分布**")
                        characteristics_df = analyze_conv_bond_characteristics(conv_bond_df)
                        render_conv_bond_characteristics_chart(characteristics_df)

                    with col_ratings:
                        st.write("**外部评级分布**")
                        ratings_df = analyze_conv_bond_ratings(conv_bond_df)
                        render_conv_bond_ratings_chart(ratings_df)

                else:
                    st.info("可转债数据匹配失败，请检查数据文件格式")
            else:
                st.warning("未找到可转债分析数据，请确保 data/conv_bond/ 目录下有相关CSV文件")
    else:
        st.divider()
        st.info("请先选择日期以查看相关分析")


# 3. 在 main() 函数中的页面路由部分添加新的条件判断
def main():
    """主函数"""
    # 初始化应用
    initialize_app()

    # 应用标题
    st.title(APP_TITLE)

    # 渲染侧边栏并获取当前页面
    current_page = render_sidebar()

    # 根据选择的页面渲染内容
    if current_page == "数据概览":
        render_data_overview()
    elif current_page == "周度汇总":  # 新增的页面处理
        try:
            render_weekly_summary_page(st.session_state.db)
        except Exception as e:
            st.error(f"周度汇总页面错误: {e}")
            import traceback
            st.code(traceback.format_exc())

            # 显示调试信息
            st.write("**调试信息:**")
            st.write("- 请确保 C:\\shared_data 目录存在")
            st.write("- 请确保实盘和仿真数据目录包含本周的数据文件")
            st.write("- 文件命名格式应为: 单元资产账户资产导出_YYYYMMDD-HHMMSS.xlsx")
    elif current_page == "每日交易统计":  # 原有的页面处理
        try:
            from components.daily_trading_stats import render_daily_trading_stats
            render_daily_trading_stats(st.session_state.db)
        except Exception as e:
            st.error(f"每日交易统计页面错误: {e}")
            import traceback
            st.code(traceback.format_exc())
    elif current_page == "实时持仓热力图":
        from components.realtime_heatmap import render_realtime_heatmap
        render_realtime_heatmap(st.session_state.db)
    elif current_page == "数据导入":
        from components.data_import import render_data_import
        render_data_import(st.session_state.db)
    elif current_page == "持仓分析":
        # 获取选中的产品（如果在数据概览页面已经选择了）
        if st.session_state.selected_product:
            try:
                from components.analysis import render_analysis
                render_analysis(st.session_state.db, st.session_state.selected_product)
            except Exception as e:
                st.error(f"持仓分析页面错误: {e}")
                import traceback
                st.code(traceback.format_exc())
        else:
            # 如果没有选择产品，在此页面也提供产品选择
            st.header("📊 持仓分析")
            selected_product = render_product_selector()
            if selected_product:
                try:
                    from components.analysis import render_analysis
                    render_analysis(st.session_state.db, selected_product)
                except Exception as e:
                    st.error(f"持仓分析页面错误: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    elif current_page == "指数成分股管理":
        try:
            from components.index_import import render_index_import
            render_index_import(st.session_state.db)
        except Exception as e:
            st.error(f"页面渲染错误: {e}")
            import traceback
            st.code(traceback.format_exc())

    # 自动更新逻辑（每日15:05）
    current_time = datetime.now()
    if (current_time.hour == 15 and current_time.minute == 5 and
            current_time.second < 30):  # 30秒内触发

        if 'last_auto_update' not in st.session_state:
            st.session_state.last_auto_update = None

        today_str = current_time.strftime('%Y%m%d')
        if st.session_state.last_auto_update != today_str:
            st.session_state.last_auto_update = today_str

            # 执行自动更新
            with st.spinner("正在执行每日自动更新..."):
                from components.holdings_updater import update_holdings_from_source
                result = update_holdings_from_source(st.session_state.db, "实盘")
                if result.get("success"):
                    st.success("✅ 每日自动更新完成！")
                else:
                    st.error(f"❌ 自动更新失败: {result.get('error')}")

    elif current_page == "产品标签管理":
        from components.product_tags import render_tag_management
        render_tag_management(st.session_state.db)


if __name__ == "__main__":
    main()