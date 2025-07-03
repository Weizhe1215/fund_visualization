"""
指数成分股导入组件
"""
import streamlit as st
import pandas as pd
from config import MAJOR_INDICES
import datetime


def process_index_components(df):
    """处理指数成分股数据"""
    # 寻找证券代码列
    stock_code_col = None
    possible_names = ['证券代码', '股票代码', 'Stock Code', 'stock_code', '代码', 'Code']

    for col in df.columns:
        if col in possible_names:
            stock_code_col = col
            break

    if stock_code_col is None:
        raise ValueError("未找到证券代码列，请确保文件包含'证券代码'列")

    # 寻找其他可能的列
    stock_name_col = None
    weight_col = None

    name_cols = ['证券名称', '股票名称', 'Stock Name', 'stock_name', '名称', 'Name']
    weight_cols = ['权重', 'Weight', 'weight', '占比', 'Ratio']

    for col in df.columns:
        if col in name_cols and stock_name_col is None:
            stock_name_col = col
        if col in weight_cols and weight_col is None:
            weight_col = col

    # 处理数据
    result_df = pd.DataFrame()
    result_df['stock_code'] = df[stock_code_col].astype(str)
    result_df['stock_name'] = df[stock_name_col] if stock_name_col else ''
    result_df['weight'] = pd.to_numeric(df[weight_col], errors='coerce') if weight_col else None

    # 清理无效数据
    result_df = result_df.dropna(subset=['stock_code'])
    result_df = result_df[result_df['stock_code'] != '']
    result_df = result_df[result_df['stock_code'] != 'nan']

    return result_df


def render_index_import(db):
    """渲染指数成分股导入页面"""
    st.header("📋 指数成分股管理")

    # 创建标签页
    tab1, tab2, tab3 = st.tabs(["📤 导入指数成分股", "📤 导入行业分类", "📊 数据概览"])

    with tab1:
        render_index_upload(db)

    with tab2:
        render_industry_upload(db)

    with tab3:
        render_index_summary(db)


def render_index_upload(db):
    """渲染指数成分股上传"""
    st.subheader("导入指数成分股")

    # 指数选择
    col1, col2 = st.columns(2)
    with col1:
        selected_index_name = st.selectbox(
            "选择指数",
            options=list(MAJOR_INDICES.keys()),
            key="index_selector"
        )
        index_code = MAJOR_INDICES[selected_index_name]

    with col2:
        # 日期选择
        selected_date = st.date_input(
            "成分股日期",
            value=datetime.date.today(),
            key="index_date_selector"
        )
        date_str = selected_date.strftime('%Y-%m-%d')

    # 显示数据格式要求
    with st.expander("📋 查看数据格式要求"):
        st.markdown("""
        **必需列：**
        - **证券代码**：支持列名 `证券代码`、`股票代码`、`Stock Code`、`stock_code`、`代码`

        **可选列：**
        - **证券名称**：支持列名 `证券名称`、`股票名称`、`Stock Name`、`stock_name`、`名称`
        - **权重**：支持列名 `权重`、`Weight`、`weight`、`占比`、`Ratio`

        **示例格式：**
        ```
        证券代码,证券名称,权重
        000001.SZ,平安银行,1.5
        000002.SZ,万科A,1.2
        600519.SH,贵州茅台,4.8
        ```
        """)

    # 文件上传
    uploaded_file = st.file_uploader(
        "选择指数成分股文件",
        type=['csv', 'xlsx', 'xls'],
        key="index_upload"
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

            # 数据处理和检测
            try:
                processed_df = process_index_components(df)

                st.write("**数据检测结果：**")
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("检测到股票数量", len(processed_df))

                with col2:
                    has_name = not processed_df['stock_name'].isna().all()
                    st.metric("股票名称", "✅ 有" if has_name else "❌ 无")

                with col3:
                    has_weight = not processed_df['weight'].isna().all()
                    st.metric("权重信息", "✅ 有" if has_weight else "❌ 无")

                # 显示处理后的数据样本
                st.write("**处理后数据样本：**")
                st.dataframe(processed_df.head(10), use_container_width=True)

                # 导入按钮
                if st.button("🚀 导入指数成分股", type="primary"):
                    try:
                        success = db.add_index_components(
                            index_code, selected_index_name, date_str, processed_df
                        )

                        if success:
                            st.success(f"成功导入 {selected_index_name} ({date_str}) 成分股 {len(processed_df)} 只！")
                            st.balloons()
                        else:
                            st.error("导入失败")
                    except Exception as e:
                        st.error(f"导入失败：{str(e)}")

            except Exception as e:
                st.error(f"数据处理失败：{str(e)}")

        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")


def render_index_summary(db):
    """渲染指数数据概览"""
    st.subheader("指数成分股数据概览")

    # 调试：直接查询数据库
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM index_components")
        total_count = cursor.fetchone()[0]
        st.write(f"Debug: 数据库中总共有 {total_count} 条指数成分股记录")

        cursor.execute("SELECT DISTINCT index_code, index_name FROM index_components")
        indices = cursor.fetchall()
        for idx in indices:
            st.write(f"Debug: 指数 {idx[0]} - {idx[1]}")
        conn.close()
    except Exception as e:
        st.error(f"Debug查询失败: {e}")

    # 获取数据概要
    summary_df = db.get_all_index_components_summary()

    if summary_df.empty:
        st.info("暂无指数成分股数据")
        return

    # 按指数分组显示
    for index_code in summary_df['index_code'].unique():
        index_data = summary_df[summary_df['index_code'] == index_code]
        index_name = index_data['index_name'].iloc[0]

        with st.expander(f"📈 {index_name} ({index_code})"):
            st.write("**历史数据：**")

            for _, row in index_data.iterrows():
                col1, col2, col3 = st.columns([2, 2, 1])

                with col1:
                    st.text(f"日期: {row['date']}")

                with col2:
                    st.text(f"成分股数量: {row['stock_count']} 只")

                with col3:
                    if st.button("🗑️", key=f"del_index_{index_code}_{row['date']}",
                                 help="删除该日期数据"):
                        st.warning("删除功能待实现")

    # 统计信息
    st.write("**总体统计：**")
    col1, col2, col3 = st.columns(3)

    with col1:
        total_indices = summary_df['index_code'].nunique()
        st.metric("指数数量", total_indices)

    with col2:
        total_dates = summary_df.groupby('index_code')['date'].nunique().sum()
        st.metric("总数据日期", total_dates)

    with col3:
        avg_stocks = summary_df['stock_count'].mean()
        st.metric("平均成分股数", f"{avg_stocks:.0f}")


def render_industry_upload(db):
    """渲染行业分类上传"""
    st.subheader("导入行业分类")

    # 显示数据格式要求
    with st.expander("📋 查看数据格式要求"):
        st.markdown("""
        **必需列：**
        - **行业名称**：第一列，行业分类名称
        - **股票代码**：第二列，6位数字股票代码（无后缀）

        **示例格式：**
        ```
        行业名称,股票代码
        银行,000001
        银行,600036
        白酒,600519
        白酒,000858
        ```

        **注意：**
        - 股票代码无需包含.SH或.SZ后缀
        - 系统会自动匹配前6位数字
        - 批量导入会覆盖现有所有行业数据
        """)

    # 文件上传
    uploaded_file = st.file_uploader(
        "选择行业分类文件",
        type=['csv', 'xlsx', 'xls'],
        key="industry_upload"
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

            # 数据处理
            if len(df.columns) >= 2:
                # 使用前两列，确保股票代码按文本读取并补齐6位
                processed_df = pd.DataFrame()
                processed_df['industry_name'] = df.iloc[:, 0].astype(str)
                processed_df['stock_code'] = df.iloc[:, 1].astype(str).str.zfill(6)  # 补齐6位数字

                # 清理数据
                processed_df = processed_df.dropna()
                processed_df = processed_df[processed_df['industry_name'] != '']
                processed_df = processed_df[processed_df['stock_code'] != '']

                # 确保股票代码是6位数字
                processed_df['stock_code'] = processed_df['stock_code'].str.replace(r'\D', '', regex=True)
                processed_df = processed_df[processed_df['stock_code'].str.len() == 6]

                st.write("**处理结果：**")
                col1, col2 = st.columns(2)

                with col1:
                    industries_count = processed_df['industry_name'].nunique()
                    st.metric("行业数量", industries_count)

                with col2:
                    stocks_count = len(processed_df)
                    st.metric("股票数量", stocks_count)

                # 显示行业分布
                st.write("**行业分布：**")
                industry_summary = processed_df.groupby('industry_name').size().reset_index(name='count')
                st.dataframe(industry_summary, use_container_width=True)

                # 导入按钮
                if st.button("🚀 导入行业分类数据", type="primary"):
                    try:
                        success = db.add_industry_components(processed_df)

                        if success:
                            st.success(f"成功导入 {industries_count} 个行业，{stocks_count} 只股票！")
                            st.balloons()
                        else:
                            st.error("导入失败")
                    except Exception as e:
                        st.error(f"导入失败：{str(e)}")
            else:
                st.error("文件至少需要包含两列：行业名称和股票代码")

        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")