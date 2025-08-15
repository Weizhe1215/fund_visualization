"""
用户管理界面组件
用于内部系统的用户和权限管理
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from database.user_management import UserManagement


def render_user_management_page(db):
    """渲染用户管理主页面"""
    st.title("👥 用户权限管理")
    st.write("管理外部用户账户和产品访问权限")

    # 初始化用户管理
    if 'user_mgmt' not in st.session_state:
        st.session_state.user_mgmt = UserManagement(db.db_path)

    user_mgmt = st.session_state.user_mgmt

    # 创建标签页
    tab1, tab2, tab3, tab4 = st.tabs(["👤 用户列表", "➕ 创建用户", "🔑 权限管理", "📊 访问日志"])

    with tab1:
        render_user_list(user_mgmt, db)

    with tab2:
        render_create_user(user_mgmt)

    with tab3:
        render_permission_management(user_mgmt, db)

    with tab4:
        render_access_logs(user_mgmt)


def render_user_list(user_mgmt, db):
    """渲染用户列表"""
    st.subheader("👤 用户列表")

    # 获取所有用户
    users = user_mgmt.get_all_users()

    if not users:
        st.info("暂无用户，请创建第一个用户")
        return

    # 转换为DataFrame
    df = pd.DataFrame(users)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    df['last_login'] = pd.to_datetime(df['last_login'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
    df['last_login'] = df['last_login'].fillna('从未登录')

    # 状态颜色映射
    def status_color(status):
        return "🟢" if status == "active" else "🔴"

    # 显示用户表格
    st.write("**用户总数:**", len(users))

    for idx, user in enumerate(users):
        with st.expander(f"{status_color(user['status'])} {user['display_name']} (@{user['username']})"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**用户ID:** {user['user_id']}")
                st.write(f"**用户名:** {user['username']}")
                st.write(f"**显示名称:** {user['display_name']}")
                st.write(f"**邮箱:** {user['email'] or '未设置'}")
                st.write(f"**手机:** {user['phone'] or '未设置'}")

            with col2:
                st.write(f"**用户类型:** {user['user_type']}")
                st.write(f"**状态:** {user['status']}")
                st.write(f"**创建时间:** {pd.to_datetime(user['created_at']).strftime('%Y-%m-%d %H:%M')}")
                st.write(
                    f"**最后登录:** {pd.to_datetime(user['last_login'], errors='coerce').strftime('%Y-%m-%d %H:%M') if user['last_login'] else '从未登录'}")

            # 获取用户权限
            permissions = user_mgmt.get_user_permissions(user['user_id'])
            if permissions:
                st.write(f"**已授权产品 ({len(permissions)}个):**")
                products = db.get_products()
                product_names = {p['product_code']: p['product_name'] for p in products}
                for perm in permissions:
                    product_name = product_names.get(perm, perm)
                    st.write(f"- {product_name} ({perm})")
            else:
                st.write("**已授权产品:** 无")

            # 操作按钮
            col_btn1, col_btn2, col_btn3 = st.columns(3)

            with col_btn1:
                new_status = "inactive" if user['status'] == "active" else "active"
                status_text = "停用" if user['status'] == "active" else "激活"
                if st.button(f"{status_text}用户", key=f"toggle_status_{user['user_id']}"):
                    result = user_mgmt.update_user_status(user['user_id'], new_status)
                    if result['success']:
                        st.success(result['message'])
                        st.rerun()
                    else:
                        st.error(result['error'])

            with col_btn2:
                if st.button("查看详情", key=f"view_detail_{user['user_id']}"):
                    st.session_state[f"show_user_detail_{user['user_id']}"] = True

            with col_btn3:
                if st.button("管理权限", key=f"manage_perm_{user['user_id']}"):
                    st.session_state['selected_user_for_permission'] = user['user_id']
                    st.rerun()


def render_create_user(user_mgmt):
    """渲染创建用户界面"""
    st.subheader("➕ 创建新用户")

    with st.form("create_user_form"):
        col1, col2 = st.columns(2)

        with col1:
            username = st.text_input("用户名*", help="登录时使用的用户名")
            display_name = st.text_input("显示名称*", help="界面显示的姓名")
            email = st.text_input("邮箱", help="可选")

        with col2:
            password = st.text_input("密码*", type="password", help="登录密码")
            confirm_password = st.text_input("确认密码*", type="password")
            phone = st.text_input("手机号", help="可选")

        user_type = st.selectbox("用户类型", ["external", "internal"],
                                 index=0, help="external: 外部用户, internal: 内部用户")

        notes = st.text_area("备注", help="可选的用户备注信息")

        submitted = st.form_submit_button("创建用户", type="primary")

        if submitted:
            # 验证必填字段
            if not all([username, password, display_name]):
                st.error("请填写所有必填字段（标记*的字段）")
                return

            # 验证密码
            if password != confirm_password:
                st.error("密码和确认密码不匹配")
                return

            if len(password) < 6:
                st.error("密码长度至少6位")
                return

            # 创建用户
            result = user_mgmt.create_user(
                username=username,
                password=password,
                display_name=display_name,
                email=email or None,
                phone=phone or None,
                user_type=user_type,
                notes=notes or None
            )

            if result['success']:
                st.success(f"✅ {result['message']}")
                st.info(f"用户ID: {result['user_id']}")
                st.rerun()
            else:
                st.error(f"❌ {result['error']}")


def render_permission_management(user_mgmt, db):
    """渲染权限管理界面"""
    st.subheader("🔑 权限管理")

    # 获取所有用户和产品
    users = user_mgmt.get_all_users()
    products = db.get_products()

    if not users:
        st.warning("请先创建用户")
        return

    if not products:
        st.warning("请先在数据导入页面添加产品")
        return

    # 用户选择
    user_options = {f"{u['display_name']} (@{u['username']})": u['user_id'] for u in users}

    # 检查是否有预选用户
    default_index = 0
    if 'selected_user_for_permission' in st.session_state:
        for i, (display, user_id) in enumerate(user_options.items()):
            if user_id == st.session_state['selected_user_for_permission']:
                default_index = i
                break
        # 清除预选状态
        del st.session_state['selected_user_for_permission']

    selected_user_display = st.selectbox(
        "选择用户",
        options=list(user_options.keys()),
        index=default_index
    )
    selected_user_id = user_options[selected_user_display]

    # 获取当前用户权限
    current_permissions = set(user_mgmt.get_user_permissions(selected_user_id))

    st.write("---")

    # 显示当前权限状态
    col1, col2 = st.columns(2)

    with col1:
        st.write("**当前已授权产品:**")
        if current_permissions:
            for product in products:
                if product['product_code'] in current_permissions:
                    st.write(f"✅ {product['product_name']} ({product['product_code']})")
        else:
            st.write("无")

    with col2:
        st.write("**可授权产品:**")
        available_products = [p for p in products if p['product_code'] not in current_permissions]
        if available_products:
            for product in available_products:
                st.write(f"⭕ {product['product_name']} ({product['product_code']})")
        else:
            st.write("无")

    st.write("---")

    # 权限操作
    tab_grant, tab_revoke = st.tabs(["授予权限", "撤销权限"])

    with tab_grant:
        if available_products:
            with st.form("grant_permission_form"):
                product_options = {f"{p['product_name']} ({p['product_code']})": p['product_code']
                                   for p in available_products}

                selected_products = st.multiselect(
                    "选择要授权的产品",
                    options=list(product_options.keys())
                )

                granted_by = st.text_input("授权人", value="系统管理员")

                if st.form_submit_button("授予权限", type="primary"):
                    if selected_products:
                        success_count = 0
                        for product_display in selected_products:
                            product_code = product_options[product_display]
                            result = user_mgmt.grant_permission(selected_user_id, product_code, granted_by)
                            if result['success']:
                                success_count += 1

                        if success_count > 0:
                            st.success(f"✅ 成功授权 {success_count} 个产品")
                            st.rerun()
        else:
            st.info("该用户已拥有所有产品的访问权限")

    with tab_revoke:
        if current_permissions:
            with st.form("revoke_permission_form"):
                revoke_options = {}
                for product in products:
                    if product['product_code'] in current_permissions:
                        revoke_options[f"{product['product_name']} ({product['product_code']})"] = product[
                            'product_code']

                selected_revoke = st.multiselect(
                    "选择要撤销的产品权限",
                    options=list(revoke_options.keys())
                )

                if st.form_submit_button("撤销权限", type="secondary"):
                    if selected_revoke:
                        success_count = 0
                        for product_display in selected_revoke:
                            product_code = revoke_options[product_display]
                            result = user_mgmt.revoke_permission(selected_user_id, product_code)
                            if result['success']:
                                success_count += 1

                        if success_count > 0:
                            st.success(f"✅ 成功撤销 {success_count} 个产品的权限")
                            st.rerun()
        else:
            st.info("该用户暂无任何产品权限")


def render_access_logs(user_mgmt):
    """渲染访问日志"""
    st.subheader("📊 访问日志")

    # 获取日志
    logs = user_mgmt.get_access_logs(limit=200)

    if not logs:
        st.info("暂无访问日志")
        return

    # 筛选选项
    col1, col2, col3 = st.columns(3)

    with col1:
        # 用户筛选
        unique_users = list(set([(log['username'], log['display_name']) for log in logs]))
        user_filter_options = ["全部用户"] + [f"{display_name} (@{username})" for username, display_name in
                                              unique_users]
        selected_user_filter = st.selectbox("筛选用户", user_filter_options)

    with col2:
        # 操作筛选
        unique_actions = list(set([log['action'] for log in logs if log['action']]))
        action_filter_options = ["全部操作"] + unique_actions
        selected_action_filter = st.selectbox("筛选操作", action_filter_options)

    with col3:
        # 显示数量
        display_limit = st.selectbox("显示数量", [50, 100, 200], index=1)

    # 应用筛选
    filtered_logs = logs[:display_limit]

    if selected_user_filter != "全部用户":
        username = selected_user_filter.split('@')[1].rstrip(')')
        filtered_logs = [log for log in filtered_logs if log['username'] == username]

    if selected_action_filter != "全部操作":
        filtered_logs = [log for log in filtered_logs if log['action'] == selected_action_filter]

    # 显示日志
    st.write(f"**显示 {len(filtered_logs)} 条日志**")

    for log in filtered_logs:
        access_time = pd.to_datetime(log['access_time']).strftime('%Y-%m-%d %H:%M:%S')

        # 操作图标
        action_icons = {
            'login': '🔐',
            'view_product': '👁️',
            'logout': '🚪'
        }
        icon = action_icons.get(log['action'], '📝')

        with st.expander(f"{icon} {access_time} - {log['display_name']} - {log['action']}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**用户:** {log['display_name']} (@{log['username']})")
                st.write(f"**操作:** {log['action']}")
                st.write(f"**时间:** {access_time}")

            with col2:
                st.write(f"**产品:** {log['product_code'] or '无'}")
                st.write(f"**IP地址:** {log['ip_address'] or '未记录'}")
                st.write(
                    f"**用户代理:** {log['user_agent'][:50] + '...' if log['user_agent'] and len(log['user_agent']) > 50 else log['user_agent'] or '未记录'}")

    # 统计信息
    if filtered_logs:
        st.write("---")
        st.write("**统计信息:**")

        col1, col2, col3 = st.columns(3)

        with col1:
            unique_users_count = len(set([log['username'] for log in filtered_logs]))
            st.metric("活跃用户", unique_users_count)

        with col2:
            login_count = len([log for log in filtered_logs if log['action'] == 'login'])
            st.metric("登录次数", login_count)

        with col3:
            view_count = len([log for log in filtered_logs if log['action'] == 'view_product'])
            st.metric("产品访问", view_count)