import streamlit as st
import pandas as pd
import numpy as np
import re
import io
import os
import pickle

st.set_page_config(page_title="지원매니저별 실적 관리 시스템", layout="wide")

CONFIG_FILE = "app_config.pkl"

# ==========================================
# 0. 토스(Toss) 스타일 커스텀 CSS
# ==========================================
st.markdown("""
<style>
/* 폰트 및 전체 느낌 부드럽게 */
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
/* 매니저 대시보드 상단 카드 디자인 */
.toss-header {
    background-color: #f2f4f6;
    padding: 32px 40px;
    border-radius: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.03);
}
.toss-title {
    color: #191f28;
    font-size: 36px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}
.toss-subtitle {
    color: #8b95a1;
    font-size: 22px;
    font-weight: 600;
    margin-left: 10px;
}
.toss-desc {
    color: #4e5968;
    font-size: 17px;
    margin: 12px 0 0 0;
    font-weight: 500;
}
/* 데이터프레임 모서리 둥글게 */
[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04);
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 1. 설정 및 데이터 영구 저장/불러오기 함수
# ==========================================
def load_data_and_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'rb') as f:
                data = pickle.load(f)
                st.session_state['df_merged'] = data.get('df_merged', pd.DataFrame())
                st.session_state['manager_col'] = data.get('manager_col', "")
                st.session_state['manager_name_col'] = data.get('manager_name_col', "")
                st.session_state['admin_cols'] = data.get('admin_cols', [])
                st.session_state['admin_goals'] = data.get('admin_goals', {})
                st.session_state['admin_categories'] = data.get('admin_categories', [])
                st.session_state['col_order'] = data.get('col_order', [])
        except:
            pass 

def save_data_and_config():
    data = {
        'df_merged': st.session_state.get('df_merged', pd.DataFrame()),
        'manager_col': st.session_state.get('manager_col', ""),
        'manager_name_col': st.session_state.get('manager_name_col', ""),
        'admin_cols': st.session_state.get('admin_cols', []),
        'admin_goals': st.session_state.get('admin_goals', {}),
        'admin_categories': st.session_state.get('admin_categories', []),
        'col_order': st.session_state.get('col_order', [])
    }
    with open(CONFIG_FILE, 'wb') as f:
        pickle.dump(data, f)

if 'df_merged' not in st.session_state:
    st.session_state['df_merged'] = pd.DataFrame()
    st.session_state['manager_col'] = ""
    st.session_state['manager_name_col'] = ""
    st.session_state['admin_cols'] = []
    st.session_state['admin_goals'] = {}
    st.session_state['admin_categories'] = []
    st.session_state['col_order'] = []
    load_data_and_config()

# ==========================================
# 2. 데이터 정제 공통 함수
# ==========================================
def decode_excel_text(val):
    if pd.isna(val): return val
    val_str = str(val)
    if '_x' not in val_str: return val_str
    def decode_match(match):
        try: return chr(int(match.group(1), 16))
        except: return match.group(0)
    return re.sub(r'_x([0-9a-fA-F]{4})_', decode_match, val_str)

def clean_key(val):
    if pd.isna(val) or str(val).strip().lower() == 'nan': return ""
    val_str = str(val).strip().replace(" ", "").upper()
    if val_str.endswith('.0'): val_str = val_str[:-2]
    return val_str

@st.cache_data(show_spinner=False)
def load_file_data(file_bytes, file_name):
    if file_name.endswith('.csv'):
        df = pd.read_csv(io.BytesIO(file_bytes), encoding='utf-8', errors='replace')
    else:
        df = pd.read_excel(io.BytesIO(file_bytes))
        
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(decode_excel_text)
    return df

# ==========================================
# 3. 사이드바 (메뉴 선택)
# ==========================================
st.sidebar.title("메뉴")
menu = st.sidebar.radio("이동할 화면을 선택하세요", ["매니저 화면 (로그인)", "관리자 화면 (설정)"])

# ==========================================
# 4. 관리자 화면 (Admin View)
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    
    st.header("1. 데이터 파일 업로드 및 관리")
    
    if not st.session_state['df_merged'].empty:
        st.success(f"✅ 현재 **{len(st.session_state['df_merged'])}행**의 데이터가 저장되어 운영 중입니다.")
        if st.button("🗑️ 기존 파일 데이터 삭제 (새 파일 업로드 시)"):
            st.session_state['df_merged'] = pd.DataFrame()
            save_data_and_config()
            st.rerun()
    else:
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
                    col_key1, col_key2 = st.columns(2)
                    with col_key1: key1 = st.selectbox("첫 번째 파일의 [설계사 코드] 열 선택", cols1)
                    with col_key2: key2 = st.selectbox("두 번째 파일의 [설계사 코드] 열 선택", cols2)
                    
                    submit_merge = st.form_submit_button("데이터 병합 및 시스템에 저장")
                    if submit_merge:
                        with st.spinner("데이터를 병합하고 저장 중입니다..."):
                            df1['merge_key1'] = df1[key1].apply(clean_key)
                            df2['merge_key2'] = df2[key2].apply(clean_key)
                            df_merged = pd.merge(df1, df2, left_on='merge_key1', right_on='merge_key2', how='outer', suffixes=('_파일1', '_파일2'))
                            st.session_state['df_merged'] = df_merged
                            save_data_and_config()
                            st.success(f"데이터 병합 완료! 총 {len(df_merged)}행의 데이터가 안전하게 저장되었습니다.")
                            st.rerun()
            except Exception as e:
                st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

    st.divider()

    if not st.session_state['df_merged'].empty:
        df = st.session_state['df_merged']
        available_columns = [c for c in df.columns if c not in ['merge_key1', 'merge_key2']]
        
        # ========================================
        st.header("2. 매니저 로그인 및 이름 표시 열 설정")
        col_m1, col_m2, col_m3 = st.columns([4, 4, 2])
        with col_m1:
            manager_col = st.selectbox("🔑 로그인 [매니저 코드] 열", available_columns, 
                                       index=available_columns.index(st.session_state['manager_col']) if st.session_state['manager_col'] in available_columns else 0)
        with col_m2:
            idx_name = available_columns.index(st.session_state['manager_name_col']) if st.session_state['manager_name_col'] in available_columns else 0
            manager_name_col = st.selectbox("👤 화면 상단 [매니저 이름] 표시 열", available_columns, index=idx_name)
        with col_m3:
            st.write("")
            st.write("")
            if st.button("저장", key="btn_save_manager"):
                st.session_state['manager_col'] = manager_col
                st.session_state['manager_name_col'] = manager_name_col
                save_data_and_config()
                st.success("로그인 및 이름 열 설정이 저장되었습니다.")

        st.divider()

        # ========================================
        st.header("3. 표시할 데이터 항목 및 필터 추가")
        c1, c2, c3, c4 = st.columns([3, 2, 3, 2])
        with c1: sel_col = st.selectbox("추가할 항목 선택", available_columns, key="sec3_col")
        with c2: col_type = st.radio("데이터 타입", ["텍스트", "숫자"], horizontal=True, key="sec3_type")
        with c3: condition = st.text_input("산식 (예: > 0)", key="sec3_cond")
        with c4:
            st.write("")
            st.write("")
            if st.button("➕ 항목 추가", key="btn_add_col"):
                st.session_state['admin_cols'].append({
                    "col": sel_col, "type": col_type, "condition": condition if col_type == "숫자" else ""
                })
                save_data_and_config()
                st.rerun()

        if st.session_state['admin_cols']:
            for i, item in enumerate(st.session_state['admin_cols']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1: st.markdown(f"- **{item['col']}** ({item['type']}) | 조건: `{item['condition']}`")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_col_{i}"):
                        st.session_state['admin_cols'].pop(i)
                        save_data_and_config()
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
                    save_data_and_config()
                    st.rerun()
                
        if st.session_state['admin_goals']:
            for g_col, tiers in list(st.session_state['admin_goals'].items()):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1: st.markdown(f"- **{g_col}**: {tiers}")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_goal_{g_col}"):
                        del st.session_state['admin_goals'][g_col]
                        save_data_and_config()
                        st.rerun()

        st.divider()

        # ========================================
        st.header("5. 맞춤형 분류(태그) 설정 (3개 조건 조합)")
        with st.form("add_cat_form"):
            col1, col2 = st.columns(2)
            with col1:
                cat_col1 = st.selectbox("1. 기준 열 선택", available_columns)
                cat_col2 = st.selectbox("2. 기준 열 선택", ["(선택안함)"] + available_columns)
                cat_col3 = st.selectbox("3. 기준 열 선택", ["(선택안함)"] + available_columns)
            with col2:
                cat_cond1 = st.text_input("1. 산식 (예: >= 500000)")
                cat_cond2 = st.text_input("2. 산식 (예: > 0, 없으면 비워둠)")
                cat_cond3 = st.text_input("3. 산식 (예: <= 100, 없으면 비워둠)")
            
            cat_name = st.text_input("부여할 분류명 (예: VIP설계사)")
            submit_cat = st.form_submit_button("➕ 기준 추가")
            
            if submit_cat:
                conditions = []
                if cat_cond1.strip() and cat_cond1.strip() != '상관없음': conditions.append({"col": cat_col1, "cond": cat_cond1.strip()})
                if cat_col2 != "(선택안함)" and cat_cond2.strip() and cat_cond2.strip() != '상관없음': conditions.append({"col": cat_col2, "cond": cat_cond2.strip()})
                if cat_col3 != "(선택안함)" and cat_cond3.strip() and cat_cond3.strip() != '상관없음': conditions.append({"col": cat_col3, "cond": cat_cond3.strip()})
                
                if conditions and cat_name.strip():
                    st.session_state['admin_categories'].append({"conditions": conditions, "name": cat_name.strip()})
                    save_data_and_config()
                    st.rerun()
            
        if st.session_state['admin_categories']:
            for i, cat in enumerate(st.session_state['admin_categories']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    cond_strs = [f"`{c['col']}` {c['cond']}" for c in cat.get('conditions', [{'col': cat.get('col'), 'cond': cat.get('condition')}])]
                    st.markdown(f"- 조건: **{' AND '.join(cond_strs)}** ➡️ **[{cat['name']}]** 태그 부여")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_cat_{i}"):
                        st.session_state['admin_categories'].pop(i)
                        save_data_and_config()
                        st.rerun()

        st.divider()

        # ========================================
        st.header("6. 📋 화면 표시 순서 커스텀 설정")
        st.markdown("매니저 화면에 출력될 열의 순서를 자유롭게 배치하세요. **(박스 안의 항목들을 마우스로 드래그해서 순서를 바꾸거나, `X`를 눌러 지우고 다시 순서대로 클릭하시면 됩니다.)**")
        
        # 조합될 모든 예상 컬럼명 수집
        expected_cols = []
        if st.session_state['admin_categories']: expected_cols.append("맞춤분류")
        for item in st.session_state['admin_cols']: expected_cols.append(item['col'])
        for g_col in st.session_state['admin_goals'].keys(): expected_cols.extend([f"{g_col}_다음목표", f"{g_col}_부족금액"])
            
        current_order = st.session_state.get('col_order', [])
        valid_order = [c for c in current_order if c in expected_cols]
        for c in expected_cols:
            if c not in valid_order:
                valid_order.append(c)
                
        new_order = st.multiselect("왼쪽부터 차례대로 화면에 표시됩니다.", expected_cols, default=valid_order)
        if st.button("순서 저장", key="btn_save_order"):
            st.session_state['col_order'] = new_order
            save_data_and_config()
            st.success("✅ 화면 표시 순서가 저장되었습니다.")
            
    else:
        st.info("👆 먼저 위에서 두 파일을 업로드하고 [데이터 병합 및 시스템에 저장]을 눌러주세요.")

# ==========================================
# 5. 매니저 화면 (Manager View)
# ==========================================
elif menu == "매니저 화면 (로그인)":
    if st.session_state['df_merged'].empty or not st.session_state['manager_col']:
        st.title("👤 매니저 전용 실적 현황")
        st.warning("현재 저장된 데이터가 없거나 관리자 설정이 완료되지 않았습니다.")
        st.stop()
        
    df = st.session_state['df_merged'].copy()
    manager_col = st.session_state['manager_col']
    manager_name_col = st.session_state.get('manager_name_col', manager_col)
    
    with st.form("login_form"):
        manager_code = st.text_input("🔑 매니저 코드를 입력하세요", type="password")
        submit_login = st.form_submit_button("로그인 및 조회")
    
    if submit_login and manager_code:
        df['search_key'] = df[manager_col].apply(clean_key)
        manager_code_clean = clean_key(manager_code)
        
        my_df = df[df['search_key'] == manager_code_clean].copy()
        if my_df.empty:
            my_df = df[df['search_key'].str.contains(manager_code_clean, na=False)].copy()

        if my_df.empty:
            st.error(f"❌ 매니저 코드 '{manager_code}'에 일치하는 데이터를 찾을 수 없습니다.")
        else:
            # 1. 상단 디자인 헤더 표시 (Toss Style)
            manager_name = str(my_df[manager_name_col].iloc[0]) if manager_name_col in my_df.columns else "매니저"
            
            st.markdown(f"""
            <div class='toss-header'>
                <h1 class='toss-title'>{manager_name} <span class='toss-subtitle'>({manager_code_clean})</span></h1>
                <p class='toss-desc'>환영합니다! 산하 설계사분들의 맞춤 실적 현황입니다. 🚀</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 2. 데이터 처리
            display_cols = []
            
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

            if st.session_state['admin_categories']:
                if '맞춤분류' not in my_df.columns:
                    my_df['맞춤분류'] = ""
                for cat in st.session_state['admin_categories']:
                    c_name = cat.get('name', '')
                    final_mask = pd.Series(True, index=my_df.index)
                    cond_list = cat.get('conditions', [{'col': cat.get('col'), 'cond': cat.get('condition')}])
                    for cond_info in cond_list:
                        if not cond_info.get('col'): continue
                        c_col = cond_info['col']
                        c_cond = cond_info['cond']
                        try:
                            try: my_df[c_col] = pd.to_numeric(my_df[c_col])
                            except ValueError: pass
                            mask = my_df.eval(f"`{c_col}` {c_cond}")
                            final_mask = final_mask & mask
                        except Exception as e:
                            final_mask = final_mask & False
                    my_df.loc[final_mask, '맞춤분류'] += f"[{c_name}] "
                if '맞춤분류' not in display_cols:
                    display_cols.insert(0, '맞춤분류')
            
            # 3. 데이터 정렬 (맞춤분류 -> 지사명 -> 성명)
            sort_keys = []
            if '맞춤분류' in my_df.columns: sort_keys.append('맞춤분류')
            ji_cols = [c for c in my_df.columns if '지사명' in c]
            if ji_cols: sort_keys.append(ji_cols[0])
            gender_name_cols = [c for c in my_df.columns if '성별' in c or '설계사명' in c or '성명' in c]
            if gender_name_cols: sort_keys.append(gender_name_cols[0])
            if sort_keys:
                my_df = my_df.sort_values(by=sort_keys, ascending=[True] * len(sort_keys))
            
            # 4. 사용자가 지정한 순서대로 열 배치
            final_cols = list(dict.fromkeys(display_cols))
            ordered_final_cols = []
            for c in st.session_state.get('col_order', []):
                if c in final_cols:
                    ordered_final_cols.append(c)
            # 만약 지정되지 않은 컬럼이 있다면 맨 뒤에 붙이기
            for c in final_cols:
                if c not in ordered_final_cols:
                    ordered_final_cols.append(c)
                    
            if not ordered_final_cols:
                st.warning("관리자 화면에서 표시할 항목을 추가해주세요.")
            else:
                final_df = my_df[ordered_final_cols]
                
                # 5. 세 자리 콤마(,) 서식 적용 및 테이블 표시
                col_configs = {}
                for c in final_df.columns:
                    # 해당 컬럼의 데이터가 숫자 형식일 경우 자동으로 콤마 포맷 지정
                    if pd.api.types.is_numeric_dtype(final_df[c]):
                        col_configs[c] = st.column_config.NumberColumn(format="{:,}")
                
                st.dataframe(
                    final_df, 
                    use_container_width=True, 
                    hide_index=True, 
                    column_config=col_configs
                )
