"""
app.py — Streamlit 메인 진입점 (자동 모드)

[구조]
  app.py          ← 이 파일 (메인 + 매니저 뷰)
  auto_loader.py  ← 데이터 자동 스캔 + stage 감지 + 설정 머지
  admin_view.py   ← 관리자 상태 화면
  render.py       ← HTML 테이블 렌더러
  prize_utils.py  ← 시상금 계산 함수들

[작동]
  앱 시작 시 auto_loader.auto_load() 가 data/ 의 최신 엑셀 3개를 자동 병합하고
  config/base.json + config/stages/{detected_stage}.json 을 읽어 session_state 를 채운다.
  매니저는 로그인만 하면 바로 실적 테이블을 볼 수 있다.
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import re

import auto_loader as al
from admin_view import render_admin_view
from render import render_html_table
from prize_utils import clean_key, calculate_prize_for_code


st.set_page_config(page_title="지원매니저별 실적 관리 시스템", layout="wide")

# 📱 모바일 뷰포트
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
""", unsafe_allow_html=True)


# ==========================================
# 메리츠 스타일 CSS
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
.toss-title { color: #ffffff !important; font-size: 36px; font-weight: 800; margin: 0; letter-spacing: -0.5px; }
.toss-subtitle { color: #ffcccc !important; font-size: 24px; font-weight: 700; margin-left: 10px; }
.toss-desc { color: #f2f4f6 !important; font-size: 17px; margin: 12px 0 0 0; font-weight: 500; }

.block-container { padding-left: 1.5rem !important; padding-right: 1.5rem !important; max-width: 100% !important; }
iframe { width: 100% !important; }

@media (max-width: 768px) {
    .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
    .toss-header { padding: 18px 16px; border-radius: 14px; margin-bottom: 14px; }
    .toss-title { font-size: 22px !important; }
    .toss-subtitle { font-size: 14px !important; display: block; margin-left: 0; margin-top: 4px; }
    .toss-desc { font-size: 13px !important; margin-top: 6px; }
    .toss-header .data-date {
        font-size: 11px !important; float: none !important;
        display: block; text-align: right; margin-bottom: 4px;
    }
    [data-testid="stSidebar"][aria-expanded="false"] ~ .block-container { padding-left: 0.5rem !important; }
    iframe { min-height: 60vh !important; }
    [data-testid="stTextInput"] input, [data-testid="stSelectbox"] > div > div { font-size: 14px !important; }
    .stButton > button, [data-testid="stFormSubmitButton"] > button {
        width: 100% !important; padding: 10px !important; font-size: 15px !important;
    }
}
@media (max-width: 480px) {
    .block-container { padding-left: 0.25rem !important; padding-right: 0.25rem !important; }
    .toss-header { padding: 14px 12px; border-radius: 10px; }
    .toss-title { font-size: 19px !important; }
    .toss-subtitle { font-size: 12px !important; }
    .toss-desc { font-size: 12px !important; }
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 세션 초기화 + 자동 로드
# ==========================================
def _reset_session_state():
    for k in ['df_merged', 'manager_col', 'manager_name_col', 'manager_col2',
              'admin_cols', 'admin_goals', 'admin_categories', 'col_order',
              'merge_key1_col', 'merge_key2_col', 'merge_key3_col',
              'col_groups', 'data_date', 'clip_footer', 'prize_config']:
        if k == 'df_merged':
            st.session_state[k] = pd.DataFrame()
        elif k in ('admin_cols', 'admin_goals', 'admin_categories',
                   'col_order', 'col_groups', 'prize_config'):
            st.session_state[k] = []
        else:
            st.session_state[k] = ''
    st.session_state['_autoload_error'] = None
    st.session_state['_autoload_info'] = {}


def load_data_and_config():
    """auto_loader로 data/ + config/ 읽어서 session_state 채우기."""
    try:
        force = st.session_state.get('_stage_override')
        result = al.auto_load(force_stage=force)
        if 'error' in result:
            st.session_state['_autoload_error'] = result['error']
            return
        st.session_state['_autoload_error'] = None
        st.session_state['df_merged'] = result['df_merged']
        for k, v in result['config'].items():
            st.session_state[k] = v
        st.session_state['_autoload_info'] = {
            'detected_stage': result['detected_stage'],
            'current_month':  result['current_month'],
            'files':          result['files'],
        }
    except Exception as e:
        st.session_state['_autoload_error'] = str(e)


def has_data():
    df = st.session_state.get('df_merged', None)
    return isinstance(df, pd.DataFrame) and not df.empty


def evaluate_condition(df, col, cond):
    cond_clean = re.sub(r'(?<=\d),(?=\d)', '', cond).strip()
    cond_clean = re.sub(r'(?<![><!= ])=(?!=)', '==', cond_clean)
    try:
        temp_s = df[col].astype(str).str.replace(',', '', regex=False)
        num_s = pd.to_numeric(temp_s, errors='coerce')
        if num_s.isna().all() and not temp_s.replace('', np.nan).isna().all():
            raise ValueError("문자형 데이터입니다.")
        temp_df = pd.DataFrame({col: num_s.fillna(0)})
        mask = temp_df.eval(f"`{col}` {cond_clean}", engine='python')
        if isinstance(mask, pd.Series):
            return mask.fillna(False).astype(bool)
        return pd.Series(bool(mask), index=df.index)
    except Exception:
        try:
            mask = df.eval(f"`{col}` {cond_clean}", engine='python')
            if isinstance(mask, pd.Series):
                return mask.fillna(False).astype(bool)
            return pd.Series(bool(mask), index=df.index)
        except Exception:
            return pd.Series(False, index=df.index)


# 첫 실행 시 자동 로드
if 'df_merged' not in st.session_state:
    _reset_session_state()
    load_data_and_config()


# ==========================================
# 사이드바
# ==========================================
st.sidebar.title("메뉴")
menu = st.sidebar.radio("이동할 화면을 선택하세요", ["매니저 화면 (로그인)", "관리자 화면 (상태)"])


# ==========================================
# 관리자 뷰 — admin_view.py 에 위임
# ==========================================
if menu == "관리자 화면 (상태)":
    render_admin_view()


# ==========================================
# 매니저 뷰
# ==========================================
elif menu == "매니저 화면 (로그인)":
    st.session_state['admin_authenticated'] = False

    # 자동 로드 에러 체크
    if st.session_state.get('_autoload_error'):
        st.title("👤 매니저 전용 실적 현황")
        st.error(f"⚠️ 자동 로드 실패: {st.session_state['_autoload_error']}")
        st.info("`data/` 폴더에 `MC_LIST_OUT_*.xlsx`, `PRIZE_6_BRIDGE_OUT_*.xlsx`, "
                "`PRIZE_SUM_OUT_*.xlsx` 3개 파일이 있는지 확인하세요.")
        st.stop()

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

        df['search_key'] = df[manager_col].apply(clean_key)
        mask = df['search_key'] == manager_code_clean

        manager_col2 = st.session_state.get('manager_col2', '')
        if manager_col2 and manager_col2 in df.columns:
            df['search_key2'] = df[manager_col2].apply(clean_key)
            mask = mask | (df['search_key2'] == manager_code_clean)

        my_df = df[mask].copy()

        if my_df.empty:
            partial_mask = df['search_key'].str.contains(manager_code_clean, na=False)
            if manager_col2 and 'search_key2' in df.columns:
                partial_mask = partial_mask | df['search_key2'].str.contains(manager_code_clean, na=False)
            my_df = df[partial_mask].copy()

        if my_df.empty:
            st.error(f"❌ 매니저 코드 '{manager_code}'에 일치하는 데이터를 찾을 수 없습니다.")
        else:
            try:
                manager_name = "매니저"
                if manager_name_col in my_df.columns:
                    name_vals = my_df[manager_name_col].dropna()
                    if not name_vals.empty:
                        manager_name = str(name_vals.iloc[0])

                data_date = st.session_state.get('data_date', '')
                date_html = (f"<span class='data-date' style='font-size:14px; color:rgba(255,255,255,0.85); "
                             f"float:right; margin-top:8px;'>📅 데이터 기준일: {data_date}</span>"
                             if data_date else "")

                st.markdown(f"""
                <div class='toss-header'>
                    {date_html}
                    <h1 class='toss-title'>{manager_name} <span class='toss-subtitle'>({manager_code_clean})</span></h1>
                    <p class='toss-desc'>산하 팀장분들의 실적 현황입니다. (총 {len(my_df)}명)</p>
                </div>
                """, unsafe_allow_html=True)

                display_cols = []

                # 맞춤 분류 적용
                if st.session_state['admin_categories']:
                    if '맞춤분류' not in my_df.columns:
                        my_df['맞춤분류'] = ""
                    for cat in st.session_state['admin_categories']:
                        c_name = cat.get('name', '')
                        final_mask = pd.Series(True, index=my_df.index)
                        cond_list = cat.get('conditions',
                                            [{'col': cat.get('col'), 'cond': cat.get('condition')}])
                        for cond_info in cond_list:
                            if not cond_info.get('col'):
                                continue
                            m_ = evaluate_condition(my_df, cond_info['col'], cond_info['cond'])
                            final_mask = final_mask & m_
                        my_df.loc[final_mask, '맞춤분류'] += f"[{c_name}] "
                    display_cols.append('맞춤분류')

                # admin_cols 적용
                for item in st.session_state['admin_cols']:
                    orig_col = item['col']
                    fallback_col = item.get('fallback_col', '')
                    disp_col = item.get('display_name', orig_col)

                    if item.get('type') == '숫자' and item.get('condition'):
                        m_ = evaluate_condition(my_df, orig_col, item['condition'])
                        my_df = my_df[m_]

                    if fallback_col and fallback_col in my_df.columns and orig_col in my_df.columns:
                        my_df[disp_col] = my_df[orig_col].combine_first(my_df[fallback_col])
                    elif orig_col in my_df.columns:
                        my_df[disp_col] = my_df[orig_col]
                    else:
                        my_df[disp_col] = ""
                    display_cols.append(disp_col)

                # 목표 구간 (admin_goals) 적용
                goals = st.session_state.get('admin_goals', [])
                if isinstance(goals, dict):
                    goals = [{"target_col": k, "ref_col": "", "tiers": v} for k, v in goals.items()]

                for goal in goals:
                    g_col = goal['target_col']
                    ref_col = goal.get('ref_col', '')
                    tiers = goal['tiers']

                    if g_col not in my_df.columns:
                        continue

                    cleaned_str = my_df[g_col].astype(str).str.replace(',', '', regex=False)
                    my_df[g_col] = pd.to_numeric(cleaned_str, errors='coerce').fillna(0)

                    if ref_col and ref_col in my_df.columns:
                        ref_cleaned = my_df[ref_col].astype(str).str.replace(',', '', regex=False)
                        my_df[ref_col] = pd.to_numeric(ref_cleaned, errors='coerce').fillna(0)

                    def _calc_shortfall(row, g_col=g_col, ref_col=ref_col, tiers=tiers):
                        val = row[g_col]
                        if ref_col and ref_col in row.index:
                            ref_val = row[ref_col]
                            applicable = [t for t in tiers if t <= ref_val]
                            if not applicable:
                                return pd.Series(["목표 없음", 0])
                        else:
                            applicable = tiers
                        for t in applicable:
                            if val < t:
                                tier_str = f"{int(t)//10000}만" if t % 10000 == 0 else f"{t/10000:g}만"
                                return pd.Series([tier_str, t - val])
                        return pd.Series(["최고 구간 달성", 0])

                    next_target_col = f"{g_col} 다음목표"
                    shortfall_col = f"{g_col} 부족금액"
                    my_df[[next_target_col, shortfall_col]] = my_df.apply(_calc_shortfall, axis=1)
                    if next_target_col not in display_cols:
                        display_cols.extend([next_target_col, shortfall_col])

                # 정렬
                sort_keys = []
                if '맞춤분류' in my_df.columns:
                    sort_keys.append('맞춤분류')
                ji_cols = [c for c in display_cols if '지사명' in c]
                if not ji_cols:
                    ji_cols = [c for c in my_df.columns if '지사명' in c]
                if ji_cols:
                    sort_keys.append(ji_cols[0])
                name_like = [c for c in display_cols
                             if any(k in c for k in ['성별', '설계사명', '성명', '이름', '팀장명'])]
                if not name_like:
                    name_like = [c for c in my_df.columns
                                 if any(k in c for k in ['성별', '설계사명', '성명', '팀장명'])]
                if name_like:
                    sort_keys.append(name_like[0])
                if sort_keys:
                    my_df = my_df.sort_values(by=sort_keys, ascending=[True]*len(sort_keys))

                # 최종 순서
                final_cols = list(dict.fromkeys(display_cols))
                ordered_final_cols = []
                for c in st.session_state.get('col_order', []):
                    if c in final_cols:
                        ordered_final_cols.append(c)
                for c in final_cols:
                    if c not in ordered_final_cols:
                        ordered_final_cols.append(c)

                if not ordered_final_cols:
                    st.warning("관리자 화면에서 표시할 항목을 추가해주세요.")
                else:
                    final_df = my_df[ordered_final_cols].copy()
                    final_df.insert(0, '순번', range(1, len(final_df) + 1))

                    # 포맷팅
                    for c in final_df.columns:
                        if c != '순번' and '코드' not in c and '연도' not in c:
                            def _fmt(val):
                                try:
                                    if pd.isna(val) or str(val).strip() == "":
                                        return ""
                                    num = float(str(val).replace(',', ''))
                                    if num == 0:
                                        return ""
                                    if num.is_integer():
                                        return f"{int(num):,}"
                                    return f"{num:,.1f}"
                                except Exception:
                                    s = str(val).strip()
                                    if s in ("0", "0.0"):
                                        return ""
                                    return val
                            final_df[c] = final_df[c].apply(_fmt)
                        elif '코드' in c or '연도' in c:
                            def _strip_dot_zero(val):
                                if pd.isna(val) or str(val).strip() == "":
                                    return ""
                                s = str(val).strip()
                                if s.endswith('.0'):
                                    s = s[:-2]
                                return s
                            final_df[c] = final_df[c].apply(_strip_dot_zero)

                    # 시상금 중복 경고
                    prize_config_raw = st.session_state.get('prize_config', [])
                    seen_names = {}
                    for pc in prize_config_raw:
                        n = pc.get('name', '')
                        seen_names[n] = seen_names.get(n, 0) + 1
                    dupes = {n: cnt for n, cnt in seen_names.items() if cnt > 1}
                    if dupes:
                        dupe_msg = ", ".join([f"'{n}' ({cnt}개)" for n, cnt in dupes.items()])
                        st.error(f"⚠️ 시상금 설정에 중복 시책이 있습니다: {dupe_msg} — 시상금이 배로 계산됩니다.")

                    # 시상금 계산
                    prize_data_map = {}
                    try:
                        prize_config = st.session_state.get('prize_config', [])
                        if prize_config:
                            df_full = st.session_state.get('df_merged', pd.DataFrame())
                            if not df_full.empty:
                                prize_code_cols = list(dict.fromkeys(
                                    c.get('col_code', '') for c in prize_config if c.get('col_code')
                                ))
                                for row_idx, (_, row) in enumerate(final_df.iterrows()):
                                    orig_idx = row.name
                                    if orig_idx in my_df.index:
                                        agent_code = ''
                                        for pc_col in prize_code_cols:
                                            if pc_col in my_df.columns:
                                                raw_code = my_df.loc[orig_idx, pc_col]
                                                if not pd.isna(raw_code) and clean_key(str(raw_code)):
                                                    agent_code = clean_key(str(raw_code))
                                                    break
                                        if not agent_code:
                                            for c in my_df.columns:
                                                if '설계사코드' in c or '사번' in c or '설계사조직코드' in c:
                                                    raw_code = my_df.loc[orig_idx, c]
                                                    if not pd.isna(raw_code) and clean_key(str(raw_code)):
                                                        agent_code = clean_key(str(raw_code))
                                                        break
                                        if agent_code:
                                            results, total = calculate_prize_for_code(
                                                agent_code, prize_config, df_full)
                                            if not results:
                                                for alt in ['본인고객번호', '본인고객ID']:
                                                    if alt in my_df.columns:
                                                        alt_raw = my_df.loc[orig_idx, alt]
                                                        if not pd.isna(alt_raw):
                                                            alt_code = clean_key(str(alt_raw))
                                                            if alt_code and alt_code != agent_code:
                                                                results, total = calculate_prize_for_code(
                                                                    alt_code, prize_config, df_full)
                                                                if results:
                                                                    break
                                            if results:
                                                prize_data_map[row_idx] = (results, total)
                    except Exception as prize_err:
                        st.warning(f"⚠️ 시상금 계산 중 오류: {prize_err}")

                    col_groups = st.session_state.get('col_groups', [])
                    table_html = render_html_table(final_df, col_groups=col_groups,
                                                   prize_data_map=prize_data_map)
                    components.html(table_html, height=800, scrolling=False)

            except Exception as e:
                st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
                st.info("관리자 화면에서 설정을 확인해주세요.")
