import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import re
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="메리츠화재 시상 현황", layout="wide")

DATA_DIR = "app_data"
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

LOG_FILE = os.path.join(DATA_DIR, "access_log.csv")

# ==========================================
# 🔧 numpy 타입 JSON 직렬화 지원
# ==========================================
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)): return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, (np.bool_,)): return bool(obj)
        return super().default(obj)

import re as _re
def _clean_excel_text(s):
    if not s or not isinstance(s, str): return s
    return _re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), s)

def save_log(user_name, user_code, action_type):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_data = pd.DataFrame([[now, user_name, user_code, action_type]], columns=["시간","이름/구분","코드","작업"])
    if not os.path.exists(LOG_FILE): log_data.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")
    else: log_data.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")

def copy_btn_component(text):
    escaped_text = json.dumps(text, ensure_ascii=False)
    js_code = f"""
    <div id="copy-container"><button id="copy-btn">💬 카카오톡 메시지 원클릭 복사</button></div>
    <script>
    document.getElementById("copy-btn").onclick = function() {{
        const text = {escaped_text};
        navigator.clipboard.writeText(text).then(function() {{
            alert("메시지가 복사되었습니다! 원하시는 채팅창에 붙여넣기(Ctrl+V) 하세요.");
        }}, function(err) {{ console.error('복사 실패:', err); }});
    }}
    </script>
    <style>
        #copy-btn {{ width:100%; height:55px; background-color:#FEE500; color:#3C1E1E;
            border:none; border-radius:12px; font-weight:800; font-size:1.1rem;
            cursor:pointer; margin-top:5px; margin-bottom:20px; box-shadow:0 4px 10px rgba(0,0,0,0.1); }}
        #copy-btn:active {{ transform:scale(0.98); }}
    </style>"""
    components.html(js_code, height=85)

def safe_str(val):
    if pd.isna(val) or val is None: return ""
    try:
        if isinstance(val, (int, float)) and float(val).is_integer(): val = int(float(val))
    except: pass
    s = str(val)
    s = re.sub(r'_[xX]([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r'\s+', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s.upper()

def get_clean_series(df, col_name):
    clean_col_name = f"_clean_{col_name}"
    if clean_col_name not in df.columns:
        df[clean_col_name] = df[col_name].apply(safe_str)
    return df[clean_col_name]

def safe_float(val):
    if pd.isna(val) or val is None: return 0.0
    s = str(val).replace(',', '').strip()
    try: return float(s)
    except: return 0.0

def _get_idx(val, opts):
    return opts.index(val) if val in opts else 0

def _get_cols_for_file(file_name):
    df = st.session_state['raw_data'].get(file_name)
    if df is not None:
        return [c for c in df.columns.tolist() if not c.startswith('_clean_')]
    return []

# ==========================================
# 🔗 사전 병합(Pre-Merge)
# ==========================================
def build_merged_data(config_list, raw_data):
    merged = {}
    for idx, cfg in enumerate(config_list):
        base_file = cfg.get('file', '')
        df_base = raw_data.get(base_file)
        if df_base is None: continue
        result = df_base.copy()
        col_code = cfg.get('col_code', '')
        if not col_code or col_code not in result.columns:
            merged[idx] = result; continue
        ext_files = {}
        for pi in cfg.get('prize_items', []):
            pi_file = pi.get('file', '') or ''
            if not pi_file or pi_file == base_file: continue
            if pi_file not in ext_files:
                ext_files[pi_file] = {'col_code_ext': pi.get('col_code_ext', ''), 'cols': set()}
            col_p = pi.get('col_prize', '')
            col_e = pi.get('col_eligible', '')
            if col_p: ext_files[pi_file]['cols'].add(col_p)
            if col_e: ext_files[pi_file]['cols'].add(col_e)
        if ext_files:
            result['_merge_key'] = result[col_code].apply(safe_str)
            for ext_fname, ext_info in ext_files.items():
                df_ext = raw_data.get(ext_fname)
                if df_ext is None: continue
                col_code_ext = ext_info['col_code_ext']
                if not col_code_ext or col_code_ext not in df_ext.columns: continue
                available = [c for c in ext_info['cols'] if c in df_ext.columns]
                if not available: continue
                df_e = df_ext.copy()
                df_e['_merge_key'] = df_e[col_code_ext].apply(safe_str)
                for c in available:
                    if c in result.columns: result.drop(columns=[c], inplace=True, errors='ignore')
                keep = ['_merge_key'] + available
                result = pd.merge(result, df_e[keep].drop_duplicates(subset=['_merge_key']),
                                  on='_merge_key', how='left')
            result.drop(columns=['_merge_key'], inplace=True, errors='ignore')
        merged[idx] = result
    return merged

def save_merged_to_disk(merged_data):
    for idx, df in merged_data.items():
        df.to_pickle(os.path.join(DATA_DIR, f"_merged_{idx}.pkl"))
    for f in os.listdir(DATA_DIR):
        if f.startswith('_merged_') and f.endswith('.pkl'):
            try:
                fidx = int(f.replace('_merged_','').replace('.pkl',''))
                if fidx not in merged_data: os.remove(os.path.join(DATA_DIR, f))
            except: pass

def load_merged_from_disk(config_list):
    merged = {}
    for idx in range(len(config_list)):
        path = os.path.join(DATA_DIR, f"_merged_{idx}.pkl")
        if os.path.exists(path):
            df = pd.read_pickle(path)
            df.columns = [_clean_excel_text(str(c)) for c in df.columns]
            for col in df.select_dtypes(include='object').columns:
                df[col] = df[col].apply(lambda v: _clean_excel_text(str(v)) if pd.notna(v) else v)
            merged[idx] = df
    return merged

def _get_merged_df(cfg_index):
    merged = st.session_state.get('merged_data', {})
    if cfg_index in merged: return merged[cfg_index]
    cfg = st.session_state['config'][cfg_index]
    return st.session_state['raw_data'].get(cfg.get('file', ''))

# ==========================================
# 📦 데이터 로딩
# ==========================================
if 'raw_data' not in st.session_state:
    st.session_state['raw_data'] = {}
    for file in os.listdir(DATA_DIR):
        if file.endswith('.pkl') and not file.startswith('_merged_'):
            df = pd.read_pickle(os.path.join(DATA_DIR, file))
            df.columns = [_clean_excel_text(str(c)) for c in df.columns]
            for col in df.select_dtypes(include='object').columns:
                df[col] = df[col].apply(lambda v: _clean_excel_text(str(v)) if pd.notna(v) else v)
            st.session_state['raw_data'][file.replace('.pkl', '')] = df

if 'config' not in st.session_state:
    config_path = os.path.join(DATA_DIR, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            st.session_state['config'] = json.load(f)
    else: st.session_state['config'] = []

for c in st.session_state['config']:
    if 'category' not in c: c['category'] = 'weekly'

if 'merged_data' not in st.session_state:
    merged = load_merged_from_disk(st.session_state['config'])
    if merged: st.session_state['merged_data'] = merged
    elif st.session_state['raw_data'] and st.session_state['config']:
        st.session_state['merged_data'] = build_merged_data(st.session_state['config'], st.session_state['raw_data'])
    else: st.session_state['merged_data'] = {}

# --- CSS ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #f2f4f6; color: #191f28; }
    span.material-symbols-rounded, span[data-testid="stIconMaterial"] { display: none !important; }
    div[data-testid="stRadio"] > div { display:flex; justify-content:center; background-color:#ffffff; padding:10px; border-radius:15px; margin-bottom:20px; margin-top:10px; box-shadow:0 4px 15px rgba(0,0,0,0.03); border:1px solid #e5e8eb; }
    .title-band { background-color:rgb(128,0,0); color:#ffffff; font-size:1.4rem; font-weight:800; text-align:center; padding:16px; border-radius:12px; margin-bottom:24px; letter-spacing:-0.5px; box-shadow:0 4px 10px rgba(128,0,0,0.2); }
    [data-testid="stForm"] { background-color:transparent; border:none; padding:0; margin-bottom:24px; }
    .admin-title { color:#191f28; font-weight:800; font-size:1.8rem; margin-top:20px; }
    .sub-title { color:#191f28; font-size:1.4rem; margin-top:30px; font-weight:700; }
    .config-title { color:#191f28; font-size:1.3rem; margin:0; font-weight:700; }
    .main-title { color:#191f28; font-weight:800; font-size:1.3rem; margin-bottom:15px; }
    .blue-title { color:#1e3c72; font-size:1.4rem; margin-top:10px; font-weight:800; }
    .agent-title { color:#3182f6; font-weight:800; font-size:1.5rem; margin-top:0; text-align:center; }
    .config-box { background:#f9fafb; padding:15px; border-radius:15px; border:1px solid #e5e8eb; margin-top:15px; }
    .config-box-blue { background:#f0f4f8; padding:15px; border-radius:15px; border:1px solid #c7d2fe; margin-top:15px; }
    .detail-box { background:#ffffff; padding:20px; border-radius:20px; border:2px solid #e5e8eb; margin-top:10px; margin-bottom:30px; }
    .summary-card { background:linear-gradient(135deg,rgb(160,20,20) 0%,rgb(128,0,0) 100%); border-radius:20px; padding:32px 24px; margin-bottom:24px; border:none; box-shadow:0 10px 25px rgba(128,0,0,0.25); }
    .cumulative-card { background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%); border-radius:20px; padding:32px 24px; margin-bottom:24px; border:none; box-shadow:0 10px 25px rgba(30,60,114,0.25); }
    .summary-label { color:rgba(255,255,255,0.85); font-size:1.15rem; font-weight:600; margin-bottom:8px; }
    .summary-total { color:#ffffff; font-size:2.6rem; font-weight:800; letter-spacing:-1px; margin-bottom:24px; white-space:nowrap; word-break:keep-all; }
    .summary-item-name { color:rgba(255,255,255,0.95); font-size:1.15rem; }
    .summary-item-val { color:#ffffff; font-size:1.3rem; font-weight:800; white-space:nowrap; }
    .summary-divider { height:1px; background-color:rgba(255,255,255,0.2); margin:16px 0; }
    .toss-card { background:#ffffff; border-radius:20px; padding:28px 24px; margin-bottom:16px; border:1px solid #e5e8eb; box-shadow:0 4px 20px rgba(0,0,0,0.03); }
    .toss-title { font-size:1.6rem; font-weight:700; color:#191f28; margin-bottom:6px; letter-spacing:-0.5px; }
    .toss-desc { font-size:1.15rem; color:rgb(128,0,0); font-weight:800; margin-bottom:24px; letter-spacing:-0.3px; line-height:1.4; word-break:keep-all; }
    .data-row { display:flex; justify-content:space-between; align-items:center; padding:12px 0; flex-wrap:nowrap; }
    .data-label { color:#8b95a1; font-size:1.1rem; word-break:keep-all; }
    .data-value { color:#333d4b; font-size:1.3rem; font-weight:600; white-space:nowrap; }
    .shortfall-row { background-color:#fff0f0; padding:14px; border-radius:12px; margin-top:15px; margin-bottom:5px; border:2px dashed #ff4b4b; text-align:center; }
    .shortfall-text { color:#d9232e; font-size:1.2rem; font-weight:800; word-break:keep-all; }
    .prize-row { display:flex; justify-content:space-between; align-items:center; padding-top:20px; margin-top:12px; flex-wrap:nowrap; }
    .prize-label { color:#191f28; font-size:1.3rem; font-weight:700; word-break:keep-all; white-space:nowrap; }
    .prize-value { color:rgb(128,0,0); font-size:1.8rem; font-weight:800; white-space:nowrap; text-align:right; }
    .toss-divider { height:1px; background-color:#e5e8eb; margin:16px 0; }
    .cumul-stack-box { background:#ffffff; border:1px solid #e5e8eb; border-left:6px solid #2a5298; border-radius:16px; padding:20px 24px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 4px 15px rgba(0,0,0,0.03); }
    .cumul-stack-info { display:flex; flex-direction:column; gap:4px; }
    .cumul-stack-title { font-size:1.25rem; color:#1e3c72; font-weight:800; word-break:keep-all; }
    .cumul-stack-val { font-size:1.05rem; color:#8b95a1; }
    .cumul-stack-prize { font-size:1.6rem; color:#d9232e; font-weight:800; text-align:right; white-space:nowrap; }
    div[data-testid="stTextInput"] input { font-size:1.3rem !important; padding:15px !important; height:55px !important; background-color:#ffffff !important; color:#191f28 !important; border:1px solid #e5e8eb !important; border-radius:12px !important; }
    div[data-testid="stSelectbox"] > div { background-color:#ffffff !important; border:1px solid #e5e8eb !important; border-radius:12px !important; }
    div[data-testid="stSelectbox"] * { font-size:1.1rem !important; }
    div.stButton > button[kind="primary"] { font-size:1.4rem !important; font-weight:800 !important; height:60px !important; border-radius:12px !important; background-color:rgb(128,0,0) !important; color:white !important; border:none !important; width:100%; margin-top:10px; margin-bottom:20px; box-shadow:0 4px 15px rgba(128,0,0,0.2) !important; }
    div.stButton > button[kind="secondary"] { font-size:1.2rem !important; font-weight:700 !important; min-height:60px !important; height:auto !important; padding:10px !important; border-radius:12px !important; background-color:#e8eaed !important; color:#191f28 !important; border:1px solid #d1d6db !important; width:100%; margin-top:5px; margin-bottom:5px; white-space:normal !important; }
    /* 오늘 접촉 대상 카드 */
    .contact-card { background:#ffffff; border-radius:20px; padding:22px 20px; margin-bottom:12px; border:1px solid #e5e8eb; box-shadow:0 4px 15px rgba(0,0,0,0.04); }
    .contact-name { font-size:1.3rem; font-weight:800; color:#191f28; }
    .contact-org { font-size:1.05rem; color:#8b95a1; margin-bottom:10px; }
    .contact-prize-total { font-size:1.6rem; font-weight:800; color:rgb(128,0,0); text-align:right; }
    .contact-shortfall { color:#d9232e; font-size:1.05rem; font-weight:700; }
    .kakao-btn { display:block; width:100%; padding:14px; background:#FEE500; color:#3C1E1E; border:none; border-radius:12px; font-size:1.2rem; font-weight:800; cursor:pointer; text-align:center; margin-top:10px; box-shadow:0 3px 8px rgba(0,0,0,0.08); }
    .kakao-btn:active { transform:scale(0.98); }
    .copy-btn { display:block; width:100%; padding:14px; background:#FEE500; color:#3C1E1E; border:none; border-radius:12px; font-size:1.2rem; font-weight:800; cursor:pointer; text-align:center; margin-top:10px; box-shadow:0 3px 8px rgba(0,0,0,0.08); }
    .msg-preview { background:#f9fafb; border:1px solid #e5e8eb; border-radius:12px; padding:14px; font-size:1.0rem; color:#333; white-space:pre-wrap; line-height:1.6; margin-top:8px; word-break:keep-all; }
    @media (prefers-color-scheme: dark) {
        [data-testid="stAppViewContainer"] { background-color:#121212 !important; color:#e0e0e0 !important; }
        label, p, .stMarkdown p { color:#e0e0e0 !important; }
        div[data-testid="stRadio"] > div { background-color:#1e1e1e !important; border-color:#333 !important; }
        .admin-title,.sub-title,.config-title,.main-title { color:#ffffff !important; }
        .blue-title,.agent-title { color:#66b2ff !important; }
        .config-box { background-color:#1a1a1a !important; border-color:#333 !important; }
        .config-box-blue { background-color:#121928 !important; border-color:#2a5298 !important; }
        .detail-box { background-color:#121212 !important; border-color:#333 !important; }
        .toss-card, .contact-card { background-color:#1e1e1e !important; border-color:#333 !important; }
        .toss-title,.contact-name { color:#ffffff !important; } .toss-desc { color:#ff6b6b !important; }
        .data-label,.contact-org { color:#a0aab5 !important; } .data-value { color:#ffffff !important; }
        .prize-label { color:#ffffff !important; } .prize-value,.contact-prize-total { color:#ff4b4b !important; }
        .toss-divider { background-color:#333 !important; }
        .shortfall-row { background-color:#2a1215 !important; border-color:#ff4b4b !important; }
        .shortfall-text,.contact-shortfall { color:#ff6b6b !important; }
        .cumul-stack-box { background-color:#1e1e1e !important; border-color:#333 !important; border-left-color:#4da3ff !important; }
        .cumul-stack-title { color:#4da3ff !important; } .cumul-stack-val { color:#a0aab5 !important; }
        .cumul-stack-prize { color:#ff4b4b !important; }
        div[data-testid="stTextInput"] input { background-color:#1e1e1e !important; color:#ffffff !important; border-color:#444 !important; }
        div[data-testid="stSelectbox"] > div { background-color:#1e1e1e !important; color:#ffffff !important; border-color:#444 !important; }
        div.stButton > button[kind="secondary"] { background-color:#2d2d2d !important; color:#ffffff !important; border-color:#444 !important; }
        .msg-preview { background-color:#1a1a1a !important; border-color:#333 !important; color:#e0e0e0 !important; }
    }
    @media (max-width: 450px) {
        .summary-total { font-size:2.1rem !important; } .prize-value { font-size:1.45rem !important; }
        .toss-title { font-size:1.4rem !important; } .shortfall-text { font-size:1.05rem !important; }
        .cumul-stack-title { font-size:1.15rem; } .cumul-stack-prize { font-size:1.4rem; }
        .contact-prize-total { font-size:1.35rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 공통 함수
# ==========================================
def _read_prize_items(cfg, match_df):
    prize_details = []
    items = cfg.get('prize_items', [])
    if items:
        for item in items:
            col_prize = item.get('col_prize', '') or item.get('col', '')
            label = item.get('label', '')
            if not col_prize or col_prize not in match_df.columns: continue
            col_elig = item.get('col_eligible', '')
            if col_elig and col_elig in match_df.columns:
                raw_elig = match_df[col_elig].values[0]
                if pd.notna(raw_elig) and str(raw_elig).strip() != '':
                    if safe_float(raw_elig) == 0: continue
            amt = safe_float(match_df[col_prize].values[0])
            prize_details.append({"label": label or col_prize, "amount": amt})
    else:
        col_prize = cfg.get('col_prize', '')
        if col_prize and col_prize in match_df.columns:
            amt = safe_float(match_df[col_prize].values[0])
            if amt != 0: prize_details.append({"label": "시상금", "amount": amt})
    return prize_details

def calculate_agent_performance(target_code):
    calculated_results = []
    for cfg_idx, cfg in enumerate(st.session_state['config']):
        df = _get_merged_df(cfg_idx)
        if df is None: continue
        col_code = cfg.get('col_code', '')
        if not col_code or col_code not in df.columns: continue
        match_df = df[get_clean_series(df, col_code) == safe_str(target_code)]
        if match_df.empty: continue
        cat = cfg.get('category', 'weekly')
        p_type = cfg.get('type', '구간 시책')
        prize_details = _read_prize_items(cfg, match_df)
        prize = sum(d['amount'] for d in prize_details)
        if cat == 'weekly':
            if "1기간" in p_type:
                if not prize_details: continue
                vp = safe_float(match_df[cfg['col_val_prev']].values[0]) if cfg.get('col_val_prev') and cfg['col_val_prev'] in df.columns else 0
                vc = safe_float(match_df[cfg['col_val_curr']].values[0]) if cfg.get('col_val_curr') and cfg['col_val_curr'] in df.columns else 0
                calculated_results.append({"name":cfg['name'],"desc":cfg.get('desc',''),"category":"weekly","type":"브릿지1","val_prev":vp,"val_curr":vc,"prize":prize,"prize_details":prize_details,"curr_req":float(cfg.get('curr_req',100000.0))})
            elif "2기간" in p_type:
                vp = safe_float(match_df[cfg['col_val_prev']].values[0]) if cfg.get('col_val_prev') and cfg['col_val_prev'] in df.columns else 0
                vc = safe_float(match_df[cfg['col_val_curr']].values[0]) if cfg.get('col_val_curr') and cfg['col_val_curr'] in df.columns else 0
                curr_req = float(cfg.get('curr_req', 100000.0))
                calc_rate=0; tier_achieved=0; prize=0
                for amt, rate in cfg.get('tiers', []):
                    if vp >= amt: tier_achieved=amt; calc_rate=rate; break
                if tier_achieved > 0: prize = (tier_achieved + curr_req) * (calc_rate / 100)
                next_tier = None
                for amt, rate in reversed(cfg.get('tiers', [])):
                    if vp < amt: next_tier = amt; break
                curr_met = vc >= curr_req
                calculated_results.append({"name":cfg['name'],"desc":cfg.get('desc',''),"category":"weekly","type":"브릿지2","val_prev":vp,"val_curr":vc,"tier":tier_achieved,"rate":calc_rate,"prize":prize,"curr_req":curr_req,"next_tier":next_tier,"shortfall":next_tier - vp if next_tier else 0,"curr_met":curr_met})
            else:
                if not prize_details: continue
                v = safe_float(match_df[cfg['col_val']].values[0]) if cfg.get('col_val') and cfg['col_val'] in df.columns else 0
                calculated_results.append({"name":cfg['name'],"desc":cfg.get('desc',''),"category":"weekly","type":"구간","val":v,"prize":prize,"prize_details":prize_details})
        elif cat == 'cumulative':
            if not prize_details: continue
            col_val = cfg.get('col_val', '')
            v = safe_float(match_df[col_val].values[0]) if col_val and col_val in match_df.columns else 0
            calculated_results.append({"name":cfg['name'],"desc":cfg.get('desc',''),"category":"cumulative","type":"누계","val":v,"prize":prize,"prize_details":prize_details})
    return calculated_results, sum(r['prize'] for r in calculated_results)

def render_ui_cards(user_name, calculated_results, total_prize_sum, show_share_text=False):
    if not calculated_results: return
    weekly_res = [r for r in calculated_results if r['category'] == 'weekly']
    cumul_res = [r for r in calculated_results if r['category'] == 'cumulative']
    weekly_total = sum(r['prize'] for r in weekly_res)
    cumul_total = sum(r['prize'] for r in cumul_res)
    share_text = f"🎯 [{user_name} 팀장님 실적 현황]\n💰 총 합산 시상금: {total_prize_sum:,.0f}원\n────────────────\n"
    if weekly_res:
        sh = f"<div class='summary-card'><div class='summary-label'>{user_name} 팀장님의 시책 현황</div><div class='summary-total'>{weekly_total:,.0f}원</div><div class='summary-divider'></div>"
        share_text += "📌 [진행 중인 시책]\n"
        for res in weekly_res:
            if res['type'] == "브릿지1":
                sh += f"<div class='data-row' style='padding:6px 0;align-items:flex-start;'><span class='summary-item-name'>{res['name']}<br><span style='font-size:0.95rem;color:rgba(255,255,255,0.7);'>(다음 달 {int(res['curr_req']//10000)}만 가동 조건)</span></span><span class='summary-item-val'>{res['prize']:,.0f}원</span></div>"
                share_text += f"🔹 {res['name']}: {res['prize']:,.0f}원 (다음 달 {int(res['curr_req']//10000)}만 가동 조건)\n"
            elif res['type'] == "브릿지2":
                sh += f"<div class='data-row' style='padding:6px 0;align-items:flex-start;'><span class='summary-item-name'>{res['name']}<br><span style='font-size:0.95rem;color:rgba(255,255,255,0.7);'>(이번 달 {int(res['curr_req']//10000)}만 가동 조건)</span></span><span class='summary-item-val'>{res['prize']:,.0f}원</span></div>"
                share_text += f"🔹 {res['name']}: {res['prize']:,.0f}원 (이번 달 {int(res['curr_req']//10000)}만 가동 조건)\n"
            else:
                sh += f"<div class='data-row' style='padding:6px 0;'><span class='summary-item-name'>{res['name']}</span><span class='summary-item-val'>{res['prize']:,.0f}원</span></div>"
                share_text += f"🔹 {res['name']}: {res['prize']:,.0f}원\n"
        sh += "</div>"
        st.markdown(sh, unsafe_allow_html=True)
        for res in weekly_res:
            desc_html = res['desc'].replace('\n','<br>') if res.get('desc') else ''
            details = res.get('prize_details', [])
            pdh = ""
            if len(details) > 1:
                for d in details: pdh += f"<div class='data-row'><span class='data-label'>{d['label']}</span><span class='data-value' style='color:rgb(128,0,0);'>{d['amount']:,.0f}원</span></div>"
                pdh += "<div class='toss-divider'></div>"
            if res['type'] == "구간":
                ch = f"<div class='toss-card'><div class='toss-title'>{res['name']}</div><div class='toss-desc'>{desc_html}</div><div class='data-row'><span class='data-label'>현재 누적 실적</span><span class='data-value'>{res['val']:,.0f}원</span></div><div class='toss-divider'></div>{pdh}<div class='prize-row'><span class='prize-label'>확보한 시상금</span><span class='prize-value'>{res['prize']:,.0f}원</span></div></div>"
                share_text += f"\n[{res['name']}]\n- 현재실적: {res['val']:,.0f}원\n- 확보금액: {res['prize']:,.0f}원\n"
                for d in details: share_text += f"  · {d['label']}: {d['amount']:,.0f}원\n"
            elif res['type'] == "브릿지1":
                ch = f"<div class='toss-card'><div class='toss-title'>{res['name']}</div><div class='toss-desc'>{desc_html}</div><div class='data-row'><span class='data-label'>전월 실적</span><span class='data-value'>{res['val_prev']:,.0f}원</span></div><div class='data-row'><span class='data-label'>당월 실적</span><span class='data-value'>{res['val_curr']:,.0f}원</span></div><div class='toss-divider'></div>{pdh}<div class='prize-row'><span class='prize-label'>다음 달 {int(res['curr_req']//10000)}만 가동 시<br>시상금</span><span class='prize-value'>{res['prize']:,.0f}원</span></div></div>"
                share_text += f"\n[{res['name']}]\n- 전월실적: {res['val_prev']:,.0f}원\n- 당월실적: {res['val_curr']:,.0f}원\n- 예상시상: {res['prize']:,.0f}원 (다음 달 {int(res['curr_req']//10000)}만 가동 조건)\n"
                for d in details: share_text += f"  · {d['label']}: {d['amount']:,.0f}원\n"
            elif res['type'] == "브릿지2":
                curr_req_val = int(res['curr_req']//10000)
                if res.get('curr_met'):
                    curr_status = f"<div class='data-row'><span class='data-label'>이번 달 {curr_req_val}만 가동</span><span class='data-value' style='color:#2e7d32;font-weight:800;'>✅ 달성</span></div>"
                    prize_label = "예상 시상금"
                else:
                    curr_short = res['curr_req'] - res['val_curr']
                    curr_status = f"<div class='data-row'><span class='data-label'>이번 달 {curr_req_val}만 가동</span><span class='data-value' style='color:#d9232e;font-weight:800;'>❌ 미달 ({curr_short:,.0f}원 부족)</span></div>"
                    prize_label = f"이번 달 {curr_req_val}만 달성 시<br>예상 시상금"
                ch = f"<div class='toss-card'><div class='toss-title'>{res['name']}</div><div class='toss-desc'>{desc_html}</div><div class='data-row'><span class='data-label'>전월 브릿지 실적</span><span class='data-value'>{res['val_prev']:,.0f}원</span></div><div class='data-row'><span class='data-label'>확보한 구간 기준</span><span class='data-value'>{res['tier']:,.0f}원</span></div><div class='data-row'><span class='data-label'>예상 적용 지급률</span><span class='data-value'>{res['rate']:g}%</span></div><div class='toss-divider'></div><div class='data-row'><span class='data-label'>당월 실적</span><span class='data-value'>{res['val_curr']:,.0f}원</span></div>{curr_status}<div class='toss-divider'></div><div class='prize-row'><span class='prize-label'>{prize_label}</span><span class='prize-value'>{res['prize']:,.0f}원</span></div></div>"
                met_txt = "달성 ✅" if res.get('curr_met') else "미달 ❌"
                share_text += f"\n[{res['name']}]\n- 전월실적: {res['val_prev']:,.0f}원 (구간: {res['tier']:,.0f}원)\n- 당월실적: {res['val_curr']:,.0f}원 ({curr_req_val}만 가동 {met_txt})\n- 예상시상: {res['prize']:,.0f}원\n"
            st.markdown(ch, unsafe_allow_html=True)
    if cumul_res:
        ch = f"<div class='cumulative-card'><div class='summary-label'>{user_name} 팀장님의 월간 누계 시상</div><div class='summary-total'>{cumul_total:,.0f}원</div><div class='summary-divider'></div>"
        share_text += f"\n🏆 [월간 확정 누계 시상]\n"
        for res in cumul_res:
            ch += f"<div class='data-row' style='padding:6px 0;'><span class='summary-item-name'>{res['name']}</span><span class='summary-item-val'>{res['prize']:,.0f}원</span></div>"
            share_text += f"🔹 {res['name']}: {res['prize']:,.0f}원 (누계 {res['val']:,.0f}원)\n"
        ch += "</div>"
        st.markdown(ch, unsafe_allow_html=True)
        st.markdown("<h3 class='blue-title'>📈 세부 항목별 시상금</h3>", unsafe_allow_html=True)
        sh = ""
        for res in cumul_res:
            details = res.get('prize_details', [])
            dl = ""
            if len(details) > 1:
                for d in details: dl += f"<span class='cumul-stack-val'>{d['label']}: {d['amount']:,.0f}원</span>"
            else: dl = f"<span class='cumul-stack-val'>누계실적: {res['val']:,.0f}원</span>"
            sh += f"<div class='cumul-stack-box'><div class='cumul-stack-info'><span class='cumul-stack-title'>{res['name']}</span>{dl}</div><div class='cumul-stack-prize'>{res['prize']:,.0f}원</div></div>"
        st.markdown(sh, unsafe_allow_html=True)
    if show_share_text:
        st.markdown("<h4 class='main-title' style='margin-top:10px;'>💬 카카오톡 바로 공유하기</h4>", unsafe_allow_html=True)
        copy_btn_component(share_text)


# ==========================================
# 📞 오늘 접촉 대상 - 카카오 전송 컴포넌트
# ==========================================
def render_kakao_send_btn(msg_key, agent_name, btn_key, height=80):
    """
    버튼 클릭 시 parent DOM의 textarea 현재값을 직접 읽어 전송.
    msg_key를 aria-label 검색용 식별자로 사용.
    """
    html = f"""
    <div id="kw_{btn_key}" style="margin-top:6px;">
      <button id="kb_{btn_key}" onclick="doSend_{btn_key}()"
        style="width:100%;padding:13px 8px;background:#FEE500;color:#3C1E1E;border:none;
               border-radius:12px;font-size:1.05rem;font-weight:800;cursor:pointer;
               box-shadow:0 3px 8px rgba(0,0,0,0.1);">
        💬 {agent_name} 팀장님께 카카오톡 보내기
      </button>
      <div id="kd_{btn_key}" style="display:none;text-align:center;padding:8px 0;
           font-weight:700;color:#2e7d32;font-size:0.95rem;"></div>
    </div>
    <script>
    function doSend_{btn_key}() {{
        // 클릭 시점에 parent DOM의 textarea 현재값을 읽음
        var text = '';
        try {{
            var labelKey = '{msg_key}';
            var parentDoc = window.parent.document;
            // Streamlit textarea: [data-testid="stTextArea"] 컨테이너 안에
            // label의 텍스트 내용이 key와 일치하는 textarea를 찾음
            var containers = parentDoc.querySelectorAll('[data-testid="stTextArea"]');
            for (var i = 0; i < containers.length; i++) {{
                var label = containers[i].querySelector('label');
                var ta    = containers[i].querySelector('textarea');
                if (ta && label && label.textContent.trim() === labelKey) {{
                    text = ta.value; break;
                }}
            }}
            // 못 찾으면 aria-label 또는 id로 fallback
            if (!text) {{
                var ta2 = parentDoc.querySelector('textarea[aria-label="' + labelKey + '"]') ||
                          parentDoc.querySelector('textarea[id*="' + labelKey + '"]');
                if (ta2) text = ta2.value;
            }}
        }} catch(e) {{}}
        var isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);

        function showDone(msg) {{
            document.getElementById('kb_{btn_key}').style.display = 'none';
            var d = document.getElementById('kd_{btn_key}');
            d.style.display = 'block';
            d.innerHTML = msg;
        }}

        function copyToClipboard(cb) {{
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text).then(cb).catch(function() {{
                    legacyCopy(); cb();
                }});
            }} else {{ legacyCopy(); cb(); }}
        }}

        function legacyCopy() {{
            var ta = document.createElement('textarea');
            ta.value = text; ta.style.position='fixed'; ta.style.opacity='0';
            document.body.appendChild(ta); ta.select();
            document.execCommand('copy'); document.body.removeChild(ta);
        }}

        if (isMobile) {{
            // 모바일: Web Share API → 카카오 대상자 선택 화면
            if (navigator.share) {{
                navigator.share({{ text: text }})
                    .then(function() {{ showDone('✅ 공유 완료!'); }})
                    .catch(function(e) {{
                        // 취소하거나 실패 시 copy+launch fallback
                        copyToClipboard(function() {{
                            showDone('✅ 복사 완료! 카카오톡에서 붙여넣기 하세요.');
                            setTimeout(function() {{ window.location.href='kakaotalk://launch'; }}, 400);
                        }});
                    }});
            }} else {{
                // Web Share 미지원 → copy + kakaotalk://launch
                copyToClipboard(function() {{
                    showDone('✅ 복사! 카카오톡 실행 중...');
                    setTimeout(function() {{ window.location.href='kakaotalk://launch'; }}, 400);
                }});
            }}
        }} else {{
            // 데스크탑: 복사 후 2.5초 뒤 버튼 원복
            copyToClipboard(function() {{
                showDone('✅ 복사 완료! 카카오톡 채팅창에 Ctrl+V 하세요.');
                setTimeout(function() {{
                    document.getElementById('kd_{btn_key}').style.display = 'none';
                    document.getElementById('kb_{btn_key}').style.display = 'block';
                }}, 2500);
            }});
        }}
    }}
    </script>
    """
    components.html(html, height=height)


# ==========================================
# 📞 오늘 접촉 대상 페이지
# ==========================================
def page_contact():
    st.markdown('<div class="title-band">📞 오늘 접촉 대상</div>', unsafe_allow_html=True)

    BRIDGE_COLS = [
        '브릿지대상_2_3월', '브릿지실적구간_2월', '연속가동대상_2_3월',
        '브릿지실적_2월', '연속가동실적_2월', '연속가동실적구간_2월',
        '브릿지실적_3월', '브릿지부족금액_3월'
    ]

    # ── 브릿지 파일 탐색 ─────────────────────────────────────
    bridge_df     = None
    mgr_code_col  = None
    agent_name_col= None
    agency_col    = None
    mgr_name_col  = None

    for cfg in st.session_state.get('config', []):
        if not mgr_code_col:   mgr_code_col   = cfg.get('col_manager_code','') or cfg.get('col_manager','')
        if not agent_name_col: agent_name_col = cfg.get('col_name','')
        if not agency_col:     agency_col     = cfg.get('col_agency','') or cfg.get('col_branch','')

    best_score = 0
    for fname, df in st.session_state['raw_data'].items():
        score = sum(1 for c in BRIDGE_COLS if c in df.columns)
        if score > best_score:
            best_score = score
            bridge_df  = df
            for col in df.columns:
                if not mgr_code_col   and any(k in col for k in ('매니저코드','지원매니저코드','매니저_코드')): mgr_code_col   = col
                if not mgr_name_col   and any(k in col for k in ('매니저명','지원매니저명','담당매니저명')):     mgr_name_col   = col
                if not agent_name_col and any(k in col for k in ('성명','이름','설계사명')):                    agent_name_col = col
                if not agency_col     and any(k in col for k in ('대리점명','소속','지사명')):                  agency_col     = col

    if bridge_df is None or best_score == 0:
        st.warning("⚠️ 브릿지 데이터 파일을 찾을 수 없습니다. 관리자 화면에서 업로드해주세요.")
        st.info(f"필요 컬럼: {', '.join(BRIDGE_COLS)}")
        return

    missing_cols = [c for c in BRIDGE_COLS if c not in bridge_df.columns]
    if missing_cols:
        st.warning(f"⚠️ 일부 컬럼 없음: {', '.join(missing_cols)}")

    # ── 로그인 ────────────────────────────────────────────────
    if 'contact_logged_in' not in st.session_state:
        st.session_state.contact_logged_in = False

    if not st.session_state.contact_logged_in:
        st.markdown("<h3 class='main-title'>지원매니저 코드를 입력하세요</h3>", unsafe_allow_html=True)
        mgr_input = st.text_input("매니저 코드", type="password", placeholder="예: 12345", label_visibility="collapsed")
        if st.button("접촉 대상 조회하기", type="primary"):
            if not mgr_input:
                st.warning("코드를 입력해주세요.")
            else:
                sic   = safe_str(mgr_input)
                found = False
                if mgr_code_col and mgr_code_col in bridge_df.columns:
                    if sic in get_clean_series(bridge_df, mgr_code_col).unique(): found = True
                if not found:
                    for ci, cfg in enumerate(st.session_state.get('config', [])):
                        mc = cfg.get('col_manager_code','') or cfg.get('col_manager','')
                        if mc:
                            df = _get_merged_df(ci)
                            if df is not None and mc in df.columns:
                                if sic in get_clean_series(df, mc).unique():
                                    found = True; mgr_code_col = mc; break
                if found:
                    st.session_state.contact_logged_in  = True
                    st.session_state.contact_mgr_code   = sic
                    # 메시지 캐시 초기화
                    for k in list(st.session_state.keys()):
                        if k.startswith('cmsg_'): del st.session_state[k]
                    st.rerun()
                else:
                    st.error(f"❌ 코드 '{mgr_input}'가 데이터에 없습니다.")
        return

    # ── 로그인 성공 ──────────────────────────────────────────
    mgr_code = st.session_state.contact_mgr_code
    col_lo, _ = st.columns([2, 8])
    with col_lo:
        if st.button("🚪 로그아웃"):
            st.session_state.contact_logged_in = False
            st.rerun()

    # 매니저 이름
    mgr_name = ""
    if mgr_name_col and mgr_name_col in bridge_df.columns and mgr_code_col and mgr_code_col in bridge_df.columns:
        mdf = bridge_df[get_clean_series(bridge_df, mgr_code_col) == mgr_code]
        if not mdf.empty: mgr_name = _clean_excel_text(safe_str(mdf[mgr_name_col].values[0]))
    if not mgr_name:
        for ci, cfg in enumerate(st.session_state.get('config', [])):
            mc = cfg.get('col_manager_code','') or cfg.get('col_manager','')
            mn = cfg.get('col_manager_name','')
            if mc and mn:
                df = _get_merged_df(ci)
                if df is not None and mc in df.columns and mn in df.columns:
                    mdf = df[get_clean_series(df, mc) == mgr_code]
                    if not mdf.empty: mgr_name = _clean_excel_text(safe_str(mdf[mn].values[0])); break

    display_mgr = mgr_name if mgr_name else mgr_code

    # ── 데이터 필터 & 계산 ──────────────────────────────────
    if not (mgr_code_col and mgr_code_col in bridge_df.columns):
        st.error("⚠️ 매니저 코드 컬럼을 찾을 수 없습니다.")
        return

    raw_df = bridge_df[get_clean_series(bridge_df, mgr_code_col) == mgr_code].copy().reset_index(drop=True)
    if raw_df.empty:
        st.info("해당 매니저의 접촉 대상이 없습니다.")
        return

    # ① 필터: 브릿지실적_2월 >= 100,000
    if '브릿지실적_2월' in raw_df.columns:
        raw_df = raw_df[raw_df['브릿지실적_2월'].apply(safe_float) >= 100000].reset_index(drop=True)

    if raw_df.empty:
        st.info("브릿지실적_2월 10만원 이상인 접촉 대상이 없습니다.")
        return

    # 전체 계산 → rows 리스트
    rows = []
    for i, row in raw_df.iterrows():
        def gv(col, r=row):
            return safe_float(r.get(col, 0))

        aname  = _clean_excel_text(safe_str(row[agent_name_col])) if agent_name_col and agent_name_col in row.index else f"설계사{i+1}"
        agency = _clean_excel_text(safe_str(row[agency_col]))     if agency_col     and agency_col     in row.index else ""

        br2  = gv('브릿지실적_2월')
        btir = gv('브릿지실적구간_2월')
        cr2  = gv('연속가동실적_2월')
        ctir = gv('연속가동실적구간_2월')
        br3  = gv('브릿지실적_3월')
        bsf  = gv('브릿지부족금액_3월')

        # 브릿지 시상금
        if btir >= 500000:   b_rate = 3.0
        elif btir >= 200000: b_rate = 2.0
        else:                b_rate = 1.0
        bp = (btir + 100000) * b_rate

        # 연속가동 시상금
        if ctir >= 500000:   c_rate = 3.0
        elif ctir >= 200000: c_rate = 2.0
        else:                c_rate = 1.0
        cp = (ctir + 100000) * c_rate

        tp = bp + cp

        achieved = (br3 >= 100000)
        if achieved:
            msg_default = f"달성!"
        else:
            msg_default = (
                f"★{aname} 팀장님!★  안녕하세요. {display_mgr} 매니저입니다.\n"
                f"팀장님께 좋은 소식 전해드리려고 연락드렸어요! 🎉\n"
                f"8일 마감이었던 브릿지+연속가동 2배 시상이\n"
                f"★15일까지 연장★되었습니다!\n\n"
                f"지난 2월 브릿지 실적 ★{br2:,.0f}원★ 으로 \n"
                f"★{bp:,.0f}원★ 브릿지 시상에\n"
                f"연속가동 실적 ★{cr2:,.0f}원★ 으로 \n"
                f"★{cp:,.0f}원★ 연속가동 시상까지\n"
                f"합산 ★{tp:,.0f}원★ 을 아직 받으실 수 있습니다.\n\n"
                f"그런데 현재 ★{br3:,.0f}원★ 이셔서 \n"
                f"★{bsf:,.0f}원★이 부족하세요. T_T\n"
                f"15일까지 10만원만 하시면 됩니다!\n\n"
                f"오늘 10만원 하실 수 있는 플랜은 \n"
                f"1. 가장 체결률 좋은 진단및치료비 + 비통치, 항암 26종 플랜\n"
                f"2. 지난 달보다 진단비 가격이 10%나 하락한 5.10.5\n"
                f"3. 새로나온 표적항암 2억에 1만원도 안되는 1.2.3 또또암 플랜 등이 있습니다.\n\n"
                f"지금 바로 연락주시면 설계 도와드릴께요!\n\n"
                f"오늘도 좋은 하루 되시고 시상금 꼭 챙겨가세요!"
            )
        rows.append(dict(
            idx=i, aname=aname, agency=agency,
            br2=br2, btir=btir, cr2=cr2, ctir=ctir,
            br3=br3, bsf=bsf, bp=bp, cp=cp, tp=tp,
            achieved=achieved, msg_default=msg_default
        ))


    # 합계 시상금 큰 순 (데스크탑/모바일 공통)
    rows.sort(key=lambda r: r['tp'], reverse=True)

    is_mobile = st.session_state.get('contact_view', 'desktop') == 'mobile'

    mgr_label = f"{mgr_name} 매니저" if mgr_name else f"코드 {mgr_code}"
    hdr_c, tog_c = st.columns([9, 1])
    with hdr_c:
        st.markdown(
            f"<h3 class='main-title' style='margin-bottom:4px;'>📋 {mgr_label}님 접촉 대상 — {len(rows)}명</h3>",
            unsafe_allow_html=True
        )
    with tog_c:
        cur_icon = "📱" if is_mobile else "🖥️"
        if st.button(cur_icon, key="cv_tog"):
            nxt = 'desktop' if is_mobile else 'mobile'
            st.session_state['contact_view'] = nxt
            st.rerun()

    if is_mobile:
        st.caption("📱 합계 시상금 큰 순 · 버튼 클릭 시 카카오톡 공유 화면으로 이동")
    else:
        st.caption("🖥️ 합계 시상금 큰 순 · 메시지 직접 수정 후 복사")

    # ── 메시지 세션 초기화 (처음 로드 시 default 삽입) ─────
    for r in rows:
        skey = f"cmsg_{r['idx']}"
        if skey not in st.session_state:
            st.session_state[skey] = r['msg_default']

    # ══════════════════════════════════════════════════════
    # 🖥️ 데스크탑 뷰: 1줄 = 정보 | 메시지 편집 | 버튼
    # ══════════════════════════════════════════════════════
    if not is_mobile:
        for r in rows:
            skey = f"cmsg_{r['idx']}"
            if r['achieved']:
                sf_badge = "<span style='color:#2e7d32;font-size:0.85rem;font-weight:800;'>🏆 달성!</span>"
                card_bg  = "#f0faf4"
                border   = "2px solid #81c995"
            else:
                sf_badge = (f"<span style='color:#d9232e;font-size:0.85rem;font-weight:700;'>"
                            f"⚠️ {r['bsf']:,.0f}원 부족</span>") if r['bsf'] > 0 else \
                           "<span style='color:#2e7d32;font-size:0.85rem;font-weight:700;'>✅ 달성</span>"
                card_bg  = "#fff"
                border   = "1px solid #e5e8eb"

            info_html = f"""
            <div style='background:{card_bg};border:{border};border-radius:12px;
                        padding:12px 14px;height:100%;'>
                <div style='font-size:1.1rem;font-weight:800;color:#191f28;margin-bottom:4px;'>
                    👤 {r['aname']}
                </div>
                <div style='font-size:0.9rem;color:#8b95a1;margin-bottom:8px;'>
                    📍 {r['agency'] if r['agency'] else '—'}
                </div>
                <div style='background:#fff8f8;border-radius:8px;padding:6px 10px;margin-bottom:4px;'>
                    <span style='font-size:0.8rem;color:#8b95a1;'>브릿지 시상금</span>
                    <span style='font-size:1.05rem;font-weight:800;color:rgb(128,0,0);
                                float:right;'>{r['bp']:,.0f}원</span>
                </div>
                <div style='background:#f8f8ff;border-radius:8px;padding:6px 10px;margin-bottom:6px;'>
                    <span style='font-size:0.8rem;color:#8b95a1;'>연속가동 시상금</span>
                    <span style='font-size:1.05rem;font-weight:800;color:#1e3c72;
                                float:right;'>{r['cp']:,.0f}원</span>
                </div>
                <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <span style='font-size:1.15rem;font-weight:800;color:rgb(128,0,0);'>
                        💰 {r['tp']:,.0f}원
                    </span>
                    {sf_badge}
                </div>
            </div>"""

            col_info, col_msg, col_btn = st.columns([2, 4, 2], gap="medium")
            with col_info:
                st.markdown(info_html, unsafe_allow_html=True)
            with col_msg:
                st.text_area(
                    skey,
                    value=st.session_state[skey],
                    key=skey,
                    height=210,
                    label_visibility="hidden",
                    disabled=r['achieved']
                )
            with col_btn:
                if r['achieved']:
                    st.markdown(
                        "<div style='display:flex;align-items:center;justify-content:center;"
                        "height:210px;font-size:1.5rem;font-weight:800;color:#2e7d32;"
                        "text-align:center;'>🏆<br>달성!</div>",
                        unsafe_allow_html=True
                    )
                else:
                    render_kakao_send_btn(skey, r['aname'], f"d{r['idx']}", height=225)

            st.markdown("<hr style='margin:6px 0 10px;opacity:0.1;'>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════
    # 📱 모바일 뷰: 카드 → 메시지 편집 → 전송 버튼
    # ══════════════════════════════════════════════════════
    else:
        for r in rows:
            skey = f"cmsg_{r['idx']}"
            if r['achieved']:
                sf_badge  = "<span style='color:#2e7d32;font-weight:800;font-size:1.05rem;'>🏆 달성!</span>"
                card_border = "border:2px solid #81c995;background:#f0faf4;"
            else:
                sf_badge  = (f"<span class='contact-shortfall'>⚠️ {r['bsf']:,.0f}원 부족</span>") \
                             if r['bsf'] > 0 else \
                             "<span style='color:#2e7d32;font-weight:700;'>✅ 달성 완료</span>"
                card_border = ""

            card_html = f"""
            <div class='contact-card' style='{card_border}'>
                <div style='display:flex;justify-content:space-between;
                            align-items:flex-start;margin-bottom:8px;'>
                    <div>
                        <div class='contact-name'>👤 {r['aname']} 팀장님</div>
                        <div class='contact-org'>📍 {r['agency'] if r['agency'] else '—'}</div>
                    </div>
                    <div class='contact-prize-total'>💰 {r['tp']:,.0f}원</div>
                </div>
                <div style='display:flex;gap:10px;flex-wrap:wrap;margin-bottom:6px;'>
                    <div style='flex:1;min-width:120px;background:#fff8f8;
                                border-radius:10px;padding:8px 10px;'>
                        <div style='font-size:0.85rem;color:#8b95a1;'>브릿지 시상금</div>
                        <div style='font-size:1.15rem;font-weight:800;
                                    color:rgb(128,0,0);'>{r['bp']:,.0f}원</div>
                        <div style='font-size:0.8rem;color:#aaa;'>2월 실적 {r['br2']:,.0f}원</div>
                    </div>
                    <div style='flex:1;min-width:120px;background:#f8f8ff;
                                border-radius:10px;padding:8px 10px;'>
                        <div style='font-size:0.85rem;color:#8b95a1;'>연속가동 시상금</div>
                        <div style='font-size:1.15rem;font-weight:800;
                                    color:#1e3c72;'>{r['cp']:,.0f}원</div>
                        <div style='font-size:0.8rem;color:#aaa;'>2월 실적 {r['cr2']:,.0f}원</div>
                    </div>
                </div>
                <div style='display:flex;justify-content:space-between;
                            align-items:center;padding:6px 0 2px;'>
                    <span style='color:#8b95a1;font-size:0.9rem;'>
                        3월 현재: {r['br3']:,.0f}원
                    </span>
                    {sf_badge}
                </div>
            </div>"""
            st.markdown(card_html, unsafe_allow_html=True)

            if r['achieved']:
                # 달성자: 메시지 창(읽기 전용) + 카톡 버튼 없음
                st.text_area(
                    f"({r['aname']})",
                    value=st.session_state[skey],
                    key=skey,
                    height=68,
                    disabled=True,
                    label_visibility="collapsed"
                )
            else:
                # 미달성: 편집 가능 + 카톡 버튼
                st.text_area(
                    skey,           # label = skey → JS 검색용
                    value=st.session_state[skey],
                    key=skey,
                    height=260,
                    label_visibility="hidden"
                )
                render_kakao_send_btn(skey, r['aname'], f"m{r['idx']}", height=80)
            st.markdown("<hr style='margin:12px 0;opacity:0.12;'>", unsafe_allow_html=True)


# ==========================================
# 📱 메뉴 (4개)
# ==========================================
mode = st.radio(
    "화면 선택",
    ["📊 내 실적 조회", "👥 매니저 관리", "📞 오늘 접촉 대상", "⚙️ 시스템 관리자"],
    horizontal=True,
    label_visibility="collapsed"
)

# ==========================================
# 📞 오늘 접촉 대상
# ==========================================
if mode == "📞 오늘 접촉 대상":
    page_contact()

# ==========================================
# 👥 매니저 관리
# ==========================================
elif mode == "👥 매니저 관리":
    st.markdown('<div class="title-band">매니저 소속 실적 관리</div>', unsafe_allow_html=True)
    if 'mgr_logged_in' not in st.session_state: st.session_state.mgr_logged_in = False
    if not st.session_state.mgr_logged_in:
        mgr_code = st.text_input("지원매니저 사번(코드)을 입력하세요", type="password", placeholder="예: 12345")
        if st.button("로그인", type="primary"):
            if not mgr_code: st.warning("지원매니저 코드를 입력해주세요.")
            else:
                sic = safe_str(mgr_code); avc = set()
                for ci, cfg in enumerate(st.session_state['config']):
                    mc = cfg.get('col_manager_code','') or cfg.get('col_manager','')
                    if mc:
                        df = _get_merged_df(ci)
                        if df is not None and mc in df.columns:
                            for cv in get_clean_series(df, mc).unique():
                                if cv: avc.add(cv)
                if sic in avc:
                    st.session_state.mgr_logged_in=True; st.session_state.mgr_code=sic; st.session_state.mgr_step='main'
                    save_log("매니저", sic, "MANAGER_LOGIN"); st.rerun()
                else:
                    st.error(f"❌ 입력하신 코드({mgr_code})가 존재하지 않습니다.")
                    if avc: st.warning(f"🧐 인식 코드 예시: {', '.join(list(avc)[:10])}")
    else:
        if st.button("🚪 로그아웃"): st.session_state.mgr_logged_in=False; st.rerun()
        st.markdown('<br>', unsafe_allow_html=True)
        step = st.session_state.get('mgr_step','main')
        if step == 'main':
            st.markdown("<h3 class='main-title'>어떤 실적을 확인하시겠습니까?</h3>", unsafe_allow_html=True)
            c1,c2=st.columns(2)
            with c1:
                if st.button("📁 구간실적 관리", use_container_width=True): st.session_state.mgr_step='tiers'; st.session_state.mgr_category='구간'; st.rerun()
            with c2:
                if st.button("📁 브릿지실적 관리", use_container_width=True): st.session_state.mgr_step='tiers'; st.session_state.mgr_category='브릿지'; st.rerun()
        elif step == 'tiers':
            if st.button("⬅️ 뒤로가기"): st.session_state.mgr_step='main'; st.rerun()
            cat=st.session_state.mgr_category; my_agents=set(); slc=st.session_state.mgr_code
            for ci,cfg in enumerate(st.session_state['config']):
                if cfg.get('category')=='cumulative': continue
                mc=cfg.get('col_manager_code','') or cfg.get('col_manager',''); cc=cfg.get('col_code','')
                if not mc or not cc: continue
                df=_get_merged_df(ci)
                if df is None or mc not in df.columns or cc not in df.columns: continue
                mask=get_clean_series(df,mc)==slc
                for ac in get_clean_series(df,cc)[mask]:
                    if ac: my_agents.add(ac)
            st.markdown(f"<h3 class='main-title'>📁 {cat}실적 근접자 조회 (소속: 총 {len(my_agents)}명)</h3>", unsafe_allow_html=True)
            ranges={500000:(300000,float('inf')),300000:(200000,300000),200000:(100000,200000),100000:(0,100000)}
            counts={k:0 for k in ranges}
            for ac in my_agents:
                cr2,_=calculate_agent_performance(ac); mf=set()
                for res in cr2:
                    if cat=="구간" and "구간" not in res['type']: continue
                    if cat=="브릿지" and "브릿지" not in res['type']: continue
                    val=res.get('val', res.get('val_prev', res.get('val_curr', 0.0)))
                    if val is None: val=0.0
                    for t,(mn,mx) in ranges.items():
                        if mn<=val<mx: mf.add(t); break
                for t in mf: counts[t]+=1
            for t,(mn,mx) in ranges.items():
                ct=counts[t]
                if t==500000: lbl=f"📁 50만 구간 근접 및 달성 (30만 이상) - 총 {ct}명"
                else: lbl=f"📁 {int(t//10000)}만 구간 근접자 ({int(mn//10000)}만~{int(mx//10000)}만) - 총 {ct}명"
                if st.button(lbl, use_container_width=True, key=f"t_{t}"):
                    st.session_state.mgr_step='list'; st.session_state.mgr_target=t
                    st.session_state.mgr_min_v=mn; st.session_state.mgr_max_v=mx
                    st.session_state.mgr_agents=my_agents; st.rerun()
        elif step == 'list':
            if st.button("⬅️ 폴더로 돌아가기"): st.session_state.mgr_step='tiers'; st.rerun()
            cat=st.session_state.mgr_category; target=st.session_state.mgr_target
            min_v=st.session_state.mgr_min_v; max_v=st.session_state.mgr_max_v; my_agents=st.session_state.mgr_agents
            if target==500000: st.markdown("<h3 class='main-title'>👥 50만 구간 근접 및 달성자 명단</h3>", unsafe_allow_html=True)
            else: st.markdown(f"<h3 class='main-title'>👥 {int(target//10000)}만 구간 근접자 명단</h3>", unsafe_allow_html=True)
            st.info("💡 이름을 클릭하면 상세 실적을 확인하고 카톡으로 전송할 수 있습니다.")
            near=[]
            for code in my_agents:
                cr2,_=calculate_agent_performance(code)
                an="이름없음"; aa=""
                for ci,cfg in enumerate(st.session_state['config']):
                    if cfg.get('col_code') and cfg.get('col_name'):
                        df=_get_merged_df(ci)
                        if df is not None and cfg['col_code'] in df.columns:
                            mask=get_clean_series(df,cfg['col_code'])==code; mdf=df[mask]
                            if not mdf.empty:
                                if cfg['col_name'] in mdf.columns: an=safe_str(mdf[cfg['col_name']].values[0])
                                ag=cfg.get('col_agency',''); br=cfg.get('col_branch','')
                                if ag and ag in df.columns: aa=_clean_excel_text(safe_str(mdf[ag].values[0]))
                                elif br and br in df.columns: aa=_clean_excel_text(safe_str(mdf[br].values[0]))
                                break
                for res in cr2:
                    if cat=="구간" and "구간" not in res['type']: continue
                    if cat=="브릿지" and "브릿지" not in res['type']: continue
                    val=res.get('val', res.get('val_prev', res.get('val_curr', 0.0)))
                    if val is None: val=0.0
                    if min_v<=val<max_v: near.append((code,an,aa,val)); break
            if not near: st.info("해당 구간에 소속 설계사가 없습니다.")
            else:
                near.sort(key=lambda x:(x[2],x[1]))
                for code,name,agency,val in near:
                    if st.button(f"👤 [{agency}] {name} 설계사님 (현재 {val:,.0f}원)", use_container_width=True, key=f"btn_{code}"):
                        st.session_state.mgr_selected_code=code; st.session_state.mgr_selected_name=f"[{agency}] {name}"
                        st.session_state.mgr_step='detail'; st.rerun()
        elif step == 'detail':
            if st.button("⬅️ 명단으로 돌아가기"): st.session_state.mgr_step='list'; st.rerun()
            code=st.session_state.mgr_selected_code; name=st.session_state.mgr_selected_name
            st.markdown("<div class='detail-box'>", unsafe_allow_html=True)
            st.markdown(f"<h4 class='agent-title'>👤 {name} 설계사님</h4>", unsafe_allow_html=True)
            cr2,tp=calculate_agent_performance(code)
            render_ui_cards(name,cr2,tp,show_share_text=True)
            ulp=os.path.join(DATA_DIR,"leaflet.png")
            if os.path.exists(ulp): st.image(ulp, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 🔒 시스템 관리자
# ==========================================
elif mode == "⚙️ 시스템 관리자":
    st.markdown("<h2 class='admin-title'>관리자 설정</h2>", unsafe_allow_html=True)
    admin_pw = st.text_input("관리자 비밀번호를 입력하세요", type="password")
    try: real_pw = st.secrets["admin_password"]
    except: real_pw = "wolf7998"
    if admin_pw != real_pw:
        if admin_pw: st.error("비밀번호가 일치하지 않습니다.")
        st.stop()
    st.success("인증 성공! 변경 사항은 가장 아래 [서버에 반영하기] 버튼을 눌러야 저장됩니다.")
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE,"rb") as f:
            st.download_button("📊 접속 로그 다운로드",data=f,file_name=f"access_log_{datetime.now().strftime('%Y%m%d')}.csv",mime="text/csv")
    st.markdown("<hr style='margin:15px 0;'>", unsafe_allow_html=True)

    # --- [1] 파일 업로드 ---
    st.markdown("<h3 class='sub-title'>📂 1. 실적 파일 업로드 및 관리</h3>", unsafe_allow_html=True)
    st.info("💡 시상 항목이 여러 파일에 나뉘어 있으면 모두 업로드하세요. 브릿지 파일도 여기서 업로드하세요.")
    uploaded_files = st.file_uploader("CSV/엑셀 파일 업로드", accept_multiple_files=True, type=['csv','xlsx'])
    if uploaded_files:
        nu = False
        for file in uploaded_files:
            if file.name not in st.session_state['raw_data']:
                if file.name.endswith('.csv'):
                    try: df=pd.read_csv(file)
                    except:
                        file.seek(0)
                        try: df=pd.read_csv(file,sep='\t')
                        except:
                            file.seek(0)
                            try: df=pd.read_csv(file,encoding='cp949')
                            except: file.seek(0); df=pd.read_csv(file,sep='\t',encoding='cp949')
                else: df=pd.read_excel(file)
                df.columns=[_clean_excel_text(str(c)) for c in df.columns]
                for col in df.select_dtypes(include='object').columns:
                    df[col]=df[col].apply(lambda v: _clean_excel_text(str(v)) if pd.notna(v) else v)
                st.session_state['raw_data'][file.name]=df
                df.to_pickle(os.path.join(DATA_DIR, f"{file.name}.pkl")); nu=True
        if nu: st.success("✅ 파일 업로드 완료."); st.rerun()
    c1,c2=st.columns([7,3])
    with c1: st.markdown(f"**현재 저장된 파일 ({len(st.session_state['raw_data'])}개)**")
    with c2:
        if st.button("🗑️ 전체 파일 삭제", use_container_width=True):
            st.session_state['raw_data'].clear(); st.session_state['merged_data']={}
            for f in os.listdir(DATA_DIR):
                if f.endswith('.pkl'): os.remove(os.path.join(DATA_DIR,f))
            st.rerun()
    if not st.session_state['raw_data']: st.info("업로드된 파일이 없습니다.")
    else:
        for fn in list(st.session_state['raw_data'].keys()):
            dfp=st.session_state['raw_data'][fn]; cc=len([c for c in dfp.columns if not c.startswith('_clean_')]); rc=len(dfp)
            cn,cb=st.columns([8,2])
            with cn: st.write(f"📄 {fn} ({rc}행 × {cc}열)")
            with cb:
                if st.button("삭제",key=f"del_file_{fn}",use_container_width=True):
                    del st.session_state['raw_data'][fn]
                    pp=os.path.join(DATA_DIR,f"{fn}.pkl")
                    if os.path.exists(pp): os.remove(pp)
                    st.rerun()
            st.markdown("<hr style='margin:5px 0;opacity:0.1;'>", unsafe_allow_html=True)

    file_opts = list(st.session_state['raw_data'].keys())

    # --- [2] 주차/브릿지 시상 ---
    st.divider()
    st.markdown("<h3 class='sub-title' style='margin-top:10px;'>🏆 2. 주차/브릿지 시상 항목 관리</h3>", unsafe_allow_html=True)
    ca,cd=st.columns(2)
    with ca:
        if st.button("➕ 신규 시상 추가", type="primary", use_container_width=True):
            if not file_opts: st.error("⚠️ 먼저 파일 업로드 필요")
            else:
                st.session_state['config'].append({
                    "name":f"신규 주차 시책 {len(st.session_state['config'])+1}",
                    "desc":"","category":"weekly","type":"구간 시책",
                    "file":file_opts[0],"col_name":"","col_code":"","col_branch":"","col_agency":"","col_manager_code":"",
                    "col_val":"","col_val_prev":"","col_val_curr":"",
                    "prize_items":[{"label":"시상금","file":"","col_code_ext":"","col_eligible":"","col_prize":""}],
                    "curr_req":100000.0,"tiers":[(500000,300),(300000,200),(200000,200),(100000,100)]
                }); st.rerun()
    with cd:
        if st.button("🗑️ 모든 시상 삭제", use_container_width=True):
            st.session_state['config']=[c for c in st.session_state['config'] if c.get('category')!='weekly']
            with open(os.path.join(DATA_DIR,'config.json'),'w',encoding='utf-8') as f: json.dump(st.session_state['config'],f,ensure_ascii=False,cls=NumpyEncoder)
            st.rerun()

    weekly_cfgs=[(i,c) for i,c in enumerate(st.session_state['config']) if c.get('category','weekly')=='weekly']
    if not weekly_cfgs: st.info("현재 설정된 주차/브릿지 시상이 없습니다.")

    def _get_idx(val, opts):
        return opts.index(val) if val in opts else 0

    for i, cfg in weekly_cfgs:
        if 'desc' not in cfg: cfg['desc']=""
        st.markdown("<div class='config-box'>", unsafe_allow_html=True)
        ct,cdl=st.columns([8,2])
        with ct: st.markdown(f"<h3 class='config-title'>📌 {cfg['name']} 설정</h3>", unsafe_allow_html=True)
        with cdl:
            if st.button("삭제",key=f"del_cfg_{i}",use_container_width=True): st.session_state['config'].pop(i); st.rerun()
        cfg['name']=st.text_input("시책명",value=cfg['name'],key=f"name_{i}")
        cfg['desc']=st.text_area("시책 설명",value=cfg.get('desc',''),key=f"desc_{i}",height=100)
        tidx=0
        if "1기간" in cfg['type']: tidx=1
        elif "2기간" in cfg['type']: tidx=2
        cfg['type']=st.radio("시책 종류",["구간 시책","브릿지 시책 (1기간: 시상 확정)","브릿지 시책 (2기간: 당월 달성 조건)"],index=tidx,horizontal=True,key=f"type_{i}")
        cfg['file']=st.selectbox("📂 기본 파일 (인적사항+실적)",file_opts,index=_get_idx(cfg.get('file',''),file_opts) if file_opts else 0,key=f"file_{i}")
        cols=_get_cols_for_file(cfg['file'])
        c1,c2=st.columns(2)
        with c1:
            st.info("💡 식별 컬럼 (기본 파일)")
            cfg['col_name']=st.selectbox("성명",cols,index=_get_idx(cfg.get('col_name',''),cols),key=f"cname_{i}")
            cfg['col_branch']=st.selectbox("지점명(조직)",cols,index=_get_idx(cfg.get('col_branch',''),cols),key=f"cbranch_{i}")
            cfg['col_agency']=st.selectbox("대리점/지사명",cols,index=_get_idx(cfg.get('col_agency',''),cols),key=f"cagency_{i}")
            cfg['col_code']=st.selectbox("설계사코드(사번)",cols,index=_get_idx(cfg.get('col_code',''),cols),key=f"ccode_{i}")
            cfg['col_manager_code']=st.selectbox("지원매니저코드",cols,index=_get_idx(cfg.get('col_manager_code',cfg.get('col_manager','')),cols),key=f"cmgrcode_{i}")
        with c2:
            st.info("💡 실적 컬럼 (기본 파일)")
            if "1기간" in cfg['type']:
                cfg['col_val_prev']=st.selectbox("전월 실적",cols,index=_get_idx(cfg.get('col_val_prev',''),cols),key=f"cvalp_{i}")
                cfg['col_val_curr']=st.selectbox("당월 실적",cols,index=_get_idx(cfg.get('col_val_curr',''),cols),key=f"cvalc_{i}")
                cfg['curr_req']=st.number_input("다음 달 필수 가동 금액",value=float(cfg.get('curr_req',100000.0)),step=10000.0,key=f"creq1_{i}")
                st.caption("💡 브릿지 1기간: 이번 달 구간 확보 → 다음 달 가동 시 시상 확정")
            elif "2기간" in cfg['type']:
                cfg['col_val_prev']=st.selectbox("전월 브릿지 실적",cols,index=_get_idx(cfg.get('col_val_prev',''),cols),key=f"cvalp2_{i}")
                cfg['col_val_curr']=st.selectbox("당월 실적",cols,index=_get_idx(cfg.get('col_val_curr',''),cols),key=f"cvalc2_{i}")
            else:
                cfg['col_val']=st.selectbox("실적 수치",cols,index=_get_idx(cfg.get('col_val',''),cols),key=f"cval_{i}")
            if "2기간" in cfg['type']:
                cfg['curr_req']=st.number_input("이번 달 필수 가동 금액",value=float(cfg.get('curr_req',100000.0)),step=10000.0,key=f"creq2_{i}")
                st.caption("💡 브릿지 2기간: 지난 달 구간 확정 → 이번 달 가동 시 시상 확정")
                st.write("📈 구간 설정 (달성금액,지급률%)")
                ts="\n".join([f"{int(t[0])},{int(t[1])}" for t in cfg.get('tiers',[])])
                ti=st.text_area("엔터로 줄바꿈",value=ts,height=150,key=f"tier_{i}")
                try:
                    nt=[]
                    for line in ti.strip().split('\n'):
                        if ',' in line: p=line.split(','); nt.append((float(p[0].strip()),float(p[1].strip())))
                    cfg['tiers']=sorted(nt,key=lambda x:x[0],reverse=True)
                except: st.error("형식 오류")
            else:
                st.markdown("**💰 시상금 항목** <small style='color:#8b95a1;'>— 항목별로 다른 파일 선택 가능</small>", unsafe_allow_html=True)
                if 'prize_items' not in cfg:
                    old_col=cfg.pop('col_prize','') or cfg.pop('col','')
                    cfg['prize_items']=[{"label":"시상금","file":"","col_code_ext":"","col_eligible":"","col_prize":old_col}] if old_col else [{"label":"시상금","file":"","col_code_ext":"","col_eligible":"","col_prize":""}]
                for _pi in cfg.get('prize_items',[]):
                    if 'col' in _pi and 'col_prize' not in _pi: _pi['col_prize']=_pi.pop('col','')
                    if 'col_eligible' not in _pi: _pi['col_eligible']=''
                    if 'file' not in _pi: _pi['file']=''
                    if 'col_code_ext' not in _pi: _pi['col_code_ext']=''
                fowds=["(기본 파일과 동일)"]+file_opts
                updated=[]
                for pi_idx,pi in enumerate(cfg.get('prize_items',[])):
                    st.markdown("<div style='background:#f8f9fa;padding:8px 10px;border-radius:8px;margin:6px 0;border:1px solid #e5e8eb;'>", unsafe_allow_html=True)
                    pc1,pc4=st.columns([8,2])
                    with pc1: pi['label']=st.text_input("시상명",value=pi.get('label',''),key=f"pilbl_{i}_{pi_idx}")
                    with pc4:
                        if st.button("🗑️",key=f"pidel_{i}_{pi_idx}",use_container_width=True):
                            st.markdown("</div>",unsafe_allow_html=True); continue
                    cpf=pi.get('file','') or ''
                    pfi=fowds.index(cpf) if cpf in fowds else 0
                    spf=st.selectbox("📂 출처 파일",fowds,index=pfi,key=f"pifile_{i}_{pi_idx}")
                    pi['file']='' if spf=="(기본 파일과 동일)" else spf
                    apf=pi['file'] if pi['file'] else cfg['file']
                    pcols=_get_cols_for_file(apf); pcols_b=["(공란)"]+pcols
                    if pi['file'] and pi['file']!=cfg['file']:
                        pi['col_code_ext']=st.selectbox("🔗 이 파일의 사번(코드) 컬럼",pcols,index=_get_idx(pi.get('col_code_ext',''),pcols),key=f"picext_{i}_{pi_idx}")
                    else: pi['col_code_ext']=''
                    p2,p3=st.columns(2)
                    with p2:
                        ce=pi.get('col_eligible','')
                        se=st.selectbox("지급률 컬럼 (0=미대상)",pcols_b,index=pcols_b.index(ce) if ce in pcols_b else 0,key=f"pielig_{i}_{pi_idx}")
                        pi['col_eligible']=se if se!="(공란)" else ""
                    with p3:
                        cp=pi.get('col_prize','')
                        sp=st.selectbox("예정시상금 컬럼",pcols_b,index=pcols_b.index(cp) if cp in pcols_b else 0,key=f"piprz_{i}_{pi_idx}")
                        pi['col_prize']=sp if sp!="(공란)" else ""
                    st.markdown("</div>",unsafe_allow_html=True)
                    updated.append(pi)
                cfg['prize_items']=updated
                if st.button("➕ 시상금 항목 추가",key=f"piadd_{i}",use_container_width=True):
                    cfg['prize_items'].append({"label":f"시상금{len(cfg['prize_items'])+1}","file":"","col_code_ext":"","col_eligible":"","col_prize":""}); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- [3] 누계 ---
    st.divider()
    st.markdown("<h3 class='blue-title'>📈 3. 월간 누계 시상 항목 관리</h3>", unsafe_allow_html=True)
    if st.button("➕ 신규 누계 항목 추가",type="primary",use_container_width=True,key="add_cumul"):
        if not file_opts: st.error("⚠️ 먼저 파일 업로드 필요")
        else:
            st.session_state['config'].append({
                "name":f"신규 누계 항목 {len(st.session_state['config'])+1}",
                "desc":"","category":"cumulative","type":"누계",
                "file":file_opts[0],"col_code":"","col_val":"",
                "prize_items":[{"label":"시상금","file":"","col_code_ext":"","col_eligible":"","col_prize":""}]
            }); st.rerun()
    cumul_cfgs=[(i,c) for i,c in enumerate(st.session_state['config']) if c.get('category')=='cumulative']
    if not cumul_cfgs: st.info("현재 설정된 누계 항목이 없습니다.")
    for i, cfg in cumul_cfgs:
        st.markdown("<div class='config-box-blue'>", unsafe_allow_html=True)
        ct,cdl=st.columns([8,2])
        with ct: st.markdown(f"<h3 class='config-title' style='color:#1e3c72;'>📘 {cfg['name']} 설정</h3>", unsafe_allow_html=True)
        with cdl:
            if st.button("삭제",key=f"del_cfg_{i}",use_container_width=True): st.session_state['config'].pop(i); st.rerun()
        cfg['name']=st.text_input("누계 항목명",value=cfg['name'],key=f"name_{i}")
        cfg['file']=st.selectbox("📂 기본 파일",file_opts,index=_get_idx(cfg.get('file',''),file_opts) if file_opts else 0,key=f"file_{i}")
        cols=_get_cols_for_file(cfg['file'])
        c1,c2=st.columns(2)
        with c1:
            cfg['col_code']=st.selectbox("설계사코드(사번)",cols,index=_get_idx(cfg.get('col_code',''),cols),key=f"ccode_{i}")
            cfg['col_val']=st.selectbox("누계 실적 컬럼",cols,index=_get_idx(cfg.get('col_val',''),cols),key=f"cval_{i}")
        with c2:
            st.markdown("**💰 시상금 항목** <small style='color:#8b95a1;'>— 항목별 파일 선택 가능</small>", unsafe_allow_html=True)
            if 'prize_items' not in cfg:
                old_col=cfg.pop('col_prize','')
                cfg['prize_items']=[{"label":"시상금","file":"","col_code_ext":"","col_eligible":"","col_prize":old_col}] if old_col else [{"label":"시상금","file":"","col_code_ext":"","col_eligible":"","col_prize":""}]
            for _pi in cfg.get('prize_items',[]):
                if 'col' in _pi and 'col_prize' not in _pi: _pi['col_prize']=_pi.pop('col','')
                if 'col_eligible' not in _pi: _pi['col_eligible']=''
                if 'file' not in _pi: _pi['file']=''
                if 'col_code_ext' not in _pi: _pi['col_code_ext']=''
            fowds=["(기본 파일과 동일)"]+file_opts
            updated=[]
            for pi_idx,pi in enumerate(cfg.get('prize_items',[])):
                st.markdown("<div style='background:#f0f4ff;padding:8px 10px;border-radius:8px;margin:6px 0;border:1px solid #c7d2fe;'>", unsafe_allow_html=True)
                pc1,pc4=st.columns([8,2])
                with pc1: pi['label']=st.text_input("시상명",value=pi.get('label',''),key=f"cpilbl_{i}_{pi_idx}")
                with pc4:
                    if st.button("🗑️",key=f"cpidel_{i}_{pi_idx}",use_container_width=True):
                        st.markdown("</div>",unsafe_allow_html=True); continue
                cpf=pi.get('file','') or ''
                pfi=fowds.index(cpf) if cpf in fowds else 0
                spf=st.selectbox("📂 출처 파일",fowds,index=pfi,key=f"cpifile_{i}_{pi_idx}")
                pi['file']='' if spf=="(기본 파일과 동일)" else spf
                apf=pi['file'] if pi['file'] else cfg['file']
                pcols=_get_cols_for_file(apf); pcols_b=["(공란)"]+pcols
                if pi['file'] and pi['file']!=cfg['file']:
                    pi['col_code_ext']=st.selectbox("🔗 이 파일의 사번(코드) 컬럼",pcols,index=_get_idx(pi.get('col_code_ext',''),pcols),key=f"cpicext_{i}_{pi_idx}")
                else: pi['col_code_ext']=''
                p2,p3=st.columns(2)
                with p2:
                    ce=pi.get('col_eligible','')
                    se=st.selectbox("지급률 컬럼 (0=미대상)",pcols_b,index=pcols_b.index(ce) if ce in pcols_b else 0,key=f"cpielig_{i}_{pi_idx}")
                    pi['col_eligible']=se if se!="(공란)" else ""
                with p3:
                    cp=pi.get('col_prize','')
                    sp=st.selectbox("예정시상금 컬럼",pcols_b,index=pcols_b.index(cp) if cp in pcols_b else 0,key=f"cpiprz_{i}_{pi_idx}")
                    pi['col_prize']=sp if sp!="(공란)" else ""
                st.markdown("</div>",unsafe_allow_html=True)
                updated.append(pi)
            cfg['prize_items']=updated
            if st.button("➕ 시상금 항목 추가",key=f"cpiadd_{i}",use_container_width=True):
                cfg['prize_items'].append({"label":f"시상금{len(cfg['prize_items'])+1}","file":"","col_code_ext":"","col_eligible":"","col_prize":""}); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- [4] 리플렛 ---
    st.divider()
    st.markdown("<h3 class='sub-title' style='margin-top:10px;'>🖼️ 4. 안내 리플렛(이미지) 등록</h3>", unsafe_allow_html=True)
    lf=st.file_uploader("리플렛 이미지 업로드",type=['jpg','jpeg','png'])
    if lf:
        with open(os.path.join(DATA_DIR,"leaflet.png"),"wb") as f: f.write(lf.getbuffer())
        st.success("✅ 리플렛 저장 완료!"); st.rerun()
    lp=os.path.join(DATA_DIR,"leaflet.png")
    if os.path.exists(lp):
        st.image(lp, width=250)
        if st.button("🗑️ 리플렛 삭제"): os.remove(lp); st.rerun()

    # --- [5] 백업/복원 ---
    st.divider()
    st.markdown("<h3 class='sub-title' style='margin-top:10px;'>💾 5. 설정 백업 및 복원</h3>", unsafe_allow_html=True)
    cb,cr=st.columns(2)
    with cb:
        if st.session_state['config']:
            st.download_button("⬇️ 설정 백업",data=json.dumps(st.session_state['config'],ensure_ascii=False,indent=2,cls=NumpyEncoder),
                file_name=f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",mime="application/json",use_container_width=True)
        else: st.warning("백업할 설정 없음")
    with cr:
        rf=st.file_uploader("백업 JSON 업로드",type=['json'],key="restore_config")
        if rf:
            try:
                rd=json.loads(rf.read().decode('utf-8'))
                if isinstance(rd,list):
                    for c in rd:
                        if 'category' not in c: c['category']='weekly'
                    st.success(f"✅ 확인: 주차 {sum(1 for c in rd if c.get('category')=='weekly')}개, 누계 {sum(1 for c in rd if c.get('category')=='cumulative')}개")
                    if st.button("🔄 복원하기",type="primary",use_container_width=True,key="do_restore"):
                        st.session_state['config']=rd
                        with open(os.path.join(DATA_DIR,'config.json'),'w',encoding='utf-8') as f: json.dump(rd,f,ensure_ascii=False,cls=NumpyEncoder)
                        st.session_state['merged_data']=build_merged_data(rd,st.session_state['raw_data'])
                        save_merged_to_disk(st.session_state['merged_data'])
                        st.success("✅ 복원 완료!"); st.rerun()
            except Exception as e: st.error(f"❌ 오류: {e}")

    # --- 서버 반영 ---
    if st.session_state['config']:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ 모든 설정 완료 및 서버에 반영하기",type="primary",use_container_width=True):
            with open(os.path.join(DATA_DIR,'config.json'),'w',encoding='utf-8') as f: json.dump(st.session_state['config'],f,ensure_ascii=False,cls=NumpyEncoder)
            st.session_state['merged_data']=build_merged_data(st.session_state['config'],st.session_state['raw_data'])
            save_merged_to_disk(st.session_state['merged_data'])
            ext_cnt=sum(1 for cfg in st.session_state['config'] for pi in cfg.get('prize_items',[]) if pi.get('file') and pi['file']!=cfg.get('file',''))
            st.success(f"✅ 서버 반영 완료! (데이터셋 {len(st.session_state['merged_data'])}개, 외부파일 항목 {ext_cnt}개 병합)")
        cp=os.path.join(DATA_DIR,'config.json')
        if os.path.exists(cp):
            st.divider()
            with open(cp,'r',encoding='utf-8') as f: cd=f.read()
            st.download_button("📥 config.json 다운로드",data=cd,file_name="config.json",mime="application/json")

# ==========================================
# 🏆 사용자 모드
# ==========================================
else:
    st.markdown('<div class="title-band">메리츠화재 시상 현황</div>', unsafe_allow_html=True)
    st.markdown("<h3 class='main-title'>이름과 지점별 코드를 입력하세요.</h3>", unsafe_allow_html=True)
    user_name=st.text_input("본인 이름",placeholder="예: 홍길동")
    branch_code_input=st.text_input("지점별 코드",placeholder="예: 1지점은 1, 11지점은 11")
    codes_found=set(); needs_dis=False
    if user_name and branch_code_input:
        for ci,cfg in enumerate(st.session_state['config']):
            if cfg.get('category')=='cumulative': continue
            df=_get_merged_df(ci)
            if df is not None:
                cn=cfg.get('col_name',''); cb=cfg.get('col_branch','')
                sn=df[cn].fillna('').astype(str).str.strip() if cn and cn in df.columns else pd.Series()
                if sn.empty: continue
                nm=(sn==user_name.strip())
                if branch_code_input.strip()=="0000": match=df[nm]
                else:
                    cc=branch_code_input.replace("지점","").strip()
                    if cc:
                        sb=df[cb].fillna('').astype(str) if cb and cb in df.columns else pd.Series()
                        if sb.empty: continue
                        match=df[nm & sb.str.contains(rf"(?<!\d){cc}\s*지점",regex=True)]
                    else: match=pd.DataFrame()
                if not match.empty and cfg.get('col_code') and cfg['col_code'] in df.columns:
                    for ac in get_clean_series(df,cfg['col_code'])[match.index]:
                        if ac: codes_found.add(ac)
    codes_found={c for c in codes_found if c}
    sel_code=None
    if len(codes_found)>1:
        st.warning("⚠️ 동명이인이 있습니다. 사번을 선택해주세요.")
        sel_code=st.selectbox("사번 선택",sorted(list(codes_found))); needs_dis=True
    if st.button("내 실적 확인하기",type="primary"):
        if not user_name or not branch_code_input: st.warning("이름과 지점코드를 입력해주세요.")
        elif not st.session_state['config']: st.warning("시책 데이터가 없습니다.")
        elif not codes_found: st.error("일치하는 정보가 없습니다.")
        else:
            fc=sel_code if needs_dis else list(codes_found)[0]
            cr2,tp=calculate_agent_performance(fc)
            if cr2:
                dn=user_name
                for ci,cfg in enumerate(st.session_state['config']):
                    df=_get_merged_df(ci)
                    if df is None: continue
                    cc=cfg.get('col_code',''); cag=cfg.get('col_agency','')
                    if not cc or cc not in df.columns: continue
                    if not cag or cag not in df.columns: continue
                    m=df[get_clean_series(df,cc)==safe_str(fc)]
                    if not m.empty:
                        av=_clean_excel_text(str(m[cag].values[0]).strip())
                        if av and av!='nan': dn=f"{av} {user_name}"; break
                save_log(f"{user_name}({branch_code_input}지점)",fc,"USER_SEARCH")
                render_ui_cards(dn,cr2,tp,show_share_text=False)
                ulp=os.path.join(DATA_DIR,"leaflet.png")
                if os.path.exists(ulp): st.markdown("<div style='margin-top:20px;'></div>",unsafe_allow_html=True); st.image(ulp,use_container_width=True)
            else: st.error("해당 조건의 실적 데이터가 없습니다.")
