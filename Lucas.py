import streamlit as st
import pandas as pd
import datetime
import streamlit_authenticator as stauth
from st_supabase_connection import SupabaseConnection
import altair as alt

# --- 页面配置 ---
st.set_page_config(page_title="宝宝日常记录仪", layout="centered")

query_param = st.query_params
auto_login_token = query_param.get("token")

# --- 1. 用户认证 ---
if auto_login_token == "momlovesyou":
    authentication_status = True
    name = "妈妈"
    username = "mom"
elif auto_login_token == "dadlovesyou":
    authentication_status = True
    name = "爸爸"
    username = "dad"
else:
    authenticator = stauth.Authenticate(
        st.secrets['credentials'].to_dict(),
        "baby_tracker_app",
        st.secrets['cookie']['key'],
        cookie_expiry_days=30
    )

authenticator.login(location="main")

# --- 2. 核心逻辑 (登录成功后执行) ---
if st.session_state["authentication_status"]:
    name = st.session_state["name"]
    username = st.session_state["username"]
    
    # 初始化 Supabase 连接
    conn = st.connection("supabase", type=SupabaseConnection)

    # 统一上传数据的函数
    def save_all_to_supabase(milk, pee, poo, excercise, extra):
        data = {
            "powder_milk(ml)": int(milk),
            "pee": "✅" if pee else None,
            "poo": "✅" if poo else None,
            "excercise": excercise if excercise else None,
            "extra": extra if extra else None,
            "user_name": name,
            "created_at": datetime.datetime.now().isoformat()
        }
        try:
            conn.table("Lucas_milk_logs").insert(data).execute()
            st.toast(f"✅ 记录已同步至云端", icon="👶")
        except Exception as e:
            st.error(f"保存失败: {e}")

    st.title(f"欢迎{name}，来记录岁岁的成长吧")

    # --- 第一部分：表单统一记录 ---
    # 使用 clear_on_submit=True 提交后会自动重置表单内容
    with st.form("baby_event_form", clear_on_submit=True):
        
        # 1. 奶量
        st.subheader("🥛 奶量记录")
        milk_140, milk_200, custom_milk = st.columns(3)
        with milk_140:
            milk_val = st.checkbox("🥛 140 ML", value=False)
        with milk_200:
            milk_val = st.checkbox("🥛 200 ML", value=False)
        with custom_milk:
            with st.popover("自定义 (ml)", use_container_width=True):
                custom_val = st.number_input("自定义 (ml)", value=None, step=10, label_visibility="collapsed")
                if st.checkbox("确认输入", value=False):
                    milk_val = custom_val
        
        st.divider()
        
        # 2. 拉撒 (并排显示)
        st.subheader("👶 拉撒玩")
        col_pee, col_poo = st.columns(2)
        with col_pee:
            is_pee = st.checkbox("💦 有小便", value=False)
        with col_poo:
            is_poo = st.checkbox("💩 有大便", value=False)
            
        
        # 3. 运动与其他
        ex_val = st.text_input("🏃 运动内容", placeholder="例如：做操、抬头训练")
        ext_val = st.text_input("☀️ 其他备注", placeholder="例如：维他命D、鱼肝油")
        
        # 提交按钮
        submitted = st.form_submit_button("✅ 确认上传记录", use_container_width=True)
        
        if submitted:
            # 只有至少有一项内容时才上传（防止误点空提交）
            if milk_val > 0 or is_pee or is_poo or ex_val or ext_val:
                save_all_to_supabase(milk_val, is_pee, is_poo, ex_val, ext_val)
            else:
                st.warning("请至少填写一项内容再提交哦！")

    st.divider()

    # --- 第二部分：数据统计与可视化 ---
    st.subheader("📊 近期统计分析")
    
    def get_data():
        try:
            res = conn.table("Lucas_milk_logs").select("*").execute()
            return pd.DataFrame(res.data)
        except Exception as e:
            st.error(f"获取数据失败：{e}")
            return pd.DataFrame()

    if st.checkbox("开启统计视图"):
        df = get_data()
        if not df.empty:
            # 数据预处理
            df.columns = [c.strip() for c in df.columns]
            df['created_at'] = pd.to_datetime(df['created_at'])
            
            # --- 奶量图表优化 ---
            milk_col = 'powder_milk(ml)'
            df[milk_col] = pd.to_numeric(df[milk_col], errors='coerce').fillna(0)
            milk_df = df[df[milk_col] > 0].copy()
            
            if not milk_df.empty:
                period = st.radio("时间统计跨度", ["实时(分钟级)", "按天合计", "按周合计"], horizontal=True)
                
                if period == "实时(分钟级)":
                    # 将时间转为字符串，确保 X 轴能具体显示每一分钟
                    plot_df = milk_df.sort_values('created_at')
                    plot_df['time_str'] = plot_df['created_at'].dt.strftime('%m-%d %H:%M')
                    
                    chart = alt.Chart(plot_df).mark_bar(size=20).encode(
                        x=alt.X('time_str:N', title='具体时间', sort=None),
                        y=alt.Y(f'{milk_col}:Q', title='奶量 (ml)'),
                        tooltip=['time_str', milk_col]
                    ).properties(height=350)
                    st.altair_chart(chart, use_container_width=True)
                else:
                    freq = {'按天合计': 'D', '按周合计': 'W'}[period]
                    chart_data = milk_df.set_index('created_at')[milk_col].resample(freq).sum().reset_index()
                    st.bar_chart(chart_data, x='created_at', y=milk_col)

            # --- 详细记录列表优化 ---
            with st.expander("📂 查看历史明细"):
                # 格式化表格显示：去除秒和毫秒，只留到分钟
                display_df = df.copy()
                display_df['created_at'] = display_df['created_at'].dt.strftime('%Y-%m-%d %H:%M')
                
                # 排序及列清理
                display_df = display_df.sort_values('created_at', ascending=False)
                target_cols = ['created_at', milk_col, 'pee', 'poo', 'excercise', 'extra', 'user_name']
                available_cols = [c for c in target_cols if c in display_df.columns]
                
                # 替换空值为横杠
                for col in available_cols:
                    display_df[col] = display_df[col].astype(str).replace(['None', 'nan', '<NA>', 'None'], '-')

                st.dataframe(
                    display_df[available_cols], 
                    use_container_width=True,
                    hide_index=True # 隐藏左侧索引列更美观
                )
        else:
            st.info("尚未发现记录数据")
    st.write("")
    st.divider()
    col_left, col_mid, col_right = st.columns([2, 1, 2])
    with col_mid:
        authenticator.logout(button_name='退出登录', location='main')

elif st.session_state["authentication_status"] is False:
    st.error('用户名或密码错误')
elif st.session_state["authentication_status"] is None:
    st.info('请先登录以开始记录')
