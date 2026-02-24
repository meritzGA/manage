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
# 1. 설정 및 데이터 영구 저장/불러오기 함수
# ==========================================
def load_data_and_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'rb') as f:
                data = pickle.load(f)
                st.session_state['df_merged'] = data.get('df_merged', pd.DataFrame())
                st.session_state['manager_col'] = data.get('manager_col', "")
                st.session_state['admin_cols'] = data.get('admin_cols', [])
                st.session_state['admin_goals'] = data.get('admin_goals', {})
                st.session_state['admin_categories'] = data.get('admin_categories', [])
        except:
            pass 

def save_data_and_config():
    data = {
        'df_merged': st.session_state.get('df_merged', pd.DataFrame()),
        'manager_col': st.session_state.get('manager_col', ""),
        'admin_cols': st.session_state.get('admin_cols', []),
        'admin_goals': st.session_state.get('admin_goals', {}),
        'admin_categories': st.session_state.get('admin_categories', [])
    }
    with open(CONFIG_FILE, 'wb') as f:
        pickle.dump(data, f)

if 'df_merged' not in st.session_state:
    st.session_state['df_merged'] = pd.DataFrame()
    st.session_state['manager_col'] = ""
    st.session_state['admin_cols'] = []
    st.session_state['admin_goals'] = {}
    st.session_state['admin_categories'] = []
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
menu = st.sidebar.radio("이동할 화면을 선택하세요", ["관리자 화면 (설정)", "매니저 화면 (로그인)"])

# ==========================================
# 4. 관리자 화면 (Admin View)
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    
    st.header("1. 데이터 파일 업로드 및 관리")
    
    if not st.session_state['df_merged'].empty:
        st.success(f"✅ 현재 **{len(st.session_state['df_merged'])}행**의 데이터가 저장되어 운영 중입니다.")
        st.markdown("새로운 달의 데이터를 올리시려면 아래 버튼을 눌러 기존 데이터를 삭제해주세요.")
        
        if st.button("🗑️ 기존 파일 데이터 삭제"):
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
                    st.write("**병합 기준 열 선택**")
                    col_key1, col_key2 = st.columns(2)
                    with col_key1:
                        key1 = st.selectbox("첫 번째 파일의 [설계사 코드] 열 선택", cols1)
                    with col_key2:
                        key2 = st.selectbox("두 번째 파일의 [설계사 코드] 열 선택", cols2)
                    
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
                save_data_and_config()
                st.success(f"로그인 열이 '{manager_col}'(으)로 설정되었습니다.")

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
            st.write("📌 **[현재 반영된 항목 목록]**")
            for i, item in enumerate(st.session_state['admin_cols']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    st.markdown(f"- **{item['col']}** ({item['type']}) | 조건: `{item['condition']}`")
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
            st.write("🎯 **[현재 반영된 목표 구간 목록]**")
            for g_col, tiers in list(st.session_state['admin_goals'].items()):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    st.markdown(f"- **{g_col}**: {tiers}")
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
                if cat_cond1.strip() and cat_cond1.strip() != '상관없음':
                    conditions.append({"col": cat_col1, "cond": cat_cond1.strip()})
                if cat_col2 != "(선택안함)" and cat_cond2.strip() and cat_cond2.strip() != '상관없음':
                    conditions.append({"col": cat_col2, "cond": cat_cond2.strip()})
                if cat_col3 != "(선택안함)" and cat_cond3.strip() and cat_cond3.strip() != '상관없음':
                    conditions.append({"col": cat_col3, "cond": cat_cond3.strip()})
                
                if conditions and cat_name.strip():
                    st.session_state['admin_categories'].append({
                        "conditions": conditions, "name": cat_name.strip()
                    })
                    save_data_and_config()
                    st.rerun()
                elif not cat_name.strip():
                    st.warning("분류명을 입력해주세요.")
            
        if st.session_state['admin_categories']:
            st.write("🏷️ **[현재 반영된 분류 기준 목록]**")
            for i, cat in enumerate(st.session_state['admin_categories']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    if 'conditions' in cat:
                        cond_strs = [f"`{c['col']}` {c['cond']}" for c in cat['conditions']]
                        cond_display = " AND ".join(cond_strs)
                    else:
                        cond_display = f"`{cat.get('col', '')}` {cat.get('condition', '')}"
                        
                    st.markdown(f"- 조건: **{cond_display}** ➡️ **[{cat['name']}]** 태그 부여")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_cat_{i}"):
                        st.session_state['admin_categories'].pop(i)
                        save_data_and_config()
                        st.rerun()
            
    else:
        st.info("👆 먼저 위에서 두 파일을 업로드하고 [데이터 병합 및 시스템에 저장]을 눌러주세요.")

# ==========================================
# 5. 매니저 화면 (Manager View)
# ==========================================
elif menu == "매니저 화면 (로그인)":
    st.title("👤 매니저 전용 실적 현황")
    
    if st.session_state['df_merged'].empty or not st.session_state['manager_col']:
        st.warning("현재 저장된 데이터가 없거나 관리자 설정이 완료되지 않았습니다.")
        st.stop()
        
    df = st.session_state['df_merged'].copy()
    manager_col = st.session_state['manager_col']
    
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
            st.error(f"❌ '{manager_col}' 열에서 매니저 코드 '{manager_code}'에 일치하는 데이터를 찾을 수 없습니다.")
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
            
            # 2. 목표 구간 처리
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

            # 3. 맞춤형 분류(태그) 설정
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
                            try:
                                my_df[c_col] = pd.to_numeric(my_df[c_col])
                            except ValueError:
                                pass
                            
                            mask = my_df.eval(f"`{c_col}` {c_cond}")
                            final_mask = final_mask & mask
                        except Exception as e:
                            final_mask = final_mask & False
                            
                    my_df.loc[final_mask, '맞춤분류'] += f"[{c_name}] "
                    
                if '맞춤분류' not in display_cols:
                    display_cols.insert(0, '맞춤분류')
            
            # ---------------------------------------------------------
            # ⭐ [신규 추가] 다중 정렬 로직 (1.분류 / 2.지사명 / 3.성별(성명))
            # ---------------------------------------------------------
            sort_keys = []
            
            # 1순위: 맞춤분류 (태그)
            if '맞춤분류' in my_df.columns:
                sort_keys.append('맞춤분류')
                
            # 2순위: 지사명 (컬럼 이름에 '지사명'이 들어간 첫 번째 열)
            ji_cols = [c for c in my_df.columns if '지사명' in c]
            if ji_cols:
                sort_keys.append(ji_cols[0])
                
            # 3순위: 성별 또는 성명/설계사명 (컬럼 이름에 포함된 첫 번째 열)
            gender_name_cols = [c for c in my_df.columns if '성별' in c or '설계사명' in c or '성명' in c]
            if gender_name_cols:
                sort_keys.append(gender_name_cols[0])
                
            # 정렬 키가 하나라도 모였으면 정렬 수행 (모두 오름차순/가나다순)
            if sort_keys:
                my_df = my_df.sort_values(by=sort_keys, ascending=[True] * len(sort_keys))
            # ---------------------------------------------------------
            
            # 최종 컬럼 중복 제거 및 디스플레이
            final_cols = list(dict.fromkeys(display_cols))
            
            if not final_cols:
                st.warning("관리자 화면에서 표시할 항목을 추가해주세요.")
            else:
                final_df = my_df[final_cols]
                st.dataframe(final_df, use_container_width=True)
