"""
用户权限管理数据库模块
扩展现有数据库，添加用户和权限管理功能
"""
import sqlite3
import hashlib
import uuid
from datetime import datetime
import pandas as pd
from typing import List, Dict, Optional


class UserManagement:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_user_tables()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_user_tables(self):
        """初始化用户相关表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                user_type TEXT DEFAULT 'external',  -- internal/external
                status TEXT DEFAULT 'active',       -- active/inactive
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                notes TEXT
            )
        ''')

        # 创建用户产品权限表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_product_permissions (
                permission_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_code TEXT NOT NULL,
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                granted_by TEXT,  -- 授权人员
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (product_code) REFERENCES products (product_code),
                UNIQUE(user_id, product_code)
            )
        ''')

        # 创建用户访问日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_access_logs (
                log_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                product_code TEXT,
                access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                action TEXT  -- login/view_product/logout
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_permissions_user_id ON user_product_permissions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_user_id ON user_access_logs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_time ON user_access_logs(access_time)')

        conn.commit()
        conn.close()

    def hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username: str, password: str, display_name: str,
                    email: str = None, phone: str = None, user_type: str = 'external',
                    notes: str = None) -> Dict:
        """创建新用户"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            user_id = str(uuid.uuid4())
            password_hash = self.hash_password(password)

            cursor.execute('''
                INSERT INTO users (user_id, username, password_hash, display_name, 
                                 email, phone, user_type, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, password_hash, display_name, email, phone, user_type, notes))

            conn.commit()
            conn.close()

            return {"success": True, "user_id": user_id, "message": "用户创建成功"}

        except sqlite3.IntegrityError:
            return {"success": False, "error": "用户名已存在"}
        except Exception as e:
            return {"success": False, "error": f"创建用户失败: {str(e)}"}

    def authenticate_user(self, username: str, password: str) -> Dict:
        """用户认证"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            password_hash = self.hash_password(password)

            cursor.execute('''
                SELECT user_id, username, display_name, user_type, status
                FROM users 
                WHERE username = ? AND password_hash = ?
            ''', (username, password_hash))

            user = cursor.fetchone()

            if user:
                if user['status'] != 'active':
                    return {"success": False, "error": "账户已被停用"}

                # 更新最后登录时间
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                ''', (user['user_id'],))

                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "user": dict(user),
                    "message": "登录成功"
                }
            else:
                conn.close()
                return {"success": False, "error": "用户名或密码错误"}

        except Exception as e:
            return {"success": False, "error": f"认证失败: {str(e)}"}

    def get_user_permissions(self, user_id: str) -> List[str]:
        """获取用户的产品权限列表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT product_code FROM user_product_permissions 
            WHERE user_id = ?
        ''', (user_id,))

        permissions = [row['product_code'] for row in cursor.fetchall()]
        conn.close()
        return permissions

    def grant_permission(self, user_id: str, product_code: str, granted_by: str) -> Dict:
        """授予用户产品权限"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            permission_id = str(uuid.uuid4())

            cursor.execute('''
                INSERT INTO user_product_permissions (permission_id, user_id, product_code, granted_by)
                VALUES (?, ?, ?, ?)
            ''', (permission_id, user_id, product_code, granted_by))

            conn.commit()
            conn.close()

            return {"success": True, "message": "权限授予成功"}

        except sqlite3.IntegrityError:
            return {"success": False, "error": "该权限已存在"}
        except Exception as e:
            return {"success": False, "error": f"授权失败: {str(e)}"}

    def revoke_permission(self, user_id: str, product_code: str) -> Dict:
        """撤销用户产品权限"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM user_product_permissions 
                WHERE user_id = ? AND product_code = ?
            ''', (user_id, product_code))

            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                return {"success": True, "message": "权限撤销成功"}
            else:
                conn.close()
                return {"success": False, "error": "权限不存在"}

        except Exception as e:
            return {"success": False, "error": f"撤销权限失败: {str(e)}"}

    def get_all_users(self) -> List[Dict]:
        """获取所有用户列表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_id, username, display_name, email, phone, 
                   user_type, status, created_at, last_login
            FROM users 
            ORDER BY created_at DESC
        ''')

        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users

    def get_user_with_permissions(self, user_id: str) -> Dict:
        """获取用户详细信息包括权限"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 获取用户基本信息
        cursor.execute('''
            SELECT * FROM users WHERE user_id = ?
        ''', (user_id,))

        user = cursor.fetchone()
        if not user:
            conn.close()
            return None

        # 获取用户权限
        cursor.execute('''
            SELECT p.product_code, p.product_name, up.granted_at, up.granted_by
            FROM user_product_permissions up
            JOIN products p ON up.product_code = p.product_code
            WHERE up.user_id = ?
        ''', (user_id,))

        permissions = [dict(row) for row in cursor.fetchall()]

        conn.close()

        user_dict = dict(user)
        user_dict['permissions'] = permissions
        return user_dict

    def update_user_status(self, user_id: str, status: str) -> Dict:
        """更新用户状态"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE users SET status = ? WHERE user_id = ?
            ''', (status, user_id))

            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                return {"success": True, "message": f"用户状态已更新为: {status}"}
            else:
                conn.close()
                return {"success": False, "error": "用户不存在"}

        except Exception as e:
            return {"success": False, "error": f"更新状态失败: {str(e)}"}

    def log_user_access(self, user_id: str, action: str, product_code: str = None,
                        ip_address: str = None, user_agent: str = None):
        """记录用户访问日志"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            log_id = str(uuid.uuid4())

            cursor.execute('''
                INSERT INTO user_access_logs (log_id, user_id, product_code, 
                                            ip_address, user_agent, action)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (log_id, user_id, product_code, ip_address, user_agent, action))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"记录访问日志失败: {e}")

    def get_access_logs(self, user_id: str = None, limit: int = 100) -> List[Dict]:
        """获取访问日志"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if user_id:
            cursor.execute('''
                SELECT l.*, u.username, u.display_name
                FROM user_access_logs l
                JOIN users u ON l.user_id = u.user_id
                WHERE l.user_id = ?
                ORDER BY l.access_time DESC
                LIMIT ?
            ''', (user_id, limit))
        else:
            cursor.execute('''
                SELECT l.*, u.username, u.display_name
                FROM user_access_logs l
                JOIN users u ON l.user_id = u.user_id
                ORDER BY l.access_time DESC
                LIMIT ?
            ''', (limit,))

        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs