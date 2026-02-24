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
# 0. 메리츠 스타일 커스텀 CSS (디자인 및 가운데 정렬)
# ==========================================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
.toss-header {
    background-color: rgb(128, 0, 0);
    padding: 32px 40px;
    border-radius: 20px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
.toss-title {
    color: #ffffff !important; 
    font-size: 36px;
    font-weight: 800;
}
.toss-subtitle {
    color: #ffcccc !important; 
    font-size: 24px;
    font-weight: 700;
    margin-left: 10px;
}
.toss-desc {
    color: #f2f4f6 !important;
    font-size: 17px;
    margin-top: 12px;
}
/* 표 전체 가운데 정렬 및 디자인 */
[data-testid="stDataFrame"] div[data-testid="stTable"] th {
    background-color: #4e5968 !important;
    color: white !important;
    text-align: center !important;
}
[data-testid="stDataFrame"] td {
    text-align: center !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 설정 및 데이터 영구 저장 함수
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
        except: pass 

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
    st.session_state['manager_col'] = ""; st.session_state['manager_name_col'] = ""
    st.session_state['admin_cols'] = []; st.session_state['admin_goals'] = {}
    st.session_state['admin_categories'] = []; st.session_state['col_order'] = []
    load_data_and_config()

# ==========================================
# 2. 데이터 정제/조건 평가 함수
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

def safe_eval_condition(df, col, cond):
    """중복 열 문제를 방지하며 조건을 안전하게 평가합니다."""
    cond_clean = re.sub(r'(?<=\d),(?=\d)', '', cond).strip()
    try:
        # 중복 열이 있을 경우 첫 번째 열만 선택
        target_series = df[col]
        if isinstance(target_series, pd.DataFrame):
            target_series = target_series.iloc[:, 0]
            
        temp_s = target_series.astype(str).str.replace(',', '', regex=False)
        num_s = pd.to_numeric(temp_s, errors='coerce').fillna(0)
        
        eval_df = pd.DataFrame({"_tmp_target": num_s}, index=df.index)
        mask = eval_df.eval(f"`_tmp_target` {cond_clean}", engine='python')
        return mask.fillna(False).astype(bool)
    except:
        try:
            # 텍스트 비교 시도
            target_series = df[col]
            if isinstance(target_series, pd.DataFrame):
                target_series = target_series.iloc[:, 0]
            eval_df = pd.DataFrame({"_tmp_target": target_series}, index=df.index)
            mask = eval_df.eval(f"`_tmp_target` {cond}", engine='python')
            return mask.fillna(False).astype(bool)
        except:
            return pd.Series(False, index=df.index)

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
# 3. 사이드바
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
        if st.button("🗑️ 기존 파일 데이터 삭제"):
            st.session_state['df_merged'] = pd.DataFrame()
            save_data_and_config(); st.rerun()
    else:
        col_file1, col_file2 = st.columns(2)
        with col_file1: file1 = st.file_uploader("첫 번째 파일 업로드", type=['csv', 'xlsx'])
        with col_file2: file2 = st.file_uploader("두 번째 파일 업로드", type=['csv', 'xlsx'])
        if file1 and file2:
            try:
                with st.spinner("파일 읽는 중..."):
                    df1 = load_file_data(file1.getvalue(), file1.name)
                    df2 = load_file_data(file2.getvalue(), file2.name)
                with st.form("merge_form"):
                    c_k1, c_k2 = st.columns(2)
                    with c_k1: key1 = st.selectbox("첫 번째 파일 [설계사 코드] 열", df1.columns)
                    with c_k2: key2 = st.selectbox("두 번째 파일 [설계사 코드] 열", df2.columns)
                    if st.form_submit_button("병합 및 저장"):
                        df1['m_key1'] = df1[key1].apply(clean_key)
                        df2['m_key2'] = df2[key2].apply(clean_key)
                        # 병합 시 중복 열을 suffix로 처리
                        df_merged = pd.merge(df1, df2, left_on='m_key1', right_on='m_key2', how='outer', suffixes=('', '_중복'))
                        st.session_state['df_merged'] = df_merged
                        save_data_and_config(); st.success("저장 완료!"); st.rerun()
            except Exception as e: st.error(f"오류: {e}")

    if not st.session_state['df_merged'].empty:
        df = st.session_state['df_merged']
        av_cols = [c for c in df.columns if c not in ['m_key1', 'm_key2']]
        st.divider()
        st.header("2. 매니저 로그인 열 설정")
        col_m1, col_m2, col_m3 = st.columns([4, 4, 2])
        with col_m1: manager_col = st.selectbox("🔑 매니저 코드 열", av_cols, index=av_cols.index(st.session_state['manager_col']) if st.session_state['manager_col'] in av_cols else 0)
        with col_m2: manager_name_col = st.selectbox("👤 매니저 이름 열", av_cols, index=av_cols.index(st.session_state['manager_name_col']) if st.session_state['manager_name_col'] in av_cols else 0)
        if st.button("저장"):
            st.session_state['manager_col'] = manager_col; st.session_state['manager_name_col'] = manager_name_col
            save_data_and_config(); st.success("저장됨")

        st.divider()
        st.header("3. 표시 항목 및 필터")
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
        with c1: sel_c = st.selectbox("항목", av_cols, key="s3c")
        with c2: disp_n = st.text_input("표시명", key="s3n")
        with c3: c_type = st.radio("타입", ["텍스트", "숫자"], horizontal=True, key="s3t")
        with c4: cond = st.text_input("산식", key="s3cond")
        if st.button("➕ 추가"):
            st.session_state['admin_cols'].append({"col": sel_c, "display_name": disp_n if disp_n else sel_c, "type": c_type, "condition": cond})
            save_data_and_config(); st.rerun()
        for i, item in enumerate(st.session_state['admin_cols']):
            r1, r2 = st.columns([8, 2])
            with r1: st.write(f"- {item['display_name']} (원본: {item['col']}) | {item['condition']}")
            with r2: 
                if st.button("❌", key=f"d_c_{i}"): st.session_state['admin_cols'].pop(i); save_data_and_config(); st.rerun()

        st.divider()
        st.header("4. 목표 구간")
        c1, c2, c3 = st.columns([3, 5, 2])
        with c1: g_col = st.selectbox("항목", av_cols, key="s4c")
        with c2: g_tiers = st.text_input("구간 (예: 100000, 200000)", key="s4t")
        if st.button("➕ 구간 추가"):
            if g_tiers:
                st.session_state['admin_goals'][g_col] = sorted([float(x.strip()) for x in g_tiers.split(",") if x.strip().isdigit()])
                save_data_and_config(); st.rerun()
        for g, t in list(st.session_state['admin_goals'].items()):
            r1, r2 = st.columns([8, 2])
            with r1: st.write(f"- {g}: {t}")
            with r2: 
                if st.button("❌", key=f"d_g_{g}"): del st.session_state['admin_goals'][g]; save_data_and_config(); st.rerun()

        st.divider()
        st.header("5. 맞춤형 분류 (태그)")
        with st.form("tag_form"):
            col1, col2 = st.columns(2)
            with col1:
                tc1 = st.selectbox("기준 1", av_cols); tc2 = st.selectbox("기준 2", ["(없음)"] + av_cols); tc3 = st.selectbox("기준 3", ["(없음)"] + av_cols)
            with col2:
                tk1 = st.text_input("산식 1"); tk2 = st.text_input("산식 2"); tk3 = st.text_input("산식 3")
            t_name = st.text_input("태그 명칭")
            if st.form_submit_button("➕ 태그 추가"):
                conds = [{"col": tc1, "cond": tk1}]
                if tc2 != "(없음)" and tk2: conds.append({"col": tc2, "cond": tk2})
                if tc3 != "(없음)" and tk3: conds.append({"col": tc3, "cond": tk3})
                if t_name: st.session_state['admin_categories'].append({"conditions": conds, "name": t_name}); save_data_and_config(); st.rerun()
        for i, cat in enumerate(st.session_state['admin_categories']):
            r1, r2 = st.columns([8, 2])
            with r1: st.write(f"- {cat['name']}: {cat['conditions']}")
            with r2: 
                if st.button("❌", key=f"d_t_{i}"): st.session_state['admin_categories'].pop(i); save_data_and_config(); st.rerun()

        st.divider()
        st.header("6. 표시 순서 및 정렬")
        expected = []
        if st.session_state['admin_categories']: expected.append("맞춤분류")
        for item in st.session_state['admin_cols']: expected.append(item['display_name'])
        for g_col in st.session_state['admin_goals'].keys(): expected.extend([f"{g_col} 다음목표", f"{g_col} 부족금액"])
        valid_o = [c for c in st.session_state.get('col_order', []) if c in expected]
        for c in expected:
            if c not in valid_o: valid_o.append(c)
        st.session_state['col_order'] = valid_o
        for i, col_n in enumerate(st.session_state['col_order']):
            c1, c2, c3 = st.columns([8, 1, 1])
            with c1: st.write(f"{i+1}. {col_n}")
            with c2: 
                if st.button("🔼", key=f"up_{i}", disabled=(i==0)):
                    st.session_state['col_order'][i], st.session_state['col_order'][i-1] = st.session_state['col_order'][i-1], st.session_state['col_order'][i]
                    save_data_and_config(); st.rerun()
            with c3:
                if st.button("🔽", key=f"dn_{i}", disabled=(i==len(st.session_state['col_order'])-1)):
                    st.session_state['col_order'][i], st.session_state['col_order'][i+1] = st.session_state['col_order'][i+1], st.session_state['col_order'][i]
                    save_data_and_config(); st.rerun()

# ==========================================
# 5. 매니저 화면 (Manager View)
# ==========================================
elif menu == "매니저 화면 (로그인)":
    if st.session_state['df_merged'].empty:
        st.warning("데이터가 없습니다. 관리자 화면에서 업로드하세요."); st.stop()
    
    with st.form("login_form"):
        m_code = st.text_input("🔑 매니저 코드 입력", type="password")
        if st.form_submit_button("조회"):
            st.session_state['current_m'] = m_code
            
    if st.session_state.get('current_m'):
        df = st.session_state['df_merged'].copy()
        m_col = st.session_state['manager_col']
        df['s_key'] = df[m_col].apply(clean_key)
        m_code_clean = clean_key(st.session_state['current_m'])
        my_df = df[df['search_key'] == m_code_clean] if 'search_key' in df else df[df['s_key'] == m_code_clean].copy()
        if my_df.empty: my_df = df[df['s_key'].str.contains(m_code_clean, na=False)].copy()

        if my_df.empty: st.error("일치하는 데이터가 없습니다.")
        else:
            m_name = str(my_df[st.session_state['manager_name_col']].iloc[0]) if st.session_state['manager_name_col'] in my_df.columns else "매니저"
            st.markdown(f"<div class='toss-header'><h1 class='toss-title'>{m_name} <span class='toss-subtitle'>({m_code_clean})</span></h1><p class='toss-desc'>환영합니다! 산하 팀장분들의 실적 현황입니다. 🚀</p></div>", unsafe_allow_html=True)
            
            # (1) 맞춤분류(태그) 실행 - 에러 방지 처리 적용
            if st.session_state['admin_categories']:
                my_df['맞춤분류'] = ""
                for cat in st.session_state['admin_categories']:
                    final_mask = pd.Series(True, index=my_df.index)
                    for cond in cat['conditions']:
                        mask = safe_eval_condition(my_df, cond['col'], cond['cond'])
                        final_mask = final_mask & mask
                    my_df.loc[final_mask, '맞춤분류'] += f"[{cat['name']}] "
            
            # (2) 필터링 및 명칭 부여
            disp_cols = []
            if st.session_state['admin_categories']: disp_cols.append("맞춤분류")
            
            for item in st.session_state['admin_cols']:
                o_c, d_n = item['col'], item['display_name']
                if item['type'] == '숫자' and item['condition']:
                    my_df = my_df[safe_eval_condition(my_df, o_c, item['condition'])]
                my_df[d_n] = my_df[o_c]
                disp_cols.append(d_n)
            
            # (3) 목표 구간
            for g, tiers in st.session_state['admin_goals'].items():
                if g in my_df.columns:
                    target_s = my_df[g].iloc[:, 0] if isinstance(my_df[g], pd.DataFrame) else my_df[g]
                    val_s = pd.to_numeric(target_s.astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    def get_g(v):
                        for t in tiers:
                            if v < t: return pd.Series([f"{int(t/10000) if t%10000==0 else t/10000:g}만", t-v])
                        return pd.Series(["최고 달성", 0])
                    nt, sf = f"{g} 다음목표", f"{g} 부족금액"
                    my_df[[nt, sf]] = val_s.apply(get_g)
                    disp_cols.extend([nt, sf])

            # 정렬 및 출력
            final_df = my_df[list(dict.fromkeys(disp_cols))].copy()
            final_o = [c for c in st.session_state['col_order'] if c in final_df.columns]
            final_df = final_df[final_o]
            
            def fmt(v):
                try:
                    num = float(str(v).replace(',', ''))
                    if num == 0: return ""
                    return f"{int(num):,}" if num.is_integer() else f"{num:,.1f}"
                except: return "" if str(v) == "0" else v
            
            for c in final_df.columns:
                if '코드' not in c and '연도' not in c: final_df[c] = final_df[c].apply(fmt)

            # 표 가운데 정렬 강제화
            st.dataframe(
                final_df.style.set_properties(**{'text-align': 'center'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background-color', '#4e5968'), ('color', 'white'), ('text-align', 'center')]},
                    {'selector': 'td', 'props': [('text-align', 'center')]}
                ]),
                use_container_width=True, hide_index=True
            )
