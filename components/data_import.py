"""
数据导入组件
"""
import streamlit as st
import pandas as pd
import io
from config import COLUMN_MAPPING, SUPPORTED_FILE_FORMATS

def detect_and_map_columns(df, data_type='nav'):
    """自动检测和映射列名"""
    if data_type == 'nav':
        column_mapping = COLUMN_MAPPING['nav_columns']
    else:  # holdings
        column_mapping = COLUMN_MAPPING['holdings_columns']

    mapped_columns = {}
    df_columns = df.columns.tolist()

    for standard_col, possible_names in column_mapping.items():
        for col in df_columns:
            if col in possible_names:
                mapped_columns[col] = standard_col
                break

    return mapped_columns

def process_nav_data(df, column_mapping):
    """处理净值数据"""
    # 重命名列
    df_processed = df.rename(columns=column_mapping)

    # 检查必需列
    required_cols = ['date', 'nav_value']
    missing_cols = [col for col in required_cols if col not in df_processed.columns]

    if missing_cols:
        raise ValueError(f"缺少必需列: {missing_cols}")

    # 数据类型转换和清理
    df_processed['date'] = pd.to_datetime(df_processed['date']).dt.strftime('%Y-%m-%d')
    df_processed['nav_value'] = pd.to_numeric(df_processed['nav_value'], errors='coerce')

    if 'cumulative_nav' in df_processed.columns:
        df_processed['cumulative_nav'] = pd.to_numeric(df_processed['cumulative_nav'], errors='coerce')
    else:
        df_processed['cumulative_nav'] = None

    # 删除无效行
    df_processed = df_processed.dropna(subset=['nav_value'])

    return df_processed[['date', 'nav_value', 'cumulative_nav']]

def process_holdings_data(df, column_mapping, data_format='matrix'):
    """处理持仓数据"""

    if data_format == 'matrix':
        # 矩阵格式：行是日期，列是股票ticker，值是裸权重
        date_col = df.columns[0]

        # 将矩阵转换为长格式
        df_long = df.melt(
            id_vars=[date_col],
            var_name='stock_code',
            value_name='raw_weight'
        )

        # 重命名日期列
        df_long = df_long.rename(columns={date_col: 'date'})

        # 处理日期 - 支持YYYYMMDD格式
        try:
            # 检查是否为YYYYMMDD格式
            sample_date = str(df_long['date'].iloc[0])
            if len(sample_date) == 8 and sample_date.isdigit():
                df_long['date'] = pd.to_datetime(df_long['date'].astype(str), format='%Y%m%d').dt.strftime('%Y-%m-%d')
            else:
                df_long['date'] = pd.to_datetime(df_long['date']).dt.strftime('%Y-%m-%d')
        except:
            raise ValueError("日期格式无法解析，请确保日期格式为 YYYYMMDD")

        # 处理权重数据
        df_long['stock_code'] = df_long['stock_code'].astype(str)
        df_long['raw_weight'] = pd.to_numeric(df_long['raw_weight'], errors='coerce')

        # 删除无效数据
        df_long = df_long.dropna(subset=['date', 'raw_weight'])
        df_long = df_long[df_long['raw_weight'] > 0]

        if df_long.empty:
            raise ValueError("处理后没有有效数据，请检查数据格式")

        # 计算相对权重
        daily_totals = df_long.groupby('date')['raw_weight'].sum()
        df_long = df_long.merge(daily_totals.rename('daily_total'), left_on='date', right_index=True)
        df_long['position_ratio'] = (df_long['raw_weight'] / df_long['daily_total']) * 100

        # 添加其他列
        df_long['stock_name'] = df_long['stock_code']
        df_long['market_value'] = None
        df_long['shares'] = None

        return df_long[['date', 'stock_code', 'stock_name', 'position_ratio', 'market_value', 'shares']]

    else:
        # 长格式处理
        df_processed = df.rename(columns=column_mapping)

        required_cols = ['date', 'stock_code']
        missing_cols = [col for col in required_cols if col not in df_processed.columns]

        if missing_cols:
            raise ValueError(f"缺少必需列: {missing_cols}")

        df_processed['date'] = pd.to_datetime(df_processed['date']).dt.strftime('%Y-%m-%d')
        df_processed['stock_code'] = df_processed['stock_code'].astype(str)

        for col in ['position_ratio', 'market_value', 'shares']:
            if col in df_processed.columns:
                df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
            else:
                df_processed[col] = None

        if 'stock_name' not in df_processed.columns:
            df_processed['stock_name'] = df_processed['stock_code']

        df_processed = df_processed.dropna(subset=['stock_code'])
        df_processed = df_processed[df_processed['stock_code'] != '']

        return df_processed[['date', 'stock_code', 'stock_name', 'position_ratio', 'market_value', 'shares']]

def render_data_import(db):
    """渲染数据导入页面"""
    st.header("📤 数据导入")

    tab1, tab2, tab3 = st.tabs(["📋 产品管理", "📈 净值数据", "📊 持仓数据"])

    with tab1:
        render_product_management(db)

    with tab2:
        render_nav_import(db)

    with tab3:
        render_holdings_import(db)

def render_product_management(db):
    """渲染产品管理页面"""
    st.subheader("产品管理")

    products = db.get_products()
    if products:
        st.write("**现有产品：**")

        for product in products:
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 3, 2, 1])

                with col1:
                    st.text(product['product_code'])
                with col2:
                    st.text(product['product_name'])
                with col3:
                    summary = db.get_product_data_summary(product['product_code'])
                    st.caption(f"净值: {summary['nav_records']}条 | 持仓: {summary['holdings_dates']}日")
                with col4:
                    if st.button("🗑️", key=f"del_{product['product_code']}",
                               help="删除产品", type="secondary"):
                        st.session_state[f"confirm_delete_{product['product_code']}"] = True

                # 确认删除对话框
                if st.session_state.get(f"confirm_delete_{product['product_code']}", False):
                    st.warning(f"⚠️ 确认删除产品 **{product['product_name']} ({product['product_code']})**？")
                    st.caption("这将删除该产品的所有净值和持仓数据，且不可恢复！")

                    col_yes, col_no, col_space = st.columns([1, 1, 3])
                    with col_yes:
                        if st.button("确认删除", key=f"confirm_yes_{product['product_code']}",
                                   type="primary"):
                            success = db.delete_product(product['product_code'])
                            if success:
                                st.success("产品删除成功！")
                                if f"confirm_delete_{product['product_code']}" in st.session_state:
                                    del st.session_state[f"confirm_delete_{product['product_code']}"]
                                st.rerun()
                            else:
                                st.error("删除失败")

                    with col_no:
                        if st.button("取消", key=f"confirm_no_{product['product_code']}"):
                            if f"confirm_delete_{product['product_code']}" in st.session_state:
                                del st.session_state[f"confirm_delete_{product['product_code']}"]
                            st.rerun()

                st.divider()

        st.write("**数据管理：**")
        if products:
            selected_product_for_data = st.selectbox(
                "选择产品进行数据管理",
                options=[f"{p['product_name']} ({p['product_code']})" for p in products],
                key="data_management_product"
            )

            if selected_product_for_data:
                product_code = selected_product_for_data.split('(')[1].split(')')[0]
                summary = db.get_product_data_summary(product_code)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("净值记录", summary['nav_records'])
                    if summary['nav_records'] > 0:
                        if st.button("🗑️ 删除净值数据", key=f"del_nav_{product_code}"):
                            success = db.delete_product_nav_data(product_code)
                            if success:
                                st.success("净值数据删除成功！")
                                st.rerun()

                with col2:
                    st.metric("持仓记录", f"{summary['holdings_records']} ({summary['holdings_dates']}日)")
                    if summary['holdings_records'] > 0:
                        if st.button("🗑️ 删除持仓数据", key=f"del_holdings_{product_code}"):
                            success = db.delete_product_holdings_data(product_code)
                            if success:
                                st.success("持仓数据删除成功！")
                                st.rerun()

    else:
        st.info("暂无产品")

    st.divider()

    st.write("**添加新产品：**")
    with st.form("add_product_form"):
        col1, col2 = st.columns(2)
        with col1:
            product_code = st.text_input("产品代码*", placeholder="例如: FUND001")
        with col2:
            product_name = st.text_input("产品名称*", placeholder="例如: 价值成长基金")

        description = st.text_area("产品描述", placeholder="可选，产品的详细描述")

        submitted = st.form_submit_button("➕ 添加产品", type="primary")

        if submitted:
            if product_code and product_name:
                success = db.add_product(product_code, product_name, description)
                if success:
                    st.success("产品添加成功！")
                    st.rerun()
                else:
                    st.error("产品添加失败，请检查代码是否重复")
            else:
                st.error("请填写产品代码和名称")


def render_nav_import(db):
    """渲染净值数据导入"""
    st.subheader("导入净值数据")

    # 产品选择
    products = db.get_products()
    if not products:
        st.warning("请先添加产品")
        return

    product_options = {f"{p['product_name']} ({p['product_code']})": p['product_code'] for p in products}
    selected_product = st.selectbox("选择产品", options=list(product_options.keys()))
    product_code = product_options[selected_product]

    # 复制粘贴导入
    st.write("**方式1：复制粘贴导入**")

    with st.expander("📋 复制粘贴净值数据"):
        st.info("从Excel复制日期和净值数据，粘贴到下方文本框中")

        # 显示格式说明
        st.markdown("""
        **支持格式：**
        ```
        2024/12/31  1.0
        2025/01/02  1.1
        2025/01/03  1.05
        ```
        """)

        # 文本输入框
        pasted_data = st.text_area(
            "粘贴数据",
            height=200,
            placeholder="请将Excel中的日期和净值数据粘贴到这里...",
            key="nav_paste_input"
        )

        if pasted_data.strip():
            try:
                # 解析粘贴的数据
                lines = [line.strip() for line in pasted_data.strip().split('\n') if line.strip()]

                parsed_data = []
                for line in lines:
                    # 分割日期和净值（支持空格、制表符等分隔符）
                    parts = line.split()
                    if len(parts) >= 2:
                        date_str = parts[0]
                        nav_value = float(parts[1])

                        # 解析日期
                        try:
                            if '/' in date_str:
                                date_obj = pd.to_datetime(date_str, format='%Y/%m/%d')
                            elif '-' in date_str:
                                date_obj = pd.to_datetime(date_str, format='%Y-%m-%d')
                            else:
                                date_obj = pd.to_datetime(date_str)

                            parsed_data.append({
                                'date': date_obj.strftime('%Y-%m-%d'),
                                'nav_value': nav_value,
                                'cumulative_nav': nav_value  # 暂时设为相同值
                            })
                        except:
                            st.warning(f"无法解析日期：{date_str}")

                if parsed_data:
                    paste_df = pd.DataFrame(parsed_data)
                    st.write("**解析结果预览：**")
                    st.dataframe(paste_df, use_container_width=True)

                    if st.button("🚀 导入粘贴的净值数据", type="primary", key="import_pasted_nav"):
                        try:
                            # 获取现有净值数据
                            existing_nav = db.get_nav_data(product_code)

                            if not existing_nav.empty:
                                # 合并新旧数据，去重（以新数据为准）
                                combined_df = pd.concat([existing_nav, paste_df], ignore_index=True)
                                # 按日期去重，保留最后一个（新数据）
                                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                                success = db.add_nav_data(product_code, combined_df, merge_mode=True)
                            else:
                                success = db.add_nav_data(product_code, paste_df, merge_mode=True)

                            if success:
                                st.success(f"成功导入 {len(paste_df)} 条净值记录！")
                                st.balloons()
                            else:
                                st.error("导入失败，请检查数据格式")
                        except Exception as e:
                            st.error(f"数据处理失败：{str(e)}")
                else:
                    st.warning("未能解析出有效数据")

            except Exception as e:
                st.error(f"数据解析失败：{str(e)}")

    st.divider()
    st.write("**方式2：文件上传**")

    with st.expander("📋 查看数据格式要求"):
        st.markdown("""
        **必需列：**
        - **日期**：支持列名 `日期`、`Date`、`date`
        - **单位净值**：支持列名 `单位净值`、`净值`、`NAV`、`nav_value`

        **可选列：**
        - **累计净值**：支持列名 `累计净值`、`累积净值`、`Cumulative NAV`、`cumulative_nav`

        **示例格式：**
        ```
        日期,单位净值,累计净值
        2024-01-01,1.0000,1.0000
        2024-01-02,1.0012,1.0012
        2024-01-03,0.9998,0.9998
        ```
        """)

    # 文件上传
    uploaded_file = st.file_uploader(
        "选择净值数据文件",
        type=['csv', 'xlsx', 'xls'],
        key="nav_upload"
    )

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            else:
                df = pd.read_excel(uploaded_file)

            st.write("**文件预览：**")
            st.dataframe(df.head(10), use_container_width=True)

            st.write("**列映射检测：**")
            column_mapping = detect_and_map_columns(df, 'nav')

            col1, col2 = st.columns(2)
            with col1:
                st.write("原始列名 → 标准列名")
                for orig, mapped in column_mapping.items():
                    st.write(f"`{orig}` → `{mapped}`")

            with col2:
                st.write("检测结果")
                required_found = all(col in column_mapping.values() for col in ['date', 'nav_value'])
                if required_found:
                    st.success("✅ 必需列检测成功")
                else:
                    st.error("❌ 缺少必需列")

            if required_found:
                if st.button("🚀 导入净值数据", type="primary"):
                    try:
                        processed_df = process_nav_data(df, column_mapping)
                        success = db.add_nav_data(product_code, processed_df, merge_mode=True)

                        if success:
                            st.success(f"成功导入 {len(processed_df)} 条净值记录！")
                            st.balloons()
                        else:
                            st.error("导入失败，请检查数据格式")
                    except Exception as e:
                        st.error(f"数据处理失败：{str(e)}")

        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")


def render_holdings_import(db):
    """渲染持仓数据导入"""
    st.subheader("导入持仓数据")

    # 产品选择
    products = db.get_products()
    if not products:
        st.warning("请先添加产品")
        return

    product_options = {f"{p['product_name']} ({p['product_code']})": p['product_code'] for p in products}
    selected_product = st.selectbox("选择产品", options=list(product_options.keys()), key="holdings_product")
    product_code = product_options[selected_product]

    # 数据格式选择
    st.write("**选择数据格式：**")
    data_format = st.radio(
        "持仓数据格式",
        options=["matrix", "long", "batch_files"],
        format_func=lambda x: "矩阵格式（行=日期，列=股票代码）" if x == "matrix"
        else "长格式（每行一条记录）" if x == "long"
        else "批量文件上传",
        index=0,
        key="data_format"
    )

    # 显示数据格式要求
    with st.expander("📋 查看数据格式要求"):
        if data_format == "matrix":
            st.markdown("""
            **矩阵格式说明：**
            - 第一列：日期（支持格式：YYYYMMDD、YYYY-MM-DD、YYYY/MM/DD）
            - 其他列：股票ticker（如 123456.SH, 000001.SZ 等）
            - 单元格值：该股票的裸权重值（非百分比）
            - 系统会自动计算相对权重：裸值/当日所有股票裸值之和
            - 空值或0值会被自动忽略

            **示例格式：**
            ```
            日期,000001.SZ,600519.SH,600036.SH,000858.SZ
            20240131,1000,2000,1500,800
            20240229,1200,1800,1400,900
            20240331,1100,2100,1600,750
            ```

            **权重计算示例：**
            - 20240131当日总裸值：1000+2000+1500+800=5300
            - 000001.SZ权重：1000/5300≈18.87%
            - 600519.SH权重：2000/5300≈37.74%
            """)
        elif data_format == "long":
            st.markdown("""
            **长格式说明：**
            - **必需列：** 日期、股票代码
            - **可选列：** 股票名称、持仓比例、持仓市值、持股数量

            **示例格式：**
            ```
            日期,股票代码,股票名称,持仓比例
            2024-03-31,600519,贵州茅台,8.5
            2024-03-31,600036,招商银行,6.1
            ```
            """)
        else:  # batch_files
            st.markdown("""
            **批量文件上传说明：**
            - 可以同时上传多个持仓文件
            - 系统会自动匹配文件中的产品名称与数据库中的产品
            - **必需列：**
              - **产品名称**：与数据库中的产品名称完全匹配
              - **日期**：持仓日期
              - **证券代码**：6位数字代码（如 688718，系统会自动添加交易所后缀）
              - **持仓市值**：该股票的市值
            - **证券代码规则**：系统会自动添加交易所后缀
              - 6开头的代码会添加 .SH 后缀（上海证券交易所）
              - 其他代码会添加 .SZ 后缀（深圳证券交易所）

            **示例格式：**
            ```
            产品名称,日期,证券代码,持仓市值
            基金A,2024-12-31,688718,1000000
            基金A,2024-12-31,600519,2000000
            ```
            """)

    # 文件上传
    if data_format == "batch_files":
        uploaded_files = st.file_uploader(
            "选择多个持仓数据文件",
            type=['csv', 'xlsx', 'xls'],
            accept_multiple_files=True,
            key="batch_holdings_upload"
        )

        if uploaded_files:
            st.write(f"**已选择 {len(uploaded_files)} 个文件**")

            # 处理所有文件
            all_processed_data = []
            file_summary = []

            for uploaded_file in uploaded_files:
                try:
                    # 读取文件
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                    else:
                        df = pd.read_excel(uploaded_file)

                    # 查找必需列
                    product_col = None
                    date_col = None
                    code_col = None
                    value_col = None

                    for col in df.columns:
                        if '产品名称' in col or '产品' in col:
                            product_col = col
                        elif '日期' in col or 'Date' in col:
                            date_col = col
                        elif '证券代码' in col or '股票代码' in col or '代码' in col:
                            code_col = col
                        elif '持仓市值' in col or '市值' in col:
                            value_col = col

                    if all([product_col, date_col, code_col, value_col]):
                        # 处理数据
                        processed_df = df[[product_col, date_col, code_col, value_col]].copy()
                        processed_df.columns = ['product_name', 'date', 'stock_code', 'market_value']

                        # 数据清理
                        processed_df['date'] = pd.to_datetime(processed_df['date']).dt.strftime('%Y-%m-%d')
                        processed_df['stock_code'] = processed_df['stock_code'].astype(str).str.zfill(6)

                        # 添加交易所后缀：6开头的是上海(.SH)，其他是深圳(.SZ)
                        def add_exchange_suffix(code):
                            code = str(code).zfill(6)  # 确保是6位数字
                            if code.startswith('6'):
                                return f"{code}.SH"
                            else:
                                return f"{code}.SZ"

                        processed_df['stock_code'] = processed_df['stock_code'].apply(add_exchange_suffix)
                        processed_df['market_value'] = pd.to_numeric(processed_df['market_value'], errors='coerce')

                        # 删除无效数据
                        processed_df = processed_df.dropna(subset=['product_name', 'stock_code', 'market_value'])
                        processed_df = processed_df[processed_df['market_value'] > 0]

                        # 添加其他必需列
                        processed_df['stock_name'] = ''  # 股票名称留空
                        processed_df['position_ratio'] = None  # 稍后计算
                        processed_df['shares'] = None

                        all_processed_data.append(processed_df)

                        # 文件摘要
                        unique_products = processed_df['product_name'].nunique()
                        unique_dates = processed_df['date'].nunique()
                        stock_count = len(processed_df)

                        file_summary.append({
                            'filename': uploaded_file.name,
                            'products': unique_products,
                            'dates': unique_dates,
                            'records': stock_count,
                            'status': '✅ 成功'
                        })
                    else:
                        missing_cols = []
                        if not product_col: missing_cols.append('产品名称')
                        if not date_col: missing_cols.append('日期')
                        if not code_col: missing_cols.append('证券代码')
                        if not value_col: missing_cols.append('持仓市值')

                        file_summary.append({
                            'filename': uploaded_file.name,
                            'products': 0,
                            'dates': 0,
                            'records': 0,
                            'status': f'❌ 缺少列: {", ".join(missing_cols)}'
                        })

                except Exception as e:
                    file_summary.append({
                        'filename': uploaded_file.name,
                        'products': 0,
                        'dates': 0,
                        'records': 0,
                        'status': f'❌ 处理失败: {str(e)}'
                    })

            # 显示文件处理摘要
            st.write("**文件处理摘要：**")
            summary_df = pd.DataFrame(file_summary)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            if all_processed_data:
                # 合并所有数据
                combined_df = pd.concat(all_processed_data, ignore_index=True)

                # 按产品分组并计算权重
                for product_name in combined_df['product_name'].unique():
                    product_mask = combined_df['product_name'] == product_name
                    product_data = combined_df[product_mask]

                    # 按日期分组计算权重
                    for date in product_data['date'].unique():
                        date_mask = (combined_df['product_name'] == product_name) & (combined_df['date'] == date)
                        date_data = combined_df[date_mask]
                        total_value = date_data['market_value'].sum()

                        if total_value > 0:
                            combined_df.loc[date_mask, 'position_ratio'] = (date_data[
                                                                                'market_value'] / total_value) * 100

                # 显示处理结果
                st.write("**处理结果概览：**")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("总记录数", len(combined_df))

                with col2:
                    st.metric("涉及产品", combined_df['product_name'].nunique())

                with col3:
                    st.metric("涉及日期", combined_df['date'].nunique())

                # 显示证券代码转换示例
                st.write("**证券代码转换示例：**")
                sample_codes = combined_df['stock_code'].drop_duplicates().head(10)
                code_examples = []
                for code in sample_codes:
                    original = code.replace('.SH', '').replace('.SZ', '')
                    code_examples.append({
                        '原始代码': original,
                        '转换后代码': code,
                        '交易所': '上海' if code.endswith('.SH') else '深圳'
                    })

                if code_examples:
                    st.dataframe(pd.DataFrame(code_examples), use_container_width=True, hide_index=True)

                # 产品匹配检查
                st.write("**产品匹配检查：**")
                db_product_names = [p['product_name'] for p in db.get_products()]
                matched_products = []
                unmatched_products = []

                for product in combined_df['product_name'].unique():
                    if product in db_product_names:
                        matched_products.append(product)
                        st.success(f"✅ {product}")
                    else:
                        unmatched_products.append(product)
                        st.error(f"❌ {product} (数据库中不存在)")

                if matched_products:
                    # 只导入匹配的产品数据
                    matched_df = combined_df[combined_df['product_name'].isin(matched_products)]

                    st.write("**数据预览：**")
                    st.dataframe(matched_df.head(10), use_container_width=True)

                    if st.button("🚀 批量导入持仓数据", type="primary"):
                        try:
                            total_imported = 0

                            for product_name in matched_products:
                                product_data = matched_df[matched_df['product_name'] == product_name]

                                # 获取对应的产品代码
                                db_products = db.get_products()
                                product_code_batch = None
                                for p in db_products:
                                    if p['product_name'] == product_name:
                                        product_code_batch = p['product_code']
                                        break

                                if product_code_batch:
                                    success = db.add_holdings_data(product_code_batch, product_data)
                                    if success:
                                        total_imported += len(product_data)

                            st.success(f"批量导入完成！总共导入 {total_imported} 条记录")
                            st.balloons()

                        except Exception as e:
                            st.error(f"批量导入失败：{str(e)}")
                else:
                    st.warning("没有匹配的产品可以导入")

    else:
        # 单文件上传
        uploaded_file = st.file_uploader(
            "选择持仓数据文件",
            type=['csv', 'xlsx', 'xls'],
            key="holdings_upload"
        )

        if uploaded_file is not None:
            try:
                # 读取文件
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
                else:
                    df = pd.read_excel(uploaded_file)

                st.write("**文件预览：**")
                st.dataframe(df.head(10), use_container_width=True)

                # 根据格式进行不同的处理
                if data_format == "matrix":
                    st.write("**矩阵格式检测：**")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("数据结构")
                        st.info(f"检测到 {len(df)} 个日期")
                        st.info(f"检测到 {len(df.columns) - 1} 只股票")

                    with col2:
                        st.write("股票代码列表")
                        stock_codes = df.columns[1:].tolist()  # 除第一列（日期）外的所有列
                        st.write(stock_codes[:10])  # 显示前10个
                        if len(stock_codes) > 10:
                            st.write(f"... 还有 {len(stock_codes) - 10} 只股票")

                    # 导入按钮
                    if st.button("🚀 导入持仓数据（矩阵格式）", type="primary"):
                        try:
                            processed_df = process_holdings_data(df, {}, data_format='matrix')
                            success = db.add_holdings_data(product_code, processed_df)

                            if success:
                                unique_dates = processed_df['date'].nunique()
                                unique_stocks = processed_df['stock_code'].nunique()
                                st.success(f"成功导入 {len(processed_df)} 条持仓记录！")
                                st.info(f"包含 {unique_dates} 个日期，{unique_stocks} 只股票")
                                st.balloons()
                            else:
                                st.error("导入失败，请检查数据格式")
                        except Exception as e:
                            st.error(f"数据处理失败：{str(e)}")
                            import traceback
                            st.code(traceback.format_exc())

                else:
                    # 长格式处理
                    st.write("**列映射检测：**")
                    column_mapping = detect_and_map_columns(df, 'holdings')

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("原始列名 → 标准列名")
                        for orig, mapped in column_mapping.items():
                            st.write(f"`{orig}` → `{mapped}`")

                    with col2:
                        st.write("检测结果")
                        required_found = all(col in column_mapping.values() for col in ['date', 'stock_code'])
                        if required_found:
                            st.success("✅ 必需列检测成功")
                            unique_dates = df[list(column_mapping.keys())[0]].nunique() if column_mapping else 0
                            st.info(f"包含 {unique_dates} 个不同日期的持仓数据")
                        else:
                            st.error("❌ 缺少必需列")

                    # 导入按钮
                    if required_found:
                        if st.button("🚀 导入持仓数据（长格式）", type="primary"):
                            try:
                                processed_df = process_holdings_data(df, column_mapping, data_format='long')
                                success = db.add_holdings_data(product_code, processed_df)

                                if success:
                                    st.success(f"成功导入 {len(processed_df)} 条持仓记录！")
                                    st.balloons()
                                else:
                                    st.error("导入失败，请检查数据格式")
                            except Exception as e:
                                st.error(f"数据处理失败：{str(e)}")

            except Exception as e:
                st.error(f"文件读取失败：{str(e)}")