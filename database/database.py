"""
数据库管理模块
"""
import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import os


class DatabaseManager:
    def __init__(self, db_path: str = "fund_data.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使查询结果可以通过列名访问
        return conn

    def init_database(self):
        """初始化数据库表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 产品表 (已存在，不变)
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS products
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           product_code
                           TEXT
                           UNIQUE
                           NOT
                           NULL,
                           product_name
                           TEXT
                           NOT
                           NULL,
                           description
                           TEXT,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        # 净值表 (已存在，不变)
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS nav_data
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           product_code
                           TEXT
                           NOT
                           NULL,
                           date
                           DATE
                           NOT
                           NULL,
                           nav_value
                           REAL
                           NOT
                           NULL,
                           cumulative_nav
                           REAL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           product_code
                       ) REFERENCES products
                       (
                           product_code
                       ),
                           UNIQUE
                       (
                           product_code,
                           date
                       )
                           )
                       ''')

        # 持仓表 (已存在，不变)
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS holdings
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           product_code
                           TEXT
                           NOT
                           NULL,
                           date
                           DATE
                           NOT
                           NULL,
                           stock_code
                           TEXT
                           NOT
                           NULL,
                           stock_name
                           TEXT,
                           position_ratio
                           REAL,
                           market_value
                           REAL,
                           shares
                           REAL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           product_code
                       ) REFERENCES products
                       (
                           product_code
                       ),
                           UNIQUE
                       (
                           product_code,
                           date,
                           stock_code
                       )
                           )
                       ''')

        # 指数成分股表 (已存在，不变)
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS index_components
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           index_code
                           TEXT
                           NOT
                           NULL,
                           index_name
                           TEXT
                           NOT
                           NULL,
                           stock_code
                           TEXT
                           NOT
                           NULL,
                           stock_name
                           TEXT,
                           weight
                           REAL,
                           date
                           DATE
                           NOT
                           NULL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           index_code,
                           stock_code,
                           date
                       )
                           )
                       ''')

        # 行业表 (已存在，不变)
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS industry_components
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           industry_name
                           TEXT
                           NOT
                           NULL,
                           stock_code
                           TEXT
                           NOT
                           NULL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           industry_name,
                           stock_code
                       )
                           )
                       ''')

        # ✅ 新增：每日交易统计表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS daily_trading_stats
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           unit_name
                           TEXT
                           NOT
                           NULL,
                           date
                           DATE
                           NOT
                           NULL,
                           equity_total_asset
                           REAL,       -- 现货总资产
                           total_market_value
                           REAL,       -- 总市值
                           bond_market_value
                           REAL,       -- 转债市值
                           stock_market_value
                           REAL,       -- 股票市值
                           equity_return_rate
                           REAL,       -- 现货收益率
                           benchmark
                           TEXT
                           DEFAULT
                           '中证1000', -- 基准
                           benchmark_return_rate
                           REAL,       -- 基准收益率
                           equity_excess_return
                           REAL,       -- 现货超额
                           futures_total_asset
                           REAL,       -- 期货总资产
                           futures_position
                           REAL,       -- 期货仓位
                           futures_market_value
                           REAL,       -- 期货市值
                           asset_summary
                           REAL,       -- 资产汇总
                           asset_return_rate
                           REAL,       -- 资产收益率
                           nav_value
                           REAL,       -- 净值
                           update_time
                           TEXT,       -- 更新时间(113000或153000)
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           unit_name,
                           date,
                           update_time
                       )
                           )
                       ''')

        # 出入金记录表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS cash_flows
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           unit_name
                           TEXT
                           NOT
                           NULL,
                           date
                           DATE
                           NOT
                           NULL,
                           flow_type
                           TEXT
                           NOT
                           NULL, -- 'inflow' 或 'outflow'
                           amount
                           REAL
                           NOT
                           NULL,
                           note
                           TEXT,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           unit_name,
                           date,
                           flow_type
                       )
                           )
                       ''')

        # 创建索引提高查询性能 (包括原有的和新增的)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nav_product_date ON nav_data(product_code, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_holdings_product_date ON holdings(product_code, date)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_index_components ON index_components(index_code, stock_code, date)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_industry_components ON industry_components(industry_name, stock_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_cash_flows_unit_date ON cash_flows(unit_name, date)')

        # ✅ 新增：交易统计表索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trading_stats_unit_date ON daily_trading_stats(unit_name, date)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_trading_stats_update_time ON daily_trading_stats(unit_name, date, update_time)')

        conn.commit()
        conn.close()

        print("✅ 数据库初始化完成")

    def add_product(self, product_code: str, product_name: str, description: str = None) -> bool:
        """添加产品"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO products (product_code, product_name, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (product_code, product_name, description))
            conn.commit()
            print(f"✅ 产品添加成功: {product_name} ({product_code})")
            return True
        except Exception as e:
            print(f"❌ 添加产品失败: {e}")
            return False
        finally:
            conn.close()

    def get_products(self) -> List[Dict]:
        """获取所有产品"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products ORDER BY product_name')
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products

    def add_nav_data(self, product_code: str, nav_df: pd.DataFrame) -> bool:
        """批量添加净值数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 删除该产品的旧数据
            cursor.execute('DELETE FROM nav_data WHERE product_code = ?', (product_code,))

            # 插入新数据，使用INSERT OR REPLACE避免唯一约束冲突
            for _, row in nav_df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO nav_data (product_code, date, nav_value, cumulative_nav)
                    VALUES (?, ?, ?, ?)
                ''', (product_code, row['date'], row['nav_value'],
                     row.get('cumulative_nav', None)))

            conn.commit()
            print(f"✅ 净值数据添加成功: {len(nav_df)} 条记录")
            return True
        except Exception as e:
            print(f"❌ 添加净值数据失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_nav_data(self, product_code: str) -> pd.DataFrame:
        """获取净值数据"""
        conn = self.get_connection()
        query = '''
            SELECT date, nav_value, cumulative_nav 
            FROM nav_data 
            WHERE product_code = ? 
            ORDER BY date
        '''
        df = pd.read_sql(query, conn, params=[product_code])
        conn.close()
        return df

    def add_holdings_data(self, product_code: str, holdings_df: pd.DataFrame) -> bool:
        """批量添加持仓数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 获取即将导入的日期范围
            import_dates = holdings_df['date'].unique()

            # 只删除即将导入的日期的数据
            for date in import_dates:
                cursor.execute('DELETE FROM holdings WHERE product_code = ? AND date = ?', (product_code, date))

            # 插入新数据（使用INSERT OR REPLACE确保无冲突）
            for _, row in holdings_df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO holdings (product_code, date, stock_code, stock_name, 
                                        position_ratio, market_value, shares)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (product_code, row['date'], row['stock_code'],
                      row.get('stock_name', ''), row.get('position_ratio', None),
                      row.get('market_value', None), row.get('shares', None)))

            conn.commit()
            print(f"✅ 持仓数据添加成功: {len(holdings_df)} 条记录，涉及日期: {list(import_dates)}")
            return True
        except Exception as e:
            print(f"❌ 添加持仓数据失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_holdings_by_date(self, product_code: str, date: str) -> pd.DataFrame:
        """获取指定日期的持仓数据"""
        conn = self.get_connection()
        query = '''
            SELECT stock_code, stock_name, position_ratio, market_value, shares
            FROM holdings 
            WHERE product_code = ? AND date = ?
            ORDER BY position_ratio DESC
        '''
        df = pd.read_sql(query, conn, params=[product_code, date])
        conn.close()
        return df

    def delete_product(self, product_code: str) -> bool:
        """删除产品及其所有相关数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 删除产品的所有持仓数据
            cursor.execute('DELETE FROM holdings WHERE product_code = ?', (product_code,))
            holdings_deleted = cursor.rowcount

            # 删除产品的所有净值数据
            cursor.execute('DELETE FROM nav_data WHERE product_code = ?', (product_code,))
            nav_deleted = cursor.rowcount

            # 删除产品本身
            cursor.execute('DELETE FROM products WHERE product_code = ?', (product_code,))
            product_deleted = cursor.rowcount

            conn.commit()

            if product_deleted > 0:
                print(f"✅ 产品删除成功: {product_code}")
                print(f"   - 删除净值记录: {nav_deleted} 条")
                print(f"   - 删除持仓记录: {holdings_deleted} 条")
                return True
            else:
                print(f"❌ 产品不存在: {product_code}")
                return False

        except Exception as e:
            print(f"❌ 删除产品失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_product_nav_data(self, product_code: str) -> bool:
        """删除产品的净值数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM nav_data WHERE product_code = ?', (product_code,))
            deleted_count = cursor.rowcount
            conn.commit()

            print(f"✅ 净值数据删除成功: {deleted_count} 条记录")
            return True
        except Exception as e:
            print(f"❌ 删除净值数据失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_product_holdings_data(self, product_code: str) -> bool:
        """删除产品的持仓数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM holdings WHERE product_code = ?', (product_code,))
            deleted_count = cursor.rowcount
            conn.commit()

            print(f"✅ 持仓数据删除成功: {deleted_count} 条记录")
            return True
        except Exception as e:
            print(f"❌ 删除持仓数据失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_product_data_summary(self, product_code: str) -> dict:
        """获取产品数据概要"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取净值数据统计
        cursor.execute('SELECT COUNT(*) FROM nav_data WHERE product_code = ?', (product_code,))
        nav_count = cursor.fetchone()[0]

        # 获取持仓数据统计
        cursor.execute('SELECT COUNT(*) FROM holdings WHERE product_code = ?', (product_code,))
        holdings_count = cursor.fetchone()[0]

        # 获取持仓日期数
        cursor.execute('SELECT COUNT(DISTINCT date) FROM holdings WHERE product_code = ?', (product_code,))
        holdings_dates = cursor.fetchone()[0]

        conn.close()

        return {
            'nav_records': nav_count,
            'holdings_records': holdings_count,
            'holdings_dates': holdings_dates
        }

    def get_available_dates(self, product_code: str) -> List[str]:
        """获取产品的所有可用日期"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT date FROM holdings 
            WHERE product_code = ? 
            ORDER BY date DESC
        ''', (product_code,))
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        return dates

    def add_index_components(self, index_code: str, index_name: str, date: str, components_df: pd.DataFrame) -> bool:
        """添加指数成分股数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 删除该指数该日期的旧数据
            cursor.execute('DELETE FROM index_components WHERE index_code = ? AND date = ?', (index_code, date))

            # 插入新数据
            for _, row in components_df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO index_components (index_code, index_name, stock_code, stock_name, weight, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (index_code, index_name, row['stock_code'],
                     row.get('stock_name', ''), row.get('weight', None), date))

            conn.commit()
            print(f"✅ 指数成分股添加成功: {index_name} {date} {len(components_df)} 只股票")
            return True
        except Exception as e:
            print(f"❌ 添加指数成分股失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_index_components_by_date(self, index_code: str, target_date: str) -> pd.DataFrame:
        """获取指定日期的指数成分股（找最接近日期）"""
        conn = self.get_connection()

        print(f"Debug: 查询指数 {index_code}, 目标日期 {target_date}")

        # 先找最接近的日期
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT date, ABS(julianday(date) - julianday(?)) as date_diff
                       FROM index_components
                       WHERE index_code = ?
                       ORDER BY date_diff ASC
                           LIMIT 1
                       ''', (target_date, index_code))

        closest_date_result = cursor.fetchone()

        if closest_date_result is None:
            print(f"Debug: 没找到指数 {index_code} 的任何数据")
            conn.close()
            return pd.DataFrame()

        closest_date = closest_date_result[0]
        print(f"Debug: 最接近的日期: {closest_date}")

        # 获取该日期的所有成分股
        query = '''
                SELECT stock_code, stock_name, weight, date
                FROM index_components
                WHERE index_code = ? AND date = ?
                ORDER BY weight DESC \
                '''
        df = pd.read_sql(query, conn, params=[index_code, closest_date])

        print(f"Debug: 查询结果数量: {len(df)}")

        conn.close()
        return df

    def get_all_index_components_summary(self) -> pd.DataFrame:
        """获取所有指数成分股数据概要"""
        conn = self.get_connection()
        query = '''
            SELECT index_code, index_name, date, COUNT(*) as stock_count
            FROM index_components 
            GROUP BY index_code, index_name, date
            ORDER BY index_code, date DESC
        '''
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    def add_industry_components(self, industry_df: pd.DataFrame) -> bool:
        """批量添加行业分类数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 清空旧数据（因为是批量导入所有行业）
            cursor.execute('DELETE FROM industry_components')

            # 插入新数据
            for _, row in industry_df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO industry_components (industry_name, stock_code)
                    VALUES (?, ?)
                ''', (row['industry_name'], row['stock_code']))

            conn.commit()
            print(f"✅ 行业分类数据添加成功: {len(industry_df)} 条记录")
            return True
        except Exception as e:
            print(f"❌ 添加行业分类数据失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_all_industries(self) -> list:
        """获取所有行业名称"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT industry_name FROM industry_components ORDER BY industry_name')
        industries = [row[0] for row in cursor.fetchall()]
        conn.close()
        return industries

    def get_industry_stocks(self, industry_name: str) -> list:
        """获取指定行业的所有股票代码"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT stock_code FROM industry_components WHERE industry_name = ?', (industry_name,))
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks

    """
    扩展database.py - 添加每日交易统计相关功能
    在您的database/database.py文件的DatabaseManager类中添加以下方法
    """

    def init_trading_stats_table(self):
        """初始化每日交易统计表 - 添加到__init__方法中"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 每日交易统计表
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS daily_trading_stats
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           unit_name
                           TEXT
                           NOT
                           NULL,
                           date
                           DATE
                           NOT
                           NULL,
                           equity_total_asset
                           REAL,       -- 现货总资产
                           total_market_value
                           REAL,       -- 总市值
                           bond_market_value
                           REAL,       -- 转债市值
                           stock_market_value
                           REAL,       -- 股票市值
                           equity_return_rate
                           REAL,       -- 现货收益率
                           benchmark
                           TEXT
                           DEFAULT
                           '中证1000', -- 基准
                           benchmark_return_rate
                           REAL,       -- 基准收益率
                           equity_excess_return
                           REAL,       -- 现货超额
                           futures_total_asset
                           REAL,       -- 期货总资产
                           futures_position
                           REAL,       -- 期货仓位
                           futures_market_value
                           REAL,       -- 期货市值
                           asset_summary
                           REAL,       -- 资产汇总
                           asset_return_rate
                           REAL,       -- 资产收益率
                           nav_value
                           REAL,       -- 净值
                           update_time
                           TEXT,       -- 更新时间(113000或153000)
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE
                       (
                           unit_name,
                           date,
                           update_time
                       )
                           )
                       ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trading_stats_unit_date ON daily_trading_stats(unit_name, date)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_trading_stats_update_time ON daily_trading_stats(unit_name, date, update_time)')

        conn.commit()
        conn.close()

    def add_trading_stats_record(self, unit_name: str, date: str, update_time: str, stats_data: dict) -> bool:
        """添加或更新交易统计记录 - 相同日期直接覆盖"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 先删除该单元该日期的所有记录
            cursor.execute('DELETE FROM daily_trading_stats WHERE unit_name = ? AND date = ?',
                           (unit_name, date))

            # 插入新记录 - 补全所有参数
            cursor.execute('''
                           INSERT INTO daily_trading_stats
                           (unit_name, date, update_time, equity_total_asset, total_market_value,
                            bond_market_value, stock_market_value, equity_return_rate,
                            benchmark, benchmark_return_rate, equity_excess_return,
                            futures_total_asset, futures_position, futures_market_value,
                            asset_summary, asset_return_rate, nav_value, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                           ''', (
                               unit_name,
                               date,
                               update_time,
                               float(stats_data.get('equity_total_asset', 0)),
                               float(stats_data.get('total_market_value', 0)),
                               float(stats_data.get('bond_market_value', 0)),
                               float(stats_data.get('stock_market_value', 0)),
                               float(stats_data.get('equity_return_rate', 0)),
                               stats_data.get('benchmark', '中证1000'),
                               float(stats_data.get('benchmark_return_rate', 0)),
                               float(stats_data.get('equity_excess_return', 0)),
                               float(stats_data.get('futures_total_asset', 0)),
                               float(stats_data.get('futures_position', 0)),
                               float(stats_data.get('futures_market_value', 0)),
                               float(stats_data.get('asset_summary', 0)),
                               float(stats_data.get('asset_return_rate', 0)),
                               float(stats_data.get('nav_value', 1.0))
                           ))

            conn.commit()
            return True
        except Exception as e:
            print(f"❌ 添加交易统计记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_trading_stats_by_unit(self, unit_name: str) -> pd.DataFrame:
        """获取指定单元的交易统计数据"""
        conn = self.get_connection()
        query = '''
                SELECT date as "日期", equity_total_asset as "现货总资产", total_market_value as "总市值", bond_market_value as "转债市值", stock_market_value as "股票市值", equity_return_rate as "现货收益率", benchmark as "基准", benchmark_return_rate as "基准收益率", equity_excess_return as "现货超额", futures_total_asset as "期货总资产", futures_position as "期货仓位", futures_market_value as "期货市值", asset_summary as "资产汇总", asset_return_rate as "资产收益率", nav_value as "净值"
                FROM daily_trading_stats
                WHERE unit_name = ?
                ORDER BY date DESC \
                '''
        df = pd.read_sql(query, conn, params=[unit_name])
        conn.close()
        return df

    def get_all_units(self) -> list:
        """获取所有单元名称"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT unit_name FROM daily_trading_stats ORDER BY unit_name')
        units = [row[0] for row in cursor.fetchall()]
        conn.close()
        return units

    def update_trading_stats_batch(self, df: pd.DataFrame, unit_name: str) -> bool:
        """批量更新交易统计数据 - 修复版本"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 删除该单元的旧数据
            cursor.execute('DELETE FROM daily_trading_stats WHERE unit_name = ?', (unit_name,))

            # 插入新数据
            for _, row in df.iterrows():
                # 确保日期不为空
                date_value = row.get('日期')
                if pd.isna(date_value) or str(date_value).strip() == '':
                    print(f"跳过空日期行: {row}")
                    continue

                cursor.execute('''
                               INSERT INTO daily_trading_stats
                               (unit_name, date, equity_total_asset, total_market_value,
                                bond_market_value, stock_market_value, equity_return_rate,
                                benchmark, benchmark_return_rate, equity_excess_return,
                                futures_total_asset, futures_position, futures_market_value,
                                asset_summary, asset_return_rate, nav_value, update_time)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                               ''', (
                                   unit_name,
                                   str(date_value),  # 确保日期转为字符串
                                   float(row.get('现货总资产', 0)) if pd.notna(row.get('现货总资产')) else 0.0,
                                   float(row.get('总市值', 0)) if pd.notna(row.get('总市值')) else 0.0,
                                   float(row.get('转债市值', 0)) if pd.notna(row.get('转债市值')) else 0.0,
                                   float(row.get('股票市值', 0)) if pd.notna(row.get('股票市值')) else 0.0,
                                   float(row.get('现货收益率', 0)) if pd.notna(row.get('现货收益率')) else 0.0,
                                   str(row.get('基准', '中证1000')),
                                   float(row.get('基准收益率', 0)) if pd.notna(row.get('基准收益率')) else 0.0,
                                   float(row.get('现货超额', 0)) if pd.notna(row.get('现货超额')) else 0.0,
                                   float(row.get('期货总资产', 0)) if pd.notna(row.get('期货总资产')) else 0.0,
                                   float(row.get('期货仓位', 0)) if pd.notna(row.get('期货仓位')) else 0.0,
                                   float(row.get('期货市值', 0)) if pd.notna(row.get('期货市值')) else 0.0,
                                   float(row.get('资产汇总', 0)) if pd.notna(row.get('资产汇总')) else 0.0,
                                   float(row.get('资产收益率', 0)) if pd.notna(row.get('资产收益率')) else 0.0,
                                   float(row.get('净值', 1.0)) if pd.notna(row.get('净值')) else 1.0,
                                   '153000'  # 默认更新时间
                               ))

            conn.commit()
            print(f"✅ 批量更新交易统计数据成功: {unit_name}, {len(df)} 条记录")
            return True
        except Exception as e:
            print(f"❌ 批量更新交易统计数据失败: {e}")
            import traceback
            print(traceback.format_exc())
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_latest_stats_for_unit(self, unit_name: str, date: str) -> dict:
        """获取指定单元和日期的最新统计数据"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT *
                       FROM daily_trading_stats
                       WHERE unit_name = ? AND date < ?
                       ORDER BY date DESC, update_time DESC
                           LIMIT 1
                       ''', (unit_name, date))

        result = cursor.fetchone()
        conn.close()

        if result:
            return dict(result)
        return None

    def delete_unit_data(self, unit_name: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM daily_trading_stats WHERE unit_name = ?', (unit_name,))
        conn.commit()
        conn.close()
        return True

    def add_cash_flow(self, unit_name: str, date: str, flow_type: str, amount: float, note: str = '') -> bool:
        """添加出入金记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO cash_flows (unit_name, date, flow_type, amount, note)
                VALUES (?, ?, ?, ?, ?)
            ''', (unit_name, date, flow_type, amount, note))
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ 添加出入金记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_cash_flows_by_unit(self, unit_name: str) -> pd.DataFrame:
        """获取指定单元的出入金记录"""
        conn = self.get_connection()
        query = '''
                SELECT date as "日期", flow_type as "类型", amount as "金额", note as "备注"
                FROM cash_flows
                WHERE unit_name = ?
                ORDER BY date DESC \
                '''
        df = pd.read_sql(query, conn, params=[unit_name])
        conn.close()
        return df

    def get_cash_flow_by_date(self, unit_name: str, date: str) -> float:
        """获取指定单元和日期的净流入金额（入金-出金）"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取入金总额
        cursor.execute('''
                       SELECT COALESCE(SUM(amount), 0)
                       FROM cash_flows
                       WHERE unit_name = ? AND date = ? AND flow_type = 'inflow'
                       ''', (unit_name, date))
        inflow = cursor.fetchone()[0]

        # 获取出金总额
        cursor.execute('''
                       SELECT COALESCE(SUM(amount), 0)
                       FROM cash_flows
                       WHERE unit_name = ? AND date = ? AND flow_type = 'outflow'
                       ''', (unit_name, date))
        outflow = cursor.fetchone()[0]

        conn.close()
        return inflow - outflow

    def delete_cash_flow(self, unit_name: str, date: str, flow_type: str, amount: float) -> bool:
        """删除出入金记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                           DELETE
                           FROM cash_flows
                           WHERE unit_name = ? AND date = ? AND flow_type = ? AND amount = ?
                           ''', (unit_name, date, flow_type, amount))
            conn.commit()
            return True
        except Exception as e:
            print(f"❌ 删除出入金记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_trading_stats_record(self, unit_name: str, date: str) -> bool:
        """删除指定单元和日期的交易统计记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM daily_trading_stats WHERE unit_name = ? AND date = ?',
                           (unit_name, date))
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"✅ 删除交易统计记录成功: {unit_name} {date}, 删除 {deleted_count} 条")
            return deleted_count > 0
        except Exception as e:
            print(f"❌ 删除交易统计记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_all_cash_flows(self, unit_name: str) -> bool:
        """删除指定单元的所有出入金记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM cash_flows WHERE unit_name = ?', (unit_name,))
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"✅ 删除所有出入金记录成功: {unit_name}, 删除 {deleted_count} 条")
            return deleted_count > 0
        except Exception as e:
            print(f"❌ 删除所有出入金记录失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()