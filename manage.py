import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import re
import io
import os
import pickle
import uuid
import shutil
import json
from datetime import datetime

st.set_page_config(page_title="지원매니저별 실적 관리 시스템", layout="wide")

# 📱 모바일 뷰포트 메타 태그 삽입
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
""", unsafe_allow_html=True)

DATA_FILE = "app_data.pkl"
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
.toss-title {
    color: #ffffff !important; 
    font-size: 36px;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.5px;
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
    margin: 12px 0 0 0;
    font-weight: 500;
}

/* 실적 테이블 스타일 */
.perf-table-wrap {
    width: 100%;
    overflow-x: auto;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    margin-top: 8px;
    -webkit-overflow-scrolling: touch;
}
.perf-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    white-space: nowrap;
}
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
.perf-table tbody td {
    text-align: center;
    padding: 8px 12px;
    border: 1px solid #e5e8eb;
}
.perf-table tbody tr:nth-child(even) {
    background-color: #f7f8fa;
}
.perf-table tbody tr:hover {
    background-color: #eef1f6;
}
.shortfall-cell {
    color: rgb(128, 0, 0);
    font-weight: 700;
}
/* 메인 영역 패딩 최소화 */
.block-container {
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}
iframe {
    width: 100% !important;
}

/* ========================================
   📱 모바일 반응형 (768px 이하)
   ======================================== */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    /* 헤더 축소 */
    .toss-header {
        padding: 18px 16px;
        border-radius: 14px;
        margin-bottom: 14px;
    }
    .toss-title {
        font-size: 22px !important;
    }
    .toss-subtitle {
        font-size: 14px !important;
        display: block;
        margin-left: 0;
        margin-top: 4px;
    }
    .toss-desc {
        font-size: 13px !important;
        margin-top: 6px;
    }
    /* 기준일 날짜 */
    .toss-header .data-date {
        font-size: 11px !important;
        float: none !important;
        display: block;
        text-align: right;
        margin-bottom: 4px;
    }
    /* 사이드바 닫혔을 때 메인 패딩 */
    [data-testid="stSidebar"][aria-expanded="false"] ~ .block-container {
        padding-left: 0.5rem !important;
    }
    /* iframe 높이 모바일 최적화 */
    iframe {
        min-height: 60vh !important;
    }
    /* selectbox, text_input 등 위젯 크기 */
    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] > div > div {
        font-size: 14px !important;
    }
    /* 폼 버튼 크기 */
    .stButton > button, [data-testid="stFormSubmitButton"] > button {
        width: 100% !important;
        padding: 10px !important;
        font-size: 15px !important;
    }
}

/* ========================================
   📱 소형 모바일 (480px 이하)
   ======================================== */
@media (max-width: 480px) {
    .block-container {
        padding-left: 0.25rem !important;
        padding-right: 0.25rem !important;
    }
    .toss-header {
        padding: 14px 12px;
        border-radius: 10px;
    }
    .toss-title {
        font-size: 19px !important;
    }
    .toss-subtitle {
        font-size: 12px !important;
    }
    .toss-desc {
        font-size: 12px !important;
    }
}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 1. 설정 및 데이터 영구 저장/불러오기 함수
# ==========================================
def load_data_and_config():
    # 구 형식(통합 pkl) 자동 마이그레이션
    if not os.path.exists(DATA_FILE) and os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'rb') as f:
                old = pickle.load(f)
            if isinstance(old, dict) and 'df_merged' in old:
                df = old['df_merged']
                if isinstance(df, pd.DataFrame) and not df.empty:
                    # DataFrame을 DATA_FILE로 분리
                    with open(DATA_FILE, 'wb') as f:
                        pickle.dump({'df_merged': df}, f)
        except Exception:
            pass
    
    # 1) 설정 로드
    cfg = None
    for fp in [CONFIG_FILE, CONFIG_FILE + ".bak"]:
        if not os.path.exists(fp): continue
        try:
            with open(fp, 'rb') as f:
                d = pickle.load(f)
            if isinstance(d, dict):
                cfg = d
                break
        except Exception:
            continue
    if cfg is None:
        cfg = {}
    
    st.session_state['manager_col'] = str(cfg.get('manager_col', ""))
    st.session_state['manager_name_col'] = str(cfg.get('manager_name_col', ""))
    st.session_state['manager_col2'] = str(cfg.get('manager_col2', ""))
    st.session_state['admin_cols'] = cfg.get('admin_cols', []) if isinstance(cfg.get('admin_cols'), list) else []
    st.session_state['admin_goals'] = cfg.get('admin_goals', [])
    if isinstance(st.session_state['admin_goals'], dict):
        st.session_state['admin_goals'] = [
            {"target_col": k, "ref_col": "", "tiers": v} 
            for k, v in st.session_state['admin_goals'].items()
        ]
    st.session_state['admin_categories'] = cfg.get('admin_categories', []) if isinstance(cfg.get('admin_categories'), list) else []
    st.session_state['col_order'] = cfg.get('col_order', []) if isinstance(cfg.get('col_order'), list) else []
    st.session_state['merge_key1_col'] = str(cfg.get('merge_key1_col', ''))
    st.session_state['merge_key2_col'] = str(cfg.get('merge_key2_col', ''))
    st.session_state['col_groups'] = cfg.get('col_groups', []) if isinstance(cfg.get('col_groups'), list) else []
    st.session_state['data_date'] = str(cfg.get('data_date', ''))
    st.session_state['clip_footer'] = str(cfg.get('clip_footer', ''))
    st.session_state['prize_config'] = cfg.get('prize_config', []) if isinstance(cfg.get('prize_config'), list) else []
    for item in st.session_state['admin_cols']:
        if 'fallback_col' not in item: item['fallback_col'] = ''
    
    # 2) DataFrame 로드 (DATA_FILE에서만)
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
            df = data.get('df_merged', pd.DataFrame()) if isinstance(data, dict) else pd.DataFrame()
            st.session_state['df_merged'] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except Exception:
            st.session_state['df_merged'] = pd.DataFrame()

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
    st.session_state['data_date'] = ''
    st.session_state['clip_footer'] = ''
    st.session_state['prize_config'] = []

def has_data():
    df = st.session_state.get('df_merged', None)
    return isinstance(df, pd.DataFrame) and not df.empty

def save_config():
    """설정만 저장 (가벼움 — 버튼 클릭 시마다 호출해도 부담 없음)"""
    cfg = {
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
        'data_date': st.session_state.get('data_date', ''),
        'clip_footer': st.session_state.get('clip_footer', ''),
        'prize_config': st.session_state.get('prize_config', []),
    }
    try:
        if os.path.exists(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, CONFIG_FILE + ".bak")
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, 'wb') as f:
            pickle.dump(cfg, f)
        shutil.move(tmp, CONFIG_FILE)
    except Exception:
        pass

def save_data():
    """DataFrame만 저장 (무거움 — 파일 병합 시에만 호출)"""
    try:
        data = {'df_merged': st.session_state.get('df_merged', pd.DataFrame())}
        tmp = DATA_FILE + ".tmp"
        with open(tmp, 'wb') as f:
            pickle.dump(data, f)
        shutil.move(tmp, DATA_FILE)
    except Exception:
        pass

def save_data_and_config():
    """하위 호환용 — 기존 코드에서 호출하는 곳은 config만 저장"""
    save_config()

# ==========================================
# 💰 시상금 계산 모듈 (자체 통합 — df_merged 사용)
# ==========================================

def _safe_float_prize(val):
    if pd.isna(val) or val is None: return 0.0
    s = str(val).replace(',', '').strip()
    try: return float(s)
    except: return 0.0

def _read_prize_items_app(cfg, match_df):
    """설정에서 시상금 항목들을 읽어 [{label, amount}] 리스트 반환.
    지급률(col_eligible)=0이면 미대상으로 제외, 그 외 값이면 대상으로 포함. 공란이면 무조건 포함."""
    prize_details = []
    items = cfg.get('prize_items', [])
    if items:
        for item in items:
            col_prize = item.get('col_prize', '') or item.get('col', '')  # 구형 호환
            label = item.get('label', '')
            if not col_prize or col_prize not in match_df.columns:
                continue
            
            # 대상 여부 확인
            col_elig = item.get('col_eligible', '')
            if col_elig and col_elig in match_df.columns:
                elig_val = _safe_float_prize(match_df[col_elig].values[0])
                if elig_val == 0:
                    continue
            
            raw = match_df[col_prize].values[0]
            amt = _safe_float_prize(raw)
            prize_details.append({"label": label or col_prize, "amount": amt})
    else:
        col_prize = cfg.get('col_prize', '')
        if col_prize and col_prize in match_df.columns:
            raw = match_df[col_prize].values[0]
            amt = _safe_float_prize(raw)
            if amt != 0:
                prize_details.append({"label": "시상금", "amount": amt})
    return prize_details

def calculate_prize_for_code(target_code, prize_config, df_src):
    """특정 사번의 시상금을 df_merged에서 직접 읽기"""
    if not prize_config or df_src is None or df_src.empty:
        return [], 0
    results = []
    safe_code = clean_key(str(target_code))
    
    for cfg in prize_config:
        col_code = cfg.get('col_code', '')
        if not col_code or col_code not in df_src.columns:
            continue
        
        _cc = f"_pclean_{col_code}"
        if _cc not in df_src.columns:
            df_src[_cc] = df_src[col_code].apply(clean_key)
        match_df = df_src[df_src[_cc] == safe_code]
        if match_df.empty:
            continue
        
        cat = cfg.get('category', 'weekly')
        p_type = cfg.get('type', '구간 시책')
        
        # 시상금 여러 항목 읽기
        prize_details = _read_prize_items_app(cfg, match_df)
        prize = sum(d['amount'] for d in prize_details)
        
        if cat == 'weekly':
            if "1기간" in p_type:
                if not prize_details: continue  # 미대상 → 항목 자체 미표시
                raw_prev = match_df[cfg['col_val_prev']].values[0] if cfg.get('col_val_prev') and cfg['col_val_prev'] in df_src.columns else 0
                raw_curr = match_df[cfg['col_val_curr']].values[0] if cfg.get('col_val_curr') and cfg['col_val_curr'] in df_src.columns else 0
                val_prev, val_curr = _safe_float_prize(raw_prev), _safe_float_prize(raw_curr)
                results.append({"name": cfg['name'], "category": "weekly", "type": "브릿지1",
                    "val_prev": val_prev, "val_curr": val_curr, "prize": prize, "prize_details": prize_details})
            elif "2기간" in p_type:
                raw_curr = match_df[cfg['col_val_curr']].values[0] if cfg.get('col_val_curr') and cfg['col_val_curr'] in df_src.columns else 0
                val_curr = _safe_float_prize(raw_curr)
                
                curr_req = float(cfg.get('curr_req', 100000.0))
                calc_rate, tier_achieved, prize = 0, 0, 0
                
                for amt, rate in cfg.get('tiers', []):
                    if val_curr >= amt:
                        tier_achieved = amt
                        calc_rate = rate
                        break
                
                if tier_achieved > 0:
                    prize = (tier_achieved + curr_req) * (calc_rate / 100)
                
                next_tier = None
                for amt, rate in reversed(cfg.get('tiers', [])):
                    if val_curr < amt:
                        next_tier = amt
                        break
                shortfall = next_tier - val_curr if next_tier else 0
                
                results.append({"name": cfg['name'], "category": "weekly", "type": "브릿지2",
                    "val": val_curr, "tier": tier_achieved, "rate": calc_rate, "prize": prize,
                    "curr_req": curr_req, "next_tier": next_tier, "shortfall": shortfall})
            else:
                if not prize_details: continue  # 미대상 → 항목 자체 미표시
                raw_val = match_df[cfg['col_val']].values[0] if cfg.get('col_val') and cfg['col_val'] in df_src.columns else 0
                val = _safe_float_prize(raw_val)
                results.append({"name": cfg['name'], "category": "weekly", "type": "구간",
                    "val": val, "prize": prize, "prize_details": prize_details})
        elif cat == 'cumulative':
            if not prize_details: continue  # 미대상 → 항목 자체 미표시
            col_val = cfg.get('col_val', '')
            raw_val = match_df[col_val].values[0] if col_val and col_val in match_df.columns else 0
            val = _safe_float_prize(raw_val)
            results.append({"name": cfg['name'], "category": "cumulative", "type": "누계",
                "val": val, "prize": prize, "prize_details": prize_details})
    
    # 총 시상 = 누계 + 브릿지만 (구간 시책은 누계에 이미 포함되므로 제외)
    cumul_sum = sum(r['prize'] for r in results if r['category'] == 'cumulative')
    bridge_sum = sum(r['prize'] for r in results if r['category'] == 'weekly' and '브릿지' in r['type'])
    total = cumul_sum + bridge_sum
    return results, total

def format_prize_clip_text(results, total):
    if not results: return ""
    gugan_res = [r for r in results if r['category'] == 'weekly' and r['type'] == '구간']
    bridge_res = [r for r in results if r['category'] == 'weekly' and '브릿지' in r['type']]
    cumul_res = [r for r in results if r['category'] == 'cumulative']
    cumul_sum = sum(r['prize'] for r in cumul_res)
    bridge_sum = sum(r['prize'] for r in bridge_res)
    
    lines = ["", "💰 예상 시상금 현황", f"  총 시상금: {total:,.0f}원"]
    if cumul_sum > 0 or bridge_sum > 0:
        parts = []
        if cumul_sum > 0: parts.append(f"누계 {cumul_sum:,.0f}")
        if bridge_sum > 0: parts.append(f"브릿지 {bridge_sum:,.0f}")
        lines.append(f"  ({' + '.join(parts)})")
    for r in gugan_res:
        if r['prize'] > 0:
            lines.append(f"  {r['name']}: {r['prize']:,.0f}원 (누계포함)")
            for d in r.get('prize_details', []):
                lines.append(f"    · {d['label']}: {d['amount']:,.0f}원")
    for r in bridge_res:
        if r['prize'] > 0:
            if r['type'] == '브릿지2':
                lines.append(f"  {r['name']}: {r['prize']:,.0f}원 (당월 {int(r.get('curr_req',100000)//10000)}만 가동 시)")
                if r.get('shortfall', 0) > 0:
                    lines.append(f"    🚀 다음 구간까지 {r['shortfall']:,.0f}원")
            else:
                lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
                for d in r.get('prize_details', []):
                    lines.append(f"    · {d['label']}: {d['amount']:,.0f}원")
    for r in cumul_res:
        if r['prize'] > 0:
            lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
            for d in r.get('prize_details', []):
                lines.append(f"    · {d['label']}: {d['amount']:,.0f}원")
    return '\n'.join(lines)

def _prize_detail_sub_html(details):
    """시상금 항목이 2개 이상일 때 상세 내역 HTML"""
    if len(details) <= 1: return ""
    h = ""
    for d in details:
        h += f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:11px;">· {d["label"]}</span><span class="m-val" style="font-size:11px;">{d["amount"]:,.0f}원</span></div>'
    return h

def build_prize_card_html(results, total):
    if not results: return ""
    gugan_res = [r for r in results if r['category'] == 'weekly' and r['type'] == '구간']
    bridge_res = [r for r in results if r['category'] == 'weekly' and '브릿지' in r['type']]
    cumul_res = [r for r in results if r['category'] == 'cumulative']
    cumul_sum = sum(r['prize'] for r in cumul_res)
    bridge_sum = sum(r['prize'] for r in bridge_res)
    
    h = '<div style="margin-top:8px; padding:10px; background:#fff8f0; border-radius:10px; border:1px solid #ffd4a8;">'
    h += f'<div style="font-weight:800;color:#d9232e;font-size:15px;margin-bottom:2px;">💰 총 시상금: {total:,.0f}원</div>'
    if cumul_sum > 0 or bridge_sum > 0:
        parts = []
        if cumul_sum > 0: parts.append(f"누계 {cumul_sum:,.0f}")
        if bridge_sum > 0: parts.append(f"브릿지 {bridge_sum:,.0f}")
        h += f'<div style="font-size:11px;color:#888;margin-bottom:6px;">({" + ".join(parts)})</div>'
    if gugan_res:
        h += '<div style="font-size:11px;color:#4e5968;font-weight:700;margin-top:4px;">📌 시책 진행 (누계에 포함)</div>'
        for r in gugan_res:
            pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
            h += f'<div class="m-row"><span class="m-label">{r["name"]}</span><span class="m-val" style="color:#888;font-weight:600;">{pz}</span></div>'
            h += _prize_detail_sub_html(r.get('prize_details', []))
    if bridge_res:
        h += '<div style="font-size:11px;color:#d4380d;font-weight:700;margin-top:4px;">🌉 브릿지 시상</div>'
        for r in bridge_res:
            pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
            if r['type'] == '브릿지2':
                label = f"{r['name']}<br><span style='font-size:10px;color:#888;'>(당월 {int(r.get('curr_req',100000)//10000)}만 가동 시)</span>"
                h += f'<div class="m-row"><span class="m-label">{label}</span><span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                if r.get('shortfall', 0) > 0:
                    h += f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:10px;color:#888;">🚀 다음 구간까지 {r["shortfall"]:,.0f}원</span><span class="m-val"></span></div>'
            else:
                h += f'<div class="m-row"><span class="m-label">{r["name"]}</span><span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                h += _prize_detail_sub_html(r.get('prize_details', []))
    if cumul_res:
        h += '<div style="font-size:11px;color:#2B6CB0;font-weight:700;margin-top:4px;">📈 누계 시상</div>'
        for r in cumul_res:
            pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
            h += f'<div class="m-row"><span class="m-label">{r["name"]}</span><span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
            h += _prize_detail_sub_html(r.get('prize_details', []))
    h += '</div>'
    return h


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
    df.columns = [decode_excel_text(c) if isinstance(c, str) else c for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(decode_excel_text)
    return df

# ==========================================
# ★ HTML 테이블 렌더링 함수
# ==========================================
def render_html_table(df, col_groups=None, prize_data_map=None):
    """DataFrame을 틀 고정 + 그룹 헤더 + 정렬 + 반응형 HTML 테이블로 변환
    ★ colspan 없이 셀 수를 항상 동일하게 유지 → 밀림 방지
    prize_data_map: {row_idx: (results, total)} — 시상금 데이터
    """
    table_id = f"perf_{uuid.uuid4().hex[:8]}"
    num_cols = len(df.columns)
    shortfall_cols = set(c for c in df.columns if '부족금액' in c)
    col_groups = col_groups or []
    has_groups = len(col_groups) > 0
    
    freeze_keywords = ['순번', '맞춤분류', '설계사', '성명', '이름', '팀장', '대리점']
    freeze_count = 0
    for i, col in enumerate(df.columns):
        if any(kw in col for kw in freeze_keywords):
            freeze_count = i + 1
    freeze_count = min(freeze_count, 4)

    base_font = max(11, 15 - num_cols // 3)
    grp_h = 30
    col_h = 36
    
    # 각 컬럼 인덱스에 대한 그룹 정보 계산
    # group_info[i] = (group_name, position) where position: 'first', 'mid', 'last', 'solo' or None
    # 그룹별 색상 팔레트 (최대 8개, 순환)
    GROUP_COLORS = [
        '#2B6CB0',  # 블루
        '#2F855A',  # 그린
        '#9B2C2C',  # 레드
        '#6B46C1',  # 퍼플
        '#B7791F',  # 골드
        '#2C7A7B',  # 틸
        '#C05621',  # 오렌지
        '#702459',  # 핑크
    ]
    
    col_to_group = {}
    group_color_map = {}  # group_name → color
    for gi, grp in enumerate(col_groups):
        color = GROUP_COLORS[gi % len(GROUP_COLORS)]
        group_color_map[grp['name']] = color
        for c in grp['cols']:
            col_to_group[c] = grp['name']
    
    columns = list(df.columns)
    
    # 각 그룹의 가운데 셀 인덱스 계산
    group_mid = {}  # group_name → column index that shows text
    for gname in set(col_to_group.values()):
        indices = [i for i, c in enumerate(columns) if col_to_group.get(c) == gname]
        if indices:
            group_mid[gname] = indices[len(indices) // 2]
    
    # group_info: (group_name, is_first, is_last, is_mid_text)
    group_info = []
    for i, col in enumerate(columns):
        gname = col_to_group.get(col, None)
        if gname is None:
            group_info.append((None, False, False, False))
        else:
            prev_grp = col_to_group.get(columns[i-1], None) if i > 0 else None
            next_grp = col_to_group.get(columns[i+1], None) if i < len(columns)-1 else None
            is_first = (prev_grp != gname)
            is_last = (next_grp != gname)
            is_text = (i == group_mid.get(gname, -1))
            group_info.append((gname, is_first, is_last, is_text))
    
    def fc(i):
        """freeze class"""
        if i >= freeze_count: return ""
        c = "col-freeze"
        if i == freeze_count - 1: c += " col-freeze-last"
        return c

    # ── CSS ──
    # 모바일 감지 기반 폰트 크기 결정
    mob_font = max(9, base_font - 2)
    
    html = f"""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; font-family: 'Pretendard', -apple-system, 'Noto Sans KR', sans-serif; }}
    .perf-table-wrap {{
        width: 100%; max-height: 85vh; overflow: auto;
        border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        -webkit-overflow-scrolling: touch;
    }}
    .perf-table {{
        width: max-content; min-width: 100%;
        border-collapse: separate; border-spacing: 0;
        white-space: nowrap; font-size: {base_font}px;
    }}
    /* 공통 헤더 */
    .perf-table thead th {{
        background-color: #4e5968; color: #fff; font-weight: 700;
        text-align: center; border: 1px solid #3d4654;
        position: sticky; z-index: 2; white-space: nowrap;
    }}
    /* 그룹 행 */
    .perf-table .rg th {{ top: 0; height: {grp_h}px; padding: 4px 6px; cursor: default; }}
    .perf-table .rg .ge {{ background: #4e5968; border-bottom-color: #4e5968; }}
    .perf-table .rg .gc {{ border-left: none; border-right: none; }}
    .perf-table .rg .gc-first {{ border-left: 1px solid #3d4654; border-right: none; }}
    .perf-table .rg .gc-last {{ border-left: none; border-right: 1px solid #3d4654; }}
    .perf-table .rg .gc-solo {{ border-left: 1px solid #3d4654; border-right: 1px solid #3d4654; }}
    /* 모바일용 컬럼 헤더 색상 바 (기본 숨김) */
    .perf-table .rc th .grp-bar {{
        display: none;
        height: 4px; border-radius: 2px;
        margin: 0 auto 3px auto; width: 80%;
    }}
    /* 컬럼 행 */
    .perf-table .rc th {{
        top: {grp_h if has_groups else 0}px; height: {col_h}px;
        padding: 6px 10px; cursor: pointer; user-select: none;
    }}
    .perf-table thead th:hover {{ background-color: #3d4654; }}
    .sa {{ margin-left: 3px; font-size: 10px; opacity: 0.5; }}
    .sa.active {{ opacity: 1; }}
    /* 본문 */
    .perf-table tbody td {{
        text-align: center; padding: 6px 10px;
        border: 1px solid #e5e8eb; white-space: nowrap;
        background-color: #fff;
    }}
    .perf-table tbody tr:nth-child(even) td {{ background-color: #f7f8fa; }}
    .perf-table tbody tr:hover td {{ background-color: #eef1f6; }}
    .sc {{ color: rgb(128, 0, 0); font-weight: 700; }}
    .col-freeze {{ position: sticky; z-index: 1; }}
    thead th.col-freeze {{ z-index: 3; }}
    .col-freeze-last {{ box-shadow: 2px 0 5px rgba(0,0,0,0.08); }}
    
    /* 📱 태블릿 */
    @media (max-width: 1200px) {{
        .perf-table {{ font-size: {max(10, 13 - num_cols // 3)}px; }}
        .perf-table thead th, .perf-table tbody td {{ padding: 5px 6px; }}
    }}
    /* 📱 모바일 */
    @media (max-width: 768px) {{
        .perf-table-wrap {{ max-height: 75vh; border-radius: 8px; }}
        .perf-table {{ font-size: {mob_font}px; }}
        .perf-table thead th {{ padding: 4px 5px; }}
        .perf-table tbody td {{ padding: 4px 5px; }}
        /* 그룹 행 숨김 → 색상 바로 대체 */
        .perf-table .rg {{ display: none; }}
        .perf-table .rc th {{ top: 0 !important; padding: 5px 5px 4px 5px; }}
        .perf-table .rc th .grp-bar {{ display: block; }}
        .sa {{ font-size: 8px; margin-left: 1px; }}
        .col-freeze-last {{ box-shadow: 2px 0 3px rgba(0,0,0,0.12); }}
    }}
    /* 📱 소형 모바일 */
    @media (max-width: 480px) {{
        .perf-table {{ font-size: {max(8, mob_font - 1)}px; }}
        .perf-table thead th, .perf-table tbody td {{ padding: 3px 3px; }}
        .perf-table .rc th {{ padding: 4px 3px 3px 3px; }}
        .perf-table .rc th .grp-bar {{ height: 3px; margin-bottom: 2px; }}
    }}
    
    /* ══════════════════════════════════════
       데스크톱/모바일 뷰 토글
       ══════════════════════════════════════ */
    .desktop-view {{ display: block; }}
    .mobile-view {{ display: none; }}
    
    @media (max-width: 768px) {{
        .desktop-view {{ display: none !important; }}
        .mobile-view {{ display: block !important; }}
    }}
    
    /* ══════════════════════════════════════
       📱 모바일 카드 스타일
       ══════════════════════════════════════ */
    .mobile-view {{
        padding: 0 4px;
        max-height: 80vh;
        overflow-y: auto;
        -webkit-overflow-scrolling: touch;
    }}
    .m-card {{
        background: #fff; border-radius: 12px;
        margin-bottom: 10px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        border: 1px solid #e5e8eb;
    }}
    .m-card-head {{
        display: flex; align-items: center; flex-wrap: wrap;
        padding: 14px 14px 12px; cursor: pointer;
        gap: 6px; position: relative;
    }}
    .m-num {{
        background: #4e5968; color: #fff;
        font-size: 11px; font-weight: 700;
        width: 24px; height: 24px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
    }}
    .m-name {{
        font-size: 16px; font-weight: 700; color: #191f28;
    }}
    .m-summary {{
        display: flex; gap: 6px; margin-left: auto; flex-shrink: 0;
    }}
    .m-goal {{
        font-size: 12px; background: #EBF5FB; color: #2B6CB0;
        padding: 2px 8px; border-radius: 10px; font-weight: 600;
    }}
    .m-sc {{
        font-size: 12px; background: #FFF5F5; color: rgb(128,0,0);
        padding: 2px 8px; border-radius: 10px; font-weight: 700;
    }}
    .m-chevron {{
        font-size: 10px; color: #8b95a1; margin-left: 6px;
        transition: transform 0.2s;
    }}
    .m-card.open .m-chevron {{ transform: rotate(180deg); }}
    .m-card-body {{
        max-height: 0; overflow: hidden;
        transition: max-height 0.3s ease;
        border-top: 1px solid #f2f4f6;
    }}
    .m-card.open .m-card-body {{
        max-height: 2000px;
    }}
    .m-grp-label {{
        font-size: 12px; font-weight: 700; color: #4e5968;
        padding: 8px 14px 4px; margin-top: 4px;
    }}
    .m-row {{
        display: flex; justify-content: space-between;
        padding: 6px 14px; font-size: 14px;
    }}
    .m-row:nth-child(even) {{ background: #f9fafb; }}
    .m-label {{ color: #6b7684; font-weight: 500; flex-shrink: 0; margin-right: 12px; }}
    .m-val {{ color: #191f28; font-weight: 600; text-align: right; }}
    .m-row.m-sc .m-val {{ color: rgb(128,0,0); font-weight: 800; }}
    
    /* 복사 버튼 */
    .m-copy-wrap {{
        padding: 10px 14px 6px; text-align: center;
    }}
    .m-copy-btn {{
        width: 100%; padding: 10px; border: none; border-radius: 10px;
        background: linear-gradient(135deg, #FEE500 0%, #F5D600 100%);
        color: #3C1E1E; font-size: 14px; font-weight: 700;
        cursor: pointer; transition: all 0.2s;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }}
    .m-copy-btn:active {{ transform: scale(0.97); }}
    .m-copy-btn.copied {{
        background: linear-gradient(135deg, #22C55E 0%, #16A34A 100%);
        color: #fff;
    }}
    /* 데스크톱 행 복사 버튼 */
    .d-copy-btn {{
        border: none; border-radius: 6px; padding: 4px 10px;
        background: #FEE500; color: #3C1E1E;
        font-size: 12px; font-weight: 700; cursor: pointer;
        white-space: nowrap; transition: all 0.15s;
    }}
    .d-copy-btn:hover {{ background: #F5D600; }}
    .d-copy-btn.copied {{ background: #22C55E; color: #fff; }}
    </style>
    """

    # ── 테이블 시작 ──
    html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    html += '<div class="desktop-view">'
    html += f'<div class="perf-table-wrap" id="wrap_{table_id}"><table class="perf-table" id="{table_id}"><thead>'
    
    # ── 그룹 행: 항상 N개 <th> (colspan 없음) ──
    if has_groups:
        html += '<tr class="rg">'
        for i, col in enumerate(columns):
            gname, is_first, is_last, is_text = group_info[i]
            f_cls = fc(i)
            if gname is None:
                html += f'<th class="ge {f_cls}" data-col="{i}"></th>'
            else:
                gc = group_color_map.get(gname, '#364152')
                # border 클래스 결정
                if is_first and is_last:
                    b_cls = "gc-solo"
                elif is_first:
                    b_cls = "gc-first"
                elif is_last:
                    b_cls = "gc-last"
                else:
                    b_cls = "gc"
                # 가운데 셀에만 텍스트 표시
                text = gname if is_text else ""
                html += f'<th class="{b_cls} {f_cls}" style="background:{gc};" data-col="{i}">{text}</th>'
        html += '<th class="ge" data-col="-1"></th>'  # 복사 열 (빈 그룹)
        html += '</tr>'
    html += '<tr class="rc">'
    for i, col in enumerate(columns):
        f_cls = fc(i)
        gname = col_to_group.get(col, None)
        if gname:
            gc = group_color_map.get(gname, '#364152')
            bar = f'<div class="grp-bar" style="background:{gc};"></div>'
        else:
            bar = ''
        html += f'<th class="{f_cls}" data-col="{i}" onclick="sortTable(this)">{bar}{col} <span class="sa">▲▼</span></th>'
    html += '<th data-col="-1" style="min-width:50px; cursor:default;">복사</th>'
    html += '</tr></thead><tbody>'

    # ── 본문 ──
    for row_idx, (_, row) in enumerate(df.iterrows()):
        html += '<tr>'
        for i, col in enumerate(columns):
            val = row[col]
            cell_val = "" if pd.isna(val) else str(val)
            f_cls = fc(i)
            extra = " sc" if (col in shortfall_cols and cell_val != "") else ""
            html += f'<td class="{f_cls}{extra}" data-col="{i}">{cell_val}</td>'
        html += f'<td data-col="-1"><button class="d-copy-btn" onclick="copyClip({row_idx}, this, event)">📋</button>'
        if prize_data_map and row_idx in prize_data_map:
            html += f'<button class="d-copy-btn" onclick="showPrize({row_idx}, event)" style="margin-left:2px;">💰</button>'
        html += '</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    # ── END desktop table ──
    html += '</div>'  # close .desktop-view
    
    # ══════════════════════════════════════════
    # 📋 각 행별 클립보드 텍스트 생성 (데스크톱/모바일 공용)
    # ══════════════════════════════════════════
    columns = list(df.columns)
    
    # 이름 열 찾기
    name_col = None
    name_keywords = ['설계사명', '성명', '이름', '팀장명']
    for c in columns:
        if any(kw in c for kw in name_keywords):
            name_col = c
            break
    
    # 식별 열 vs 데이터 열 분류
    # 카톡 이름줄: 지사명 + 설계사명 딱 2개만
    clip_name_keywords = ['지사', '설계사명', '성명', '이름', '팀장명']
    goal_keywords = ['다음목표', '부족금액']
    
    clip_name_cols = []
    data_cols = []
    for c in columns:
        if c == '순번' or c == '맞춤분류':
            continue
        if any(kw in c for kw in goal_keywords):
            data_cols.append(c)
        elif any(kw in c for kw in clip_name_keywords) and '코드' not in c and '번호' not in c:
            clip_name_cols.append(c)
        else:
            data_cols.append(c)
    
    # 그룹별 열 매핑
    col_to_grp = {}
    for grp in col_groups:
        for c in grp['cols']:
            col_to_grp[c] = grp['name']
    
    # 기준일 / 인사말
    data_date = ''
    clip_footer = ''
    try:
        data_date = st.session_state.get('data_date', '')
        clip_footer = st.session_state.get('clip_footer', '')
    except Exception:
        pass
    if not clip_footer.strip():
        clip_footer = "팀장님! 시상 부족금액 안내드려요!\n부족한 거 챙겨서 꼭 시상 많이 받아 가셨으면 좋겠습니다!\n좋은 하루 되세요!"
    
    clip_texts = []
    for row_idx, (_, row) in enumerate(df.iterrows()):
        # 인적사항 조합: 대리점명 + 이름 + "팀장님"
        name_parts = []
        for c in clip_name_cols:
            v = str(row[c]) if not pd.isna(row[c]) else ''
            if v.strip() and v != '0':
                name_parts.append(v.strip())
        person_line = ' '.join(name_parts)
        if person_line and not person_line.endswith('님'):
            person_line += ' 팀장님'
        
        lines = []
        lines.append("📋 메리츠 시상 현황 안내")
        if data_date:
            lines.append(f"📅 기준일: {data_date}")
        lines.append("")
        lines.append(f"👤 {person_line}")
        lines.append("")
        
        current_group = None
        for c in data_cols:
            # 코드 열은 카톡 복사에서 제외
            if '코드' in c or '번호' in c:
                continue
            val = str(row[c]) if not pd.isna(row[c]) else ''
            if not val.strip() or val == '0':
                continue
            
            grp = col_to_grp.get(c)
            is_goal = any(kw in c for kw in goal_keywords)
            
            if grp and grp != current_group:
                if current_group is not None:
                    lines.append("")
                lines.append(f"━━ {grp} ━━")
                current_group = grp
            elif grp is None and not is_goal and current_group is not None:
                # 일반 데이터 열이 그룹 밖으로 나가면 구분선
                lines.append("")
                current_group = None
            # is_goal이면 이전 그룹 유지 (구분선 삽입 안 함)
            
            if '부족금액' in c:
                lines.append(f"🔴 {c}: {val}")
            elif '다음목표' in c:
                lines.append(f"🎯 {c}: {val}")
            else:
                lines.append(f"  {c}: {val}")
        
        # 시상금 정보 추가
        if prize_data_map and row_idx in prize_data_map:
            p_results, p_total = prize_data_map[row_idx]
            prize_text = format_prize_clip_text(p_results, p_total)
            if prize_text:
                lines.append(prize_text)
        
        # 인사말 추가
        if clip_footer:
            lines.append("")
            lines.append(clip_footer)
        
        clip_texts.append('\n'.join(lines))
    
    # JS 안전하게 전달 — HTML-safe base64 인코딩
    import base64 as _b64
    clip_json_bytes = json.dumps(clip_texts, ensure_ascii=False).encode('utf-8')
    clip_b64 = _b64.b64encode(clip_json_bytes).decode('ascii')
    
    # 💰 시상금 HTML 데이터 (행별)
    prize_htmls = []
    for row_idx in range(len(df)):
        if prize_data_map and row_idx in prize_data_map:
            p_results, p_total = prize_data_map[row_idx]
            p_gugan = [r for r in p_results if r['category'] == 'weekly' and r['type'] == '구간']
            p_bridge = [r for r in p_results if r['category'] == 'weekly' and '브릿지' in r['type']]
            p_cumul = [r for r in p_results if r['category'] == 'cumulative']
            p_cumul_sum = sum(r['prize'] for r in p_cumul)
            p_bridge_sum = sum(r['prize'] for r in p_bridge)
            
            ph = f'<div style="padding:5px;">'
            ph += f'<div style="font-weight:800;color:#d9232e;font-size:18px;margin-bottom:4px;">💰 총 시상금: {p_total:,.0f}원</div>'
            if p_cumul_sum > 0 or p_bridge_sum > 0:
                parts = []
                if p_cumul_sum > 0: parts.append(f"누계 {p_cumul_sum:,.0f}")
                if p_bridge_sum > 0: parts.append(f"브릿지 {p_bridge_sum:,.0f}")
                ph += f'<div style="color:#888;font-size:13px;margin-bottom:12px;">({" + ".join(parts)})</div>'
            if p_gugan:
                ph += '<div style="font-size:12px;color:#4e5968;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">📌 시책 진행 현황 (누계에 포함)</div>'
                for r in p_gugan:
                    pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
                    ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#888;">{r["name"]}</span><span style="color:#888;font-weight:600;">{pz}</span></div>'
                    if len(r.get('prize_details', [])) > 1:
                        for d in r.get('prize_details', []):
                            ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#aaa;font-size:11px;">· {d["label"]}</span><span style="color:#aaa;font-size:11px;">{d["amount"]:,.0f}원</span></div>'
            if p_bridge:
                ph += '<div style="font-size:12px;color:#d4380d;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">🌉 브릿지 시상</div>'
                for r in p_bridge:
                    pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
                    if r['type'] == '브릿지2':
                        ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#555;">{r["name"]}<br><span style="font-size:10px;color:#888;">(당월 {int(r.get("curr_req",100000)//10000)}만 가동 시)</span></span><span style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                        if r.get('shortfall', 0) > 0:
                            ph += f'<div style="padding:2px 0 2px 8px;font-size:10px;color:#888;">🚀 다음 구간까지 {r["shortfall"]:,.0f}원</div>'
                    else:
                        ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#555;">{r["name"]}</span><span style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                        if len(r.get('prize_details', [])) > 1:
                            for d in r.get('prize_details', []):
                                ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#aaa;font-size:11px;">· {d["label"]}</span><span style="color:#aaa;font-size:11px;">{d["amount"]:,.0f}원</span></div>'
            if p_cumul:
                ph += '<div style="font-size:12px;color:#2B6CB0;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">📈 누계 시상</div>'
                for r in p_cumul:
                    pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
                    ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#555;">{r["name"]}</span><span style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                    if len(r.get('prize_details', [])) > 1:
                        for d in r.get('prize_details', []):
                            ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#aaa;font-size:11px;">· {d["label"]}</span><span style="color:#aaa;font-size:11px;">{d["amount"]:,.0f}원</span></div>'
            ph += '</div>'
            prize_htmls.append(ph)
        else:
            prize_htmls.append('')
    
    prize_json_bytes = json.dumps(prize_htmls, ensure_ascii=False).encode('utf-8')
    prize_b64 = _b64.b64encode(prize_json_bytes).decode('ascii')
    
    # ══════════════════════════════════════════
    # 📱 모바일 카드 뷰 생성
    # ══════════════════════════════════════════
    html += '<div class="mobile-view">'
    
    for row_idx, (_, row) in enumerate(df.iterrows()):
        # 인적사항 조합
        name_parts_card = []
        for c in clip_name_cols:
            v = str(row[c]) if not pd.isna(row[c]) else ''
            if v.strip() and v != '0':
                name_parts_card.append(v.strip())
        person_card = ' '.join(name_parts_card) if name_parts_card else ''
        
        # 이름만 추출 (카드 헤더 굵은 글씨용)
        name_val = str(row.get(name_col, '')) if name_col else (person_card or '')
        num_val = str(row.get('순번', row_idx + 1)) if '순번' in columns else str(row_idx + 1)
        
        html += f'<div class="m-card">'
        
        # 카드 헤더: 이름 + 요약 배지
        summary_items = []
        for c in data_cols:
            if '부족금액' in c:
                v = str(row[c]) if not pd.isna(row[c]) else ''
                if v and v != '0' and v.strip():
                    summary_items.append(f'<span class="m-sc">부족 {v}</span>')
            elif '다음목표' in c:
                v = str(row[c]) if not pd.isna(row[c]) else ''
                if v and v.strip():
                    summary_items.append(f'<span class="m-goal">{v}</span>')
        summary = ' '.join(summary_items)
        
        # 시상금 배지 추가
        if prize_data_map and row_idx in prize_data_map:
            _, p_total = prize_data_map[row_idx]
            if p_total > 0:
                p_display = f"{int(p_total)//10000}만" if p_total >= 10000 and p_total % 10000 == 0 else f"{p_total:,.0f}"
                summary_items.append(f'<span style="background:#fff3e0;color:#d9232e;padding:2px 6px;border-radius:4px;font-size:11px;font-weight:700;">💰{p_display}</span>')
                summary = ' '.join(summary_items)
        
        html += f'<div class="m-card-head" onclick="this.parentElement.classList.toggle(\'open\')">'
        html += f'<span class="m-num">{num_val}</span><span class="m-name">{name_val}</span>'
        if summary:
            html += f'<span class="m-summary">{summary}</span>'
        html += '<span class="m-chevron">&#9660;</span></div>'
        
        # 카드 본문
        html += '<div class="m-card-body">'
        
        # 📋 복사 버튼 + 💰 시상금 조회 버튼
        html += f'<div class="m-copy-wrap"><button class="m-copy-btn" onclick="copyClip({row_idx}, this, event)">📋 카톡 보내기</button>'
        if prize_data_map and row_idx in prize_data_map:
            html += f'<button class="m-copy-btn" onclick="showPrize({row_idx}, event)" style="background:#fff3e0;color:#d9232e;border:1px solid #ffd4a8;margin-top:4px;">💰 시상금 상세 조회</button>'
        html += '</div>'
        
        # 인적사항 (이름 외 추가 정보)
        for c in clip_name_cols:
            if c == name_col:
                continue
            val = str(row[c]) if not pd.isna(row[c]) else ''
            if val.strip() and val != '0':
                html += f'<div class="m-row"><span class="m-label">{c}</span><span class="m-val">{val}</span></div>'
        
        # 실적 데이터
        current_group = None
        for c in data_cols:
            val = str(row[c]) if not pd.isna(row[c]) else ''
            if not val.strip() or val == '0':
                continue
            
            grp = col_to_grp.get(c)
            is_goal = any(kw in c for kw in goal_keywords)
            
            if grp and grp != current_group:
                gc = group_color_map.get(grp, '#4e5968')
                html += f'<div class="m-grp-label" style="border-left:3px solid {gc}; padding-left:8px;">{grp}</div>'
                current_group = grp
            elif grp is None and not is_goal and current_group is not None:
                current_group = None
            
            extra_cls = ' m-sc' if c in shortfall_cols else ''
            html += f'<div class="m-row{extra_cls}"><span class="m-label">{c}</span><span class="m-val">{val}</span></div>'
        
        # 시상금 섹션
        if prize_data_map and row_idx in prize_data_map:
            p_results, p_total = prize_data_map[row_idx]
            html += build_prize_card_html(p_results, p_total)
        
        html += '</div></div>'  # m-card-body, m-card
    
    html += '</div>'  # mobile-view
    
    # ── 복사 팝업 오버레이 (iframe 내부) ──
    html += """
    <div id="clip-overlay" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0;
        background:rgba(0,0,0,0.5); z-index:99999; justify-content:center; align-items:center; padding:20px;"
        onclick="if(event.target===this){this.style.display='none';}">
        <div style="background:#fff; border-radius:16px; padding:20px; width:100%;
            max-width:500px; max-height:70vh; box-shadow:0 10px 40px rgba(0,0,0,0.3);">
            <h3 style="margin:0 0 10px; font-size:16px;">📋 아래 텍스트를 복사하세요</h3>
            <textarea id="clip-ta" style="width:100%; height:200px; border:1px solid #ddd; border-radius:8px;
                padding:10px; font-size:14px; resize:none; font-family:inherit; box-sizing:border-box;"></textarea>
            <button id="clip-copy-btn" onclick="doCopyOverlay()" style="margin-top:10px; width:100%; padding:12px;
                border:none; border-radius:10px; font-size:15px; font-weight:700; cursor:pointer;
                background:#FEE500; color:#3C1E1E;">📋 복사하기</button>
            <button onclick="document.getElementById('clip-overlay').style.display='none'" style="margin-top:6px;
                width:100%; padding:12px; border:none; border-radius:10px; font-size:15px; font-weight:700;
                cursor:pointer; background:#f2f4f6; color:#333;">닫기</button>
        </div>
    </div>
    <div id="prize-overlay" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0;
        background:rgba(0,0,0,0.5); z-index:99999; justify-content:center; align-items:center; padding:20px;"
        onclick="if(event.target===this){this.style.display='none';}">
        <div style="background:#fff; border-radius:16px; padding:24px; width:100%;
            max-width:450px; max-height:70vh; overflow-y:auto; box-shadow:0 10px 40px rgba(0,0,0,0.3);">
            <h3 style="margin:0 0 12px; font-size:17px;">💰 시상금 상세 조회</h3>
            <div id="prize-content"></div>
            <button onclick="document.getElementById('prize-overlay').style.display='none'" style="margin-top:12px;
                width:100%; padding:12px; border:none; border-radius:10px; font-size:15px; font-weight:700;
                cursor:pointer; background:#f2f4f6; color:#333;">닫기</button>
        </div>
    </div>
    """

    # ── JavaScript ──
    html += f"""
    <script>
    var FC_DESKTOP = {freeze_count};
    var FC = FC_DESKTOP;
    var clipData = JSON.parse(decodeURIComponent(escape(atob("{clip_b64}"))));
    var prizeHtml = JSON.parse(decodeURIComponent(escape(atob("{prize_b64}"))));
    
    function isMobile() {{ return window.innerWidth <= 768; }}
    
    function copyClip(idx, btn, evt) {{
        evt.stopPropagation();
        var text = clipData[idx];
        if (!text) return;
        
        // 📱 모바일: 네이티브 공유 (카톡 직접 선택 가능)
        if (isMobile() && navigator.share) {{
            navigator.share({{ text: text }}).then(function() {{
                showCopied(btn);
            }}).catch(function() {{
                fallbackCopy(text, btn);
            }});
            return;
        }}
        
        // 🖥️ PC: 동일 클릭 이벤트 내에서 즉시 복사 시도
        fallbackCopy(text, btn);
    }}
    function fallbackCopy(text, btn) {{
        // 방법 1: 임시 textarea + execCommand (user gesture 내)
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        ta.setSelectionRange(0, 999999);
        var ok = false;
        try {{ ok = document.execCommand('copy'); }} catch(e) {{}}
        document.body.removeChild(ta);
        
        if (ok) {{
            showCopied(btn);
            return;
        }}
        
        // 방법 2: Clipboard API
        if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function() {{
                showCopied(btn);
            }}).catch(function() {{
                showOverlay(text);
            }});
            return;
        }}
        
        // 방법 3: 오버레이 (수동 복사)
        showOverlay(text);
    }}
    function showOverlay(text) {{
        var ov = document.getElementById('clip-overlay');
        var ta = document.getElementById('clip-ta');
        ta.value = text;
        ov.style.display = 'flex';
        setTimeout(function() {{ ta.focus(); ta.select(); ta.setSelectionRange(0, 999999); }}, 100);
    }}
    function doCopyOverlay() {{
        var ta = document.getElementById('clip-ta');
        var text = ta.value;
        
        // 임시 textarea로 복사 (오버레이 textarea 대신 새로 만들어서)
        var tmp = document.createElement('textarea');
        tmp.value = text;
        tmp.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0;';
        document.body.appendChild(tmp);
        tmp.focus();
        tmp.select();
        tmp.setSelectionRange(0, 999999);
        var ok = false;
        try {{ ok = document.execCommand('copy'); }} catch(e) {{}}
        document.body.removeChild(tmp);
        
        if (!ok) {{
            // 원래 textarea로도 시도
            ta.readOnly = false;
            ta.focus(); ta.select(); ta.setSelectionRange(0, 999999);
            try {{ ok = document.execCommand('copy'); }} catch(e2) {{}}
            ta.readOnly = true;
        }}
        
        var btn = document.getElementById('clip-copy-btn');
        btn.textContent = ok ? '✅ 복사 완료!' : '⚠️ 텍스트를 직접 선택 후 Ctrl+C';
        btn.style.background = ok ? '#22C55E' : '#f59e0b'; btn.style.color = '#fff';
        if (ok) {{
            setTimeout(function() {{
                document.getElementById('clip-overlay').style.display = 'none';
                btn.textContent = '📋 복사하기';
                btn.style.background = '#FEE500'; btn.style.color = '#3C1E1E';
            }}, 1200);
        }} else {{
            // 실패 시 textarea를 편집 가능하게 열어두고 선택 상태 유지
            ta.readOnly = false;
            ta.focus(); ta.select(); ta.setSelectionRange(0, 999999);
        }}
    }}
    function showCopied(btn) {{
        var orig = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = '✅ 복사 완료!';
        setTimeout(function() {{ btn.classList.remove('copied'); btn.innerHTML = orig; }}, 1500);
    }}
    function showPrize(idx, evt) {{
        if (evt) evt.stopPropagation();
        var h = prizeHtml[idx];
        if (!h) {{ alert('시상금 데이터가 없습니다.'); return; }}
        document.getElementById('prize-content').innerHTML = h;
        document.getElementById('prize-overlay').style.display = 'flex';
    }}
    
    function applyFreeze() {{
        var t = document.getElementById("{table_id}");
        // 모바일에서는 고정 열 최대 2개로 제한
        FC = isMobile() ? Math.min(FC_DESKTOP, 2) : FC_DESKTOP;
        if (!t || FC === 0) return;
        var fr = t.querySelector("tbody tr");
        if (!fr) return;
        var lp = [], cl = 0;
        for (var i = 0; i < FC; i++) {{ lp.push(cl); if (fr.cells[i]) cl += fr.cells[i].offsetWidth; }}
        t.querySelectorAll(".col-freeze").forEach(function(c) {{
            var idx = parseInt(c.getAttribute("data-col"));
            if (!isNaN(idx) && idx < FC) {{
                c.style.left = lp[idx] + "px";
                c.style.position = "sticky";
                c.style.zIndex = c.tagName === "TH" ? "3" : "1";
            }} else if (!isNaN(idx) && idx >= FC) {{
                // 모바일에서 초과 고정 열 해제
                c.style.position = "static";
                c.style.boxShadow = "none";
            }}
        }});
    }}
    function autoResize() {{
        if (!window.frameElement) return;
        var vh = window.parent.innerHeight || 900;
        if (isMobile()) {{
            var mv = document.querySelector('.mobile-view');
            if (mv) window.frameElement.style.height = Math.min(mv.scrollHeight + 20, Math.round(vh * 0.80)) + "px";
        }} else {{
            var w = document.getElementById("wrap_{table_id}");
            if (w) window.frameElement.style.height = Math.min(w.scrollHeight + 4, Math.round(vh * 0.85)) + "px";
        }}
    }}
    window.addEventListener('load', function() {{ applyFreeze(); autoResize(); }});
    window.addEventListener('resize', function() {{ applyFreeze(); autoResize(); }});
    var ss = {{}};
    function sortTable(th) {{
        var t = document.getElementById("{table_id}");
        var tb = t.querySelector("tbody");
        var rows = Array.from(tb.querySelectorAll("tr"));
        var ci = parseInt(th.getAttribute("data-col"));
        if (isNaN(ci)) return;
        var asc = ss[ci] !== true; ss = {{}}; ss[ci] = asc;
        rows.sort(function(a, b) {{
            var aT = a.cells[ci].textContent.trim(), bT = b.cells[ci].textContent.trim();
            var aN = parseFloat(aT.replace(/,/g,"")), bN = parseFloat(bT.replace(/,/g,""));
            if (aT === "" && bT === "") return 0;
            if (aT === "") return 1; if (bT === "") return -1;
            if (!isNaN(aN) && !isNaN(bN)) return asc ? aN - bN : bN - aN;
            return asc ? aT.localeCompare(bT,'ko') : bT.localeCompare(aT,'ko');
        }});
        rows.forEach(function(r) {{ tb.appendChild(r); }});
        // 순번 재배정
        var allRows = tb.querySelectorAll("tr");
        allRows.forEach(function(r, idx) {{ if (r.cells[0]) r.cells[0].textContent = idx + 1; }});
        t.querySelectorAll("thead th").forEach(function(h) {{
            var ar = h.querySelector(".sa"); if (!ar) return;
            var hi = parseInt(h.getAttribute("data-col"));
            if (hi === ci) {{ ar.textContent = asc ? "▲" : "▼"; ar.className = "sa active"; }}
            else {{ ar.textContent = "▲▼"; ar.className = "sa"; }}
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

# 백업/초기화는 관리자 로그인 후에만 표시
if st.session_state.get('admin_authenticated', False) and menu == "관리자 화면 (설정)":
    st.sidebar.divider()
    with st.sidebar.expander("💾 설정 백업 / 복원"):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'rb') as f:
                cfg_bytes = f.read()
            st.download_button("⬇️ 현재 설정 다운로드", cfg_bytes,
                             file_name="meritz_config_backup.pkl", mime="application/octet-stream")
        else:
            st.caption("저장된 설정이 없습니다.")
        restore_file = st.file_uploader("⬆️ 백업 파일로 복원", type=['pkl'], key="restore_pkl")
        if restore_file is not None:
            if st.button("복원 실행", key="btn_restore"):
                try:
                    test = pickle.loads(restore_file.getvalue())
                    if isinstance(test, dict):
                        with open(CONFIG_FILE, 'wb') as f:
                            f.write(restore_file.getvalue())
                        _reset_session_state()
                        load_data_and_config()
                        st.success("✅ 복원 완료!")
                        st.rerun()
                    else:
                        st.error("유효하지 않은 파일입니다.")
                except Exception as e:
                    st.error(f"복원 실패: {e}")
    with st.sidebar.expander("⚠️ 시스템 초기화 (주의)"):
        st.caption("모든 설정과 데이터가 삭제됩니다.")
        confirm = st.text_input("'reset' 입력 후 실행", key="reset_confirm")
        if st.button("🔄 초기화 실행", disabled=(confirm != "reset")):
            for fp in [CONFIG_FILE, DATA_FILE]:
                try:
                    if os.path.exists(fp):
                        shutil.copy2(fp, fp + ".before_reset")
                        os.remove(fp)
                except Exception:
                    pass
            _reset_session_state()
            st.rerun()

# ==========================================
# 4. 관리자 화면 (Admin View)
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    
    ADMIN_PASSWORD = "wolf7998"
    
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
                        # ✅ 파일 생성일자 추출 (최신 날짜 저장)
                        file_dates = []
                        for f_obj in [file1, file2]:
                            if f_obj.name.endswith('.xlsx'):
                                try:
                                    import openpyxl
                                    wb = openpyxl.load_workbook(io.BytesIO(f_obj.getvalue()), read_only=True)
                                    d = wb.properties.modified or wb.properties.created
                                    if d: file_dates.append(d)
                                    wb.close()
                                except Exception:
                                    pass
                        if file_dates:
                            st.session_state['data_date'] = max(file_dates).strftime("%Y.%m.%d")
                        else:
                            st.session_state['data_date'] = datetime.now().strftime("%Y.%m.%d")
                        
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
                        # (section 7에서 col_order 재계산 시 자동 정리됨)
                        
                        save_data()    # DataFrame 저장 (무거움 — 여기서만 호출)
                        save_config()  # 설정 저장 (가벼움)
                        st.success(f"✅ 데이터 교체 완료! 총 {len(df_merged)}행 | 기존 설정이 유지되었습니다.")
                        st.rerun()
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

    st.divider()
    
    # ✅ 설정 검증 경고 표시 (열이 사라진 경우)
    if has_data():
        warnings = []
        if not st.session_state['manager_col']:
            warnings.append("⚠️ **매니저 코드 열**이 설정되지 않았습니다. 아래 3번에서 다시 선택해주세요.")
        if not st.session_state['manager_name_col']:
            warnings.append("⚠️ **매니저 이름 열**이 설정되지 않았습니다. 아래 3번에서 다시 선택해주세요.")
        for w in warnings:
            st.warning(w)
        df = st.session_state['df_merged']
        available_columns = [c for c in df.columns if c not in ['merge_key1', 'merge_key2', '_unified_search_key']]
        
        # ========================================
        st.header("2. 📅 기준일 및 카톡 복사 문구 설정")
        with st.form("date_footer_form"):
            current_date = st.session_state.get('data_date', '')
            new_date = st.text_input("데이터 기준일 (예: 2026.02.24)", value=current_date)
            
            default_footer = "팀장님! 시상 부족금액 안내드려요!\n부족한 거 챙겨서 꼭 시상 많이 받아 가셨으면 좋겠습니다!\n좋은 하루 되세요!"
            current_footer = st.session_state.get('clip_footer', '') or default_footer
            new_footer = st.text_area("카톡 하단 인사말 (줄바꿈 가능)", value=current_footer, height=100)
            
            if st.form_submit_button("저장"):
                st.session_state['data_date'] = new_date
                st.session_state['clip_footer'] = new_footer
                save_data_and_config()
                st.rerun()
        
        # ========================================
        st.header("3. 매니저 로그인 및 이름 표시 열 설정")
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
        st.header("4. 표시할 데이터 항목 및 필터 추가")
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
                    fb_text = f" (대체: `{item['fallback_col']}`)" if item.get('fallback_col') else ""
                    st.markdown(f"- 📄 원본: `{item['col']}`{fb_text} | **화면 표시: [{disp}]** ({item['type']}) | 조건: `{item['condition']}`")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_col_{i}"):
                        st.session_state['admin_cols'].pop(i)
                        save_data_and_config()
                        st.rerun()

        st.divider()

        # ========================================
        st.header("5. 목표 구간 설정 (기준열 연동 가능)")
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
                    st.markdown(f"- **{goal['target_col']}** | 구간: {', '.join(tiers_display)}{ref_text}")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_goal_{i}"):
                        goals.pop(i)
                        st.session_state['admin_goals'] = goals
                        save_data_and_config()
                        st.rerun()

        st.divider()

        # ========================================
        st.header("6. 맞춤형 분류(태그) 설정 (3개 조건 조합)")
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
                    st.markdown(f"- 조건: **{' AND '.join(cond_strs)}** | **[{cat['name']}]** 태그 부여")
                with row_c2:
                    if st.button("❌ 삭제", key=f"del_cat_{i}"):
                        st.session_state['admin_categories'].pop(i)
                        save_data_and_config()
                        st.rerun()

        st.divider()

        # ========================================
        st.header("7. 📋 화면 표시 순서 커스텀 설정")
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
            # 자동 저장하지 않음 — 다른 설정 변경 시 함께 저장됨

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
        st.header("8. 📊 항목 그룹 헤더 설정")
        st.caption("여러 항목을 묶어서 상단에 그룹명을 표시합니다. (예: A, B, C 항목을 '2~3월 시책 현황')")
        
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
                        st.markdown(f"- **[{grp['name']}]** : {', '.join(grp['cols'])}")
                    with row_c2:
                        if st.button("❌ 삭제", key=f"del_grp_{i}"):
                            st.session_state['col_groups'].pop(i)
                            save_data_and_config()
                            st.rerun()
        else:
            st.info("먼저 7번에서 표시 순서를 설정해주세요.")
        
        # ========================================
        st.divider()
        st.header("9. 💰 시상금 설정")
        st.caption("시상금 시책을 설정합니다. 실적과 시상금을 파일에서 직접 읽어옵니다. 매니저 화면의 📋 카톡에 시상금이 포함되고 💰 버튼이 표시됩니다.")
        
        prize_cfgs = st.session_state.get('prize_config', [])
        
        # ── 주차/브릿지 시상 추가 ──
        st.markdown("**📌 주차/브릿지 시상**")
        if st.button("➕ 주차/브릿지 시상 추가", key="add_prize_weekly"):
            prize_cfgs.append({
                "name": f"신규 시책 {len(prize_cfgs)+1}", "category": "weekly",
                "type": "구간 시책", "col_code": "", "col_val": "",
                "col_val_prev": "", "col_val_curr": "",
                "prize_items": [{"label": "시상금", "col_eligible": "", "col_prize": ""}],
                "curr_req": 100000.0,
                "tiers": [(500000, 300), (300000, 200), (200000, 200), (100000, 100)]
            })
            st.session_state['prize_config'] = prize_cfgs
            save_data_and_config()
            st.rerun()
        
        weekly_prizes = [(i, c) for i, c in enumerate(prize_cfgs) if c.get('category', 'weekly') == 'weekly']
        for idx, cfg in weekly_prizes:
            with st.expander(f"📌 {cfg.get('name', '시책')} ({cfg.get('type', '구간')})", expanded=False):
                c1, c2 = st.columns([8, 2])
                with c2:
                    if st.button("🗑️ 삭제", key=f"del_prize_{idx}"):
                        prize_cfgs.pop(idx)
                        st.session_state['prize_config'] = prize_cfgs
                        save_data_and_config()
                        st.rerun()
                
                cfg['name'] = st.text_input("시책명", value=cfg.get('name', ''), key=f"pname_{idx}")
                
                type_idx = 0
                if "1기간" in cfg.get('type', ''): type_idx = 1
                elif "2기간" in cfg.get('type', ''): type_idx = 2
                cfg['type'] = st.radio("시책 종류", 
                    ["구간 시책", "브릿지 시책 (1기간: 시상 확정)", "브릿지 시책 (2기간: 당월 달성 조건)"],
                    index=type_idx, horizontal=True, key=f"ptype_{idx}")
                
                cols = available_columns
                def _gi(v, opts): return opts.index(v) if v in opts else 0
                
                cfg['col_code'] = st.selectbox("설계사코드(사번) 열", cols, index=_gi(cfg.get('col_code',''), cols), key=f"pccode_{idx}")
                
                if "1기간" in cfg['type']:
                    c1, c2 = st.columns(2)
                    with c1: cfg['col_val_prev'] = st.selectbox("전월 실적 열", cols, index=_gi(cfg.get('col_val_prev',''), cols), key=f"pprev_{idx}")
                    with c2: cfg['col_val_curr'] = st.selectbox("당월 실적 열", cols, index=_gi(cfg.get('col_val_curr',''), cols), key=f"pcurr_{idx}")
                elif "2기간" in cfg['type']:
                    cfg['col_val_curr'] = st.selectbox("당월 실적 열", cols, index=_gi(cfg.get('col_val_curr',''), cols), key=f"pcurr2_{idx}")
                else:
                    cfg['col_val'] = st.selectbox("실적 수치 열", cols, index=_gi(cfg.get('col_val',''), cols), key=f"pval_{idx}")
                
                if "2기간" in cfg['type']:
                    # 🌟 브릿지2: 구간/지급률 계산
                    cfg['curr_req'] = st.number_input("당월 필수 달성 금액 (합산용)", value=float(cfg.get('curr_req', 100000.0)), step=10000.0, key=f"creq2_{idx}")
                    st.write("📈 구간 설정 (달성금액, 지급률%)")
                    tier_str = "\n".join([f"{int(t[0])},{int(t[1])}" for t in cfg.get('tiers', [])])
                    tier_input = st.text_area("엔터로 줄바꿈", value=tier_str, height=120, key=f"tier_{idx}")
                    try:
                        new_tiers = []
                        for line in tier_input.strip().split('\n'):
                            if ',' in line:
                                parts = line.split(',')
                                new_tiers.append((float(parts[0].strip()), float(parts[1].strip())))
                        cfg['tiers'] = sorted(new_tiers, key=lambda x: x[0], reverse=True)
                    except:
                        st.error("형식이 올바르지 않습니다.")
                    st.caption("💡 브릿지 2기간: (확보구간 + 당월가동금액) × 지급률")
                else:
                    # 🌟 구간/브릿지1: 시상금 다중 항목 직접 읽기
                    st.markdown("**💰 시상금 항목 (여러 개 가능)**")
                    st.caption("지급률 컬럼: 0이면 미대상(미표시). 공란이면 무조건 대상 처리.")
                    if 'prize_items' not in cfg:
                        old_col = cfg.pop('col_prize', '') or cfg.pop('col', '')
                        cfg['prize_items'] = [{"label": "시상금", "col_eligible": "", "col_prize": old_col}] if old_col else [{"label": "시상금", "col_eligible": "", "col_prize": ""}]
                    for _pi in cfg.get('prize_items', []):
                        if 'col' in _pi and 'col_prize' not in _pi:
                            _pi['col_prize'] = _pi.pop('col', '')
                        if 'col_eligible' not in _pi:
                            _pi['col_eligible'] = ''
                    
                    cols_with_blank = ["(공란)"] + cols
                    updated_items = []
                    for pi_idx, pi in enumerate(cfg.get('prize_items', [])):
                        st.markdown(f"<div style='background:#f8f9fa;padding:6px 8px;border-radius:6px;margin:4px 0;'>", unsafe_allow_html=True)
                        pc1, pc4 = st.columns([8, 2])
                        with pc1:
                            pi['label'] = st.text_input("시상명", value=pi.get('label', ''), key=f"wpilbl_{idx}_{pi_idx}", placeholder="시상 항목명")
                        with pc4:
                            if st.button("🗑️", key=f"wpidel_{idx}_{pi_idx}", use_container_width=True):
                                st.markdown("</div>", unsafe_allow_html=True)
                                continue
                        pc2, pc3 = st.columns(2)
                        with pc2:
                            cur_elig = pi.get('col_eligible', '')
                            elig_idx = cols_with_blank.index(cur_elig) if cur_elig in cols_with_blank else 0
                            sel_elig = st.selectbox("지급률 컬럼 (0=미대상)", cols_with_blank, index=elig_idx, key=f"wpielig_{idx}_{pi_idx}")
                            pi['col_eligible'] = sel_elig if sel_elig != "(공란)" else ""
                        with pc3:
                            cur_prize = pi.get('col_prize', '')
                            prize_idx = cols_with_blank.index(cur_prize) if cur_prize in cols_with_blank else 0
                            sel_prize = st.selectbox("예정시상금 컬럼", cols_with_blank, index=prize_idx, key=f"wpiprz_{idx}_{pi_idx}")
                            pi['col_prize'] = sel_prize if sel_prize != "(공란)" else ""
                        st.markdown("</div>", unsafe_allow_html=True)
                        updated_items.append(pi)
                    cfg['prize_items'] = updated_items
                    
                    if st.button("➕ 시상금 항목 추가", key=f"wpiadd_{idx}", use_container_width=True):
                        cfg['prize_items'].append({"label": f"시상금{len(cfg['prize_items'])+1}", "col_eligible": "", "col_prize": ""})
                        st.rerun()
                
                if st.button("💾 이 시책 저장", key=f"psave_{idx}"):
                    st.session_state['prize_config'] = prize_cfgs
                    save_data_and_config()
                    st.success(f"'{cfg['name']}' 저장됨")
        
        st.markdown("---")
        
        # ── 누계 시상 추가 ──
        st.markdown("**📈 월간 누계 시상**")
        if st.button("➕ 누계 시상 추가", key="add_prize_cumul"):
            prize_cfgs.append({
                "name": f"신규 누계 {len(prize_cfgs)+1}", "category": "cumulative",
                "type": "누계", "col_code": "", "col_val": "",
                "prize_items": [{"label": "시상금", "col_eligible": "", "col_prize": ""}]
            })
            st.session_state['prize_config'] = prize_cfgs
            save_data_and_config()
            st.rerun()
        
        cumul_prizes = [(i, c) for i, c in enumerate(prize_cfgs) if c.get('category') == 'cumulative']
        for idx, cfg in cumul_prizes:
            with st.expander(f"📈 {cfg.get('name', '누계')}", expanded=False):
                c1, c2 = st.columns([8, 2])
                with c2:
                    if st.button("🗑️ 삭제", key=f"del_prize_{idx}"):
                        prize_cfgs.pop(idx)
                        st.session_state['prize_config'] = prize_cfgs
                        save_data_and_config()
                        st.rerun()
                
                cols = available_columns
                def _gi(v, opts): return opts.index(v) if v in opts else 0
                
                cfg['name'] = st.text_input("누계 항목명", value=cfg.get('name', ''), key=f"pname_{idx}")
                cfg['col_code'] = st.selectbox("설계사코드(사번) 열", cols, index=_gi(cfg.get('col_code',''), cols), key=f"pccode_{idx}")
                cfg['col_val'] = st.selectbox("누계 실적 열", cols, index=_gi(cfg.get('col_val',''), cols), key=f"pval_{idx}")
                
                # 🌟 시상금 다중 항목 설정
                st.markdown("**💰 시상금 항목 (여러 개 가능)**")
                st.caption("지급률 컬럼: 0이면 미대상(미표시). 공란이면 무조건 대상 처리.")
                if 'prize_items' not in cfg:
                    old_col = cfg.pop('col_prize', '')
                    cfg['prize_items'] = [{"label": "시상금", "col_eligible": "", "col_prize": old_col}] if old_col else [{"label": "시상금", "col_eligible": "", "col_prize": ""}]
                for _pi in cfg.get('prize_items', []):
                    if 'col' in _pi and 'col_prize' not in _pi:
                        _pi['col_prize'] = _pi.pop('col', '')
                    if 'col_eligible' not in _pi:
                        _pi['col_eligible'] = ''
                
                cols_with_blank = ["(공란)"] + cols
                updated_items = []
                for pi_idx, pi in enumerate(cfg.get('prize_items', [])):
                    st.markdown(f"<div style='background:#f0f4ff;padding:6px 8px;border-radius:6px;margin:4px 0;'>", unsafe_allow_html=True)
                    pc1, pc4 = st.columns([8, 2])
                    with pc1:
                        pi['label'] = st.text_input("시상명", value=pi.get('label', ''), key=f"cpilbl_{idx}_{pi_idx}", placeholder="시상 항목명")
                    with pc4:
                        if st.button("🗑️", key=f"cpidel_{idx}_{pi_idx}", use_container_width=True):
                            st.markdown("</div>", unsafe_allow_html=True)
                            continue
                    pc2, pc3 = st.columns(2)
                    with pc2:
                        cur_elig = pi.get('col_eligible', '')
                        elig_idx = cols_with_blank.index(cur_elig) if cur_elig in cols_with_blank else 0
                        sel_elig = st.selectbox("지급률 컬럼 (0=미대상)", cols_with_blank, index=elig_idx, key=f"cpielig_{idx}_{pi_idx}")
                        pi['col_eligible'] = sel_elig if sel_elig != "(공란)" else ""
                    with pc3:
                        cur_prize = pi.get('col_prize', '')
                        prize_idx = cols_with_blank.index(cur_prize) if cur_prize in cols_with_blank else 0
                        sel_prize = st.selectbox("예정시상금 컬럼", cols_with_blank, index=prize_idx, key=f"cpiprz_{idx}_{pi_idx}")
                        pi['col_prize'] = sel_prize if sel_prize != "(공란)" else ""
                    st.markdown("</div>", unsafe_allow_html=True)
                    updated_items.append(pi)
                cfg['prize_items'] = updated_items
                
                if st.button("➕ 시상금 항목 추가", key=f"cpiadd_{idx}", use_container_width=True):
                    cfg['prize_items'].append({"label": f"시상금{len(cfg['prize_items'])+1}", "col_eligible": "", "col_prize": ""})
                    st.rerun()
                
                if st.button("💾 이 항목 저장", key=f"psave_{idx}"):
                    st.session_state['prize_config'] = prize_cfgs
                    save_data_and_config()
                    st.success(f"'{cfg['name']}' 저장됨")
        
        if not prize_cfgs:
            st.info("시상금 시책이 없습니다. 위 버튼으로 추가하거나, 아래에서 기존 앱의 설정을 가져오세요.")
        
        st.markdown("---")
        st.markdown("**📥 기존 시상금 앱에서 설정 가져오기**")
        st.caption("기존 시상금 계산 앱의 config.json 파일을 업로드하면 시책 설정이 자동으로 변환됩니다.")
        json_file = st.file_uploader("config.json 파일 업로드", type=['json'], key="import_prize_json")
        if json_file is not None:
            try:
                imported = json.load(json_file)
                if not isinstance(imported, list):
                    st.error("올바른 config.json 형식이 아닙니다.")
                else:
                    # 호환성 처리
                    for c in imported:
                        if 'category' not in c: c['category'] = 'weekly'
                        # file 키 제거 (우리 앱은 df_merged 사용)
                        c.pop('file', None)
                        c.pop('col_name', None)
                        c.pop('col_branch', None)
                        c.pop('col_agency', None)
                        c.pop('col_manager_code', None)
                        c.pop('col_manager', None)
                    
                    weekly_cnt = sum(1 for c in imported if c.get('category', 'weekly') == 'weekly')
                    cumul_cnt = sum(1 for c in imported if c.get('category') == 'cumulative')
                    st.success(f"✅ {len(imported)}개 시책 감지됨 (주차/브릿지 {weekly_cnt}개 + 누계 {cumul_cnt}개)")
                    
                    for c in imported:
                        st.markdown(f"- {'📌' if c.get('category')=='weekly' else '📈'} **{c.get('name', '?')}** ({c.get('type', '?')})")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("✅ 기존 설정에 추가 (병합)", key="merge_json"):
                            prize_cfgs.extend(imported)
                            st.session_state['prize_config'] = prize_cfgs
                            save_data_and_config()
                            st.success("기존 설정에 추가 완료!")
                            st.rerun()
                    with col_b:
                        if st.button("🔄 기존 설정 대체 (교체)", key="replace_json"):
                            st.session_state['prize_config'] = imported
                            save_data_and_config()
                            st.success("설정 교체 완료!")
                            st.rerun()
            except json.JSONDecodeError:
                st.error("JSON 파일 형식이 올바르지 않습니다.")
            
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
          try:
            manager_name = "매니저"
            if manager_name_col in my_df.columns:
                name_vals = my_df[manager_name_col].dropna()
                if not name_vals.empty:
                    manager_name = str(name_vals.iloc[0])
            
            data_date = st.session_state.get('data_date', '')
            date_html = f"<span class='data-date' style='font-size:14px; color:rgba(255,255,255,0.85); float:right; margin-top:8px;'>📅 데이터 기준일: {data_date}</span>" if data_date else ""
            
            st.markdown(f"""
            <div class='toss-header'>
                {date_html}
                <h1 class='toss-title'>{manager_name} <span class='toss-subtitle'>({manager_code_clean})</span></h1>
                <p class='toss-desc'>산하 팀장분들의 실적 현황입니다. (총 {len(my_df)}명)</p>
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
                
                # 순번 열 추가 (맨 앞)
                final_df.insert(0, '순번', range(1, len(final_df) + 1))
                
                # 5. 세 자리 콤마(,) 포맷팅 및 [0값 빈칸 숨김 처리]
                for c in final_df.columns:
                    if c != '순번' and '코드' not in c and '연도' not in c:
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
                
                # 💰 시상금 계산 (자체 통합 — prize_config + df_merged)
                prize_data_map = {}
                try:
                    prize_config = st.session_state.get('prize_config', [])
                    if prize_config:
                        df_full = st.session_state.get('df_merged', pd.DataFrame())
                        if not df_full.empty:
                            # 사번 열 찾기
                            code_col = None
                            if '_unified_search_key' in my_df.columns:
                                code_col = '_unified_search_key'
                            else:
                                for c in my_df.columns:
                                    if '설계사코드' in c or '사번' in c:
                                        code_col = c; break
                                if not code_col:
                                    mk1 = st.session_state.get('merge_key1_col', '')
                                    if mk1 and mk1 in my_df.columns:
                                        code_col = mk1
                            
                            if code_col:
                                for row_idx, (_, row) in enumerate(final_df.iterrows()):
                                    orig_idx = row.name
                                    if orig_idx in my_df.index:
                                        raw_code = my_df.loc[orig_idx, code_col] if code_col in my_df.columns else ''
                                        agent_code = clean_key(str(raw_code)) if not pd.isna(raw_code) else ''
                                        if agent_code:
                                            results, total = calculate_prize_for_code(agent_code, prize_config, df_full)
                                            if results:
                                                prize_data_map[row_idx] = (results, total)
                except Exception:
                    pass
                
                table_html = render_html_table(final_df, col_groups=col_groups, prize_data_map=prize_data_map)
                
                # 테이블 내부 스크롤 사용 — iframe 높이는 뷰포트 85%로 제한
                components.html(table_html, height=800, scrolling=False)
          except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
            st.info("관리자 화면에서 설정을 확인해주세요.")

