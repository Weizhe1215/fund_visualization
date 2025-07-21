"""
每日交易统计组件
创建新文件: components/daily_trading_stats.py
"""
import streamlit as st
import pandas as pd
import pypinyin
from datetime import datetime, date
from .futures_data_reader import FuturesDataReader


def sort_units_by_pinyin(units):
    """按拼音首字母排序单元名称"""

    def get_first_letter(name):
        try:
            first_char = name[0]
            pinyin = pypinyin.lazy_pinyin(first_char)[0]
            return pinyin[0].upper()
        except:
            return 'Z'  # 无法识别的字符排到最后

    return sorted(units, key=get_first_letter)


def calculate_derived_values(df, db, unit_name):
    """计算衍生字段"""
    df = df.copy()
    df = df.sort_values('日期')

    # 确保日期列为字符串格式
    df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')

    for i, row in df.iterrows():
        current_date = row['日期']

        # 获取上一期数据用于计算收益率
        prev_data = db.get_latest_stats_for_unit(unit_name, current_date)

        # 现货收益率计算
        # 现货收益率计算
        if prev_data and prev_data.get('equity_total_asset'):
            prev_equity = prev_data.get('equity_total_asset') or prev_data.get('现货总资产', 0)
            current_equity = row['现货总资产']
            current_market_value = row['总市值']

            # 获取当日现货出入金影响
            cash_flow = db.get_cash_flow_by_date(unit_name, current_date)

            # 调整后现货资产 = 当前现货资产 - 净流入
            adjusted_current_equity = current_equity - cash_flow

            if prev_equity > 0:
                equity_return = (adjusted_current_equity / prev_equity - 1) * 100
                df.at[i, '现货收益率'] = equity_return

                # 修改现货超额计算：(今日现货-昨日现货)/今日总市值 - 基准收益率
                if current_market_value > 0:
                    equity_excess = ((current_equity - prev_equity) / current_market_value * 100) - row.get(
                        '基准收益率', 0)
                else:
                    equity_excess = equity_return - row.get('基准收益率', 0)  # 如果总市值为0，用原来的计算方式

                df.at[i, '现货超额'] = equity_excess
        else:
            df.at[i, '现货收益率'] = 0.0
            df.at[i, '现货超额'] = 0.0 - row.get('基准收益率', 0)

        # 资产收益率计算（扣除出入金影响）
        if prev_data and prev_data.get('asset_summary'):
            prev_asset = prev_data.get('asset_summary') or prev_data.get('资产汇总', 0)
            current_asset = row['资产汇总']

            # 获取当日出入金
            cash_flow = db.get_cash_flow_by_date(unit_name, current_date)

            # 调整后资产 = 当前资产 - 净流入
            adjusted_current_asset = current_asset - cash_flow

            if prev_asset > 0:
                asset_return = (adjusted_current_asset / prev_asset - 1) * 100
                df.at[i, '资产收益率'] = asset_return
            else:
                df.at[i, '资产收益率'] = 0.0
        else:
            df.at[i, '资产收益率'] = 0.0

    # 净值计算 - 从第一行开始，第一行设为1，后续行累积计算
    df.reset_index(drop=True, inplace=True)
    df.at[0, '净值'] = 1.0

    for i in range(1, len(df)):
        prev_nav = df.at[i - 1, '净值']
        asset_return_rate = df.at[i, '资产收益率'] / 100  # 转换为小数
        df.at[i, '净值'] = prev_nav * (1 + asset_return_rate)

    return df


def render_auto_pull_section(db):
    """渲染自动拉取区域"""
    st.write("**自动数据拉取**")

    if st.button("🔍 扫描最新数据", type="secondary", key="scan_data"):
        with st.spinner("正在扫描数据..."):
            reader = FuturesDataReader()
            all_data = reader.get_latest_data_by_units()

            if all_data:
                st.session_state['scanned_data'] = all_data
                st.success(f"扫描完成！发现 {len(all_data)} 个单元的数据")
            else:
                st.warning("未找到可用数据")

    # 显示扫描结果并允许选择导入
    if 'scanned_data' in st.session_state:
        st.write("**扫描到的数据：**")

        all_data = st.session_state['scanned_data']
        existing_units = db.get_all_units()

        for unit_name, time_data in all_data.items():
            with st.container():
                # 检查是否为现有单元
                is_existing = unit_name in existing_units
                status = "✅ 现有单元" if is_existing else "🆕 新单元"

                st.write(f"**{unit_name}** {status}")

                for update_time, data in time_data.items():
                    time_label = "午盘 (11:30)" if update_time == "113000" else "收盘 (15:30)"

                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.write(f"**{time_label}**")
                        st.write(f"日期: {data['date']}")
                        st.write(f"现货资产: {data.get('equity_total_asset', 0):,.0f}")
                        st.write(f"期货资产: {data.get('futures_total_asset', 0):,.0f}")
                        st.write(f"资产汇总: {data.get('asset_summary', 0):,.0f}")

                    with col2:
                        st.write(f"基准收益率: {data.get('benchmark_return_rate', 0):.4f}")
                        st.write(f"期货市值: {data.get('futures_market_value', 0):,.0f}")
                        st.write(f"总市值: {data.get('total_market_value', 0):,.0f}")

                    with col3:
                        if is_existing:
                            if st.button("📥 导入", key=f"import_{unit_name}_{update_time}", type="primary"):
                                # 执行导入
                                stats_data = {
                                    'equity_total_asset': data.get('equity_total_asset', 0),
                                    'total_market_value': data.get('total_market_value', 0),
                                    'bond_market_value': data.get('bond_market_value', 0),
                                    'stock_market_value': data.get('stock_market_value', 0),
                                    'benchmark': '中证1000',
                                    'benchmark_return_rate': data.get('benchmark_return_rate', 0),
                                    'futures_total_asset': data.get('futures_total_asset', 0),
                                    'futures_market_value': data.get('futures_market_value', 0),
                                    'asset_summary': data.get('asset_summary', 0)
                                }

                                # 计算收益率
                                prev_data = db.get_latest_stats_for_unit(unit_name, data['date'])

                                if prev_data:
                                    if prev_data.get('equity_total_asset'):
                                        cash_flow = db.get_cash_flow_by_date(unit_name, data['date'])
                                        adjusted_equity = stats_data['equity_total_asset'] - cash_flow
                                        equity_return = (adjusted_equity / prev_data['equity_total_asset'] - 1) * 100
                                        stats_data['equity_return_rate'] = equity_return
                                        stats_data['equity_excess_return'] = equity_return - stats_data[
                                            'benchmark_return_rate']

                                    if prev_data.get('asset_summary'):
                                        cash_flow = db.get_cash_flow_by_date(unit_name, data['date'])
                                        adjusted_asset = stats_data['asset_summary'] - cash_flow
                                        asset_return = (adjusted_asset / prev_data['asset_summary'] - 1) * 100
                                        stats_data['asset_return_rate'] = asset_return
                                        prev_nav = prev_data.get('nav_value', 1.0)
                                        stats_data['nav_value'] = prev_nav * (1 + asset_return / 100)
                                else:
                                    stats_data['equity_return_rate'] = 0.0
                                    stats_data['equity_excess_return'] = -stats_data['benchmark_return_rate']
                                    stats_data['asset_return_rate'] = 0.0
                                    stats_data['nav_value'] = 1.0

                                # 保存到数据库
                                success = db.add_trading_stats_record(unit_name, data['date'], update_time, stats_data)

                                if success:
                                    st.success(f"✅ {unit_name} {time_label} 导入成功！")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {unit_name} {time_label} 导入失败")
                        else:
                            st.info("请先创建单元")

                st.divider()

        # 清除扫描数据按钮
        if st.button("🗑️ 清除扫描结果", key="clear_scan"):
            if 'scanned_data' in st.session_state:
                del st.session_state['scanned_data']
            st.rerun()


def render_editable_data_table(df, unit_name, db):
    """渲染可编辑的数据表格"""
    st.write(f"**{unit_name} 交易统计数据**")

    # 列配置
    column_config = {
        "日期": st.column_config.DateColumn(
            "日期",
            min_value=date(2020, 1, 1),
            max_value=date(2030, 12, 31),
            format="YYYY-MM-DD",
            step=1,
        ),
        "现货总资产": st.column_config.NumberColumn(
            "现货总资产",
            help="单元资产账户资产导出文件的总资产列",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "总市值": st.column_config.NumberColumn(
            "总市值",
            help="股票市值+转债市值",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "转债市值": st.column_config.NumberColumn(
            "转债市值",
            help="债券资产列",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "股票市值": st.column_config.NumberColumn(
            "股票市值",
            help="A股资产列",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "现货收益率": st.column_config.NumberColumn(
            "现货收益率(%)",
            help="今日现货总资产/昨日现货总资产-1",
            step=0.01,
            format="%.4f",
        ),
        "基准": st.column_config.TextColumn(
            "基准",
            help="基准指数名称",
            default="中证1000",
        ),
        "基准收益率": st.column_config.NumberColumn(
            "基准收益率(%)",
            help="期货文件Sheet2中的中证1000当日收益率",
            step=0.01,
            format="%.4f",
        ),
        "现货超额": st.column_config.NumberColumn(
            "现货超额(%)",
            help="现货收益率-基准收益率",
            step=0.01,
            format="%.4f",
        ),
        "期货总资产": st.column_config.NumberColumn(
            "期货总资产",
            help="期货文件中的客户权益列",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "期货仓位": st.column_config.NumberColumn(
            "期货仓位",
            help="期货仓位信息",
            min_value=0,
            step=0.01,
            format="%.2f",
        ),
        "期货市值": st.column_config.NumberColumn(
            "期货市值",
            help="期货市值",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "资产汇总": st.column_config.NumberColumn(
            "资产汇总",
            help="现货总资产+期货总资产",
            min_value=0,
            step=1000,
            format="%.2f",
        ),
        "资产收益率": st.column_config.NumberColumn(
            "资产收益率(%)",
            help="今日资产汇总/昨日资产汇总-1",
            step=0.01,
            format="%.4f",
        ),
        "净值": st.column_config.NumberColumn(
            "净值",
            help="累积净值",
            min_value=0,
            step=0.0001,
            format="%.6f",
        ),
    }

    # 可编辑表格
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editable_table_{unit_name}",
        hide_index=True
    )

    # 保存按钮
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if st.button("💾 保存修改", type="primary", key=f"save_changes_{unit_name}"):
            try:
                # 重新计算衍生字段
                processed_df = calculate_derived_values(edited_df, db, unit_name)

                # 保存到数据库
                success = db.update_trading_stats_batch(processed_df, unit_name)
                if success:
                    st.success("数据保存成功！")
                    st.rerun()
                else:
                    st.error("保存失败")
            except Exception as e:
                st.error(f"保存时发生错误: {e}")

    with col2:
        if st.button("🔄 重新计算", key=f"recalc_{unit_name}"):
            try:
                processed_df = calculate_derived_values(edited_df, db, unit_name)
                st.success("重新计算完成")
                st.dataframe(processed_df, use_container_width=True)
            except Exception as e:
                st.error(f"计算时发生错误: {e}")

    with col3:
        if st.button("🗑️ 删除数据", key=f"delete_{unit_name}", type="secondary"):
            success = db.delete_unit_data(unit_name)
            if success:
                st.success("数据已删除")
                st.rerun()

    with col4:
        if st.button("🗑️ 删除选中行", key=f"delete_row_{unit_name}"):
            # 显示删除选项
            if f"show_delete_{unit_name}" not in st.session_state:
                st.session_state[f"show_delete_{unit_name}"] = True
                st.rerun()

    # 删除行选择界面
    if st.session_state.get(f"show_delete_{unit_name}", False):
        st.write("**选择要删除的记录：**")

        if not edited_df.empty:
            # 创建选择选项
            delete_options = []
            for idx, row in edited_df.iterrows():
                date_str = str(row['日期'])
                delete_options.append(f"{date_str} (资产汇总: {row.get('资产汇总', 0):,.0f})")

            selected_delete = st.selectbox("选择要删除的记录", delete_options, key=f"delete_select_{unit_name}")

            col_del1, col_del2, col_del3 = st.columns([1, 1, 2])

            with col_del1:
                if st.button("确认删除", type="primary", key=f"confirm_delete_{unit_name}"):
                    if selected_delete:
                        # 提取日期并标准化格式
                        selected_date = selected_delete.split(' ')[0]

                        # 标准化日期格式
                        try:
                            if len(selected_date) == 8:  # YYYYMMDD
                                formatted_date = pd.to_datetime(selected_date, format='%Y%m%d').strftime('%Y-%m-%d')
                            else:  # YYYY-MM-DD
                                formatted_date = pd.to_datetime(selected_date).strftime('%Y-%m-%d')
                        except:
                            formatted_date = selected_date

                        # 从数据库删除 - 尝试两种格式
                        success = db.delete_trading_stats_record(unit_name, formatted_date)
                        if not success:
                            # 如果标准格式失败，尝试原始格式
                            success = db.delete_trading_stats_record(unit_name, selected_date)
                        if success:
                            st.success(f"已删除 {selected_date} 的记录")
                            # 清除选择状态
                            if f"show_delete_{unit_name}" in st.session_state:
                                del st.session_state[f"show_delete_{unit_name}"]
                            st.rerun()
                        else:
                            st.error("删除失败")

            with col_del2:
                if st.button("取消", key=f"cancel_delete_{unit_name}"):
                    if f"show_delete_{unit_name}" in st.session_state:
                        del st.session_state[f"show_delete_{unit_name}"]
                    st.rerun()

    return edited_df


def render_daily_trading_stats(db):
    """渲染每日交易统计主页面"""
    st.header("📊 每日交易统计")

    # 数据导入区域
    with st.expander("📤 数据管理", expanded=False):
        render_data_import_section(db)

    # 获取所有单元
    units = db.get_all_units()

    if not units:
        st.info("暂无交易数据，请先导入数据或自动拉取数据")
        return

    # 按拼音排序
    sorted_units = sort_units_by_pinyin(units)

    # 创建标签页 - 原有单元 + 出入金管理
    tab_names = [f"{unit} ({len(db.get_trading_stats_by_unit(unit))}条)" for unit in sorted_units]
    tab_names.append("💰 出入金管理")
    tabs = st.tabs(tab_names)

    # 原有单元的tabs
    for i, unit_name in enumerate(sorted_units):
        with tabs[i]:
            df = db.get_trading_stats_by_unit(unit_name)

            if not df.empty:
                # 确保有必要的列
                required_columns = ['日期', '现货总资产', '总市值', '转债市值', '股票市值', '现货收益率',
                                    '基准', '基准收益率', '现货超额', '期货总资产', '期货仓位', '期货市值',
                                    '资产汇总', '资产收益率', '净值']

                for col in required_columns:
                    if col not in df.columns:
                        df[col] = 0.0 if col != '基准' else '中证1000'

                df = df[required_columns].copy()

                # 确保日期格式正确
                def parse_date_safe(date_str):
                    try:
                        if len(str(date_str)) == 8:  # YYYYMMDD格式
                            return pd.to_datetime(date_str, format='%Y%m%d').date()
                        else:  # YYYY-MM-DD格式
                            return pd.to_datetime(date_str).date()
                    except:
                        return pd.to_datetime(date_str, format='mixed').date()

                df['日期'] = df['日期'].apply(parse_date_safe)
                df = df.sort_values('日期', ascending=True)

                render_editable_data_table(df, unit_name, db)
            else:
                st.info(f"单元 {unit_name} 暂无数据")

                # 提供添加数据选项
                if st.button(f"➕ 为 {unit_name} 添加数据", key=f"add_data_{unit_name}"):
                    # 创建空的数据框
                    today = datetime.now().date()
                    empty_df = pd.DataFrame([{
                        '日期': today,
                        '现货总资产': 0.0,
                        '总市值': 0.0,
                        '转债市值': 0.0,
                        '股票市值': 0.0,
                        '现货收益率': 0.0,
                        '基准': '中证1000',
                        '基准收益率': 0.0,
                        '现货超额': 0.0,
                        '期货总资产': 0.0,
                        '期货仓位': 0.0,
                        '期货市值': 0.0,
                        '资产汇总': 0.0,
                        '资产收益率': 0.0,
                        '净值': 1.0
                    }])

                    st.write("请填写数据:")
                    render_editable_data_table(empty_df, unit_name, db)

    # 新增出入金管理tab
    with tabs[-1]:
        render_cash_flow_management(db, sorted_units)


def render_paste_import_section(db):
    """渲染复制粘贴导入区域 - 修复版本"""
    st.write("**复制粘贴导入**")

    selected_unit_import = st.selectbox(
        "选择要导入的单元",
        options=db.get_all_units() + ["新建单元"],
        key="import_unit_selector"
    )

    if selected_unit_import == "新建单元":
        new_unit_name = st.text_input("输入新单元名称", key="new_unit_input")
        if new_unit_name:
            selected_unit_import = new_unit_name

    # 数据粘贴区域
    pasted_data = st.text_area(
        "粘贴数据",
        height=200,
        placeholder="请将数据粘贴到这里，支持制表符分隔的格式...",
        help="支持从Excel复制的制表符分隔格式",
        key="trading_stats_paste"
    )

    if pasted_data.strip() and selected_unit_import and selected_unit_import != "新建单元":
        try:
            # 解析粘贴的数据
            lines = [line.strip() for line in pasted_data.strip().split('\n') if line.strip()]

            if len(lines) > 1:
                # 第一行作为列标题
                headers = [h.strip() for h in lines[0].split('\t')]
                data_rows = []

                # 处理数据行
                for line in lines[1:]:
                    row_data = [cell.strip() for cell in line.split('\t')]
                    # 确保行数据长度与标题一致
                    while len(row_data) < len(headers):
                        row_data.append('')
                    data_rows.append(row_data)

                # 创建DataFrame
                import_df = pd.DataFrame(data_rows, columns=headers)

                st.write("**原始数据预览：**")
                st.dataframe(import_df, use_container_width=True)

                # 列名映射
                column_mapping = {
                    '日期': '日期',
                    'date': '日期',
                    'Date': '日期',
                    '现货总资产': '现货总资产',
                    '总资产': '现货总资产',
                    '总市值': '总市值',
                    '市值': '总市值',
                    '转债市值': '转债市值',
                    '债券市值': '转债市值',
                    '股票市值': '股票市值',
                    'A股市值': '股票市值',
                    '现货收益率': '现货收益率',
                    '收益率': '现货收益率',
                    '基准': '基准',
                    '基准收益率': '基准收益率',
                    '现货超额': '现货超额',
                    '超额收益': '现货超额',
                    '期货总资产': '期货总资产',
                    '期货资产': '期货总资产',
                    '期货仓位': '期货仓位',
                    '期货市值': '期货市值',
                    '资产汇总': '资产汇总',
                    '总资产汇总': '资产汇总',
                    '资产收益率': '资产收益率',
                    '净值': '净值'
                }

                # 应用列名映射
                mapped_df = import_df.copy()
                for old_name, new_name in column_mapping.items():
                    if old_name in mapped_df.columns:
                        mapped_df = mapped_df.rename(columns={old_name: new_name})

                # 数据处理和验证
                processed_df = mapped_df.copy()

                # 1. 处理日期列
                if '日期' in processed_df.columns:
                    # 删除空的日期行
                    processed_df = processed_df[processed_df['日期'].notna()]
                    processed_df = processed_df[processed_df['日期'].astype(str).str.strip() != '']

                    # 日期格式转换
                    def parse_date(date_str):
                        if pd.isna(date_str) or str(date_str).strip() == '':
                            return None

                        date_str = str(date_str).strip()

                        # 尝试多种格式
                        formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%m/%d/%Y', '%d/%m/%Y']

                        for fmt in formats:
                            try:
                                return pd.to_datetime(date_str, format=fmt).strftime('%Y-%m-%d')
                            except:
                                continue

                        # 如果都失败，尝试自动解析
                        try:
                            return pd.to_datetime(date_str).strftime('%Y-%m-%d')
                        except:
                            return None

                    processed_df['日期'] = processed_df['日期'].apply(parse_date)
                    processed_df = processed_df.dropna(subset=['日期'])

                    if processed_df.empty:
                        st.error("所有日期都无法解析，请检查日期格式")
                        return
                else:
                    st.error("未找到日期列，请确保数据包含'日期'列")
                    return

                # 2. 处理数值列 - 区分百分比列和普通数值列
                percentage_columns = ['现货收益率', '基准收益率', '现货超额', '资产收益率']
                money_columns = ['现货总资产', '总市值', '转债市值', '股票市值', '期货总资产',
                                 '期货仓位', '期货市值', '资产汇总', '净值']

                # 处理百分比列（特殊处理）
                for col in percentage_columns:
                    if col in processed_df.columns:
                        processed_df[col] = process_percentage_column(processed_df[col], col)

                # 处理普通数值列
                for col in money_columns:
                    if col in processed_df.columns:
                        # 清理数值格式（移除逗号，但保留%的处理已在上面完成）
                        processed_df[col] = processed_df[col].astype(str).str.replace(',', '')
                        processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
                        processed_df[col] = processed_df[col].fillna(0)

                # 3. 填充缺失的必要列
                required_columns = ['日期', '现货总资产', '总市值', '转债市值', '股票市值', '现货收益率',
                                    '基准', '基准收益率', '现货超额', '期货总资产', '期货仓位', '期货市值',
                                    '资产汇总', '资产收益率', '净值']

                for col in required_columns:
                    if col not in processed_df.columns:
                        if col == '基准':
                            processed_df[col] = '中证1000'
                        else:
                            processed_df[col] = 0.0

                # 确保列顺序
                processed_df = processed_df[required_columns]

                # 按日期排序
                processed_df = processed_df.sort_values('日期')
                processed_df = processed_df.reset_index(drop=True)

                st.write("**处理后数据预览：**")
                # 显示时为百分比列添加%符号以便查看
                display_df = processed_df.copy()
                for col in percentage_columns:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "0.00%")

                st.dataframe(display_df, use_container_width=True)

                # 数据验证信息
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("记录数", len(processed_df))
                with col2:
                    date_range = f"{processed_df['日期'].min()} ~ {processed_df['日期'].max()}" if not processed_df.empty else "无数据"
                    st.metric("日期范围", date_range)
                with col3:
                    non_zero_fields = sum(
                        [(processed_df[col] != 0).sum() for col in money_columns if col in processed_df.columns])
                    st.metric("非零字段数", non_zero_fields)

                if st.button("确认导入", type="primary", key="confirm_import"):
                    try:
                        # 重新计算衍生字段
                        st.write("**调试 - calculate前：**", processed_df.head())
                        final_df = calculate_derived_values(processed_df, db, selected_unit_import)
                        st.write("**调试 - calculate后：**", final_df.head())

                        # 保存到数据库
                        success = db.update_trading_stats_batch(final_df, selected_unit_import)
                        if success:
                            st.success(f"成功导入 {len(final_df)} 条记录到单元 {selected_unit_import}")

                            st.balloons()
                            st.rerun()
                        else:
                            st.error("导入失败")

                    except Exception as e:
                        st.error(f"数据处理失败：{str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
            else:
                st.warning("请至少粘贴标题行和一行数据")



        except Exception as e:
            st.error(f"数据解析失败: {e}")
            import traceback
            st.code(traceback.format_exc())


def process_percentage_column(series, column_name):
    """
    智能处理百分比列
    如果数据包含%符号，则移除%号但保持数值
    如果数据是小数形式（如0.005），则转换为百分比（0.5%）
    """

    def convert_value(val):
        if pd.isna(val):
            return 0.0

        val_str = str(val).strip()

        # 如果包含%符号，直接移除%符号
        if '%' in val_str:
            try:
                return float(val_str.replace('%', ''))
            except:
                return 0.0

        # 如果是数字，判断是否需要转换
        try:
            num_val = float(val_str.replace(',', ''))

            # 对于收益率列，如果数值在-1到1之间（如0.005），可能是小数形式，转换为百分比
            if column_name in ['现货收益率', '基准收益率', '现货超额', '资产收益率']:
                if -1 <= num_val <= 1 and abs(num_val) < 0.1:  # 小于10%的小数值
                    # 询问用户是否需要转换
                    return num_val * 100  # 转换为百分比
                else:
                    return num_val  # 已经是百分比形式
            else:
                return num_val

        except:
            return 0.0

    return series.apply(convert_value)


def render_cash_flow_management(db, units):
    """渲染出入金管理页面"""
    st.subheader("💰 出入金管理")

    if not units:
        st.info("暂无单元数据")
        return

    # 选择单元
    selected_unit = st.selectbox("选择单元", options=units, key="cash_flow_unit")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("**添加出入金记录**")

        with st.form("add_cash_flow"):
            flow_date = st.date_input("日期")
            flow_type = st.selectbox("类型", options=["inflow", "outflow"],
                                     format_func=lambda x: "入金" if x == "inflow" else "出金")
            amount = st.number_input("金额", min_value=0.0, step=1000.0)
            note = st.text_input("备注（可选）")

            if st.form_submit_button("添加记录", type="primary"):
                if amount > 0:
                    success = db.add_cash_flow(selected_unit, flow_date.strftime('%Y-%m-%d'),
                                               flow_type, amount, note)
                    if success:
                        st.success("记录添加成功！")
                        st.rerun()
                    else:
                        st.error("添加失败")
                else:
                    st.error("请输入有效金额")

    with col2:
        st.write("**出入金记录**")

        cash_flows = db.get_cash_flows_by_unit(selected_unit)

        if not cash_flows.empty:
            # 格式化显示
            display_df = cash_flows.copy()
            display_df['类型'] = display_df['类型'].map({'inflow': '入金', 'outflow': '出金'})
            display_df['金额'] = display_df['金额'].apply(lambda x: f"{x:,.0f}")

            # 添加选择列
            display_df.insert(0, '选择', False)

            # 可编辑表格用于选择删除
            edited_flows = st.data_editor(
                display_df,
                column_config={
                    "选择": st.column_config.CheckboxColumn("选择", help="选择要删除的记录"),
                    "日期": st.column_config.DateColumn("日期"),
                    "类型": st.column_config.TextColumn("类型"),
                    "金额": st.column_config.TextColumn("金额"),
                    "备注": st.column_config.TextColumn("备注")
                },
                disabled=["日期", "类型", "金额", "备注"],
                hide_index=True,
                use_container_width=True,
                key=f"cash_flows_editor_{selected_unit}"
            )

            # 删除按钮
            col_del1, col_del2 = st.columns(2)

            with col_del1:
                if st.button("🗑️ 删除选中记录", key=f"delete_selected_flows_{selected_unit}"):
                    selected_rows = edited_flows[edited_flows['选择'] == True]

                    if not selected_rows.empty:
                        deleted_count = 0
                        for _, row in selected_rows.iterrows():
                            # 恢复原始格式进行删除
                            original_amount = float(row['金额'].replace(',', ''))
                            flow_type = 'inflow' if row['类型'] == '入金' else 'outflow'

                            success = db.delete_cash_flow(selected_unit, row['日期'], flow_type, original_amount)
                            if success:
                                deleted_count += 1

                        if deleted_count > 0:
                            st.success(f"成功删除 {deleted_count} 条记录")
                            st.rerun()
                        else:
                            st.error("删除失败")
                    else:
                        st.warning("请选择要删除的记录")

            with col_del2:
                if st.button("⚠️ 删除全部记录", key=f"delete_all_flows_{selected_unit}", type="secondary"):
                    if f"confirm_delete_all_{selected_unit}" not in st.session_state:
                        st.session_state[f"confirm_delete_all_{selected_unit}"] = True
                        st.rerun()

            # 确认删除全部的对话框
            if st.session_state.get(f"confirm_delete_all_{selected_unit}", False):
                st.warning(f"⚠️ 确认删除 **{selected_unit}** 的所有出入金记录？此操作不可恢复！")

                col_confirm1, col_confirm2 = st.columns(2)
                with col_confirm1:
                    if st.button("确认删除全部", key=f"confirm_delete_all_yes_{selected_unit}", type="primary"):
                        success = db.delete_all_cash_flows(selected_unit)
                        if success:
                            st.success("已删除所有出入金记录")
                            if f"confirm_delete_all_{selected_unit}" in st.session_state:
                                del st.session_state[f"confirm_delete_all_{selected_unit}"]
                            st.rerun()
                        else:
                            st.error("删除失败")

                with col_confirm2:
                    if st.button("取消", key=f"confirm_delete_all_no_{selected_unit}"):
                        if f"confirm_delete_all_{selected_unit}" in st.session_state:
                            del st.session_state[f"confirm_delete_all_{selected_unit}"]
                        st.rerun()

            # 统计信息
            total_inflow = cash_flows[cash_flows['类型'] == 'inflow']['金额'].sum() if 'inflow' in cash_flows[
                '类型'].values else 0
            total_outflow = cash_flows[cash_flows['类型'] == 'outflow']['金额'].sum() if 'outflow' in cash_flows[
                '类型'].values else 0

            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("总入金", f"{total_inflow:,.0f}")
            with col_stat2:
                st.metric("总出金", f"{total_outflow:,.0f}")
            with col_stat3:
                st.metric("净流入", f"{total_inflow - total_outflow:,.0f}")
        else:
            st.info("暂无出入金记录")


def render_data_import_section(db):
    """渲染数据导入区域"""
    st.subheader("📤 数据导入")

    col1, col2 = st.columns(2)

    with col1:
        render_paste_import_section(db)

    with col2:
        render_auto_pull_section(db)
