import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import re
import io
import os
import pickle
import uuid

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
/* Streamlit 메인 영역 패딩 최소화 → 화면 폭 최대 활용 */
.block-container {
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}
/* iframe(테이블) 전체 폭 사용 */
iframe {
    width: 100% !important;
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
            if not isinstance(data, dict):
                raise ValueError("Invalid config format")
            
            df = data.get('df_merged', pd.DataFrame())
            st.session_state['df_merged'] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
            st.session_state['manager_col'] = str(data.get('manager_col', ""))
            st.session_state['manager_name_col'] = str(data.get('manager_name_col', ""))
            st.session_state['manager_col2'] = str(data.get('manager_col2', ""))
            st.session_state['admin_cols'] = data.get('admin_cols', []) if isinstance(data.get('admin_cols'), list) else []
            st.session_state['admin_goals'] = data.get('admin_goals', [])
            # 기존 dict 형태 → list 형태 자동 변환
            if isinstance(st.session_state['admin_goals'], dict):
                st.session_state['admin_goals'] = [
                    {"target_col": k, "ref_col": "", "tiers": v} 
                    for k, v in st.session_state['admin_goals'].items()
                ]
            st.session_state['admin_categories'] = data.get('admin_categories', []) if isinstance(data.get('admin_categories'), list) else []
            st.session_state['col_order'] = data.get('col_order', []) if isinstance(data.get('col_order'), list) else []
            st.session_state['merge_key1_col'] = str(data.get('merge_key1_col', ''))
            st.session_state['merge_key2_col'] = str(data.get('merge_key2_col', ''))
            st.session_state['col_groups'] = data.get('col_groups', []) if isinstance(data.get('col_groups'), list) else []
            
            # 기존 admin_cols에 fallback_col 키가 없으면 추가
            for item in st.session_state['admin_cols']:
                if 'fallback_col' not in item:
                    item['fallback_col'] = ''
        except Exception:
            try:
                os.remove(CONFIG_FILE)
            except Exception:
                pass
            _reset_session_state()

def _reset_session_state():
    st.session_state['df_merged'] = pd.DataFrame()
    st.session_state['manager_col'] = ""
    st.session_state['manager_name_col'] = ""
    st.session_state['manager_col2'] = ""
    st.session_state['admin_cols'] = []
    st.session_state['admin_goals'] = []
    st.session_state['admin_categories'] = []
    st.session_state['col_order'] = []
    st.session_state['merge_key1_col'] = ''
    st.session_state['merge_key2_col'] = ''
    st.session_state['col_groups'] = []

def has_data():
    """df_merged가 유효한 DataFrame이고 비어있지 않은지 확인"""
    df = st.session_state.get('df_merged', None)
    return isinstance(df, pd.DataFrame) and not df.empty

def save_data_and_config():
    data = {
        'df_merged': st.session_state.get('df_merged', pd.DataFrame()),
        'manager_col': st.session_state.get('manager_col', ""),
        'manager_name_col': st.session_state.get('manager_name_col', ""),
        'manager_col2': st.session_state.get('manager_col2', ""),
        'admin_cols': st.session_state.get('admin_cols', []),
        'admin_goals': st.session_state.get('admin_goals', []),
        'admin_categories': st.session_state.get('admin_categories', []),
        'col_order': st.session_state.get('col_order', []),
        'merge_key1_col': st.session_state.get('merge_key1_col', ''),
        'merge_key2_col': st.session_state.get('merge_key2_col', ''),
        'col_groups': st.session_state.get('col_groups', []),
    }
    with open(CONFIG_FILE, 'wb') as f:
        pickle.dump(data, f)

if 'df_merged' not in st.session_state:
    _reset_session_state()
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
def render_html_table(df, col_groups=None):
    """DataFrame을 틀 고정 + 그룹 헤더 + 정렬 + 반응형 HTML 테이블로 변환"""
    table_id = f"perf_{uuid.uuid4().hex[:8]}"
    num_cols = len(df.columns)
    shortfall_cols = set(c for c in df.columns if '부족금액' in c)
    col_groups = col_groups or []
    
    # 그룹 헤더 존재 여부
    has_groups = len(col_groups) > 0
    
    # 좌측 고정할 열 개수 자동 판단
    freeze_keywords = ['맞춤분류', '설계사', '성명', '이름', '팀장', '대리점']
    freeze_count = 0
    for i, col in enumerate(df.columns):
        if any(kw in col for kw in freeze_keywords):
            freeze_count = i + 1
    freeze_count = min(freeze_count, 4)

    base_font = max(11, 15 - num_cols // 3)
    
    # 그룹 매핑: 각 컬럼이 어떤 그룹에 속하는지
    col_to_group = {}
    for grp in col_groups:
        for c in grp['cols']:
            col_to_group[c] = grp['name']
    
    html = f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; font-family: 'Pretendard', -apple-system, 'Noto Sans KR', sans-serif; }}
    
    .perf-table-wrap {{
        width: 100%;
        max-height: 85vh;
        overflow: auto;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        position: relative;
    }}
    .perf-table {{
        width: max-content;
        min-width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        white-space: nowrap;
        font-size: {base_font}px;
    }}
    
    /* 헤더 공통 */
    .perf-table thead th {{
        background-color: #4e5968; color: #ffffff; font-weight: 700;
        text-align: center; padding: 8px 10px; border: 1px solid #3d4654;
        position: sticky; z-index: 2;
        white-space: nowrap;
    }}
    /* 그룹 헤더 행 (1행) */
    .perf-table thead tr.group-row th {{
        top: 0;
        cursor: default;
    }}
    .perf-table thead tr.group-row th.group-label {{
        background-color: #364152;
        font-size: {max(11, base_font)}px;
        letter-spacing: 0.5px;
    }}
    /* 컬럼 헤더 행 (2행 또는 1행) */
    .perf-table thead tr.col-row th {{
        top: {"36px" if has_groups else "0"};
        cursor: pointer;
        user-select: none;
    }}
    .perf-table thead th:hover {{ background-color: #3d4654; }}
    .perf-table thead th .sort-arrow {{ margin-left: 3px; font-size: 10px; opacity: 0.5; }}
    .perf-table thead th .sort-arrow.active {{ opacity: 1; }}
    
    /* 본문 셀 */
    .perf-table tbody td {{
        text-align: center; padding: 6px 10px;
        border: 1px solid #e5e8eb; white-space: nowrap;
        background-color: #ffffff;
    }}
    .perf-table tbody tr:nth-child(even) td {{ background-color: #f7f8fa; }}
    .perf-table tbody tr:hover td {{ background-color: #eef1f6; }}
    .shortfall-cell {{ color: rgb(128, 0, 0); font-weight: 700; }}
    
    /* 좌측 고정 열 */
    .col-freeze {{ position: sticky; z-index: 1; }}
    thead th.col-freeze {{ z-index: 3; }}
    .col-freeze-last {{ box-shadow: 2px 0 5px rgba(0,0,0,0.08); }}
    
    @media (max-width: 1200px) {{
        .perf-table {{ font-size: {max(10, 13 - num_cols // 3)}px; }}
        .perf-table thead th, .perf-table tbody td {{ padding: 5px 6px; }}
    }}
    @media (max-width: 768px) {{
        .perf-table {{ font-size: {max(9, 11 - num_cols // 4)}px; }}
        .perf-table thead th, .perf-table tbody td {{ padding: 4px 4px; }}
    }}
    </style>
    """

    columns = list(df.columns)
    
    html += f'<div class="perf-table-wrap" id="wrap_{table_id}"><table class="perf-table" id="{table_id}"><thead>'
    
    # ── 그룹 헤더 행 (1행) ──
    if has_groups:
        html += '<tr class="group-row">'
        i = 0
        while i < len(columns):
            col = columns[i]
            grp_name = col_to_group.get(col, None)
            
            # 고정 열 CSS
            freeze_cls = ""
            if i < freeze_count:
                freeze_cls = "col-freeze"
                if i == freeze_count - 1:
                    freeze_cls += " col-freeze-last"
            
            if grp_name:
                # 같은 그룹의 연속 컬럼 수 세기
                span = 0
                for j in range(i, len(columns)):
                    if col_to_group.get(columns[j]) == grp_name:
                        span += 1
                    else:
                        break
                html += f'<th class="group-label {freeze_cls}" colspan="{span}" data-col="{i}">{grp_name}</th>'
                i += span
            else:
                # 그룹 없는 컬럼은 2행 병합 (rowspan)
                html += f'<th class="{freeze_cls}" rowspan="2" data-col="{i}" onclick="sortTable(this)">{col} <span class="sort-arrow">▲▼</span></th>'
                i += 1
        html += '</tr>'
    
    # ── 컬럼 헤더 행 ──
    html += '<tr class="col-row">'
    for i, col in enumerate(columns):
        # 그룹 헤더가 있고, 이 컬럼이 그룹에 속하지 않으면 이미 rowspan으로 처리됨
        if has_groups and col not in col_to_group:
            continue
        
        freeze_cls = ""
        if i < freeze_count:
            freeze_cls = "col-freeze"
            if i == freeze_count - 1:
                freeze_cls += " col-freeze-last"
        html += f'<th class="{freeze_cls}" data-col="{i}" onclick="sortTable(this)">{col} <span class="sort-arrow">▲▼</span></th>'
    html += '</tr></thead><tbody>'

    # ── 본문 행 ──
    for _, row in df.iterrows():
        html += '<tr>'
        for i, col in enumerate(columns):
            val = row[col]
            cell_val = "" if pd.isna(val) else str(val)
            freeze_cls = ""
            if i < freeze_count:
                freeze_cls = "col-freeze"
                if i == freeze_count - 1:
                    freeze_cls += " col-freeze-last"
            extra_cls = " shortfall-cell" if (col in shortfall_cols and cell_val and cell_val != "") else ""
            html += f'<td class="{freeze_cls}{extra_cls}" data-col="{i}">{cell_val}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'

    # JavaScript
    html += f"""
    <script>
    var FREEZE_COUNT = {freeze_count};
    
    function applyFreezePositions() {{
        var table = document.getElementById("{table_id}");
        if (!table || FREEZE_COUNT === 0) return;
        // 컬럼 행에서 폭 측정 (col-row의 th 또는 tbody 첫 행)
        var firstRow = table.querySelector("tbody tr");
        if (!firstRow) return;
        var leftPos = [];
        var cumLeft = 0;
        for (var i = 0; i < FREEZE_COUNT; i++) {{
            leftPos.push(cumLeft);
            if (firstRow.cells[i]) cumLeft += firstRow.cells[i].offsetWidth;
        }}
        var allCells = table.querySelectorAll(".col-freeze");
        allCells.forEach(function(cell) {{
            var colIdx = parseInt(cell.getAttribute("data-col"));
            if (!isNaN(colIdx) && colIdx < leftPos.length) {{
                cell.style.left = leftPos[colIdx] + "px";
            }}
        }});
    }}
    
    function autoResize() {{
        var wrap = document.getElementById("wrap_{table_id}");
        if (window.frameElement) {{
            var viewH = window.parent.innerHeight || 900;
            var targetH = Math.min(wrap.scrollHeight + 4, Math.round(viewH * 0.85));
            window.frameElement.style.height = targetH + "px";
        }}
    }}
    
    window.addEventListener('load', function() {{ applyFreezePositions(); autoResize(); }});
    window.addEventListener('resize', function() {{ applyFreezePositions(); autoResize(); }});

    var sortState = {{}};
    function sortTable(th) {{
        var table = document.getElementById("{table_id}");
        var tbody = table.querySelector("tbody");
        var rows = Array.from(tbody.querySelectorAll("tr"));
        var colIdx = parseInt(th.getAttribute("data-col"));
        if (isNaN(colIdx)) return;

        var asc = sortState[colIdx] !== true;
        sortState = {{}};
        sortState[colIdx] = asc;

        rows.sort(function(a, b) {{
            var aText = a.cells[colIdx].textContent.trim();
            var bText = b.cells[colIdx].textContent.trim();
            var aNum = parseFloat(aText.replace(/,/g, "").replace(/[▲▼]/g, ""));
            var bNum = parseFloat(bText.replace(/,/g, "").replace(/[▲▼]/g, ""));
            if (aText === "" && bText === "") return 0;
            if (aText === "") return 1;
            if (bText === "") return -1;
            if (!isNaN(aNum) && !isNaN(bNum)) return asc ? aNum - bNum : bNum - aNum;
            return asc ? aText.localeCompare(bText, 'ko') : bText.localeCompare(aText, 'ko');
        }});
        rows.forEach(function(r) {{ tbody.appendChild(r); }});
        
        // 모든 헤더 행의 정렬 화살표 업데이트
        table.querySelectorAll("thead th").forEach(function(h) {{
            var hIdx = parseInt(h.getAttribute("data-col"));
            var arrow = h.querySelector(".sort-arrow");
            if (!arrow) return;
            if (hIdx === colIdx) {{
                arrow.textContent = asc ? "▲" : "▼";
                arrow.className = "sort-arrow active";
            }} else {{
                arrow.textContent = "▲▼";
                arrow.className = "sort-arrow";
            }}
        }});
        setTimeout(autoResize, 50);
    }}
    </script>
    """
    return html

# ==========================================
# 3. 사이드바 (메뉴 선택)
# ==========================================
st.sidebar.title("메뉴")
menu = st.sidebar.radio("이동할 화면을 선택하세요", ["매니저 화면 (로그인)", "관리자 화면 (설정)"])
st.sidebar.divider()
if st.sidebar.button("🔄 시스템 초기화 (오류 시)", type="secondary"):
    try:
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
    except Exception:
        pass
    _reset_session_state()
    st.rerun()

# ==========================================
# 4. 관리자 화면 (Admin View)
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    
    ADMIN_PASSWORD = "meritz0085"
    
    if not st.session_state.get('admin_authenticated', False):
        with st.form("admin_login_form"):
            admin_pw = st.text_input("🔒 관리자 비밀번호를 입력하세요", type="password")
            submit_pw = st.form_submit_button("로그인")
            if submit_pw:
                if admin_pw == ADMIN_PASSWORD:
                    st.session_state['admin_authenticated'] = True
                    st.rerun()
                else:
                    st.error("❌ 비밀번호가 일치하지 않습니다.")
        st.stop()
    
    st.header("1. 데이터 파일 업로드 및 관리")
    if has_data():
        st.success(f"✅ 현재 **{len(st.session_state['df_merged'])}행**의 데이터가 운영 중입니다. 새 파일을 업로드하면 데이터만 교체됩니다 (설정 유지).")
    
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
            
            # 이전에 저장된 merge key가 있으면 자동 선택
            prev_key1 = st.session_state.get('merge_key1_col', '')
            prev_key2 = st.session_state.get('merge_key2_col', '')
            idx1 = cols1.index(prev_key1) if prev_key1 in cols1 else 0
            idx2 = cols2.index(prev_key2) if prev_key2 in cols2 else 0
            
            with st.form("merge_form"):
                col_key1, col_key2 = st.columns(2)
                with col_key1: key1 = st.selectbox("첫 번째 파일의 [설계사 코드] 열 선택", cols1, index=idx1)
                with col_key2: key2 = st.selectbox("두 번째 파일의 [설계사 코드] 열 선택", cols2, index=idx2)
                
                submit_merge = st.form_submit_button("🔄 데이터 병합 및 교체 (설정 유지)")
                if submit_merge:
                    with st.spinner("데이터를 병합하고 저장 중입니다..."):
                        df1['merge_key1'] = df1[key1].apply(clean_key)
                        df2['merge_key2'] = df2[key2].apply(clean_key)
                        df_merged = pd.merge(df1, df2, left_on='merge_key1', right_on='merge_key2', how='outer', suffixes=('_파일1', '_파일2'))
                        
                        # ✅ suffix로 분리된 동일 열을 자동 통합 (coalesce)
                        cols_1 = [c for c in df_merged.columns if c.endswith('_파일1')]
                        for c1 in cols_1:
                            base = c1.replace('_파일1', '')
                            c2 = base + '_파일2'
                            if c2 in df_merged.columns:
                                df_merged[base] = df_merged[c1].combine_first(df_merged[c2])
                                df_merged.drop(columns=[c1, c2], inplace=True)
                        
                        # ✅ 두 파일의 merge key를 통합한 검색용 키 생성
                        df_merged['_unified_search_key'] = df_merged['merge_key1'].combine_first(df_merged['merge_key2'])
                        
                        # merge key 선택값 저장 (다음 업로드 시 자동 선택)
                        st.session_state['merge_key1_col'] = key1
                        st.session_state['merge_key2_col'] = key2
                        st.session_state['df_merged'] = df_merged
                        
                        # ✅ 기존 설정 검증 - 사라진 열이 있는 항목만 제거, 나머지 유지
                        new_cols = [c for c in df_merged.columns if c not in ['merge_key1', 'merge_key2']]
                        
                        # manager_col / manager_name_col 검증
                        if st.session_state['manager_col'] not in new_cols:
                            st.session_state['manager_col'] = ""
                        if st.session_state.get('manager_col2', '') and st.session_state['manager_col2'] not in new_cols:
                            st.session_state['manager_col2'] = ""
                        if st.session_state['manager_name_col'] not in new_cols:
                            st.session_state['manager_name_col'] = ""
                        
                        # admin_cols 검증 - 열이 살아있는 항목만 유지, fallback도 검증
                        valid_admin_cols = []
                        for item in st.session_state['admin_cols']:
                            if item['col'] in new_cols:
                                if item.get('fallback_col') and item['fallback_col'] not in new_cols:
                                    item['fallback_col'] = ''
                                valid_admin_cols.append(item)
                        st.session_state['admin_cols'] = valid_admin_cols
                        
                        # admin_goals 검증 (list 형태)
                        goals = st.session_state.get('admin_goals', [])
                        if isinstance(goals, dict):
                            goals = [{"target_col": k, "ref_col": "", "tiers": v} for k, v in goals.items()]
                        valid_goals = []
                        for goal in goals:
                            if goal['target_col'] in new_cols:
                                if goal.get('ref_col') and goal['ref_col'] not in new_cols:
                                    goal['ref_col'] = ''
                                valid_goals.append(goal)
                        st.session_state['admin_goals'] = valid_goals
                        
                        # admin_categories 검증 - 모든 조건 열이 존재하는 것만 유지
                        valid_cats = []
                        for cat in st.session_state['admin_categories']:
                            cond_list = cat.get('conditions', [])
                            if all(c.get('col', '') in new_cols for c in cond_list):
                                valid_cats.append(cat)
                        st.session_state['admin_categories'] = valid_cats
                        
                        # col_groups는 display name 기반이므로 유효한 항목만 보정
                        # (section 6에서 col_order 재계산 시 자동 정리됨)
                        
                        save_data_and_config()
                        st.success(f"✅ 데이터 교체 완료! 총 {len(df_merged)}행 | 기존 설정이 유지되었습니다.")
                        st.rerun()
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

    st.divider()
    
    # ✅ 설정 검증 경고 표시 (열이 사라진 경우)
    if has_data():
        warnings = []
        if not st.session_state['manager_col']:
            warnings.append("⚠️ **매니저 코드 열**이 설정되지 않았습니다. 아래 2번에서 다시 선택해주세요.")
        if not st.session_state['manager_name_col']:
            warnings.append("⚠️ **매니저 이름 열**이 설정되지 않았습니다. 아래 2번에서 다시 선택해주세요.")
        for w in warnings:
            st.warning(w)
        df = st.session_state['df_merged']
        available_columns = [c for c in df.columns if c not in ['merge_key1', 'merge_key2', '_unified_search_key']]
        
        # ========================================
        st.header("2. 매니저 로그인 및 이름 표시 열 설정")
        st.caption("두 파일의 매니저 코드 열 이름이 다른 경우, 보조 열을 추가 선택하면 양쪽 모두 검색됩니다.")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            manager_col = st.selectbox("🔑 로그인 [매니저 코드] 열 (파일1)", available_columns, 
                                       index=available_columns.index(st.session_state['manager_col']) if st.session_state['manager_col'] in available_columns else 0)
        with col_m2:
            manager_col2_options = ["(없음 - 단일 열 사용)"] + available_columns
            prev_col2 = st.session_state.get('manager_col2', '')
            idx_col2 = manager_col2_options.index(prev_col2) if prev_col2 in manager_col2_options else 0
            manager_col2 = st.selectbox("🔑 보조 [매니저 코드] 열 (파일2, 열 이름이 다를 때)", manager_col2_options, index=idx_col2)
        
        col_m3, col_m4 = st.columns([8, 2])
        with col_m3:
            idx_name = available_columns.index(st.session_state['manager_name_col']) if st.session_state['manager_name_col'] in available_columns else 0
            manager_name_col = st.selectbox("👤 화면 상단 [매니저 이름] 표시 열", available_columns, index=idx_name)
        with col_m4:
            st.write(""); st.write("")
            if st.button("저장", key="btn_save_manager"):
                st.session_state['manager_col'] = manager_col
                st.session_state['manager_col2'] = manager_col2 if manager_col2 != "(없음 - 단일 열 사용)" else ""
                st.session_state['manager_name_col'] = manager_name_col
                save_data_and_config()
                st.success("로그인 및 이름 열 설정이 저장되었습니다.")

        st.divider()

        # ========================================
        st.header("3. 표시할 데이터 항목 및 필터 추가")
        c1, c2, c3 = st.columns([3, 3, 3])
        with c1: sel_col = st.selectbox("항목 선택 (주 열)", available_columns, key="sec3_col")
        with c2: 
            fallback_options = ["(없음)"] + available_columns
            fallback_col = st.selectbox("대체 열 (주 열에 값이 없을 때)", fallback_options, key="sec3_fallback")
        with c3: display_name = st.text_input("표시 명칭 (선택)", placeholder="미입력시 원본유지", key="sec3_disp")
        
        c4, c5, c6 = st.columns([3, 3, 1])
        with c4: col_type = st.radio("데이터 타입", ["텍스트", "숫자"], horizontal=True, key="sec3_type")
        with c5: condition = st.text_input("산식 (예: >= 500,000)", key="sec3_cond")
        with c6:
            st.write(""); st.write("")
            if st.button("➕ 추가", key="btn_add_col"):
                final_display_name = display_name.strip() if display_name.strip() else sel_col
                fb = fallback_col if fallback_col != "(없음)" else ""
                st.session_state['admin_cols'].append({
                    "col": sel_col, "fallback_col": fb, "display_name": final_display_name, "type": col_type, "condition": condition if col_type == "숫자" else ""
                })
                save_data_and_config()
                st.rerun()

        if st.session_state['admin_cols']:
            for i, item in enumerate(st.session_state['admin_cols']):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    disp = item.get('display_name', item['col'])
                    fb_text = f" ← 대체: `{item['fallback_col']}`" if item.get('fallback_col') else ""
                    st.markdown(f"- 📄 원본: `{item['col']}`{fb_text} ➡️ **화면 표시: [{disp}]** ({item['type']}) | 조건: `{item['condition']}`")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_col_{i}"):
                        st.session_state['admin_cols'].pop(i)
                        save_data_and_config()
                        st.rerun()

        st.divider()

        # ========================================
        st.header("4. 목표 구간 설정 (기준열 연동 가능)")
        st.caption("기준 열(A)을 설정하면, A값이 B 목표의 상한선이 됩니다. (예: A=40만이면 B의 최대 목표도 40만)")
        c1, c2 = st.columns(2)
        with c1: 
            goal_target = st.selectbox("목표를 적용할 항목 (B열)", available_columns, key="sec4_target")
        with c2:
            goal_ref_options = ["(없음 - 고정 구간)"] + available_columns
            goal_ref = st.selectbox("기준 열 (A열) — B의 최소 목표 기준", goal_ref_options, key="sec4_ref")
        c3, c4 = st.columns([7, 1])
        with c3: goal_tiers = st.text_input("구간 금액 입력 (예: 200000, 400000, 600000)", key="sec4_tiers")
        with c4:
            st.write(""); st.write("")
            if st.button("➕ 추가", key="btn_add_goal"):
                if goal_tiers:
                    tiers_list = [float(x.strip()) for x in goal_tiers.split(",") if x.strip().replace('.','',1).isdigit()]
                    if tiers_list:
                        ref = goal_ref if goal_ref != "(없음 - 고정 구간)" else ""
                        # admin_goals를 list 형태로 관리
                        goals = st.session_state.get('admin_goals', [])
                        if isinstance(goals, dict):
                            goals = [{"target_col": k, "ref_col": "", "tiers": v} for k, v in goals.items()]
                        goals.append({"target_col": goal_target, "ref_col": ref, "tiers": sorted(tiers_list)})
                        st.session_state['admin_goals'] = goals
                        save_data_and_config()
                        st.rerun()
                
        # 기존 dict 형태 → list 형태 자동 변환
        goals = st.session_state.get('admin_goals', [])
        if isinstance(goals, dict):
            goals = [{"target_col": k, "ref_col": "", "tiers": v} for k, v in goals.items()]
            st.session_state['admin_goals'] = goals
            save_data_and_config()
        
        if goals:
            for i, goal in enumerate(goals):
                row_c1, row_c2 = st.columns([8, 2])
                with row_c1:
                    ref_text = f" (상한: **{goal['ref_col']}** 값까지)" if goal.get('ref_col') else " (고정 구간)"
                    tiers_display = [f"{int(t)//10000}만" if t % 10000 == 0 else f"{t:,.0f}" for t in goal['tiers']]
                    st.markdown(f"- **{goal['target_col']}** → 구간: {', '.join(tiers_display)}{ref_text}")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_goal_{i}"):
                        goals.pop(i)
                        st.session_state['admin_goals'] = goals
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
        for goal in (st.session_state['admin_goals'] if isinstance(st.session_state['admin_goals'], list) else []): 
            expected_cols.extend([f"{goal['target_col']} 다음목표", f"{goal['target_col']} 부족금액"])
            
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

        st.divider()

        # ========================================
        st.header("7. 📊 항목 그룹 헤더 설정")
        st.caption("여러 항목을 묶어서 상단에 그룹명을 표시합니다. (예: A, B, C 항목 → '2~3월 시책 현황')")
        
        # 표시 순서에 등록된 항목 목록을 선택지로 사용
        col_order = st.session_state.get('col_order', [])
        if col_order:
            with st.form("add_group_form"):
                g_name = st.text_input("그룹 헤더명 (예: 2~3월 시책 현황)")
                g_cols = st.multiselect("묶을 항목 선택 (표시 순서 기준)", col_order)
                submit_group = st.form_submit_button("➕ 그룹 추가")
                if submit_group and g_name.strip() and g_cols:
                    groups = st.session_state.get('col_groups', [])
                    groups.append({"name": g_name.strip(), "cols": g_cols})
                    st.session_state['col_groups'] = groups
                    save_data_and_config()
                    st.rerun()
            
            if st.session_state.get('col_groups'):
                for i, grp in enumerate(st.session_state['col_groups']):
                    row_c1, row_c2 = st.columns([8, 2])
                    with row_c1:
                        st.markdown(f"- **[{grp['name']}]** ← {', '.join(grp['cols'])}")
                    with row_c2:
                        if st.button("❌ 삭제", key=f"del_grp_{i}"):
                            st.session_state['col_groups'].pop(i)
                            save_data_and_config()
                            st.rerun()
        else:
            st.info("먼저 6번에서 표시 순서를 설정해주세요.")
            
    else:
        st.info("👆 먼저 위에서 두 파일을 업로드하고 [데이터 병합 및 교체]를 눌러주세요.")

# ==========================================
# 5. 매니저 화면 (Manager View)
# ==========================================
elif menu == "매니저 화면 (로그인)":
    st.session_state['admin_authenticated'] = False
    
    df_check = st.session_state.get('df_merged', pd.DataFrame())
    if not isinstance(df_check, pd.DataFrame) or df_check.empty or not st.session_state.get('manager_col'):
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
        manager_code_clean = clean_key(manager_code)
        
        # ✅ 주 매니저 코드 열 검색
        df['search_key'] = df[manager_col].apply(clean_key)
        mask = df['search_key'] == manager_code_clean
        
        # ✅ 보조 매니저 코드 열 검색 (두 파일의 열 이름이 다를 때)
        manager_col2 = st.session_state.get('manager_col2', '')
        if manager_col2 and manager_col2 in df.columns:
            df['search_key2'] = df[manager_col2].apply(clean_key)
            mask = mask | (df['search_key2'] == manager_code_clean)
        
        my_df = df[mask].copy()
        
        if my_df.empty:
            # 부분 일치 검색 (fallback)
            partial_mask = df['search_key'].str.contains(manager_code_clean, na=False)
            if manager_col2 and 'search_key2' in df.columns:
                partial_mask = partial_mask | df['search_key2'].str.contains(manager_code_clean, na=False)
            my_df = df[partial_mask].copy()

        if my_df.empty:
            st.error(f"❌ 매니저 코드 '{manager_code}'에 일치하는 데이터를 찾을 수 없습니다.")
        else:
            manager_name = "매니저"
            if manager_name_col in my_df.columns:
                name_vals = my_df[manager_name_col].dropna()
                if not name_vals.empty:
                    manager_name = str(name_vals.iloc[0])
            
            st.markdown(f"""
            <div class='toss-header'>
                <h1 class='toss-title'>{manager_name} <span class='toss-subtitle'>({manager_code_clean})</span></h1>
                <p class='toss-desc'>환영합니다! 산하 팀장분들의 실적 현황입니다. (총 {len(my_df)}명) 🚀</p>
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
                fallback_col = item.get('fallback_col', '')
                disp_col = item.get('display_name', orig_col)
                
                if item['type'] == '숫자' and item['condition']:
                    mask = evaluate_condition(my_df, orig_col, item['condition'])
                    my_df = my_df[mask]
                
                # ✅ 주 열 값이 없으면 대체 열에서 가져오기
                if fallback_col and fallback_col in my_df.columns and orig_col in my_df.columns:
                    my_df[disp_col] = my_df[orig_col].combine_first(my_df[fallback_col])
                elif orig_col in my_df.columns:
                    my_df[disp_col] = my_df[orig_col]
                else:
                    my_df[disp_col] = ""
                display_cols.append(disp_col)
            
            # -------------------------------------------------------------------
            # (3) 목표 구간 처리 (기준열 연동 지원)
            # -------------------------------------------------------------------
            goals = st.session_state.get('admin_goals', [])
            # 기존 dict 형태 호환
            if isinstance(goals, dict):
                goals = [{"target_col": k, "ref_col": "", "tiers": v} for k, v in goals.items()]
            
            for goal in goals:
                g_col = goal['target_col']
                ref_col = goal.get('ref_col', '')
                tiers = goal['tiers']
                
                if g_col not in my_df.columns:
                    continue
                
                # B열(target) 숫자 변환
                cleaned_str = my_df[g_col].astype(str).str.replace(',', '', regex=False)
                my_df[g_col] = pd.to_numeric(cleaned_str, errors='coerce').fillna(0)
                
                # A열(ref) 숫자 변환 (있는 경우)
                if ref_col and ref_col in my_df.columns:
                    ref_cleaned = my_df[ref_col].astype(str).str.replace(',', '', regex=False)
                    my_df[ref_col] = pd.to_numeric(ref_cleaned, errors='coerce').fillna(0)
                
                def calc_shortfall(row):
                    val = row[g_col]
                    
                    # 기준열(A)이 있으면, A값이 B 목표의 상한선
                    if ref_col and ref_col in row.index:
                        ref_val = row[ref_col]
                        applicable_tiers = [t for t in tiers if t <= ref_val]
                        if not applicable_tiers:
                            # A값이 최소 구간보다 작으면 목표 없음
                            return pd.Series(["목표 없음", 0])
                    else:
                        applicable_tiers = tiers
                    
                    # 적용 가능한 구간 중 다음 목표 찾기
                    for t in applicable_tiers:
                        if val < t:
                            if t % 10000 == 0: tier_str = f"{int(t)//10000}만"
                            else: tier_str = f"{t/10000:g}만"
                            return pd.Series([tier_str, t - val])
                    return pd.Series(["최고 구간 달성", 0])
                
                next_target_col = f"{g_col} 다음목표"
                shortfall_col = f"{g_col} 부족금액"
                
                my_df[[next_target_col, shortfall_col]] = my_df.apply(calc_shortfall, axis=1)
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
                
                # 6. ★ HTML 테이블로 렌더링 (틀 고정 + 그룹 헤더 + 정렬 + 반응형)
                col_groups = st.session_state.get('col_groups', [])
                table_html = render_html_table(final_df, col_groups=col_groups)
                # 테이블 내부 스크롤 사용 — iframe 높이는 뷰포트 85%로 제한
                components.html(table_html, height=800, scrolling=False)
