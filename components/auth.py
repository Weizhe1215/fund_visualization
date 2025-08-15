"""
认证和权限控制组件
用于外部系统的用户登录和权限验证
"""
import streamlit as st
from database.user_management import UserManagement
from datetime import datetime, timedelta


class AuthManager:
    def __init__(self, db_path: str):
        self.user_mgmt = UserManagement(db_path)

    def is_logged_in(self) -> bool:
        """检查用户是否已登录"""
        return (
                'authenticated' in st.session_state and
                st.session_state.authenticated and
                'user_info' in st.session_state and
                st.session_state.user_info is not None
        )

    def get_current_user(self) -> dict:
        """获取当前登录用户信息"""
        if self.is_logged_in():
            return st.session_state.user_info
        return None

    def get_user_permissions(self) -> list:
        """获取当前用户权限"""
        if self.is_logged_in():
            user_id = st.session_state.user_info['user_id']
            return self.user_mgmt.get_user_permissions(user_id)
        return []

    def has_product_permission(self, product_code: str) -> bool:
        """检查用户是否有特定产品权限"""
        permissions = self.get_user_permissions()
        return product_code in permissions

    def login(self, username: str, password: str) -> dict:
        """用户登录"""
        result = self.user_mgmt.authenticate_user(username, password)

        if result['success']:
            # 设置session状态
            st.session_state.authenticated = True
            st.session_state.user_info = result['user']
            st.session_state.login_time = datetime.now()

            # 记录登录日志
            self.user_mgmt.log_user_access(
                user_id=result['user']['user_id'],
                action='login'
            )

        return result

    def logout(self):
        """用户登出"""
        if self.is_logged_in():
            # 记录登出日志
            self.user_mgmt.log_user_access(
                user_id=st.session_state.user_info['user_id'],
                action='logout'
            )

        # 清除session状态
        st.session_state.authenticated = False
        st.session_state.user_info = None
        if 'login_time' in st.session_state:
            del st.session_state.login_time

        st.rerun()

    def check_session_timeout(self, timeout_hours: int = 8):
        """检查会话是否超时"""
        if self.is_logged_in() and 'login_time' in st.session_state:
            login_time = st.session_state.login_time
            if datetime.now() - login_time > timedelta(hours=timeout_hours):
                self.logout()
                return True
        return False


def render_login_page(auth_manager: AuthManager):
    """渲染登录页面（移动端优化）"""
    # 移动端优化的页面配置
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem 1rem;
    }
    .login-title {
        text-align: center;
        font-size: 2rem;
        margin-bottom: 2rem;
        color: #1f77b4;
    }
    .login-form {
        background: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stTextInput > div > div > input {
        height: 3rem;
        font-size: 1.1rem;
    }
    .stButton > button {
        height: 3rem;
        font-size: 1.1rem;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

    # 检查会话超时
    if auth_manager.check_session_timeout():
        st.warning("会话已超时，请重新登录")

    # 居中容器
    st.markdown('<div class="login-container">', unsafe_allow_html=True)

    # 标题
    st.markdown('<h1 class="login-title">📈 基金净值查看系统</h1>', unsafe_allow_html=True)

    # 登录表单
    with st.container():
        st.markdown('<div class="login-form">', unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            st.markdown("### 用户登录")

            # 大字体输入框
            username = st.text_input(
                "用户名",
                placeholder="请输入用户名",
                help="请联系管理员获取账号"
            )

            password = st.text_input(
                "密码",
                type="password",
                placeholder="请输入密码"
            )

            # 登录按钮
            login_clicked = st.form_submit_button(
                "🔐 登录",
                type="primary",
                use_container_width=True
            )

            if login_clicked:
                if not username or not password:
                    st.error("请输入用户名和密码")
                else:
                    with st.spinner("登录中..."):
                        result = auth_manager.login(username, password)

                    if result['success']:
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error(f"登录失败：{result['error']}")

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # 页面底部信息
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        💡 如需账号或遇到问题，请联系管理员<br>
        🔒 系统会在8小时后自动登出
        </div>
        """,
        unsafe_allow_html=True
    )


def render_user_header(auth_manager: AuthManager):
    """渲染用户信息头部（移动端优化）"""
    if not auth_manager.is_logged_in():
        return

    user = auth_manager.get_current_user()
    permissions = auth_manager.get_user_permissions()

    # 移动端优化的头部样式
    st.markdown("""
    <style>
    .user-header {
        background: linear-gradient(90deg, #1f77b4, #17a2b8);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .user-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
    }
    .user-name {
        font-size: 1.2rem;
        font-weight: bold;
    }
    .product-count {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    </style>
    """, unsafe_allow_html=True)

    # 用户信息栏
    col1, col2, col3 = st.columns([3, 2, 1])

    with col1:
        st.markdown(f"**👤 {user['display_name']}**")
        st.caption(f"可访问 {len(permissions)} 个产品")

    with col2:
        login_time = st.session_state.get('login_time')
        if login_time:
            st.caption(f"登录时间: {login_time.strftime('%H:%M')}")

    with col3:
        if st.button("🚪 登出", key="logout_btn"):
            auth_manager.logout()


def require_auth(auth_manager: AuthManager):
    """装饰器：要求用户认证"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not auth_manager.is_logged_in():
                render_login_page(auth_manager)
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_product_permission(auth_manager: AuthManager, product_code: str):
    """装饰器：要求特定产品权限"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not auth_manager.has_product_permission(product_code):
                st.error("❌ 您没有访问此产品的权限")
                return None

            # 记录产品访问日志
            user = auth_manager.get_current_user()
            if user:
                auth_manager.user_mgmt.log_user_access(
                    user_id=user['user_id'],
                    action='view_product',
                    product_code=product_code
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def render_permission_error():
    """渲染权限错误页面"""
    st.markdown("""
    <div style='text-align: center; padding: 3rem 1rem;'>
        <h2>🚫 访问受限</h2>
        <p style='font-size: 1.1rem; color: #666;'>
            您没有访问此功能的权限<br>
            请联系管理员开通相关权限
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_mobile_navigation(auth_manager: AuthManager):
    """渲染移动端导航（底部导航栏风格）"""
    if not auth_manager.is_logged_in():
        return

    permissions = auth_manager.get_user_permissions()

    st.markdown("""
    <style>
    .mobile-nav {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        border-top: 1px solid #ddd;
        padding: 0.5rem;
        z-index: 1000;
    }
    .nav-item {
        text-align: center;
        padding: 0.5rem;
        border-radius: 8px;
        cursor: pointer;
    }
    .nav-item:hover {
        background: #f0f0f0;
    }
    .nav-item.active {
        background: #1f77b4;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

    # 产品快速切换
    if len(permissions) > 1:
        st.markdown("### 📊 选择产品")

        # 获取产品信息
        from database.database import DatabaseManager
        db = DatabaseManager()
        products = db.get_products()

        # 筛选用户有权限的产品
        user_products = [p for p in products if p['product_code'] in permissions]

        # 产品选择器（移动端友好）
        if user_products:
            product_options = {f"{p['product_name']}": p['product_code'] for p in user_products}

            cols = st.columns(min(len(user_products), 3))
            for i, (name, code) in enumerate(product_options.items()):
                with cols[i % 3]:
                    if st.button(
                            f"📈 {name}",
                            key=f"nav_product_{code}",
                            use_container_width=True
                    ):
                        st.session_state['selected_product'] = code
                        st.rerun()


def get_client_info():
    """获取客户端信息（用于日志记录）"""
    # 这里可以扩展获取更多客户端信息
    return {
        'ip_address': st.session_state.get('client_ip', 'unknown'),
        'user_agent': st.session_state.get('user_agent', 'unknown')
    }