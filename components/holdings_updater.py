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
    """渲染持仓更新UI组件"""
    st.subheader("📊 持仓数据更新")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        data_source = st.selectbox("数据源", options=["实盘", "仿真"], key="holdings_update_source")

    with col2:
        if st.button("🔄 手动更新持仓", type="primary"):
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

                if result.get("success"):
                    st.success(f"✅ 更新成功！")
                    if result.get("updated_products"):
                        st.write(f"更新的产品: {result['updated_products']}")
                else:
                    st.error(f"❌ 更新失败: {result.get('error', '未知错误')}")

    with col3:
        # 显示自动更新状态
        current_time = datetime.now()
        if current_time.hour == 15 and current_time.minute >= 5:
            st.info("📅 今日已过自动更新时间(15:05)")
        else:
            st.info("📅 每日15:05自动更新持仓数据")


