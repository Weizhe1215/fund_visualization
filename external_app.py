"""
外部用户应用入口
专为客户端用户设计的简化版基金净值查看系统
"""
import streamlit as st
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from database.database import DatabaseManager
from components.auth import AuthManager, render_login_page
from components.external_view import render_external_main_page


def init_external_app():
    """初始化外部应用"""
    # 移动端优化的页面配置
    st.set_page_config(
        page_title="基金净值查看系统",
        page_icon="📈",
        layout="centered",  # 使用居中布局，更适合移动端
        initial_sidebar_state="collapsed",  # 隐藏侧边栏
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': "基金净值查看系统 - 外部用户版本"
        }
    )

    # 全局样式和PWA支持
    st.markdown("""
    <!-- PWA配置 -->
    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#1f77b4">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="基金净值">
    <link rel="apple-touch-icon" sizes="180x180" href="/static/icon-180x180.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/static/icon-32x32.png">
    <link rel="icon" type="image/png" sizes="96x96" href="/static/icon-96x96.png">
    
    <style>
    /* 隐藏Streamlit默认元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 移动端优化 */
    .main > div {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* 响应式容器 */
    .block-container {
        max-width: 100%;
        padding: 1rem;
    }
    
    /* 移动端字体优化 */
    @media (max-width: 768px) {
        .block-container {
            padding: 0.5rem;
        }
        
        h1 {
            font-size: 1.8rem !important;
        }
        
        h2 {
            font-size: 1.5rem !important;
        }
        
        h3 {
            font-size: 1.3rem !important;
        }
        
        .stButton > button {
            height: 3rem;
            font-size: 1.1rem;
        }
        
        .stSelectbox > div > div {
            font-size: 1.1rem;
        }
    }
    
    /* 自定义按钮样式 */
    .stButton > button {
        border-radius: 8px;
        border: none;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* 加载动画 */
    .loading-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
    }
    
    .loading-spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #1f77b4;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    /* 错误提示样式 */
    .error-container {
        background: #fee;
        border: 1px solid #fcc;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        text-align: center;
    }
    
    /* 成功提示样式 */
    .success-container {
        background: #efe;
        border: 1px solid #cfc;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

    # 初始化数据库和认证管理器
    if 'db' not in st.session_state:
        try:
            st.session_state.db = DatabaseManager()
        except Exception as e:
            st.error(f"数据库连接失败：{str(e)}")
            st.stop()

    if 'auth_manager' not in st.session_state:
        try:
            st.session_state.auth_manager = AuthManager(st.session_state.db.db_path)
        except Exception as e:
            st.error(f"认证系统初始化失败：{str(e)}")
            st.stop()


def main():
    """主应用函数"""
    # 初始化应用
    init_external_app()

    auth_manager = st.session_state.auth_manager
    db = st.session_state.db

    # 检查会话超时
    if auth_manager.check_session_timeout():
        st.warning("⏰ 会话已超时，请重新登录")
        auth_manager.logout()

    # 主要逻辑
    if not auth_manager.is_logged_in():
        # 显示登录页面
        render_login_page(auth_manager)
    else:
        # 已登录，显示主界面
        render_authenticated_app(auth_manager, db)


def render_authenticated_app(auth_manager, db):
    """渲染已认证用户的应用界面"""
    try:
        # 只显示主要内容，移除所有额外信息
        render_external_main_page(auth_manager, db)

        # 简化的登出按钮（右上角）
        render_simple_logout_button(auth_manager)

    except Exception as e:
        st.error("系统错误，请稍后重试")
        st.exception(e)  # 开发时显示详细错误，生产环境可以移除


def render_simple_logout_button(auth_manager):
    """渲染简单的登出按钮"""
    # 使用HTML将登出按钮固定在右上角
    logout_html = """
    <style>
    .logout-container {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1000;
    }
    .logout-btn {
        background: rgba(239, 68, 68, 0.9);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        font-size: 0.8rem;
        cursor: pointer;
        backdrop-filter: blur(10px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .logout-btn:hover {
        background: rgba(239, 68, 68, 1);
    }
    </style>
    <div class="logout-container">
        <button class="logout-btn" onclick="window.location.reload()">🚪 登出</button>
    </div>
    """

    st.components.v1.html(logout_html, height=0)

    # 在侧边栏添加登出功能（作为备用）
    with st.sidebar:
        if st.button("🚪 登出", key="sidebar_logout", type="secondary"):
            auth_manager.logout()


def render_bottom_toolbar(auth_manager):
    """渲染底部工具栏"""
    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 刷新", use_container_width=True, key="refresh_main"):
            st.rerun()

    with col2:
        if st.button("🏠 首页", use_container_width=True, key="home_main"):
            # 清除产品选择，回到首页
            if 'selected_product' in st.session_state:
                st.session_state.selected_product = None
            st.rerun()

    with col3:
        if st.button("🚪 登出", use_container_width=True, key="logout_main"):
            auth_manager.logout()


def render_error_page(error_message, show_retry=True):
    """渲染错误页面"""
    st.markdown(f"""
    <div class="error-container">
        <h2>❌ 系统错误</h2>
        <p>{error_message}</p>
        {f'<button onclick="window.location.reload()">🔄 重试</button>' if show_retry else ''}
    </div>
    """, unsafe_allow_html=True)


def render_maintenance_page():
    """渲染维护页面"""
    st.markdown("""
    <div style='text-align: center; padding: 3rem 1rem;'>
        <h1>🔧 系统维护中</h1>
        <p style='font-size: 1.2rem; color: #666; line-height: 1.6;'>
            系统正在进行维护升级<br>
            预计维护时间：30分钟<br>
            给您带来的不便敬请谅解
        </p>
        <div style='margin-top: 2rem;'>
            <button onclick='window.location.reload()' 
                    style='background: #1f77b4; color: white; border: none; 
                           padding: 1rem 2rem; border-radius: 8px; font-size: 1.1rem;'>
                🔄 重新检查
            </button>
        </div>
        <div style='margin-top: 2rem; font-size: 0.9rem; color: #888;'>
            如有紧急事务，请联系管理员
        </div>
    </div>
    """, unsafe_allow_html=True)


def check_system_status():
    """检查系统状态"""
    # 这里可以添加系统健康检查逻辑
    # 例如检查数据库连接、必要文件是否存在等
    try:
        # 检查数据库连接
        db = DatabaseManager()
        products = db.get_products()
        return True, "系统正常"
    except Exception as e:
        return False, f"系统异常：{str(e)}"


def render_loading_page():
    """渲染加载页面"""
    st.markdown("""
    <div class="loading-container">
        <div style='text-align: center;'>
            <div class="loading-spinner"></div>
            <p style='margin-top: 1rem; font-size: 1.1rem;'>正在加载...</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


# 应用启动检查和错误处理
def safe_main():
    """安全的主函数，包含错误处理"""
    try:
        # 系统状态检查
        status_ok, status_msg = check_system_status()

        if not status_ok:
            render_error_page(status_msg)
            return

        # 运行主应用
        main()

    except KeyboardInterrupt:
        st.warning("应用已停止")
    except Exception as e:
        st.error("应用启动失败")
        st.exception(e)

        # 提供重启按钮
        if st.button("🔄 重新启动应用"):
            st.rerun()


if __name__ == "__main__":
    # 运行安全的主函数
    safe_main()

    # 添加应用信息（开发时使用，生产环境可以移除）
    if st.sidebar.button("ℹ️ 应用信息", key="app_info"):
        st.sidebar.write("**基金净值查看系统**")
        st.sidebar.write("版本：外部用户版 v1.0")
        st.sidebar.write("优化：移动端响应式设计")
        st.sidebar.write("更新时间：2025年")

    # PWA支持提示（可选）
    st.markdown("""
    <script>
    // 检测移动设备
    if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)) {
        // 可以在这里添加PWA安装提示逻辑
        console.log('移动设备访问');
    }
    
    // 禁用双击缩放（改善移动端体验）
    document.addEventListener('touchstart', function(event) {
        if (event.touches.length > 1) {
            event.preventDefault();
        }
    });
    
    var lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        var now = (new Date()).getTime();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, false);
    </script>
    """, unsafe_allow_html=True)