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
# 0. 메리츠 스타일 커스텀 CSS
# ==========================================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
html, body, [class*="css"] {
    font-family: 'Pretendard', sans-serif;
}
/* 상단 매니저 박스: 메리츠 다크레드 */
.toss-header {
    background-color: rgb(128, 0, 0);
    padding: 32px 40px;
    border-radius: 20px;
    margin-bottom: 24px;
}
.toss-title { color: #ffffff !important; font-size: 36px; font-weight: 800; }
.toss-subtitle { color: #ffcccc !important; font-size: 24px; margin-left: 10px; }
.toss-desc { color: #f2f4f6 !important; font-size: 17px; margin-top: 12px; }

/* 표 헤더 디자인 및 가운데 정렬 */
[data-testid="stDataFrame"] th {
    background-color: #4e5968 !important;
    color: white !important;
    text-align: center !important;
}
/* 모든 셀 가운데 정렬 강제 */
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
    """중복 열을 방지하며 숫자를 안전하게 평가합니다."""
    cond_clean = re.sub(r'(?<=\d),(?=\d)', '', cond).strip()
    try:
        # 중복 열이 있는 경우 첫 번째 열만 타겟팅 (ValueError 방지 핵심)
        target_data = df[[col]].iloc[:, 0] if col in df.columns else pd.Series(0, index=df.index)
        
        temp_s = target_data.astype(str).str.replace(',', '', regex=False)
        num_s = pd.to_numeric(temp_s, errors='coerce').fillna(0)
        
        eval_df = pd.DataFrame({"_target": num_s}, index=df.index)
        mask = eval_df.eval(f"`_target` {cond_clean}", engine='python')
        return mask.fillna(False).astype(bool)
    except:
        try:
            target_data = df[[col]].iloc[:, 0]
            eval_df = pd.DataFrame({"_target": target_data}, index=df.index)
            mask = eval_df.eval(f"`_target` {cond}", engine='python')
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
# 3. 메뉴 구성
# ==========================================
st.sidebar.title("메뉴")
menu = st.sidebar.radio("화면 선택", ["매니저 화면 (로그인)", "관리자 화면 (설정)"])

# ==========================================
# 4. 관리자 화면
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    st.header("1. 데이터 파일 업로드")
    if not st.session_state['df_merged'].empty:
        st.success(f"✅ 데이터 저장 중 ({len(st.session_state['df_merged'])}행)")
        if st.button("🗑️ 기존 데이터 삭제"):
            st.session_state['df_merged'] = pd.DataFrame()
            save_data_and_config(); st.rerun()
    else:
        c_f1, c_f2 = st.columns(2)
        with c_f1: f1 = st.file_uploader("파일 1", type=['csv', 'xlsx'])
        with c_f2: f2 = st.file_uploader("파일 2", type=['csv', 'xlsx'])
        if f1 and f2:
            try:
                df1, df2 = load_file_data(f1.getvalue(), f1.name), load_file_data(f2.getvalue(), f2.name)
                with st.form("merge_form"):
                    k1 = st.selectbox("파일1 기준열", df1.columns)
                    k2 = st.selectbox("파일2 기준열", df2.columns)
                    if st.form_submit_button("병합 및 저장"):
                        df1['m_key1'] = df1[k1].apply(clean_key)
                        df2['m_key2'] = df2[k2].apply(clean_key)
                        # 중복 열 정리: 이름이 같으면 파일2의 열 이름을 강제 변경
                        df_merged = pd.merge(df1, df2, left_on='m_key1', right_on='m_key2', how='outer', suffixes=('', '_중복'))
                        st.session_state['df_merged'] = df_merged
                        save_data_and_config(); st.rerun()
            except Exception as e: st.error(f"오류: {e}")

    if not st.session_state['df_merged'].empty:
        df = st.session_state['df_merged']
        av_cols = [c for c in df.columns if c not in ['m_key1', 'm_key2']]
        st.divider()
        st.header("2. 로그인 설정")
        col_m1, col_m2 = st.columns(2)
        with col_m1: m_col = st.selectbox("매니저 코드 열", av_cols, index=av_cols.index(st.session_state['manager_col']) if st.session_state['manager_col'] in av_cols else 0)
        with col_m2: mn_col = st.selectbox("매니저 이름 열", av_cols, index=av_cols.index(st.session_state['manager_name_col']) if st.session_state['manager_name_col'] in av_cols else 0)
        if st.button("설정 저장"):
            st.session_state['manager_col'] = m_col; st.session_state['manager_name_col'] = mn_col
            save_data_and_config(); st.success("저장됨")

        st.divider()
        st.header("3. 표시 항목 및 필터")
        with st.form("add_col_form"):
            c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
            with c1: s_c = st.selectbox("항목", av_cols)
            with c2: d_n = st.text_input("표시명")
            with c3: t_p = st.radio("타입", ["텍스트", "숫자"])
            with c4: c_d = st.text_input("산식")
            if st.form_submit_button("➕ 추가"):
                st.session_state['admin_cols'].append({"col": s_c, "display_name": d_n if d_n else s_c, "type": t_p, "condition": c_d})
                save_data_and_config(); st.rerun()

        st.divider()
        st.header("4. 목표 구간")
        c1, c2 = st.columns([4, 6])
        with c1: g_c = st.selectbox("목표 항목", av_cols)
        with c2: g_t = st.text_input("구간 금액 (쉼표 구분)")
        if st.button("➕ 목표 추가"):
            st.session_state['admin_goals'][g_c] = sorted([float(x.strip()) for x in g_t.split(",") if x.strip().isdigit()])
            save_data_and_config(); st.rerun()

        st.divider()
        st.header("5. 맞춤형 분류")
        with st.form("tag_form_final"):
            c1, c2 = st.columns(2)
            with c1:
                tc1 = st.selectbox("기준1", av_cols); tc2 = st.selectbox("기준2", ["(없음)"]+av_cols); tc3 = st.selectbox("기준3", ["(없음)"]+av_cols)
            with c2:
                tk1 = st.text_input("산식1"); tk2 = st.text_input("산식2"); tk3 = st.text_input("산식3")
            t_n = st.text_input("태그명")
            if st.form_submit_button("➕ 태그 추가"):
                conds = [{"col": tc1, "cond": tk1}]
                if tc2 != "(없음)" and tk2: conds.append({"col": tc2, "cond": tk2})
                if tc3 != "(없음)" and tk3: conds.append({"col": tc3, "cond": tk3})
                st.session_state['admin_categories'].append({"conditions": conds, "name": t_n})
                save_data_and_config(); st.rerun()

# ==========================================
# 5. 매니저 화면
# ==========================================
elif menu == "매니저 화면 (로그인)":
    if st.session_state['df_merged'].empty: st.warning("데이터가 없습니다."); st.stop()
    
    with st.form("login"):
        m_code = st.text_input("🔑 매니저 코드", type="password")
        if st.form_submit_button("조회"): st.session_state['current_m'] = m_code
            
    if st.session_state.get('current_m'):
        df = st.session_state['df_merged'].copy()
        m_code_clean = clean_key(st.session_state['current_m'])
        df['_m_key'] = df[st.session_state['manager_col']].apply(clean_key)
        my_df = df[df['_m_key'] == m_code_clean].copy()
        
        if my_df.empty: st.error("일치하는 데이터가 없습니다.")
        else:
            m_name = str(my_df[st.session_state['manager_name_col']].iloc[0])
            st.markdown(f"<div class='toss-header'><h1 class='toss-title'>{m_name} <span class='toss-subtitle'>({m_code_clean})</span></h1><p class='toss-desc'>환영합니다! 산하 팀장분들의 실적 현황입니다. 🚀</p></div>", unsafe_allow_html=True)
            
            # (1) 분류 실행 (중복 열 방지 로직 적용)
            if st.session_state['admin_categories']:
                my_df['맞춤분류'] = ""
                for cat in st.session_state['admin_categories']:
                    final_mask = pd.Series(True, index=my_df.index)
                    for cond in cat['conditions']:
                        mask = safe_eval_condition(my_df, cond['col'], cond['cond'])
                        final_mask = final_mask & mask
                    # 중복 열 에러 방지용: '맞춤분류'가 단일 컬럼임을 보장
                    my_df.loc[final_mask, '맞춤분류'] += f"[{cat['name']}] "

            # (2) 필터 및 명칭
            disp_cols = []
            if '맞춤분류' in my_df.columns: disp_cols.append('맞춤분류')
            for item in st.session_state['admin_cols']:
                if item['type'] == '숫자' and item['condition']:
                    my_df = my_df[safe_eval_condition(my_df, item['col'], item['condition'])]
                my_df[item['display_name']] = my_df[item['col']]
                disp_cols.append(item['display_name'])

            # (3) 목표
            for g, tiers in st.session_state['admin_goals'].items():
                val_s = pd.to_numeric(my_df[g].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                def get_g(v):
                    for t in tiers:
                        if v < t: return pd.Series([f"{int(t/10000) if t%10000==0 else t/10000:g}만", t-v])
                    return pd.Series(["최고 달성", 0])
                nt, sf = f"{g} 다음목표", f"{g} 부족금액"
                my_df[[nt, sf]] = val_s.apply(get_g)
                disp_cols.extend([nt, sf])

            # (4) 최종 출력 및 포맷
            final_df = my_df[list(dict.fromkeys(disp_cols))].copy()
            # 정렬 순서 적용
            final_o = [c for c in st.session_state.get('col_order', []) if c in final_df.columns]
            final_df = final_df[[c for c in final_o] + [c for c in final_df.columns if c not in final_o]]

            def fmt_val(v):
                try:
                    num = float(str(v).replace(',', ''))
                    if num == 0: return ""
                    return f"{int(num):,}" if num.is_integer() else f"{num:,.1f}"
                except: return "" if str(v) == "0" else v

            for c in final_df.columns:
                if '코드' not in c and '연도' not in c: final_df[c] = final_df[c].apply(fmt_val)

            # 스타일링 (가운데 정렬 고정)
            st.dataframe(
                final_df.style.set_properties(**{'text-align': 'center'})
                .set_table_styles([
                    {'selector': 'th', 'props': [('background-color', '#4e5968'), ('color', 'white'), ('text-align', 'center')]},
                    {'selector': 'td', 'props': [('text-align', 'center')]}
                ]),
                use_container_width=True, hide_index=True
            )
