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
# 0. 메리츠 스타일 커스텀 CSS (디자인 전면 개편)
# ==========================================
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
/* 1. 상단 매니저 박스: 메리츠 다크레드 바탕 */
.toss-header {
    background-color: rgb(128, 0, 0);
    padding: 32px 40px;
    border-radius: 20px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}
/* 매니저 이름 흰색 강제 적용 */
.toss-title {
    color: #ffffff !important; 
    font-size: 36px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
}
/* 코드명 서브타이틀 */
.toss-subtitle {
    color: #ffcccc !important; 
    font-size: 24px;
    font-weight: 700;
    margin-left: 10px;
}
.toss-desc {
    color: #f2f4f6 !important;
    font-size: 17px;
    margin: 12px 0 0 0;
    font-weight: 500;
}

/* ===============================================
   실적 테이블 스타일 (HTML 테이블 전용)
   =============================================== */
.perf-table-wrap {
    width: 100%;
    overflow-x: auto;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    margin-top: 8px;
}
.perf-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    white-space: nowrap;
}
/* 헤더: 짙은 회색 배경 + 흰색 글씨 */
.perf-table thead th {
    background-color: #4e5968;
    color: #ffffff;
    font-weight: 700;
    text-align: center;
    padding: 10px 14px;
    border: 1px solid #3d4654;
    position: sticky;
    top: 0;
    z-index: 1;
}
/* 본문 셀: 가운데 정렬 */
.perf-table tbody td {
    text-align: center;
    padding: 8px 12px;
    border: 1px solid #e5e8eb;
}
/* 짝수 행 배경 */
.perf-table tbody tr:nth-child(even) {
    background-color: #f7f8fa;
}
/* 호버 효과 */
.perf-table tbody tr:hover {
    background-color: #eef1f6;
}
/* 헤더 클릭 정렬 커서 & 화살표 */
.perf-table thead th {
    cursor: pointer;
    user-select: none;
}
.perf-table thead th .sort-arrow {
    margin-left: 4px;
    font-size: 11px;
    opacity: 0.5;
}
.perf-table thead th .sort-arrow.active {
    opacity: 1;
}
/* 부족금액 강조: 다크레드 */
.shortfall-cell {
    color: rgb(128, 0, 0);
    font-weight: 700;
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
# 2. 데이터 정제 및 스마트 조건 평가 함수
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

# 숫자/텍스트 혼동 및 콤마 완벽 해결 평가 함수
def evaluate_condition(df, col, cond):
    cond_clean = re.sub(r'(?<=\d),(?=\d)', '', cond).strip()
    # ✅ 단일 = 를 == 로 자동 변환 (>=, <=, !=, == 는 건드리지 않음)
    cond_clean = re.sub(r'(?<![><!= ])=(?!=)', '==', cond_clean)
    try:
        temp_s = df[col].astype(str).str.replace(',', '', regex=False)
        num_s = pd.to_numeric(temp_s, errors='coerce')
        if num_s.isna().all() and not temp_s.replace('', np.nan).isna().all():
            raise ValueError("문자형 데이터입니다.")
        temp_df = pd.DataFrame({col: num_s.fillna(0)})
        mask = temp_df.eval(f"`{col}` {cond_clean}", engine='python')
        if isinstance(mask, pd.Series): return mask.fillna(False).astype(bool)
        else: return pd.Series(bool(mask), index=df.index)
    except Exception:
        try:
            mask = df.eval(f"`{col}` {cond_clean}", engine='python')
            if isinstance(mask, pd.Series): return mask.fillna(False).astype(bool)
            else: return pd.Series(bool(mask), index=df.index)
        except Exception:
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
# ★ HTML 테이블 렌더링 함수
# ==========================================
def render_html_table(df):
    """DataFrame을 짙은회색 헤더 + 가운데 정렬 + 헤더 클릭 정렬 HTML 테이블로 변환"""
    import uuid
    table_id = f"perf_{uuid.uuid4().hex[:8]}"
    shortfall_cols = set(c for c in df.columns if '부족금액' in c)

    # iframe 내부에서 독립 렌더링되므로 CSS를 직접 포함
    html = f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    body {{ margin: 0; padding: 0; font-family: 'Pretendard', -apple-system, 'Noto Sans KR', sans-serif; }}
    .perf-table-wrap {{ width: 100%; overflow-x: auto; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }}
    .perf-table {{ width: 100%; border-collapse: collapse; font-size: 14px; white-space: nowrap; }}
    .perf-table thead th {{
        background-color: #4e5968; color: #ffffff; font-weight: 700;
        text-align: center; padding: 10px 14px; border: 1px solid #3d4654;
        position: sticky; top: 0; z-index: 1;
        cursor: pointer; user-select: none;
    }}
    .perf-table thead th:hover {{ background-color: #3d4654; }}
    .perf-table thead th .sort-arrow {{ margin-left: 4px; font-size: 11px; opacity: 0.5; }}
    .perf-table thead th .sort-arrow.active {{ opacity: 1; }}
    .perf-table tbody td {{ text-align: center; padding: 8px 12px; border: 1px solid #e5e8eb; }}
    .perf-table tbody tr:nth-child(even) {{ background-color: #f7f8fa; }}
    .perf-table tbody tr:hover {{ background-color: #eef1f6; }}
    .shortfall-cell {{ color: rgb(128, 0, 0); font-weight: 700; }}
    </style>
    """

    html += f'<div class="perf-table-wrap"><table class="perf-table" id="{table_id}"><thead><tr>'
    for col in df.columns:
        html += f'<th onclick="sortTable(this)">{col} <span class="sort-arrow">▲▼</span></th>'
    html += '</tr></thead><tbody>'

    for _, row in df.iterrows():
        html += '<tr>'
        for col in df.columns:
            val = row[col]
            cell_val = "" if pd.isna(val) else str(val)
            if col in shortfall_cols and cell_val and cell_val != "":
                html += f'<td class="shortfall-cell">{cell_val}</td>'
            else:
                html += f'<td>{cell_val}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'

    # JavaScript: 헤더 클릭 시 오름차순/내림차순 토글 정렬
    html += f"""
    <script>
    var sortState = {{}};
    function sortTable(th) {{
        var table = document.getElementById("{table_id}");
        var tbody = table.querySelector("tbody");
        var rows = Array.from(tbody.querySelectorAll("tr"));
        var headers = Array.from(table.querySelectorAll("thead th"));
        var colIdx = headers.indexOf(th);
        if (colIdx < 0) return;

        var asc = sortState[colIdx] !== true;
        sortState = {{}};
        sortState[colIdx] = asc;

        rows.sort(function(a, b) {{
            var aText = a.cells[colIdx].textContent.trim();
            var bText = b.cells[colIdx].textContent.trim();
            var aNum = parseFloat(aText.replace(/,/g, "").replace(/▲|▼/g, ""));
            var bNum = parseFloat(bText.replace(/,/g, "").replace(/▲|▼/g, ""));
            if (aText === "" && bText === "") return 0;
            if (aText === "") return 1;
            if (bText === "") return -1;
            if (!isNaN(aNum) && !isNaN(bNum)) {{
                return asc ? aNum - bNum : bNum - aNum;
            }}
            return asc ? aText.localeCompare(bText, 'ko') : bText.localeCompare(aText, 'ko');
        }});

        rows.forEach(function(r) {{ tbody.appendChild(r); }});

        headers.forEach(function(h, i) {{
            var arrow = h.querySelector(".sort-arrow");
            if (i === colIdx) {{
                arrow.textContent = asc ? "▲" : "▼";
                arrow.className = "sort-arrow active";
            }} else {{
                arrow.textContent = "▲▼";
                arrow.className = "sort-arrow";
            }}
        }});
    }}
    </script>
    """
    return html

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
        with col_file1: file1 = st.file_uploader("첫 번째 파일 업로드", type=['csv', 'xlsx'])
        with col_file2: file2 = st.file_uploader("두 번째 파일 업로드", type=['csv', 'xlsx'])
            
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
            st.write(""); st.write("")
            if st.button("저장", key="btn_save_manager"):
                st.session_state['manager_col'] = manager_col
                st.session_state['manager_name_col'] = manager_name_col
                save_data_and_config()
                st.success("로그인 및 이름 열 설정이 저장되었습니다.")

        st.divider()

        # ========================================
        st.header("3. 표시할 데이터 항목 및 필터 추가")
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
        with c1: sel_col = st.selectbox("항목 선택", available_columns, key="sec3_col")
        with c2: display_name = st.text_input("표시 명칭 (선택)", placeholder="미입력시 원본유지", key="sec3_disp")
        with c3: col_type = st.radio("데이터 타입", ["텍스트", "숫자"], horizontal=True, key="sec3_type")
        with c4: condition = st.text_input("산식 (예: >= 500,000)", key="sec3_cond")
        with c5:
            st.write(""); st.write("")
            if st.button("➕ 추가", key="btn_add_col"):
                final_display_name = display_name.strip() if display_name.strip() else sel_col
                st.session_state['admin_cols'].append({
                    "col": sel_col, "display_name": final_display_name, "type": col_type, "condition": condition if col_type == "숫자" else ""
                })
                save_data_and_config()
                st.rerun()

        if st.session_state['admin_cols']:
            for i, item in enumerate(st.session_state['admin_cols']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    disp = item.get('display_name', item['col'])
                    st.markdown(f"- 📄 원본: `{item['col']}` ➡️ **화면 표시: [{disp}]** ({item['type']}) | 조건: `{item['condition']}`")
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
            st.write(""); st.write("")
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
                cat_cond1 = st.text_input("1. 산식 (예: >= 500000, 텍스트는 == '정상')")
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
        expected_cols = []
        if st.session_state['admin_categories']: expected_cols.append("맞춤분류")
        for item in st.session_state['admin_cols']: expected_cols.append(item.get('display_name', item['col']))
        for g_col in st.session_state['admin_goals'].keys(): expected_cols.extend([f"{g_col} 다음목표", f"{g_col} 부족금액"])
            
        current_order = st.session_state.get('col_order', [])
        valid_order = [c for c in current_order if c in expected_cols]
        for c in expected_cols:
            if c not in valid_order:
                valid_order.append(c)
                
        if st.session_state.get('col_order', []) != valid_order:
            st.session_state['col_order'] = valid_order
            save_data_and_config()

        if st.session_state['col_order']:
            st.write("---")
            for i, col_name in enumerate(st.session_state['col_order']):
                c1, c2, c3 = st.columns([8, 1, 1])
                with c1: st.markdown(f"**{i+1}.** {col_name}")
                with c2:
                    if st.button("🔼", key=f"up_{i}", disabled=(i == 0)):
                        st.session_state['col_order'][i], st.session_state['col_order'][i-1] = st.session_state['col_order'][i-1], st.session_state['col_order'][i]
                        save_data_and_config()
                        st.rerun()
                with c3:
                    if st.button("🔽", key=f"down_{i}", disabled=(i == len(st.session_state['col_order']) - 1)):
                        st.session_state['col_order'][i], st.session_state['col_order'][i+1] = st.session_state['col_order'][i+1], st.session_state['col_order'][i]
                        save_data_and_config()
                        st.rerun()
            st.write("---")
            
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
            manager_name = str(my_df[manager_name_col].iloc[0]) if manager_name_col in my_df.columns else "매니저"
            
            st.markdown(f"""
            <div class='toss-header'>
                <h1 class='toss-title'>{manager_name} <span class='toss-subtitle'>({manager_code_clean})</span></h1>
                <p class='toss-desc'>환영합니다! 산하 팀장분들의 실적 현황입니다. 🚀</p>
            </div>
            """, unsafe_allow_html=True)
            
            display_cols = []
            
            # -------------------------------------------------------------------
            # ⭐ (1) 가장 먼저 "맞춤분류(태그)" 평가 실행 (원본 데이터 손실 전)
            # -------------------------------------------------------------------
            if st.session_state['admin_categories']:
                if '맞춤분류' not in my_df.columns:
                    my_df['맞춤분류'] = ""
                for cat in st.session_state['admin_categories']:
                    c_name = cat.get('name', '')
                    final_mask = pd.Series(True, index=my_df.index)
                    cond_list = cat.get('conditions', [{'col': cat.get('col'), 'cond': cat.get('condition')}])
                    
                    for cond_info in cond_list:
                        if not cond_info.get('col'): continue
                        mask = evaluate_condition(my_df, cond_info['col'], cond_info['cond'])
                        final_mask = final_mask & mask
                        
                    my_df.loc[final_mask, '맞춤분류'] += f"[{c_name}] "
                display_cols.append('맞춤분류')
            
            # -------------------------------------------------------------------
            # (2) 일반 항목 필터 및 데이터 삭제 실행
            # -------------------------------------------------------------------
            for item in st.session_state['admin_cols']:
                orig_col = item['col']
                disp_col = item.get('display_name', orig_col)
                
                if item['type'] == '숫자' and item['condition']:
                    mask = evaluate_condition(my_df, orig_col, item['condition'])
                    my_df = my_df[mask]
                
                my_df[disp_col] = my_df[orig_col]
                display_cols.append(disp_col)
            
            # -------------------------------------------------------------------
            # (3) 목표 구간 처리 (20만 등 텍스트 변환)
            # -------------------------------------------------------------------
            for g_col, tiers in st.session_state['admin_goals'].items():
                if g_col in my_df.columns:
                    cleaned_str = my_df[g_col].astype(str).str.replace(',', '', regex=False)
                    my_df[g_col] = pd.to_numeric(cleaned_str, errors='coerce').fillna(0)
                    
                    def calc_shortfall(val):
                        for t in tiers:
                            if val < t:
                                if t % 10000 == 0: tier_str = f"{int(t)//10000}만"
                                else: tier_str = f"{t/10000:g}만"
                                return pd.Series([tier_str, t - val])
                        return pd.Series(["최고 구간 달성", 0])
                    
                    next_target_col = f"{g_col} 다음목표"
                    shortfall_col = f"{g_col} 부족금액"
                    
                    my_df[[next_target_col, shortfall_col]] = my_df[g_col].apply(calc_shortfall)
                    if next_target_col not in display_cols:
                        display_cols.extend([next_target_col, shortfall_col])

            # 3. 데이터 정렬
            sort_keys = []
            if '맞춤분류' in my_df.columns: sort_keys.append('맞춤분류')
            ji_cols = [c for c in display_cols if '지사명' in c]
            if not ji_cols: ji_cols = [c for c in my_df.columns if '지사명' in c]
            if ji_cols: sort_keys.append(ji_cols[0])
            gender_name_cols = [c for c in display_cols if '성별' in c or '설계사명' in c or '성명' in c or '이름' in c or '팀장명' in c]
            if not gender_name_cols: gender_name_cols = [c for c in my_df.columns if '성별' in c or '설계사명' in c or '성명' in c or '팀장명' in c]
            if gender_name_cols: sort_keys.append(gender_name_cols[0])
            if sort_keys:
                my_df = my_df.sort_values(by=sort_keys, ascending=[True] * len(sort_keys))
            
            # 4. 사용자 지정 순서 정렬
            final_cols = list(dict.fromkeys(display_cols))
            ordered_final_cols = []
            for c in st.session_state.get('col_order', []):
                if c in final_cols: ordered_final_cols.append(c)
            for c in final_cols:
                if c not in ordered_final_cols: ordered_final_cols.append(c)
                    
            if not ordered_final_cols:
                st.warning("관리자 화면에서 표시할 항목을 추가해주세요.")
            else:
                final_df = my_df[ordered_final_cols].copy()
                
                # 5. 세 자리 콤마(,) 포맷팅 및 [0값 빈칸 숨김 처리]
                for c in final_df.columns:
                    if '코드' not in c and '연도' not in c:
                        def format_with_comma_and_hide_zero(val):
                            try:
                                if pd.isna(val) or str(val).strip() == "": return ""
                                clean_val = str(val).replace(',', '')
                                num = float(clean_val)
                                if num == 0: return ""
                                if num.is_integer(): return f"{int(num):,}"
                                return f"{num:,.1f}"
                            except:
                                if str(val).strip() == "0" or str(val).strip() == "0.0": return ""
                                return val
                        
                        final_df[c] = final_df[c].apply(format_with_comma_and_hide_zero)
                
                # 6. ★ HTML 테이블로 렌더링 (짙은 회색 헤더 + 흰색 글씨 + 가운데 정렬)
                import streamlit.components.v1 as components
                table_html = render_html_table(final_df)
                # 행 수 기반 높이 자동 계산 (헤더 45px + 행당 38px + 여유 20px)
                table_height = min(45 + len(final_df) * 38 + 20, 2000)
                components.html(table_html, height=table_height, scrolling=True)
