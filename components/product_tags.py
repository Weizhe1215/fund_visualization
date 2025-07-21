"""
产品标签管理组件
"""
import streamlit as st
import pandas as pd


def render_tag_management(db):
    """渲染标签管理界面"""
    st.subheader("🏷️ 产品标签管理")

    # 创建两列：标签管理 | 产品标签分配
    col_tags, col_assign = st.columns([1, 1])

    with col_tags:
        st.write("**标签管理**")

        # 添加新标签
        with st.form("add_tag_form"):
            new_tag_name = st.text_input("标签名称", placeholder="例如: 实盘产品")
            new_tag_color = st.color_picker("标签颜色", value="#1f77b4")

            if st.form_submit_button("➕ 添加标签"):
                if new_tag_name.strip():
                    success = db.add_tag(new_tag_name.strip(), new_tag_color)
                    if success:
                        st.success(f"✅ 标签 '{new_tag_name}' 添加成功！")
                        st.rerun()
                    else:
                        st.error("❌ 标签添加失败")
                else:
                    st.error("❌ 请输入标签名称")

        # 显示现有标签
        st.write("**现有标签：**")
        tags = db.get_all_tags()

        if tags:
            for tag in tags:
                with st.container():
                    col_tag_info, col_tag_action = st.columns([3, 1])

                    with col_tag_info:
                        st.markdown(
                            f'<span style="background-color: {tag["color"]}; '
                            f'color: white; padding: 2px 8px; border-radius: 12px; '
                            f'font-size: 12px;">{tag["name"]}</span>',
                            unsafe_allow_html=True
                        )

                    with col_tag_action:
                        if st.button("🗑️", key=f"del_tag_{tag['name']}", help="删除标签"):
                            # 这里可以添加删除确认逻辑
                            st.warning("删除功能待实现")
        else:
            st.info("暂无标签")

    with col_assign:
        st.write("**产品标签分配**")

        # 选择产品
        products = db.get_products()
        if not products:
            st.warning("暂无产品")
            return

        product_options = {f"{p['product_name']} ({p['product_code']})": p['product_code']
                           for p in products}

        selected_product_display = st.selectbox(
            "选择产品",
            options=list(product_options.keys()),
            key="tag_assign_product"
        )

        selected_product_code = product_options[selected_product_display]

        # 显示当前产品的标签
        current_tags = db.get_product_tags(selected_product_code)

        st.write("**当前标签：**")
        if current_tags:
            cols = st.columns(len(current_tags))
            for i, tag in enumerate(current_tags):
                with cols[i]:
                    st.markdown(
                        f'<span style="background-color: {tag["color"]}; '
                        f'color: white; padding: 2px 8px; border-radius: 12px; '
                        f'font-size: 12px;">{tag["name"]}</span>',
                        unsafe_allow_html=True
                    )
                    if st.button("❌", key=f"remove_tag_{selected_product_code}_{tag['name']}", help="移除标签"):
                        success = db.remove_product_tag(selected_product_code, tag['name'])
                        if success:
                            st.success(f"✅ 标签 '{tag['name']}' 已移除")
                            st.rerun()
        else:
            st.info("该产品暂无标签")

        # 添加标签
        st.write("**添加标签：**")
        available_tags = db.get_all_tags()
        current_tag_names = [tag['name'] for tag in current_tags]
        available_tag_names = [tag['name'] for tag in available_tags if tag['name'] not in current_tag_names]

        if available_tag_names:
            selected_tag = st.selectbox(
                "选择要添加的标签",
                options=available_tag_names,
                key="add_tag_to_product"
            )

            if st.button("➕ 添加到产品"):
                success = db.add_product_tag(selected_product_code, selected_tag)
                if success:
                    st.success(f"✅ 标签 '{selected_tag}' 已添加到产品")
                    st.rerun()
                else:
                    st.error("❌ 添加标签失败")
        else:
            st.info("没有可添加的标签（所有标签都已分配或无可用标签）")


def get_product_options_by_tag(db, tag_filter="全部"):
    """根据标签筛选获取产品选项"""
    if tag_filter == "全部":
        products = db.get_products()
    else:
        products = db.get_products_by_tag(tag_filter)

    return {f"{p['product_name']} ({p['product_code']})": p['product_code']
            for p in products}


def render_tag_filter(db, key_suffix=""):
    """渲染标签筛选下拉框"""
    tags = db.get_all_tags()
    tag_options = ["全部"] + [tag['name'] for tag in tags]

    selected_tag = st.selectbox(
        "按标签筛选",
        options=tag_options,
        key=f"tag_filter_{key_suffix}"
    )

    return selected_tag