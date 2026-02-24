import streamlit as st
import pandas as pd
import numpy as np
import re
import io

st.set_page_config(page_title="지원매니저별 실적 관리 시스템", layout="wide")

# ==========================================
# 1. 세션 상태 초기화
# ==========================================
if 'df_merged' not in st.session_state:
    st.session_state['df_merged'] = pd.DataFrame()
if 'manager_col' not in st.session_state:
    st.session_state['manager_col'] = ""
if 'admin_cols' not in st.session_state:
    st.session_state['admin_cols'] = []
if 'admin_goals' not in st.session_state:
    st.session_state['admin_goals'] = {}
if 'admin_categories' not in st.session_state:
    st.session_state['admin_categories'] = []

# ==========================================
# 2. 공통 함수
# ==========================================
def clean_special_chars(val):
    if pd.isna(val):
        return val
    val_str = str(val)
    cleaned = re.sub(r'_x[0-9a-fA-F]{4}_', '', val_str)
    return cleaned.strip()

@st.cache_data(show_spinner=False)
def load_file_data(file_bytes, file_name):
    if file_name.endswith('.csv'):
        return pd.read_csv(io.BytesIO(file_bytes), encoding='utf-8', errors='replace')
    else:
        return pd.read_excel(io.BytesIO(file_bytes))

# ==========================================
# 3. 사이드바 (메뉴 선택)
# ==========================================
st.sidebar.title("메뉴")
menu = st.sidebar.radio("이동할 화면을 선택하세요", ["관리자 화면 (설정)", "매니저 화면 (로그인)"])

# ==========================================
# 4. 관리자 화면 (Admin View)
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    
    st.header("1. 데이터 파일 업로드 및 병합 설정")
    col_file1, col_file2 = st.columns(2)
    with col_file1:
        file1 = st.file_uploader("첫 번째 파일 업로드", type=['csv', 'xlsx'])
    with col_file2:
        file2 = st.file_uploader("두 번째 파일 업로드", type=['csv', 'xlsx'])
        
    if file1 is not None and file2 is not None:
        try:
            with st.spinner("파일을 읽고 있습니다..."):
                df1 = load_file_data(file1.getvalue(), file1.name)
                df2 = load_file_data(file2.getvalue(), file2.name)
            
            cols1 = df1.columns.tolist()
            cols2 = df2.columns.tolist()
            
            with st.form("merge_form"):
                st.write("**병합 기준 열 선택**")
                col_key1, col_key2 = st.columns(2)
                with col_key1:
                    key1 = st.selectbox("첫 번째 파일의 [설계사 코드] 열 선택", cols1)
                with col_key2:
                    key2 = st.selectbox("두 번째 파일의 [설계사 코드] 열 선택", cols2)
                
                submit_merge = st.form_submit_button("데이터 병합 실행")
                if submit_merge:
                    with st.spinner("데이터를 병합하고 있습니다..."):
                        df1[key1] = df1[key1].apply(clean_special_chars)
                        df2[key2] = df2[key2].apply(clean_special_chars)
                        df_merged = pd.merge(df1, df2, left_on=key1, right_on=key2, how='outer', suffixes=('_파일1', '_파일2'))
                        st.session_state['df_merged'] = df_merged
                        st.success(f"데이터 병합 완료! 총 {len(df_merged)}행의 데이터가 준비되었습니다.")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

    st.divider()

    # 데이터가 병합된 이후에만 아래 설정 항목들 표시
    if not st.session_state['df_merged'].empty:
        df = st.session_state['df_merged']
        available_columns = df.columns.tolist()
        
        # ========================================
        st.header("2. 매니저 로그인 기준 열 설정")
        col_m1, col_m2 = st.columns([8, 2])
        with col_m1:
            manager_col = st.selectbox("로그인에 사용할 [지원매니저 코드] 열을 선택하세요", available_columns, 
                                       index=available_columns.index(st.session_state['manager_col']) if st.session_state['manager_col'] in available_columns else 0)
        with col_m2:
            st.write("")
            st.write("")
            if st.button("저장", key="btn_save_manager"):
                st.session_state['manager_col'] = manager_col
                st.success(f"로그인 열이 '{manager_col}'(으)로 설정되었습니다.")

        st.divider()

        # ========================================
        st.header("3. 표시할 데이터 항목 및 필터 추가")
        st.markdown("항목을 계속해서 추가할 수 있으며, 하단 목록에서 삭제할 수 있습니다.")
        
        c1, c2, c3, c4 = st.columns([3, 2, 3, 2])
        with c1: sel_col = st.selectbox("추가할 항목 선택", available_columns, key="sec3_col")
        with c2: col_type = st.radio("데이터 타입", ["텍스트", "숫자"], horizontal=True, key="sec3_type")
        with c3: condition = st.text_input("산식 (예: > 0)", key="sec3_cond")
        with c4:
            st.write("") # 줄맞춤용 빈공간
            st.write("")
            if st.button("➕ 항목 추가", key="btn_add_col"):
                st.session_state['admin_cols'].append({
                    "col": sel_col, "type": col_type, "condition": condition if col_type == "숫자" else ""
                })
                st.rerun()

        if st.session_state['admin_cols']:
            st.write("📌 **[현재 반영된 항목 목록]**")
            for i, item in enumerate(st.session_state['admin_cols']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    st.markdown(f"- **{item['col']}** ({item['type']}) | 조건: `{item['condition']}`")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_col_{i}"):
                        st.session_state['admin_cols'].pop(i)
                        st.rerun()

        st.divider()

        # ========================================
        st.header("4. 목표 구간 다중 설정")
        c1, c2, c3 = st.columns([3, 5, 2])
        with c1: goal_col = st.selectbox("목표 구간을 적용할 항목", available_columns, key="sec4_col")
        with c2: goal_tiers = st.text_input("구간 금액 입력 (예: 100000, 200000)", key="sec4_tiers")
        with c3:
            st.write("")
            st.write("")
            if st.button("➕ 구간 추가", key="btn_add_goal"):
                if goal_tiers:
                    tiers_list = [float(x.strip()) for x in goal_tiers.split(",") if x.strip().isdigit()]
                    st.session_state['admin_goals'][goal_col] = sorted(tiers_list)
                    st.rerun()
                
        if st.session_state['admin_goals']:
            st.write("🎯 **[현재 반영된 목표 구간 목록]**")
            # dictionary 항목을 순회하며 개별 삭제 버튼 생성
            for g_col, tiers in list(st.session_state['admin_goals'].items()):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    st.markdown(f"- **{g_col}**: {tiers}")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_goal_{g_col}"):
                        del st.session_state['admin_goals'][g_col]
                        st.rerun()

        st.divider()

        # ========================================
        st.header("5. 맞춤형 분류(태그) 설정")
        c1, c2, c3, c4 = st.columns([3, 2, 3, 2])
        with c1: cat_col = st.selectbox("분류 기준 항목", available_columns, key="sec5_col")
        with c2: cat_cond = st.text_input("조건 (예: >= 500000)", key="sec5_cond")
        with c3: cat_name = st.text_input("부여할 분류명 (예: VIP)", key="sec5_name")
        with c4:
            st.write("")
            st.write("")
            if st.button("➕ 기준 추가", key="btn_add_cat"):
                st.session_state['admin_categories'].append({
                    "col": cat_col, "condition": cat_cond, "name": cat_name
                })
                st.rerun()
            
        if st.session_state['admin_categories']:
            st.write("🏷️ **[현재 반영된 분류 기준 목록]**")
            for i, cat in enumerate(st.session_state['admin_categories']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    st.markdown(f"- 항목: **{cat['col']}** | 조건: `{cat['condition']}` ➡️ **[{cat['name']}]**")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_cat_{i}"):
                        st.session_state['admin_categories'].pop(i)
                        st.rerun()
            
    else:
        st.info("👆 먼저 위에서 두 파일을 업로드하고 [데이터 병합 실행]을 눌러주세요.")

# ==========================================
# 5. 매니저 화면 (Manager View)
# ==========================================
elif menu == "매니저 화면 (로그인)":
    st.title("👤 매니저 전용 실적 현황")
    
    if st.session_state['df_merged'].empty or not st.session_state['manager_col']:
        st.warning("데이터가 없거나 관리자 설정이 완료되지 않았습니다. 관리자 화면에서 파일 업로드 및 설정을 진행해주세요.")
        st.stop()
        
    df = st.session_state['df_merged'].copy()
    manager_col = st.session_state['manager_col']
    
    with st.form("login_form"):
        manager_code = st.text_input("🔑 매니저 코드를 입력하세요", type="password")
        submit_login = st.form_submit_button("로그인 및 조회")
    
    if submit_login and manager_code:
        # 매니저 코드 정제 및 필터링
        df[manager_col] = df[manager_col].apply(clean_special_chars)
        manager_code_clean = clean_special_chars(manager_code)
        
        my_df = df[df[manager_col].astype(str).str.contains(manager_code_clean, na=False)].copy()
        
        if my_df.empty:
            st.error("일치하는 산하 설계사 데이터가 없습니다. 코드를 확인해주세요.")
        else:
            st.success(f"총 {len(my_df)}명의 설계사 데이터가 조회되었습니다.")
            
            display_cols = []
            
            # 1. 항목 표시 및 필터 적용
            for item in st.session_state['admin_cols']:
                col_name = item['col']
                display_cols.append(col_name)
                
                if item['type'] == '숫자' and item['condition']:
                    try:
                        my_df[col_name] = pd.to_numeric(my_df[col_name], errors='coerce').fillna(0)
                        mask = my_df.eval(f"`{col_name}` {item['condition']}")
                        my_df = my_df[mask]
                    except Exception as e:
                        pass
            
            # 2. 다중 목표 구간 및 부족분 계산
            for g_col, tiers in st.session_state['admin_goals'].items():
                if g_col in my_df.columns:
                    my_df[g_col] = pd.to_numeric(my_df[g_col], errors='coerce').fillna(0)
                    
                    def calc_shortfall(val):
                        for t in tiers:
                            if val < t:
                                return pd.Series([f"{t:,.0f} 목표", t - val])
                        return pd.Series(["최고 구간 달성", 0])
                    
                    my_df[[f'{g_col}_다음목표', f'{g_col}_부족금액']] = my_df[g_col].apply(calc_shortfall)
                    
                    if f'{g_col}_다음목표' not in display_cols:
                        display_cols.extend([f'{g_col}_다음목표', f'{g_col}_부족금액'])

            # 3. 맞춤형 분류(태그) 지정
            if st.session_state['admin_categories']:
                my_df['맞춤분류'] = ""
                for cat in st.session_state['admin_categories']:
                    c_col = cat['col']
                    c_cond = cat['condition']
                    c_name = cat['name']
                    try:
                        my_df[c_col] = pd.to_numeric(my_df[c_col], errors='coerce').fillna(0)
                        mask = my_df.eval(f"`{c_col}` {c_cond}")
                        my_df.loc[mask, '맞춤분류'] += f"[{c_name}] "
                    except:
                        pass
                if '맞춤분류' not in display_cols:
                    display_cols.insert(0, '맞춤분류')
            
            # 중복 컬럼 제거 후 최종 출력
            final_cols = list(dict.fromkeys(display_cols))
            
            if not final_cols:
                st.warning("관리자 화면에서 표시할 항목을 추가해주세요.")
            else:
                final_df = my_df[final_cols]
                st.dataframe(final_df, use_container_width=True)
