"""
prize_app_v2.py — 메리츠화재 시상 현황 (자동 감지 Ver 2.0)
=============================================================
• data/ 폴더의 Excel 파일을 자동 감지·병합
• 컬럼 패턴으로 시상 구조 자동 인식 (config 불필요)
• 내 실적 조회 / 매니저 관리 / 관리자 상태 확인
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import re
import glob
from datetime import datetime
import streamlit.components.v1 as components

st.set_page_config(page_title="메리츠화재 시상 현황", layout="wide")

DATA_DIR = "data"
SETTINGS_FILE = "settings.json"

# ═══════════════════════════════════════════════════════
# 0. 유틸리티
# ═══════════════════════════════════════════════════════
def _clean_excel_text(s):
    if not s or not isinstance(s, str): return s
    return re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), s)

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

def safe_float(val):
    if pd.isna(val) or val is None: return 0.0
    s = str(val).replace(',', '').strip()
    try: return float(s)
    except: return 0.0

def get_clean_series(df, col_name):
    ck = f"_ck_{col_name}"
    if ck not in df.columns:
        df[ck] = df[col_name].apply(safe_str)
    return df[ck]


# ═══════════════════════════════════════════════════════
# 1. 설정
# ═══════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    "admin_password": "wolf7998",
    "clip_footer": "",
    "prize_labels": {
        "base": "인보험 기본", "상품": "상품 추가",
        "상품추가": "상품 추가2", "유퍼간편": "유퍼스트",
        "추가": "인보험 추가"
    }
}

@st.cache_data(show_spinner=False)
def load_settings():
    s = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                u = json.load(f)
            for k, v in u.items():
                if isinstance(v, dict) and isinstance(s.get(k), dict):
                    s[k].update(v)
                else:
                    s[k] = v
        except: pass
    return s


# ═══════════════════════════════════════════════════════
# 2. 데이터 로딩
# ═══════════════════════════════════════════════════════
def find_latest_files():
    if not os.path.exists(DATA_DIR):
        return None, None, None
    def _latest(pattern):
        files = glob.glob(os.path.join(DATA_DIR, pattern))
        if not files: return None
        def _d(f):
            m = re.search(r'(\d{8})', os.path.basename(f))
            return m.group(1) if m else '00000000'
        return max(files, key=_d)
    sp = _latest("PRIZE_SUM_OUT_*.xlsx")
    bp = _latest("PRIZE_6_BRIDGE_OUT_*.xlsx")
    dd = None
    if sp:
        m = re.search(r'(\d{8})', os.path.basename(sp))
        if m:
            from datetime import timedelta
            file_date = datetime.strptime(m.group(1), '%Y%m%d')
            base_date = file_date - timedelta(days=1)
            dd = base_date.strftime('%Y.%m.%d')
    return sp, bp, dd

@st.cache_data(show_spinner="데이터를 로딩하고 있습니다...")
def load_and_merge(sum_path, bridge_path, cache_ver=None):
    def _read(path):
        df = pd.read_excel(path)
        df.columns = [_clean_excel_text(str(c)) if isinstance(c, str) else c for c in df.columns]
        for col in df.columns:
            if df[col].dtype == 'object' or pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].apply(lambda v: _clean_excel_text(str(v)) if pd.notna(v) else v)
        return df
    df_sum = _read(sum_path)
    mc = '대리점설계사조직코드'
    df_sum['_key'] = df_sum[mc].apply(safe_str)
    if bridge_path and os.path.exists(bridge_path):
        df_br = _read(bridge_path)
        df_br['_key'] = df_br[mc].apply(safe_str)
        br_only = [c for c in df_br.columns if c not in df_sum.columns or c == '_key']
        df = pd.merge(df_sum, df_br[br_only], on='_key', how='left')
    else:
        df = df_sum.copy()
    return df


# ═══════════════════════════════════════════════════════
# 3. 시상 구조 자동 감지
# ═══════════════════════════════════════════════════════
@st.cache_data(show_spinner=False)
def detect_prize_structure(cols_tuple, labels_json):
    cols = set(cols_tuple)
    labels = json.loads(labels_json)
    wp = re.compile(r'^추가13회예정금_(\d+)주대상$')
    sp = re.compile(r'^추가13회예정금_(\d+)주대상_(.+)$')
    mp = re.compile(r'^추가13회예정금_(\d+)_(\d+)주대상$')  # 연속주차 (예: 1_2주)
    smap = {'상품': '상품', '상품추가': '상품추가', '유퍼': '유퍼간편', '추가': '추가'}

    detected = {}
    for c in sorted(cols):
        # 기본: 추가13회예정금_{N}주대상
        m = wp.match(c)
        if m:
            w = int(m.group(1))
            pc = f'추가13회예정금_{w}주'
            if pc in cols:
                detected.setdefault(w, []).append({
                    'label': labels.get('base', '인보험 기본'),
                    'elig': c, 'prize': pc})
        # 서브: 추가13회예정금_{N}주대상_상품 등
        m2 = sp.match(c)
        if m2:
            w, sfx = int(m2.group(1)), m2.group(2)
            ps = smap.get(sfx, sfx)
            pc = f'추가13회예정금_{w}주_{ps}'
            if pc in cols:
                detected.setdefault(w, []).append({
                    'label': labels.get(ps, labels.get(sfx, sfx)),
                    'elig': c, 'prize': pc})
        # 연속주차: 추가13회예정금_{A}_{B}주대상 → B주차 하위항목으로 편입
        m3 = mp.match(c)
        if m3:
            a, b = int(m3.group(1)), int(m3.group(2))
            pc = f'추가13회예정금_{a}_{b}주'
            if pc in cols:
                detected.setdefault(b, []).append({
                    'label': f"{labels.get('base', '인보험 기본')} ({a}주)",
                    'elig': c, 'prize': pc})

    weeks = {}
    for w in sorted(detected.keys()):
        pf = f'실적_{w}주차'
        weeks[w] = {'perf': pf if pf in cols else None, 'items': detected[w]}

    cumul = None
    if '추가13회예정금_월대상' in cols and '추가13회예정금계' in cols:
        cumul = {'elig': '추가13회예정금_월대상', 'prize': '추가13회예정금계'}

    bridge = None
    if '브릿지시상금' in cols:
        bm = sorted(set(int(m.group(1)) for c in cols for m in [re.match(r'^브릿지실적_(\d+)월$', c)] if m))
        pm, cm = (bm[0] if len(bm) >= 1 else None), (bm[1] if len(bm) >= 2 else None)
        bridge = {
            'prev': f'브릿지실적_{pm}월' if pm else None,
            'curr': f'브릿지실적_{cm}월' if cm else None,
            'prize': '브릿지시상금',
            'shortfall': f'브릿지부족금액_{cm}월' if cm and f'브릿지부족금액_{cm}월' in cols else None,
            'target': f'브릿지실적목표_{cm}월' if cm and f'브릿지실적목표_{cm}월' in cols else None,
            'lp': f'{pm}월' if pm else '', 'lc': f'{cm}월' if cm else '',
        }

    consec = None
    if '연속가동시상금' in cols:
        cm2 = sorted(set(int(m.group(1)) for c in cols for m in [re.match(r'^연속가동실적_(\d+)월$', c)] if m))
        pm2, cm2b = (cm2[0] if len(cm2) >= 1 else None), (cm2[1] if len(cm2) >= 2 else None)
        consec = {
            'prev': f'연속가동실적_{pm2}월' if pm2 else None,
            'curr': f'연속가동실적_{cm2b}월' if cm2b else None,
            'prize': '연속가동시상금',
            'shortfall': f'연속가동부족금액_{cm2b}월' if cm2b and f'연속가동부족금액_{cm2b}월' in cols else None,
            'target': f'연속가동실적목표_{cm2b}월' if cm2b and f'연속가동실적목표_{cm2b}월' in cols else None,
            'lp': f'{pm2}월' if pm2 else '', 'lc': f'{cm2b}월' if cm2b else '',
        }

    # ── 주차연속가동 (동적 주차 감지) ──
    weekly_consec = None
    if '주차연속가동대상' in cols:
        # 주차연속가동_N주실적 패턴에서 N 추출
        wc_weeks = sorted(set(
            int(m.group(1))
            for c in cols
            for m in [re.match(r'^주차연속가동_(\d+)주실적$', c)]
            if m
        ))
        w_prev = wc_weeks[0] if len(wc_weeks) >= 1 else None  # 이전 주차 (2주 or 3주)
        w_curr = wc_weeks[1] if len(wc_weeks) >= 2 else None  # 현재 주차 (3주 or 4주)
        weekly_consec = {
            'target_col': '주차연속가동대상',
            'perf_prev': f'주차연속가동_{w_prev}주실적' if w_prev else None,
            'perf_curr': f'주차연속가동_{w_curr}주실적' if w_curr else None,
            'tier_prev': f'주차연속가동_{w_prev}주구간' if w_prev and f'주차연속가동_{w_prev}주구간' in cols else None,
            'tier_curr': f'주차연속가동_{w_curr}주구간' if w_curr and f'주차연속가동_{w_curr}주구간' in cols else None,
            'target': '주차연속가동_실적목표' if '주차연속가동_실적목표' in cols else None,
            'shortfall': '주차연속가동_실적부족액' if '주차연속가동_실적부족액' in cols else None,
            'prize': '추가13회예정금_주차연속가동' if '추가13회예정금_주차연속가동' in cols else None,
            'w_prev': w_prev, 'w_curr': w_curr,
        }

    return {'weeks': weeks, 'cumul': cumul,
            'bridge': bridge, 'consec': consec,
            'weekly_consec': weekly_consec}


# ═══════════════════════════════════════════════════════
# 4. 에이전트 시상 계산
# ═══════════════════════════════════════════════════════
def calculate_agent_performance(target_code, df, ps):
    """설계사 코드로 시상 결과 리스트 반환. Returns (results, total)"""
    code_col = '대리점설계사조직코드'
    if code_col not in df.columns:
        return [], 0
    match = df[get_clean_series(df, code_col) == safe_str(target_code)]
    if match.empty:
        return [], 0
    row = match.iloc[0]
    results = []

    # ── 주차별 시상 ──
    for w, info in ps['weeks'].items():
        perf = safe_float(row.get(info['perf'], 0)) if info['perf'] else 0
        details = []
        has_eligible = False
        for it in info['items']:
            elig = safe_float(row.get(it['elig'], 0))
            if elig == 0: continue
            has_eligible = True
            amt = safe_float(row.get(it['prize'], 0))
            if amt > 0:
                details.append({'label': it['label'], 'amount': amt})
        prize = sum(d['amount'] for d in details)
        if details or perf > 0 or has_eligible:
            results.append({
                'name': f'{w}주차 시상', 'desc': '', 'category': 'weekly',
                'type': '구간', 'val': perf, 'prize': prize,
                'prize_details': details
            })

    # ── 주차연속가동 (동적 주차) ──
    if ps.get('weekly_consec'):
        wc = ps['weekly_consec']
        tgt_val = safe_float(row.get(wc['target_col'], 0))
        if tgt_val != 0:  # 대상자만
            wp = wc.get('w_prev'); wn = wc.get('w_curr')
            perf_prev = safe_float(row.get(wc['perf_prev'], 0)) if wc.get('perf_prev') else 0
            perf_curr = safe_float(row.get(wc['perf_curr'], 0)) if wc.get('perf_curr') else 0
            tier_prev = safe_float(row.get(wc['tier_prev'], 0)) if wc.get('tier_prev') else 0
            tier_curr = safe_float(row.get(wc['tier_curr'], 0)) if wc.get('tier_curr') else 0
            target_amt = safe_float(row.get(wc['target'], 0)) if wc.get('target') else 0
            shortfall = safe_float(row.get(wc['shortfall'], 0)) if wc.get('shortfall') else 0
            prize_amt = safe_float(row.get(wc['prize'], 0)) if wc.get('prize') else 0
            has_prize = wc.get('prize') is not None
            wlabel = f"{wp}~{wn}주" if wp and wn else (f"{wp}주" if wp else "")
            if perf_prev > 0 or perf_curr > 0 or prize_amt > 0:
                results.append({
                    'name': f'주차연속가동 ({wlabel})',
                    'desc': '',
                    'category': 'weekly', 'type': '주차연속가동',
                    'perf_prev': perf_prev, 'perf_curr': perf_curr,
                    'tier_prev': tier_prev, 'tier_curr': tier_curr,
                    'w_prev': wp, 'w_curr': wn,
                    'target': target_amt, 'shortfall': shortfall,
                    'prize': prize_amt, 'has_prize': has_prize,
                })

    # ── 연속가동 (브릿지보다 먼저 표시) ──
    if ps.get('consec'):
        c = ps['consec']
        cp = safe_float(row.get(c['prize'], 0))
        vp = safe_float(row.get(c['prev'], 0)) if c['prev'] else 0
        vc = safe_float(row.get(c['curr'], 0)) if c['curr'] else 0
        sf = safe_float(row.get(c.get('shortfall', ''), 0)) if c.get('shortfall') else 0
        tgt = safe_float(row.get(c.get('target', ''), 0)) if c.get('target') else 0
        if vp > 0 or vc > 0 or cp > 0:
            results.append({
                'name': f"연속가동 시상 ({c['lp']}~{c['lc']})",
                'desc': '', 'category': 'weekly', 'type': '연속가동 브릿지',
                'val_prev': vp, 'val_curr': vc,
                'prize': cp, 'shortfall': sf, 'target': tgt,
                'label_prev': c['lp'], 'label_curr': c['lc'],
            })

    # ── 브릿지 ──
    if ps.get('bridge'):
        b = ps['bridge']
        bp = safe_float(row.get(b['prize'], 0))
        vp = safe_float(row.get(b['prev'], 0)) if b['prev'] else 0
        vc = safe_float(row.get(b['curr'], 0)) if b['curr'] else 0
        sf = safe_float(row.get(b.get('shortfall', ''), 0)) if b.get('shortfall') else 0
        tgt = safe_float(row.get(b.get('target', ''), 0)) if b.get('target') else 0
        if vp > 0 or vc > 0 or bp > 0:
            results.append({
                'name': f"브릿지 시상 ({b['lp']}~{b['lc']})",
                'desc': '', 'category': 'weekly', 'type': '브릿지_확정',
                'val_prev': vp, 'val_curr': vc,
                'prize': bp, 'shortfall': sf, 'target': tgt,
                'label_prev': b['lp'], 'label_curr': b['lc'],
            })

    total = sum(r['prize'] for r in results)
    return results, total


# ═══════════════════════════════════════════════════════
# 5. 카카오톡 복사 컴포넌트
# ═══════════════════════════════════════════════════════
def copy_btn_component(text):
    escaped = json.dumps(text, ensure_ascii=False)
    js = f"""
    <div id="copy-container"><button id="copy-btn">💬 카카오톡 메시지 원클릭 복사</button></div>
    <script>
    document.getElementById("copy-btn").onclick = function() {{
        const text = {escaped};
        var isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
        if (isMobile && navigator.share) {{
            navigator.share({{ text: text }}).catch(function() {{
                navigator.clipboard.writeText(text).then(function() {{
                    alert("복사 완료! 카카오톡 채팅창에 붙여넣기 하세요.");
                }});
            }});
        }} else {{
            navigator.clipboard.writeText(text).then(function() {{
                var btn = document.getElementById("copy-btn");
                btn.textContent = "✅ 복사 완료! 채팅창에 붙여넣기(Ctrl+V) 하세요";
                btn.style.backgroundColor = "#22C55E";
                btn.style.color = "#fff";
                setTimeout(function() {{
                    btn.textContent = "💬 카카오톡 메시지 원클릭 복사";
                    btn.style.backgroundColor = "#FEE500";
                    btn.style.color = "#3C1E1E";
                }}, 2500);
            }}).catch(function() {{
                alert("복사에 실패했습니다. 직접 선택하여 복사해주세요.");
            }});
        }}
    }}
    </script>
    <style>
        #copy-btn {{ width:100%; height:55px; background-color:#FEE500; color:#3C1E1E;
            border:none; border-radius:12px; font-weight:800; font-size:1.1rem;
            cursor:pointer; margin-top:5px; margin-bottom:20px;
            box-shadow:0 4px 10px rgba(0,0,0,0.1); }}
        #copy-btn:active {{ transform:scale(0.98); }}
    </style>"""
    components.html(js, height=85)


# ═══════════════════════════════════════════════════════
# 6. UI 카드 렌더링
# ═══════════════════════════════════════════════════════
def render_ui_cards(user_name, results, total_prize, data_date, show_share=False):
    if not results: return

    date_html = f"<div class='date-badge'>📅 기준일: {data_date}</div>" if data_date else ""

    share = f"🎯 [{user_name} 팀장님 실적 현황]\n"
    if data_date: share += f"📅 기준일: {data_date}\n"
    share += f"💰 시책 합산 시상금: {total_prize:,.0f}원\n────────────────\n"

    # ── 시책 요약 카드 ──
    if results:
        sh = f"<div class='summary-card'><div class='summary-label'>{user_name} 팀장님의 시책 현황</div>{date_html}<div class='summary-total'>{total_prize:,.0f}원</div><div class='summary-divider'></div>"
        share += "📌 [진행 중인 시책]\n"
        for r in results:
            if r['type'] == '구간':
                sh += f"<div class='data-row' style='padding:6px 0;'><span class='summary-item-name'>{r['name']}</span><span class='summary-item-val'>{r['prize']:,.0f}원</span></div>"
                share += f"🔹 {r['name']}: {r['prize']:,.0f}원\n"
            elif r['type'] in ('브릿지_확정', '연속가동 브릿지'):
                sh += f"<div class='data-row' style='padding:6px 0;'><span class='summary-item-name'>{r['name']}</span><span class='summary-item-val'>{r['prize']:,.0f}원</span></div>"
                share += f"🔹 {r['name']}: {r['prize']:,.0f}원\n"
            elif r['type'] == '주차연속가동':
                wp = r.get('w_prev', '?'); wn = r.get('w_curr', '?')
                tier_txt = f"{r['tier_prev']:,.0f}원 구간" if r.get('tier_prev', 0) > 0 else "미달성"
                if r.get('has_prize') and r['prize'] > 0:
                    sh += f"<div class='data-row' style='padding:6px 0;align-items:flex-start;'><span class='summary-item-name'>{r['name']}<br><span style='font-size:0.95rem;color:rgba(255,255,255,0.7);'>({wp}주: {r['perf_prev']:,.0f} / {tier_txt})</span></span><span class='summary-item-val'>{r['prize']:,.0f}원</span></div>"
                    share += f"🔹 {r['name']}: {r['prize']:,.0f}원 ({wp}주 실적 {r['perf_prev']:,.0f}원)\n"
                else:
                    sub = "시상금 추후" if not r.get('has_prize') else "0원"
                    sh += f"<div class='data-row' style='padding:6px 0;align-items:flex-start;'><span class='summary-item-name'>{r['name']}<br><span style='font-size:0.95rem;color:rgba(255,255,255,0.7);'>({wp}주: {r['perf_prev']:,.0f} / {tier_txt})</span></span><span class='summary-item-val' style='font-size:1.0rem;color:rgba(255,255,255,0.85);'>{sub}</span></div>"
                    share += f"🔹 {r['name']}: {wp}주 실적 {r['perf_prev']:,.0f}원 ({tier_txt})\n"
        sh += "</div>"
        st.markdown(sh, unsafe_allow_html=True)

        # ── 상세 카드 ──
        for r in results:
            desc_html = r['desc'].replace('\n', '<br>') if r.get('desc') else ''
            details = r.get('prize_details', [])

            if r['type'] == '구간':
                pdh = ""
                if len(details) > 1:
                    for d in details:
                        pdh += f"<div class='data-row'><span class='data-label'>{d['label']}</span><span class='data-value' style='color:rgb(128,0,0);'>{d['amount']:,.0f}원</span></div>"
                    pdh += "<div class='toss-divider'></div>"
                ch = f"<div class='toss-card'><div class='toss-title'>{r['name']}</div><div class='toss-desc'>{desc_html}</div><div class='data-row'><span class='data-label'>주차 누계 실적</span><span class='data-value'>{r['val']:,.0f}원</span></div><div class='toss-divider'></div>{pdh}<div class='prize-row'><span class='prize-label'>확보한 시상금</span><span class='prize-value'>{r['prize']:,.0f}원</span></div></div>"
                share += f"\n[{r['name']}]\n- 실적: {r['val']:,.0f}원\n- 시상금: {r['prize']:,.0f}원\n"
                for d in details: share += f"  · {d['label']}: {d['amount']:,.0f}원\n"

            elif r['type'] in ('브릿지_확정', '연속가동 브릿지'):
                lp, lc = r.get('label_prev', '전월'), r.get('label_curr', '당월')
                icon = "🌉" if "브릿지" in r['type'] else "🔗"
                ch = (
                    f"<div class='toss-card'>"
                    f"<div class='toss-title'>{icon} {r['name']}</div>"
                    f"<div class='toss-desc'>{desc_html}</div>"
                    f"<div class='data-row'><span class='data-label'>{lp} 실적</span><span class='data-value'>{r['val_prev']:,.0f}원</span></div>"
                    f"<div class='data-row'><span class='data-label'>{lc} 실적</span><span class='data-value'>{r['val_curr']:,.0f}원</span></div>"
                    f"<div class='toss-divider'></div>"
                    f"<div class='prize-row'><span class='prize-label'>시상금</span><span class='prize-value'>{r['prize']:,.0f}원</span></div>"
                    f"</div>"
                )
                share += f"\n[{r['name']}]\n- {lp}: {r['val_prev']:,.0f}원 / {lc}: {r['val_curr']:,.0f}원\n- 시상금: {r['prize']:,.0f}원\n"

            elif r['type'] == '주차연속가동':
                wp = r.get('w_prev', '?'); wn = r.get('w_curr', '?')
                tier_prev_txt = f"{r['tier_prev']:,.0f}원 구간" if r.get('tier_prev', 0) > 0 else "미달성"
                # 후속 주차 실적이 있으면 표시
                wn_html = ""
                if r.get('perf_curr', 0) > 0:
                    tier_curr_txt = f"{r['tier_curr']:,.0f}원 구간" if r.get('tier_curr', 0) > 0 else ""
                    wn_html = (
                        f"<div class='data-row'><span class='data-label'>{wn}주 실적</span><span class='data-value'>{r['perf_curr']:,.0f}원</span></div>"
                        + (f"<div class='data-row'><span class='data-label'>{wn}주 확보 구간</span><span class='data-value'>{tier_curr_txt}</span></div>" if tier_curr_txt else "")
                    )
                # 시상금
                if r.get('has_prize') and r['prize'] > 0:
                    prize_html = f"<div class='prize-row'><span class='prize-label'>시상금</span><span class='prize-value'>{r['prize']:,.0f}원</span></div>"
                elif r.get('has_prize'):
                    prize_html = f"<div class='prize-row'><span class='prize-label'>시상금</span><span class='prize-value'>0원</span></div>"
                else:
                    prize_html = f"<div class='prize-row'><span class='prize-label'>시상금</span><span class='prize-value' style='font-size:1.3rem;'>추후 확정</span></div>"
                ch = (
                    f"<div class='toss-card'>"
                    f"<div class='toss-title'>🔥 {r['name']}</div>"
                    f"<div class='toss-desc'>{desc_html}</div>"
                    f"<div class='data-row'><span class='data-label'>{wp}주 실적</span><span class='data-value'>{r['perf_prev']:,.0f}원</span></div>"
                    f"<div class='data-row'><span class='data-label'>{wp}주 확보 구간</span><span class='data-value'>{tier_prev_txt}</span></div>"
                    f"{wn_html}"
                    f"<div class='toss-divider'></div>"
                    f"{prize_html}"
                    f"</div>"
                )
                share += f"\n[{r['name']}]\n- {wp}주 실적: {r['perf_prev']:,.0f}원 ({tier_prev_txt})\n"
                if r.get('perf_curr', 0) > 0:
                    share += f"- {wn}주 실적: {r['perf_curr']:,.0f}원\n"
                if r.get('has_prize'):
                    share += f"- 시상금: {r['prize']:,.0f}원\n"
                else:
                    share += "- 시상금: 추후 확정\n"

            else:
                continue

            st.markdown(ch, unsafe_allow_html=True)

    if show_share:
        st.markdown("<h4 class='main-title' style='margin-top:10px;'>💬 카카오톡 바로 공유하기</h4>", unsafe_allow_html=True)
        copy_btn_component(share)


# ═══════════════════════════════════════════════════════
# 7. CSS
# ═══════════════════════════════════════════════════════
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background-color: #f2f4f6; color: #191f28; }
    span.material-symbols-rounded, span[data-testid="stIconMaterial"] { display: none !important; }
    div[data-testid="stRadio"] > div { display:flex; justify-content:center; background-color:#ffffff; padding:10px; border-radius:15px; margin-bottom:20px; margin-top:10px; box-shadow:0 4px 15px rgba(0,0,0,0.03); border:1px solid #e5e8eb; }
    .title-band { background-color:rgb(128,0,0); color:#ffffff; font-size:1.4rem; font-weight:800; text-align:center; padding:16px; border-radius:12px; margin-bottom:24px; letter-spacing:-0.5px; box-shadow:0 4px 10px rgba(128,0,0,0.2); }
    .date-badge { display:inline-block; background:rgba(255,255,255,0.15); color:rgba(255,255,255,0.9); font-size:0.85rem; font-weight:600; padding:4px 12px; border-radius:20px; margin-top:6px; }
    [data-testid="stForm"] { background-color:transparent; border:none; padding:0; margin-bottom:24px; }
    .admin-title { color:#191f28; font-weight:800; font-size:1.8rem; margin-top:20px; }
    .sub-title { color:#191f28; font-size:1.4rem; margin-top:30px; font-weight:700; }
    .main-title { color:#191f28; font-weight:800; font-size:1.3rem; margin-bottom:15px; }
    .blue-title { color:#1e3c72; font-size:1.4rem; margin-top:10px; font-weight:800; }
    .agent-title { color:#3182f6; font-weight:800; font-size:1.5rem; margin-top:0; text-align:center; }
    .detail-box { background:#ffffff; padding:20px; border-radius:20px; border:2px solid #e5e8eb; margin-top:10px; margin-bottom:30px; }
    .summary-card { background:linear-gradient(135deg,rgb(160,20,20) 0%,rgb(128,0,0) 100%); border-radius:20px; padding:32px 24px; margin-bottom:24px; border:none; box-shadow:0 10px 25px rgba(128,0,0,0.25); }
    .cumulative-card { background:linear-gradient(135deg,#1e3c72 0%,#2a5298 100%); border-radius:20px; padding:32px 24px; margin-bottom:24px; border:none; box-shadow:0 10px 25px rgba(30,60,114,0.25); }
    .summary-label { color:rgba(255,255,255,0.85); font-size:1.15rem; font-weight:600; margin-bottom:8px; }
    .summary-total { color:#ffffff; font-size:2.6rem; font-weight:800; letter-spacing:-1px; margin-bottom:24px; white-space:nowrap; }
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
    div[data-testid="stTextInput"] input { font-size:1.3rem !important; padding:15px !important; height:55px !important; background-color:#ffffff !important; border:1px solid #e5e8eb !important; border-radius:12px !important; }
    div.stButton > button[kind="primary"] { font-size:1.4rem !important; font-weight:800 !important; height:60px !important; border-radius:12px !important; background-color:rgb(128,0,0) !important; color:white !important; border:none !important; width:100%; margin-top:10px; margin-bottom:20px; box-shadow:0 4px 15px rgba(128,0,0,0.2) !important; }
    div.stButton > button[kind="secondary"] { font-size:1.2rem !important; font-weight:700 !important; min-height:60px !important; height:auto !important; padding:10px !important; border-radius:12px !important; background-color:#e8eaed !important; color:#191f28 !important; border:1px solid #d1d6db !important; width:100%; margin-top:5px; margin-bottom:5px; white-space:normal !important; }
    @media (prefers-color-scheme: dark) {
        [data-testid="stAppViewContainer"] { background-color:#121212 !important; color:#e0e0e0 !important; }
        label, p, .stMarkdown p { color:#e0e0e0 !important; }
        div[data-testid="stRadio"] > div { background-color:#1e1e1e !important; border-color:#333 !important; }
        .admin-title,.sub-title,.main-title { color:#ffffff !important; }
        .blue-title,.agent-title { color:#66b2ff !important; }
        .detail-box { background-color:#121212 !important; border-color:#333 !important; }
        .toss-card { background-color:#1e1e1e !important; border-color:#333 !important; }
        .toss-title { color:#ffffff !important; } .toss-desc { color:#ff6b6b !important; }
        .data-label { color:#a0aab5 !important; } .data-value { color:#ffffff !important; }
        .prize-label { color:#ffffff !important; } .prize-value { color:#ff4b4b !important; }
        .toss-divider { background-color:#333 !important; }
        .shortfall-row { background-color:#2a1215 !important; border-color:#ff4b4b !important; }
        .shortfall-text { color:#ff6b6b !important; }
        .cumul-stack-box { background-color:#1e1e1e !important; border-color:#333 !important; border-left-color:#4da3ff !important; }
        .cumul-stack-title { color:#4da3ff !important; } .cumul-stack-val { color:#a0aab5 !important; }
        .cumul-stack-prize { color:#ff4b4b !important; }
        div[data-testid="stTextInput"] input { background-color:#1e1e1e !important; color:#ffffff !important; border-color:#444 !important; }
        div.stButton > button[kind="secondary"] { background-color:#2d2d2d !important; color:#ffffff !important; border-color:#444 !important; }
    }
    @media (max-width: 450px) {
        .summary-total { font-size:2.1rem !important; } .prize-value { font-size:1.45rem !important; }
        .toss-title { font-size:1.4rem !important; } .shortfall-text { font-size:1.05rem !important; }
        .cumul-stack-title { font-size:1.15rem; } .cumul-stack-prize { font-size:1.4rem; }
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════
# 8. 메인 앱
# ═══════════════════════════════════════════════════════
settings = load_settings()
sp, bp, data_date = find_latest_files()

if not sp:
    st.markdown('<div class="title-band">메리츠화재 시상 현황</div>', unsafe_allow_html=True)
    st.error(f"❌ `{DATA_DIR}/` 폴더에 PRIZE_SUM_OUT_*.xlsx 파일이 없습니다.")
    st.markdown("""
    ### 📁 설정 방법
    1. 프로젝트 루트에 `data/` 폴더를 만드세요
    2. `PRIZE_SUM_OUT_YYYYMMDD.xlsx` · `PRIZE_6_BRIDGE_OUT_YYYYMMDD.xlsx` 를 넣고 push
    3. Streamlit Cloud가 자동 배포합니다
    """)
    st.stop()

sp_mtime = os.path.getmtime(sp) if sp else 0
bp_mtime = os.path.getmtime(bp) if bp and os.path.exists(bp) else 0
df_merged = load_and_merge(sp, bp, cache_ver=f"{sp_mtime}_{bp_mtime}")
ps = detect_prize_structure(
    tuple(df_merged.columns.tolist()),
    json.dumps(settings.get('prize_labels', DEFAULT_SETTINGS['prize_labels']), ensure_ascii=False)
)

mode = st.radio(
    "화면 선택",
    ["📊 내 실적 조회", "👥 매니저 관리", "⚙️ 시스템 관리자"],
    horizontal=True,
    label_visibility="collapsed"
)

# ──────────────────────────────────────────
# 📊 내 실적 조회
# ──────────────────────────────────────────
if mode == "📊 내 실적 조회":
    dd_html = f"<br><span style='font-size:0.85rem;font-weight:600;opacity:0.85;'>📅 기준일: {data_date}</span>" if data_date else ""
    st.markdown(f'<div class="title-band">메리츠화재 시상 현황{dd_html}</div>', unsafe_allow_html=True)
    st.markdown("<h3 class='main-title'>이름과 지점별 코드를 입력하세요.</h3>", unsafe_allow_html=True)

    user_name = st.text_input("본인 이름", placeholder="예: 홍길동")
    branch_code = st.text_input("지점별 코드", placeholder="예: 1지점은 1, 11지점은 11")

    codes_found = set()
    nc, bc = '대리점설계사명', '지점조직명'
    cc = '대리점설계사조직코드'

    if user_name and branch_code and nc in df_merged.columns and cc in df_merged.columns:
        sn = df_merged[nc].fillna('').astype(str).str.strip()
        nm = (sn == user_name.strip())
        if branch_code.strip() == "0000":
            match = df_merged[nm]
        else:
            code_num = branch_code.replace("지점", "").strip()
            if code_num and bc in df_merged.columns:
                sb = df_merged[bc].fillna('').astype(str)
                match = df_merged[nm & sb.str.contains(rf"(?<!\d){code_num}\s*지점", regex=True)]
            else:
                match = pd.DataFrame()
        if not match.empty and cc in df_merged.columns:
            for ac in get_clean_series(df_merged, cc)[match.index]:
                if ac: codes_found.add(ac)

    sel_code = None
    if len(codes_found) > 1:
        st.warning("⚠️ 동명이인이 있습니다. 사번을 선택해주세요.")
        sel_code = st.selectbox("사번 선택", sorted(list(codes_found)))

    if st.button("내 실적 확인하기", type="primary"):
        if not user_name or not branch_code:
            st.warning("이름과 지점코드를 입력해주세요.")
        elif not codes_found:
            st.error("일치하는 정보가 없습니다.")
        else:
            fc = sel_code if sel_code else list(codes_found)[0]
            cr, tp = calculate_agent_performance(fc, df_merged, ps)
            if cr:
                dn = user_name
                ac_col = '대리점지사명'
                if ac_col in df_merged.columns:
                    m = df_merged[get_clean_series(df_merged, cc) == safe_str(fc)]
                    if not m.empty:
                        av = _clean_excel_text(str(m[ac_col].values[0]).strip())
                        if av and av != 'nan': dn = f"{av} {user_name}"
                render_ui_cards(dn, cr, tp, data_date, show_share=False)
            else:
                st.error("해당 조건의 실적 데이터가 없습니다.")

# ──────────────────────────────────────────
# 👥 매니저 관리
# ──────────────────────────────────────────
elif mode == "👥 매니저 관리":
    st.markdown('<div class="title-band">매니저 소속 실적 관리</div>', unsafe_allow_html=True)

    mc_col = '지원매니저코드'
    mn_col = '지원매니저명'
    ac_col = '대리점설계사조직코드'
    an_col = '대리점설계사명'
    ag_col = '대리점지사명'

    if 'mgr_logged_in' not in st.session_state:
        st.session_state.mgr_logged_in = False

    if not st.session_state.mgr_logged_in:
        mgr_input = st.text_input("지원매니저 사번(코드)을 입력하세요", type="password", placeholder="예: 12345")
        if st.button("로그인", type="primary"):
            if not mgr_input:
                st.warning("코드를 입력해주세요.")
            else:
                sic = safe_str(mgr_input)
                if mc_col in df_merged.columns and sic in get_clean_series(df_merged, mc_col).unique():
                    st.session_state.mgr_logged_in = True
                    st.session_state.mgr_code = sic
                    st.session_state.mgr_step = 'main'
                    st.rerun()
                else:
                    st.error(f"❌ 코드 '{mgr_input}'가 존재하지 않습니다.")
    else:
        if st.button("🚪 로그아웃"):
            st.session_state.mgr_logged_in = False
            st.rerun()
        st.markdown('<br>', unsafe_allow_html=True)

        slc = st.session_state.mgr_code

        # 매니저 이름
        mgr_name = ""
        if mn_col in df_merged.columns and mc_col in df_merged.columns:
            mdf = df_merged[get_clean_series(df_merged, mc_col) == slc]
            if not mdf.empty and mn_col in mdf.columns:
                mgr_name = _clean_excel_text(safe_str(mdf[mn_col].values[0]))

        # 소속 설계사 코드 목록
        my_agents = set()
        if mc_col in df_merged.columns and ac_col in df_merged.columns:
            mask = get_clean_series(df_merged, mc_col) == slc
            for ac in get_clean_series(df_merged, ac_col)[mask]:
                if ac: my_agents.add(ac)

        step = st.session_state.get('mgr_step', 'main')

        if step == 'main':
            st.markdown("<h3 class='main-title'>어떤 실적을 확인하시겠습니까?</h3>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📁 구간실적 관리", use_container_width=True):
                    st.session_state.mgr_step = 'tiers'
                    st.session_state.mgr_category = '구간'
                    st.rerun()
            with c2:
                if st.button("📁 브릿지실적 관리", use_container_width=True):
                    st.session_state.mgr_step = 'tiers'
                    st.session_state.mgr_category = '브릿지'
                    st.rerun()

        elif step == 'tiers':
            if st.button("⬅️ 뒤로가기"):
                st.session_state.mgr_step = 'main'
                st.rerun()
            cat = st.session_state.mgr_category
            ranges = {500000: (300000, float('inf')), 300000: (200000, 300000),
                      200000: (100000, 200000), 100000: (0, 100000)}
            counts = {k: 0 for k in ranges}

            for ac in my_agents:
                cr, _ = calculate_agent_performance(ac, df_merged, ps)
                matched_tiers = set()
                for res in cr:
                    if cat == "구간" and "구간" not in res['type']: continue
                    if cat == "브릿지" and "브릿지" not in res['type']: continue
                    val = res.get('val', res.get('val_prev', res.get('val_curr', 0.0))) or 0
                    for t, (mn, mx) in ranges.items():
                        if mn <= val < mx:
                            matched_tiers.add(t)
                            break
                for t in matched_tiers:
                    counts[t] += 1

            st.markdown(f"<h3 class='main-title'>📁 {cat}실적 근접자 조회 (소속: 총 {len(my_agents)}명)</h3>", unsafe_allow_html=True)
            for t, (mn, mx) in ranges.items():
                ct = counts[t]
                if t == 500000:
                    lbl = f"📁 50만 구간 근접 및 달성 (30만 이상) - 총 {ct}명"
                else:
                    lbl = f"📁 {int(t//10000)}만 구간 근접자 ({int(mn//10000)}만~{int(mx//10000)}만) - 총 {ct}명"
                if st.button(lbl, use_container_width=True, key=f"t_{t}"):
                    st.session_state.mgr_step = 'list'
                    st.session_state.mgr_target = t
                    st.session_state.mgr_min_v = mn
                    st.session_state.mgr_max_v = mx
                    st.rerun()

        elif step == 'list':
            if st.button("⬅️ 폴더로 돌아가기"):
                st.session_state.mgr_step = 'tiers'
                st.rerun()
            cat = st.session_state.mgr_category
            target = st.session_state.mgr_target
            min_v = st.session_state.mgr_min_v
            max_v = st.session_state.mgr_max_v

            if target == 500000:
                st.markdown("<h3 class='main-title'>👥 50만 구간 근접 및 달성자 명단</h3>", unsafe_allow_html=True)
            else:
                st.markdown(f"<h3 class='main-title'>👥 {int(target//10000)}만 구간 근접자 명단</h3>", unsafe_allow_html=True)
            st.info("💡 이름을 클릭하면 상세 실적을 확인하고 카톡으로 전송할 수 있습니다.")

            near = []
            for code in my_agents:
                cr, _ = calculate_agent_performance(code, df_merged, ps)
                # 이름/소속 가져오기
                aname = "이름없음"
                agency = ""
                if an_col in df_merged.columns and ac_col in df_merged.columns:
                    m = df_merged[get_clean_series(df_merged, ac_col) == code]
                    if not m.empty:
                        aname = _clean_excel_text(safe_str(m[an_col].values[0]))
                        if ag_col in m.columns:
                            agency = _clean_excel_text(safe_str(m[ag_col].values[0]))

                for res in cr:
                    if cat == "구간" and "구간" not in res['type']: continue
                    if cat == "브릿지" and "브릿지" not in res['type']: continue
                    val = res.get('val', res.get('val_prev', res.get('val_curr', 0.0))) or 0
                    if min_v <= val < max_v:
                        near.append((code, aname, agency, val))
                        break

            if not near:
                st.info("해당 구간에 소속 설계사가 없습니다.")
            else:
                near.sort(key=lambda x: (x[2], x[1]))
                for code, name, agency, val in near:
                    if st.button(f"👤 [{agency}] {name} 설계사님 (현재 {val:,.0f}원)", use_container_width=True, key=f"btn_{code}"):
                        st.session_state.mgr_selected_code = code
                        st.session_state.mgr_selected_name = f"[{agency}] {name}"
                        st.session_state.mgr_step = 'detail'
                        st.rerun()

        elif step == 'detail':
            if st.button("⬅️ 명단으로 돌아가기"):
                st.session_state.mgr_step = 'list'
                st.rerun()
            code = st.session_state.mgr_selected_code
            name = st.session_state.mgr_selected_name
            st.markdown("<div class='detail-box'>", unsafe_allow_html=True)
            st.markdown(f"<h4 class='agent-title'>👤 {name} 설계사님</h4>", unsafe_allow_html=True)
            cr, tp = calculate_agent_performance(code, df_merged, ps)
            render_ui_cards(name, cr, tp, data_date, show_share=True)
            st.markdown("</div>", unsafe_allow_html=True)

# ──────────────────────────────────────────
# ⚙️ 시스템 관리자
# ──────────────────────────────────────────
elif mode == "⚙️ 시스템 관리자":
    st.markdown("<h2 class='admin-title'>시스템 상태</h2>", unsafe_allow_html=True)
    pw = st.text_input("관리자 비밀번호", type="password")
    if pw != settings.get('admin_password', 'wolf7998'):
        if pw: st.error("비밀번호가 일치하지 않습니다.")
        st.stop()
    st.success("✅ 인증 성공")

    if st.button("🔄 데이터 캐시 초기화 (파일 교체 후 사용)", type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.header("📁 로드된 데이터")
    st.markdown(f"- **SUM 파일**: `{os.path.basename(sp)}`")
    st.markdown(f"- **BRIDGE 파일**: `{os.path.basename(bp) if bp else '없음'}`")
    st.markdown(f"- **기준일**: {data_date or '감지 안됨'}")
    st.markdown(f"- **총 행 수**: {len(df_merged):,}명")

    st.header("🔍 자동 감지된 시상 구조")
    st.subheader("📌 주차별 시상")
    for w, info in ps['weeks'].items():
        with st.expander(f"{w}주차 — {len(info['items'])}개 항목", expanded=False):
            if info['perf']: st.markdown(f"**실적**: `{info['perf']}`")
            for p in info['items']:
                st.markdown(f"- **{p['label']}**: `{p['elig']}` → `{p['prize']}`")

    if ps['bridge']:
        st.subheader("🌉 브릿지")
        b = ps['bridge']
        st.markdown(f"- {b['lp']}: `{b['prev']}` / {b['lc']}: `{b['curr']}`")
        st.markdown(f"- 시상금: `{b['prize']}` / 부족액: `{b.get('shortfall', '없음')}`")

    if ps['consec']:
        st.subheader("🔗 연속가동")
        c = ps['consec']
        st.markdown(f"- {c['lp']}: `{c['prev']}` / {c['lc']}: `{c['curr']}`")
        st.markdown(f"- 시상금: `{c['prize']}` / 부족액: `{c.get('shortfall', '없음')}`")

    if ps.get('weekly_consec'):
        wc = ps['weekly_consec']
        wp = wc.get('w_prev', '?'); wn = wc.get('w_curr', '?')
        st.subheader(f"🔥 주차연속가동 ({wp}~{wn}주)")
        st.markdown(f"- {wp}주: `{wc.get('perf_prev','없음')}` / 구간: `{wc.get('tier_prev','없음')}`")
        st.markdown(f"- {wn}주: `{wc.get('perf_curr','없음')}` / 구간: `{wc.get('tier_curr','없음')}`")
        st.markdown(f"- 목표: `{wc.get('target','없음')}` / 부족액: `{wc.get('shortfall','없음')}`")
        if wc.get('prize'):
            st.markdown(f"- 시상금: `{wc['prize']}` ✅")
        else:
            st.caption("💡 시상금 컬럼 없음 → '추후 확정' 표시")

    st.divider()
    st.markdown("""
    ### 📝 설정 변경
    시상 라벨이나 카톡 문구를 변경하려면 프로젝트 루트의 `settings.json`을 수정하세요.
    ```json
    {
      "admin_password": "wolf7998",
      "prize_labels": {
        "base": "인보험 기본",
        "상품": "상품 추가",
        "상품추가": "상품 추가2",
        "유퍼간편": "유퍼스트"
      }
    }
    ```
    """)
