"""
期货数据读取模块
创建新文件: components/futures_data_reader.py
"""
import os
import glob
import pandas as pd
from datetime import datetime
import streamlit as st


class FuturesDataReader:
    def __init__(self):
        self.futures_path = r"C:\shared_data\期货"
        self.stocks_path = r"C:\shared_data\实盘\交易数据定频导出"

    def get_futures_files_by_time(self, target_time="153000"):
        """
        获取指定时间的期货文件
        target_time: "113000" 或 "153000"
        """
        if not os.path.exists(self.futures_path):
            return []

        files = glob.glob(os.path.join(self.futures_path, "期货资产导出_*.xls"))
        target_files = []

        for file in files:
            filename = os.path.basename(file)
            # 解析文件名: 期货资产导出_20250701-150000.xls
            try:
                time_part = filename.replace('期货资产导出_', '').replace('.xls', '')
                date_str, time_str = time_part.split('-')

                if time_str.startswith("1130") if target_time == "113000" else time_str.startswith("15"):  # 匹配小时和分钟
                    target_files.append({
                        'file_path': file,
                        'date': date_str,
                        'time': time_str,
                        'datetime': datetime.strptime(time_part, '%Y%m%d-%H%M%S')
                    })
            except:
                continue

        return sorted(target_files, key=lambda x: x['datetime'], reverse=True)

    def read_futures_file(self, file_path):
        """读取期货文件"""
        try:
            # 读取Sheet1 - 主要数据
            df_main = pd.read_excel(file_path, sheet_name=0)

            # 读取Sheet2 - 基准收益率数据
            try:
                df_benchmark = pd.read_excel(file_path, sheet_name=1)
            except:
                df_benchmark = None

            return df_main, df_benchmark
        except Exception as e:
            st.error(f"读取期货文件失败 {file_path}: {e}")
            return None, None

    def get_benchmark_return(self, df_benchmark, benchmark_name="中证1000当日收益率"):
        """从基准数据中提取收益率"""
        if df_benchmark is None:
            return 0.0

        try:
            # 在第一列中查找基准名称
            first_col = df_benchmark.columns[0]
            mask = df_benchmark[first_col].astype(str).str.contains(benchmark_name, na=False)

            if mask.any():
                # 找到对应行，取第二列的值
                second_col = df_benchmark.columns[1]
                benchmark_value = df_benchmark.loc[mask, second_col].iloc[0]

                if pd.notna(benchmark_value):
                    # 转换为百分比数值（如果是小数形式需要*100）
                    value = float(benchmark_value)

                    # 如果数值在-1到1之间，可能是小数形式，转换为百分比
                    if -1 <= value <= 1:
                        return value * 100  # 转换为百分比
                    else:
                        return value  # 已经是百分比形式

            return 0.0
        except Exception as e:
            print(f"获取基准收益率失败: {e}")
            return 0.0

    def get_stocks_files_by_time(self, target_time="153000"):
        """获取指定时间的股票资产文件"""
        if not os.path.exists(self.stocks_path):
            return []

        all_files = []
        # 获取所有日期文件夹
        date_folders = [f for f in os.listdir(self.stocks_path)
                        if f.isdigit() and len(f) == 8 and os.path.isdir(os.path.join(self.stocks_path, f))]

        for date_folder in sorted(date_folders, reverse=True)[:5]:  # 最近5天
            folder_path = os.path.join(self.stocks_path, date_folder)

            # 递归查找资产文件
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.startswith("单元资产账户资产导出") and file.endswith('.xlsx'):
                        file_path = os.path.join(root, file)

                        try:
                            # 解析时间
                            time_part = file.replace('单元资产账户资产导出_', '').replace('.xlsx', '')
                            time_str = time_part.split('-')[-1]

                            if time_str.startswith("1130") if target_time == "113000" else time_str.startswith("15"):
                                all_files.append({
                                    'file_path': file_path,
                                    'date': date_folder,
                                    'time': time_str,
                                    'datetime': datetime.strptime(f"{date_folder}-{time_str}", '%Y%m%d-%H%M%S')
                                })
                        except:
                            continue

        return sorted(all_files, key=lambda x: x['datetime'], reverse=True)

    def read_stocks_asset_file(self, file_path):
        """读取股票资产文件"""
        try:
            df = pd.read_excel(file_path)

            # 查找必要的列
            # 查找必要的列 - 修复重复映射问题
            column_mapping = {}
            for col in df.columns:
                if '单元名称' in col and 'unit_name' not in column_mapping.values():
                    column_mapping[col] = 'unit_name'
                elif col == '总资产' and 'total_asset' not in column_mapping.values():  # 精确匹配，避免"昨日总资产"
                    column_mapping[col] = 'total_asset'
                elif col == 'A股资产' and 'stock_asset' not in column_mapping.values():  # 精确匹配，避免占比
                    column_mapping[col] = 'stock_asset'
                elif col == '债券资产' and 'bond_asset' not in column_mapping.values():  # 精确匹配，避免占比
                    column_mapping[col] = 'bond_asset'

            df = df.rename(columns=column_mapping)


            # 数据清理
            if 'unit_name' in df.columns:

                df['unit_name'] = df['unit_name'].astype(str)

                # 这里可能出错
                df = df.dropna(subset=['unit_name'], how='any')

                df = df[df['unit_name'].notna()]

                df = df[df['unit_name'] != '']

                # 数值列转换
                numeric_cols = ['total_asset', 'stock_asset', 'bond_asset']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        df[col] = df[col].fillna(0)


                return df

            return pd.DataFrame()

        except Exception as e:
            st.error(f"**调试ERROR - 读取股票资产文件失败:** {e}")
            import traceback
            st.code(traceback.format_exc())
            return pd.DataFrame()

    def get_latest_data_by_units(self, target_times=["113000", "150000"]):
        """按单元名称获取最新的综合数据 - 支持多个时间点"""
        all_units_data = {}

        # 处理每个时间点
        for target_time in target_times:
            # 获取期货数据
            futures_files = self.get_futures_files_by_time(target_time)
            stocks_files = self.get_stocks_files_by_time(target_time)

            if not futures_files and not stocks_files:
                continue

            units_data = {}

            # 处理期货数据
            if futures_files:
                latest_futures = futures_files[0]
                df_futures, df_benchmark = self.read_futures_file(latest_futures['file_path'])

                if df_futures is not None:
                    # 获取基准收益率
                    benchmark_return = self.get_benchmark_return(df_benchmark)

                    # 处理期货数据
                    for _, row in df_futures.iterrows():
                        unit_name = str(row.get('单元名称', ''))
                        if unit_name and unit_name != '':
                            if unit_name not in units_data:
                                units_data[unit_name] = {
                                    'date': latest_futures['date'],
                                    'time': latest_futures['time'],
                                    'update_time': target_time
                                }

                            units_data[unit_name].update({
                                'futures_total_asset': float(row.get('客户权益', 0)),
                                'futures_market_value': float(row.get('期货市值', 0)),
                                'benchmark_return_rate': benchmark_return
                            })

            # 处理股票资产数据
            if stocks_files:
                latest_stocks = stocks_files[0]
                df_stocks = self.read_stocks_asset_file(latest_stocks['file_path'])

                if not df_stocks.empty:
                    for _, row in df_stocks.iterrows():
                        unit_name = str(row.get('unit_name', ''))
                        if unit_name and unit_name != '':
                            if unit_name not in units_data:
                                units_data[unit_name] = {
                                    'date': latest_stocks['date'],
                                    'time': latest_stocks['time'],
                                    'update_time': target_time
                                }

                            units_data[unit_name].update({
                                'equity_total_asset': float(row.get('total_asset', 0)),
                                'stock_market_value': float(row.get('stock_asset', 0)),
                                'bond_market_value': float(row.get('bond_asset', 0)),
                            })

            # 计算衍生字段
            for unit_name, data in units_data.items():
                # 总市值 = 股票市值 + 转债市值
                data['total_market_value'] = data.get('stock_market_value', 0) + data.get('bond_market_value', 0)

                # 资产汇总 = 现货总资产 + 期货总资产
                data['asset_summary'] = data.get('equity_total_asset', 0) + data.get('futures_total_asset', 0)

                # 为每个时间点的数据添加时间标识
                data['update_time'] = target_time

                # 如果该单元已存在，更新或添加新时间点的数据
                if unit_name not in all_units_data:
                    all_units_data[unit_name] = {}

                all_units_data[unit_name][target_time] = data

        return all_units_data