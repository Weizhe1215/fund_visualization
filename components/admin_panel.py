"""
管理员面板组件
用于内部系统集成用户管理功能
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from components.user_management import render_user_management_page
from database.user_management import UserManagement
import plotly.express as px
import plotly.graph_objects as go


def render_admin_panel_page(db):
    """渲染管理员面板主页面"""
    st.title("⚙️ 系统管理面板")
    st.write("管理用户权限和系统监控")

    # 初始化用户管理
    if 'user_mgmt' not in st.session_state:
        st.session_state.user_mgmt = UserManagement(db.db_path)

    user_mgmt = st.session_state.user_mgmt

    # 创建标签页
    tab1, tab2, tab3, tab4 = st.tabs(["📊 系统概览", "👥 用户管理", "📈 使用统计", "🔧 系统设置"])

    with tab1:
        render_system_overview(user_mgmt, db)

    with tab2:
        render_user_management_page(db)

    with tab3:
        render_usage_statistics(user_mgmt, db)

    with tab4:
        render_system_settings(user_mgmt, db)


def render_system_overview(user_mgmt, db):
    """渲染系统概览"""
    st.subheader("📊 系统概览")

    # 获取统计数据
    users = user_mgmt.get_all_users()
    products = db.get_products()
    recent_logs = user_mgmt.get_access_logs(limit=50)

    # 统计指标
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_users = len(users)
        active_users = len([u for u in users if u['status'] == 'active'])
        st.metric(
            "总用户数",
            total_users,
            delta=f"{active_users} 活跃"
        )

    with col2:
        total_products = len(products)
        # 计算有权限分配的产品数量
        all_permissions = []
        for user in users:
            permissions = user_mgmt.get_user_permissions(user['user_id'])
            all_permissions.extend(permissions)
        authorized_products = len(set(all_permissions))

        st.metric(
            "产品数量",
            total_products,
            delta=f"{authorized_products} 已授权"
        )

    with col3:
        # 今日登录次数
        today = datetime.now().date()
        today_logins = len([
            log for log in recent_logs
            if log['action'] == 'login' and
               pd.to_datetime(log['access_time']).date() == today
        ])

        st.metric("今日登录", today_logins)

    with col4:
        # 最近24小时活跃用户
        last_24h = datetime.now() - timedelta(hours=24)
        active_24h = len(set([
            log['user_id'] for log in recent_logs
            if pd.to_datetime(log['access_time']) >= last_24h
        ]))

        st.metric("24h活跃用户", active_24h)

    st.divider()

    # 权限分布饼图
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("用户状态分布")
        status_counts = {}
        for user in users:
            status = user['status']
            status_counts[status] = status_counts.get(status, 0) + 1

        if status_counts:
            fig_status = px.pie(
                values=list(status_counts.values()),
                names=list(status_counts.keys()),
                title="用户状态分布"
            )
            fig_status.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.info("暂无用户数据")

    with col2:
        st.subheader("产品权限分布")
        if products and users:
            product_permission_counts = {}
            for product in products:
                count = 0
                for user in users:
                    permissions = user_mgmt.get_user_permissions(user['user_id'])
                    if product['product_code'] in permissions:
                        count += 1
                product_permission_counts[product['product_name']] = count

            if any(product_permission_counts.values()):
                fig_products = px.bar(
                    x=list(product_permission_counts.keys()),
                    y=list(product_permission_counts.values()),
                    title="各产品授权用户数"
                )
                fig_products.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_products, use_container_width=True)
            else:
                st.info("暂无权限分配数据")
        else:
            st.info("请先添加产品和用户")

    # 最近活动
    st.subheader("最近活动")
    if recent_logs:
        # 显示最近10条日志
        recent_activities = recent_logs[:10]

        activity_data = []
        for log in recent_activities:
            activity_data.append({
                "时间": pd.to_datetime(log['access_time']).strftime('%m-%d %H:%M'),
                "用户": log['display_name'],
                "操作": get_action_text(log['action']),
                "产品": log['product_code'] or '-'
            })

        if activity_data:
            df_activity = pd.DataFrame(activity_data)
            st.dataframe(df_activity, use_container_width=True, hide_index=True)
    else:
        st.info("暂无活动记录")


def render_usage_statistics(user_mgmt, db):
    """渲染使用统计"""
    st.subheader("📈 使用统计")

    # 时间范围选择
    col1, col2 = st.columns(2)

    with col1:
        date_range = st.selectbox(
            "统计时间范围",
            ["最近7天", "最近30天", "最近90天", "全部时间"],
            index=1
        )

    with col2:
        stat_type = st.selectbox(
            "统计类型",
            ["登录统计", "产品访问", "用户活跃度"],
            index=0
        )

    # 根据时间范围获取数据
    if date_range == "全部时间":
        logs = user_mgmt.get_access_logs(limit=1000)
    else:
        days_map = {"最近7天": 7, "最近30天": 30, "最近90天": 90}
        days = days_map[date_range]
        cutoff_date = datetime.now() - timedelta(days=days)

        all_logs = user_mgmt.get_access_logs(limit=1000)
        logs = [
            log for log in all_logs
            if pd.to_datetime(log['access_time']) >= cutoff_date
        ]

    if not logs:
        st.info("选定时间范围内无数据")
        return

    # 根据统计类型渲染不同图表
    if stat_type == "登录统计":
        render_login_statistics(logs)
    elif stat_type == "产品访问":
        render_product_access_statistics(logs, db)
    else:
        render_user_activity_statistics(logs)


def render_login_statistics(logs):
    """渲染登录统计"""
    # 筛选登录日志
    login_logs = [log for log in logs if log['action'] == 'login']

    if not login_logs:
        st.info("无登录记录")
        return

    # 按日期统计登录次数
    daily_logins = {}
    for log in login_logs:
        date = pd.to_datetime(log['access_time']).date()
        daily_logins[date] = daily_logins.get(date, 0) + 1

    # 创建时间序列图
    dates = sorted(daily_logins.keys())
    counts = [daily_logins[date] for date in dates]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=counts,
        mode='lines+markers',
        name='每日登录次数',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))

    fig.update_layout(
        title="每日登录趋势",
        xaxis_title="日期",
        yaxis_title="登录次数",
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # 统计信息
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("总登录次数", len(login_logs))

    with col2:
        unique_users = len(set([log['user_id'] for log in login_logs]))
        st.metric("登录用户数", unique_users)

    with col3:
        avg_daily = len(login_logs) / max(len(dates), 1)
        st.metric("日均登录", f"{avg_daily:.1f}")


def render_product_access_statistics(logs, db):
    """渲染产品访问统计"""
    # 筛选产品访问日志
    view_logs = [log for log in logs if log['action'] == 'view_product' and log['product_code']]

    if not view_logs:
        st.info("无产品访问记录")
        return

    # 统计各产品访问次数
    product_counts = {}
    for log in view_logs:
        product_code = log['product_code']
        product_counts[product_code] = product_counts.get(product_code, 0) + 1

    # 获取产品名称
    products = db.get_products()
    product_names = {p['product_code']: p['product_name'] for p in products}

    # 创建柱状图
    product_labels = []
    access_counts = []

    for code, count in sorted(product_counts.items(), key=lambda x: x[1], reverse=True):
        name = product_names.get(code, code)
        product_labels.append(f"{name}\n({code})")
        access_counts.append(count)

    fig = px.bar(
        x=product_labels,
        y=access_counts,
        title="产品访问统计",
        labels={'x': '产品', 'y': '访问次数'}
    )
    fig.update_layout(xaxis_tickangle=-45, height=400)

    st.plotly_chart(fig, use_container_width=True)

    # 访问详情表格
    st.subheader("访问详情")
    access_data = []
    for code, count in sorted(product_counts.items(), key=lambda x: x[1], reverse=True):
        name = product_names.get(code, code)
        # 计算独立用户数
        unique_users = len(set([
            log['user_id'] for log in view_logs
            if log['product_code'] == code
        ]))
        access_data.append({
            "产品名称": name,
            "产品代码": code,
            "总访问次数": count,
            "独立用户数": unique_users,
            "平均访问/用户": f"{count / unique_users:.1f}" if unique_users > 0 else "0"
        })

    if access_data:
        df_access = pd.DataFrame(access_data)
        st.dataframe(df_access, use_container_width=True, hide_index=True)


def render_user_activity_statistics(logs):
    """渲染用户活跃度统计"""
    # 按用户统计活动
    user_activity = {}
    for log in logs:
        user_id = log['user_id']
        user_name = log['display_name']

        if user_id not in user_activity:
            user_activity[user_id] = {
                'name': user_name,
                'login_count': 0,
                'view_count': 0,
                'total_actions': 0,
                'last_activity': None
            }

        user_activity[user_id]['total_actions'] += 1

        if log['action'] == 'login':
            user_activity[user_id]['login_count'] += 1
        elif log['action'] == 'view_product':
            user_activity[user_id]['view_count'] += 1

        # 更新最后活动时间
        activity_time = pd.to_datetime(log['access_time'])
        if (user_activity[user_id]['last_activity'] is None or
                activity_time > user_activity[user_id]['last_activity']):
            user_activity[user_id]['last_activity'] = activity_time

    # 创建活跃度数据
    activity_data = []
    for user_id, data in user_activity.items():
        activity_data.append({
            "用户": data['name'],
            "总操作数": data['total_actions'],
            "登录次数": data['login_count'],
            "产品访问": data['view_count'],
            "最后活动": data['last_activity'].strftime('%m-%d %H:%M') if data['last_activity'] else '-'
        })

    # 按总操作数排序
    activity_data.sort(key=lambda x: x['总操作数'], reverse=True)

    if activity_data:
        df_activity = pd.DataFrame(activity_data)
        st.dataframe(df_activity, use_container_width=True, hide_index=True)

        # 活跃度图表
        if len(activity_data) > 1:
            fig = px.scatter(
                df_activity,
                x="登录次数",
                y="产品访问",
                size="总操作数",
                hover_name="用户",
                title="用户活跃度分布"
            )
            st.plotly_chart(fig, use_container_width=True)


def render_system_settings(user_mgmt, db):
    """渲染系统设置"""
    st.subheader("🔧 系统设置")

    # 数据库维护
    st.markdown("### 数据库维护")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑️ 清理过期日志", type="secondary"):
            # 这里可以添加清理过期日志的逻辑
            st.success("日志清理完成")

    with col2:
        if st.button("📊 数据库统计", type="secondary"):
            render_database_stats(user_mgmt, db)

    st.divider()

    # 系统配置
    st.markdown("### 系统配置")

    # 会话超时设置
    session_timeout = st.slider(
        "会话超时时间（小时）",
        min_value=1,
        max_value=24,
        value=8,
        help="用户登录后多长时间自动登出"
    )

    # 日志保留天数
    log_retention = st.slider(
        "日志保留天数",
        min_value=7,
        max_value=365,
        value=90,
        help="系统访问日志的保留时间"
    )

    if st.button("💾 保存设置", type="primary"):
        # 这里可以添加保存配置的逻辑
        st.success("设置已保存")

    st.divider()

    # 系统信息
    st.markdown("### 系统信息")

    info_col1, info_col2 = st.columns(2)

    with info_col1:
        st.write("**数据库路径:**", db.db_path)
        st.write("**系统版本:**", "v1.0")
        st.write("**部署时间:**", datetime.now().strftime("%Y-%m-%d"))

    with info_col2:
        # 显示数据库大小等信息
        import os
        if os.path.exists(db.db_path):
            db_size = os.path.getsize(db.db_path) / (1024 * 1024)  # MB
            st.write("**数据库大小:**", f"{db_size:.2f} MB")

        users_count = len(user_mgmt.get_all_users())
        products_count = len(db.get_products())
        st.write("**用户数量:**", users_count)
        st.write("**产品数量:**", products_count)


def render_database_stats(user_mgmt, db):
    """渲染数据库统计信息"""
    st.subheader("📊 数据库统计")

    # 获取各表的记录数量
    conn = db.get_connection()
    cursor = conn.cursor()

    stats = {}
    tables = ['products', 'nav_data', 'holdings', 'users', 'user_product_permissions', 'user_access_logs']

    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats[table] = count
        except Exception:
            stats[table] = 0

    conn.close()

    # 显示统计信息
    col1, col2 = st.columns(2)

    with col1:
        st.write("**核心数据表:**")
        st.write(f"- 产品: {stats['products']} 条")
        st.write(f"- 净值数据: {stats['nav_data']} 条")
        st.write(f"- 持仓数据: {stats['holdings']} 条")

    with col2:
        st.write("**用户管理表:**")
        st.write(f"- 用户: {stats['users']} 条")
        st.write(f"- 权限: {stats['user_product_permissions']} 条")
        st.write(f"- 访问日志: {stats['user_access_logs']} 条")


def get_action_text(action):
    """获取操作的中文描述"""
    action_map = {
        'login': '登录',
        'logout': '登出',
        'view_product': '查看产品'
    }
    return action_map.get(action, action)