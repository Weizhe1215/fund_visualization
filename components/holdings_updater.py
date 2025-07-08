"""
持仓数据自动更新组件
"""
import streamlit as st
import pandas as pd
import os
import glob
from datetime import datetime, timedelta
import time

# 数据路径配置
DATA_PATHS = {
    "实盘": r"C:\shared_data\实盘\交易数据定频导出",
    "仿真": r"C:\shared_data\仿真\交易数据定频导出"
}

def add_exchange_suffix(stock_code):
    """为股票代码添加交易所后缀"""
    code = str(stock_code).zfill(6)  # 确保是6位数字

    # 沪市：6开头的股票，688/689开头的科创板，1开头的转债
    if code.startswith('6') or code.startswith('688') or code.startswith('689') or code.startswith('1'):
        return f"{code}.SH"
    # 深市：0/3开头的股票，其他转债
    else:
        return f"{code}.SZ"


def get_all_holdings_files(data_source="实盘", target_time="150000"):
    """获取指定数据源所有日期的持仓文件"""
    try:
        base_path = DATA_PATHS[data_source]
        if not os.path.exists(base_path):
            return {"error": f"路径不存在: {base_path}"}

        # 获取所有日期文件夹并排序
        date_folders = [f for f in os.listdir(base_path)
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(base_path, f))]

        if not date_folders:
            return {"error": "未找到日期文件夹"}

        date_folders.sort()  # 按日期排序

        # 按日期收集文件
        date_files = {}
        total_files = 0

        for date_folder in date_folders:
            date_folder_path = os.path.join(base_path, date_folder)

            # 查找该日期的150000时间文件
            target_files = []
            for root, dirs, files in os.walk(date_folder_path):
                for file in files:
                    if (file.startswith("单元资产账户持仓导出") and
                            file.endswith('.xlsx') and
                            target_time in file):
                        target_files.append(os.path.join(root, file))

            if target_files:
                date_files[date_folder] = target_files
                total_files += len(target_files)

        return {
            "success": True,
            "date_files": date_files,  # 按日期分组的文件
            "data_source": data_source,
            "debug_info": {
                "total_dates": len(date_files),
                "total_files": total_files,
                "date_list": list(date_files.keys()),
                "search_path": base_path
            }
        }

    except Exception as e:
        return {"error": f"读取{data_source}文件失败: {str(e)}"}


def read_holdings_file(file_path):
    """读取单个持仓文件"""
    try:
        df = pd.read_excel(file_path)

        # 查找需要的列
        product_col = None
        stock_code_col = None
        market_value_col = None

        for col in df.columns:
            if '产品名称' in col:
                product_col = col
            elif '证券代码' in col:
                stock_code_col = col
            elif '持仓市值' in col:
                market_value_col = col

        # 检查必需列是否存在
        if not all([product_col, stock_code_col, market_value_col]):
            return {"error": f"缺少必需列，文件: {os.path.basename(file_path)}"}

        # 提取需要的数据
        result_df = df[[product_col, stock_code_col, market_value_col]].copy()
        result_df.columns = ['product_name', 'stock_code', 'market_value']

        # 数据清理
        result_df['product_name'] = result_df['product_name'].astype(str)
        result_df['stock_code'] = result_df['stock_code'].astype(str).str.zfill(6)
        result_df['market_value'] = pd.to_numeric(result_df['market_value'], errors='coerce')

        # 删除无效数据
        result_df = result_df.dropna(subset=['product_name', 'stock_code', 'market_value'])
        result_df = result_df[result_df['market_value'] > 0]

        # 添加交易所后缀
        result_df['stock_code'] = result_df['stock_code'].apply(add_exchange_suffix)

        return {"success": True, "data": result_df}

    except Exception as e:
        return {"error": f"读取文件失败 {os.path.basename(file_path)}: {str(e)}"}


def update_holdings_to_database(db, holdings_data, date_str):
    """将持仓数据更新到数据库"""
    try:

        # 按产品分组处理
        updated_products = []

        for product_name in holdings_data['product_name'].unique():


            # 获取该产品的持仓数据
            product_data = holdings_data[holdings_data['product_name'] == product_name].copy()


            # 按股票代码合并（同一产品可能有多条记录）
            merged_data = product_data.groupby('stock_code').agg({
                'market_value': 'sum',
                'product_name': 'first'
            }).reset_index()


            # 计算持仓比例
            total_value = merged_data['market_value'].sum()
            if total_value > 0:
                merged_data['position_ratio'] = (merged_data['market_value'] / total_value) * 100
            else:
                merged_data['position_ratio'] = 0

            # 添加其他必需列
            # 确保日期格式正确 (YYYYMMDD -> YYYY-MM-DD)
            if len(date_str) == 8:  # 如果是YYYYMMDD格式
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                formatted_date = date_str
            merged_data['date'] = formatted_date
            merged_data['stock_name'] = ''  # 暂时留空
            merged_data['shares'] = None

            # 检查产品是否在数据库中存在
            db_products = db.get_products()
            product_code = None
            for p in db_products:
                if p['product_name'] == product_name:
                    product_code = p['product_code']
                    break

            if product_code:
                # 准备数据格式
                final_data = merged_data[
                    ['date', 'stock_code', 'stock_name', 'position_ratio', 'market_value', 'shares']]

                # 更新到数据库
                success = db.add_holdings_data(product_code, final_data)
                if success:
                    updated_products.append(product_name)
            else:
                print(f"  未找到匹配的产品代码，跳过")

        return {
            "success": True,
            "updated_products": updated_products,
            "total_records": len(holdings_data)
        }

    except Exception as e:
        pass
        return {"error": f"数据库更新失败: {str(e)}"}


def update_holdings_from_source(db, data_source="实盘", target_time="150000"):
    """从指定数据源更新所有日期的持仓数据"""
    try:
        # 获取所有日期的文件列表
        file_result = get_all_holdings_files(data_source, target_time)

        if "error" in file_result:
            return file_result

        date_files = file_result.get("date_files", {})
        if not date_files:
            return {
                "error": f"未找到{data_source}的{target_time}时间持仓文件",
                "debug_info": file_result.get("debug_info", {})
            }

        # 按日期处理
        updated_dates = []
        failed_dates = []
        total_updated_products = set()

        for date_str, files in date_files.items():
            try:
                # 读取该日期的所有文件
                date_holdings = []

                for file_path in files:
                    read_result = read_holdings_file(file_path)
                    if "error" not in read_result:
                        date_holdings.append(read_result["data"])

                if date_holdings:
                    # 合并该日期的所有持仓数据
                    combined_holdings = pd.concat(date_holdings, ignore_index=True)

                    # 更新到数据库
                    update_result = update_holdings_to_database(db, combined_holdings, date_str)

                    if update_result.get("success"):
                        updated_dates.append(date_str)
                        total_updated_products.update(update_result.get("updated_products", []))
                    else:
                        failed_dates.append({"date": date_str, "error": update_result.get("error")})
                else:
                    failed_dates.append({"date": date_str, "error": "所有文件读取失败"})

            except Exception as e:
                failed_dates.append({"date": date_str, "error": str(e)})

        return {
            "success": True,
            "updated_dates": updated_dates,
            "failed_dates": failed_dates,
            "data_source": data_source,
            "total_updated_products": list(total_updated_products),
            "debug_info": file_result.get("debug_info", {})
        }

    except Exception as e:
        return {"error": f"批量更新持仓数据失败: {str(e)}"}


def render_holdings_update_section(db):
    """渲染数据更新UI组件"""
    st.subheader("📊 数据更新")

    # 创建两列：持仓更新 | 净值更新
    col_holdings, col_nav = st.columns(2)

    # 持仓更新列
    with col_holdings:
        st.write("**📋 持仓数据更新**")

        data_source = st.selectbox(
            "数据源",
            options=["实盘", "仿真"],
            key="holdings_update_source"
        )

        if st.button("🔄 更新持仓", type="primary", use_container_width=True):
            with st.spinner(f"正在从{data_source}更新持仓数据..."):
                result = update_holdings_from_source(db, data_source)

                if result.get("success"):
                    st.success(f"✅ 更新成功！")
                    if result.get("updated_dates"):
                        st.info(f"📅 更新日期: {len(result['updated_dates'])}天")
                    if result.get("total_updated_products"):
                        st.info(f"📊 更新产品: {', '.join(result['total_updated_products'])}")
                else:
                    st.error(f"❌ 更新失败: {result.get('error', '未知错误')}")

        # 持仓更新说明
        st.caption("📂 从交易数据定频导出读取15:00持仓")

        # 自动更新状态
        current_time = datetime.now()
        if current_time.hour == 15 and current_time.minute >= 5:
            st.info("📅 今日已过自动更新时间(15:05)")
        else:
            st.info("📅 每日15:05自动更新")

    # 净值更新列
    with col_nav:
        st.write("**📈 净值数据更新**")

        # 占位，保持与持仓列对齐
        st.write("")  # 占位替代selectbox的空间

        if st.button("📈 更新净值", type="primary", use_container_width=True):
            with st.spinner("正在从账户资产文件更新净值数据..."):
                # 读取净值数据
                nav_result = update_nav_from_excel()

                if nav_result.get("success"):
                    # 更新到数据库
                    update_result = update_nav_to_database(db, nav_result["nav_data"])

                    if update_result.get("success"):
                        st.success(f"✅ 净值更新成功！")
                        st.info(f"📊 更新产品: {', '.join(update_result['updated_products'])}")
                        st.info(f"📄 处理Sheet: {update_result['total_sheets']}个")
                    else:
                        st.error(f"❌ 净值更新失败: {update_result.get('error')}")
                else:
                    st.error(f"❌ 读取净值文件失败: {nav_result.get('error')}")

        # 净值更新说明
        st.caption("📄 从账户资产.xlsx读取净值数据")
        st.caption("🔍 自动匹配产品名称和k-前缀")


def read_nav_excel_file(file_path):
    """读取账户资产Excel文件，返回所有sheet的净值数据"""
    try:
        import pandas as pd

        # 读取所有sheet
        all_sheets = pd.read_excel(file_path, sheet_name=None)

        nav_data_by_product = {}

        for sheet_name, df in all_sheets.items():
            if df.empty:
                continue

            # 查找净值列
            nav_col = None
            for col in df.columns:
                if '净值' in str(col) or 'NAV' in str(col).upper() or '单位净值' in str(col):
                    nav_col = col
                    break

            if nav_col is None:
                continue

            # 第一列作为日期列
            date_col = df.columns[0]

            # 提取数据
            result_df = df[[date_col, nav_col]].copy()
            result_df.columns = ['date', 'nav_value']

            # 数据清理
            result_df = result_df.dropna(subset=['date', 'nav_value'])
            result_df['nav_value'] = pd.to_numeric(result_df['nav_value'], errors='coerce')
            result_df = result_df.dropna(subset=['nav_value'])

            # ✅ 新增：只保留净值大于0的数据
            result_df = result_df[result_df['nav_value'] > 0]

            # 日期格式处理
            try:
                result_df['date'] = pd.to_datetime(result_df['date']).dt.strftime('%Y-%m-%d')
            except:
                continue

            # ✅ 新增：按日期排序，确保数据的连续性
            result_df = result_df.sort_values('date')

            # ✅ 新增：只保留到昨天为止的数据
            from datetime import datetime, timedelta
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            result_df = result_df[result_df['date'] <= yesterday]

            if not result_df.empty:
                nav_data_by_product[sheet_name] = result_df

        return {"success": True, "data": nav_data_by_product}

    except Exception as e:
        return {"error": f"读取净值文件失败: {str(e)}"}


def update_nav_to_database(db, nav_data_dict):
    """将净值数据更新到数据库"""
    try:
        updated_products = []

        # 获取数据库中的产品列表
        db_products = db.get_products()
        db_product_names = {p['product_name']: p['product_code'] for p in db_products}

        for sheet_name, nav_df in nav_data_dict.items():
            # 尝试匹配产品名称
            product_code = None

            # 1. 精确匹配
            if sheet_name in db_product_names:
                product_code = db_product_names[sheet_name]
            else:
                # 2. 去除空格的匹配
                for db_name, db_code in db_product_names.items():
                    if sheet_name.strip() == db_name.strip():
                        product_code = db_code
                        break

                # 3. 处理 "k-XXXX" 格式的匹配
                if product_code is None and sheet_name.startswith('k-'):
                    # 提取k-后面的部分
                    name_part = sheet_name[2:].strip()  # 去掉"k-"前缀

                    for db_name, db_code in db_product_names.items():
                        # 检查数据库中的产品名是否包含这个名称部分
                        if name_part in db_name or db_name in name_part:
                            product_code = db_code
                            break

                # 4. 更宽松的包含匹配
                if product_code is None:
                    for db_name, db_code in db_product_names.items():
                        # 互相包含的匹配
                        if (sheet_name.lower().strip() in db_name.lower().strip() or
                                db_name.lower().strip() in sheet_name.lower().strip()):
                            product_code = db_code
                            break

            if product_code:
                # 添加累计净值列（设为与单位净值相同）
                nav_df['cumulative_nav'] = nav_df['nav_value']

                # 更新到数据库
                success = db.add_nav_data(product_code, nav_df)
                if success:
                    updated_products.append(f"{sheet_name} → {product_code}")
            else:
                # 记录未匹配的sheet
                print(f"未匹配的Sheet: {sheet_name}")

        return {
            "success": True,
            "updated_products": updated_products,
            "total_sheets": len(nav_data_dict)
        }

    except Exception as e:
        return {"error": f"净值数据库更新失败: {str(e)}"}


def update_nav_from_excel():
    """从账户资产Excel文件更新净值数据"""
    file_path = r"C:\shared_data\账户资产.xlsx"

    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    # 读取Excel文件
    read_result = read_nav_excel_file(file_path)

    if "error" in read_result:
        return read_result

    nav_data = read_result["data"]
    if not nav_data:
        return {"error": "未找到有效的净值数据"}

    return {
        "success": True,
        "nav_data": nav_data,
        "total_sheets": len(nav_data)
    }


