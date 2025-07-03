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

        # 产品表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT UNIQUE NOT NULL,
                product_name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 净值表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nav_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                date DATE NOT NULL,
                nav_value REAL NOT NULL,
                cumulative_nav REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_code) REFERENCES products (product_code),
                UNIQUE(product_code, date)
            )
        ''')

        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL,
                date DATE NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                position_ratio REAL,
                market_value REAL,
                shares REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_code) REFERENCES products (product_code),
                UNIQUE(product_code, date, stock_code)
            )
        ''')

        # 指数成分股表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS index_components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                index_name TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                weight REAL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(index_code, stock_code, date)
            )
        ''')

        # 在 init_database 方法中，添加行业表（在指数成分股表后面）
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




        # 创建索引提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nav_product_date ON nav_data(product_code, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_holdings_product_date ON holdings(product_code, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_index_components ON index_components(index_code, stock_code, date)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_industry_components ON industry_components(industry_name, stock_code)')

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