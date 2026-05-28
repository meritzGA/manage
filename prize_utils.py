"""
prize_utils.py — 시상금 계산 유틸리티 모듈
============================================
manage.py, render.py 에서 import 하여 사용.
Streamlit 앱 코드(st.set_page_config 등)는 포함하지 않음.
"""
import pandas as pd
import re


# ═══════════════════════════════════════════════════════
# 키 정제
# ═══════════════════════════════════════════════════════
def clean_key(val):
    """설계사코드 등을 비교용 문자열로 정제."""
    if pd.isna(val) or str(val).strip().lower() == 'nan':
        return ""
    val_str = str(val).strip().replace(" ", "").upper()
    val_str = re.sub(r'_[xX]([0-9A-Fa-f]{4})_',
                     lambda m: chr(int(m.group(1), 16)), val_str)
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    return val_str


# ═══════════════════════════════════════════════════════
# 내부 헬퍼
# ═══════════════════════════════════════════════════════
def _safe_float_prize(val):
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).replace(',', '').strip()
    try:
        return float(s)
    except Exception:
        return 0.0


def _first_valid(df, col):
    """지정 열에서 NaN이 아닌 첫 번째 값을 반환. 없으면 0."""
    if not col or col not in df.columns:
        return 0
    s = df[col].dropna()
    return s.values[0] if not s.empty else 0


def _read_prize_items_app(cfg, match_df):
    """설정에서 시상금 항목들을 읽어 [{label, amount}] 리스트 반환."""
    prize_details = []
    items = cfg.get('prize_items', [])
    if items:
        for item in items:
            col_prize = item.get('col_prize', '') or item.get('col', '')
            label = item.get('label', '')
            if not col_prize or col_prize not in match_df.columns:
                continue

            col_elig = item.get('col_eligible', '')
            if col_elig and col_elig in match_df.columns:
                elig_series = match_df[col_elig].dropna()
                elig_val = _safe_float_prize(elig_series.values[0]) if not elig_series.empty else 0
                if elig_val == 0:
                    continue

            prize_series = match_df[col_prize].dropna()
            raw = prize_series.values[0] if not prize_series.empty else 0
            amt = _safe_float_prize(raw)
            prize_details.append({"label": label or col_prize, "amount": amt})
    else:
        col_prize = cfg.get('col_prize', '')
        if col_prize and col_prize in match_df.columns:
            prize_series = match_df[col_prize].dropna()
            raw = prize_series.values[0] if not prize_series.empty else 0
            amt = _safe_float_prize(raw)
            if amt != 0:
                prize_details.append({"label": "시상금", "amount": amt})
    return prize_details


# ═══════════════════════════════════════════════════════
# 시상금 계산 (config 기반)
# ═══════════════════════════════════════════════════════
def calculate_prize_for_code(target_code, prize_config, df_src):
    """특정 사번의 시상금을 df_merged 에서 직접 읽기.
    Returns (results_list, total_prize).
    """
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
            for alt_col in ['본인고객번호', '본인고객ID', '_unified_search_key']:
                if alt_col in df_src.columns:
                    _ac = f"_pclean_{alt_col}"
                    if _ac not in df_src.columns:
                        df_src[_ac] = df_src[alt_col].apply(clean_key)
                    match_df = df_src[df_src[_ac] == safe_code]
                    if not match_df.empty:
                        break
        if match_df.empty:
            continue

        cat = cfg.get('category', 'weekly')
        p_type = cfg.get('type', '구간 시책')

        prize_details = _read_prize_items_app(cfg, match_df)
        prize = sum(d['amount'] for d in prize_details)

        if cat == 'weekly':
            if "1기간" in p_type:
                if not prize_details:
                    continue
                val_prev = _safe_float_prize(_first_valid(match_df, cfg.get('col_val_prev', '')))
                val_curr = _safe_float_prize(_first_valid(match_df, cfg.get('col_val_curr', '')))
                results.append({
                    "name": cfg['name'], "category": "weekly", "type": "브릿지1",
                    "val_prev": val_prev, "val_curr": val_curr,
                    "prize": prize, "prize_details": prize_details
                })

            elif "2기간" in p_type:
                val_prev = _safe_float_prize(_first_valid(match_df, cfg.get('col_val_prev', '')))
                val_curr = _safe_float_prize(_first_valid(match_df, cfg.get('col_val_curr', '')))
                curr_req = float(cfg.get('curr_req', 100000.0))
                calc_rate, tier_achieved, prize = 0, 0, 0
                for amt, rate in cfg.get('tiers', []):
                    if val_prev >= amt:
                        tier_achieved = amt
                        calc_rate = rate
                        break
                if tier_achieved > 0:
                    prize = (tier_achieved + curr_req) * (calc_rate / 100)
                next_tier = None
                for amt, rate in reversed(cfg.get('tiers', [])):
                    if val_prev < amt:
                        next_tier = amt
                        break
                shortfall = next_tier - val_prev if next_tier else 0
                curr_met = val_curr >= curr_req
                results.append({
                    "name": cfg['name'], "category": "weekly", "type": "브릿지2",
                    "val": val_prev, "val_curr": val_curr,
                    "tier": tier_achieved, "rate": calc_rate, "prize": prize,
                    "curr_req": curr_req, "next_tier": next_tier,
                    "shortfall": shortfall, "curr_met": curr_met
                })

            elif "주차브릿지" in p_type:
                w3 = _safe_float_prize(_first_valid(match_df, cfg.get('col_val_w3', '')))
                w3_label = cfg.get('w3_label', '3주')
                w4_label = cfg.get('w4_label', '4주')
                wb_tiers = cfg.get('weekly_bridge_tiers', [])
                tier_achieved = 0
                projected_prize = 0
                for threshold, prize_amt in wb_tiers:
                    if w3 >= threshold:
                        tier_achieved = threshold
                        projected_prize = prize_amt
                        break
                next_tier = None
                next_tier_prize = 0
                for threshold, prize_amt in reversed(wb_tiers):
                    if w3 < threshold:
                        next_tier = threshold
                        next_tier_prize = prize_amt
                        break
                shortfall = max(0, (next_tier or 0) - w3) if next_tier else 0
                if w3 == 0:
                    continue
                results.append({
                    "name": cfg['name'], "category": "weekly", "type": "주차브릿지",
                    "val_w3": w3, "tier": tier_achieved, "prize": projected_prize,
                    "next_tier": next_tier,
                    "next_tier_prize": next_tier_prize if next_tier else 0,
                    "shortfall": shortfall,
                    "w3_label": w3_label, "w4_label": w4_label
                })

            else:
                if not prize_details:
                    continue
                val = _safe_float_prize(_first_valid(match_df, cfg.get('col_val', '')))
                results.append({
                    "name": cfg['name'], "category": "weekly", "type": "구간",
                    "val": val, "prize": prize, "prize_details": prize_details
                })

        elif cat == 'cumulative':
            if not prize_details:
                continue
            val = _safe_float_prize(_first_valid(match_df, cfg.get('col_val', '')))
            results.append({
                "name": cfg['name'], "category": "cumulative", "type": "누계",
                "val": val, "prize": prize, "prize_details": prize_details
            })

    total = sum(r['prize'] for r in results)
    return results, total


# ═══════════════════════════════════════════════════════
# 카톡 복사용 텍스트
# ═══════════════════════════════════════════════════════
def format_prize_clip_text(results, total):
    """시상 결과를 카카오톡 공유용 텍스트로 변환."""
    if not results:
        return ""
    gugan_res = [r for r in results if r['category'] == 'weekly' and r['type'] == '구간']
    bridge_res = [r for r in results if r['category'] == 'weekly' and '브릿지' in r['type']]
    cumul_res = [r for r in results if r['category'] == 'cumulative']
    cumul_sum = sum(r['prize'] for r in cumul_res)
    gugan_sum = sum(r['prize'] for r in gugan_res)
    bridge_sum = sum(r['prize'] for r in bridge_res)

    lines = ["", f"💰 예상 시상금: {total:,.0f}원"]
    if cumul_sum > 0 or gugan_sum > 0 or bridge_sum > 0:
        parts = []
        if cumul_sum > 0: parts.append(f"누계 {cumul_sum:,.0f}")
        if gugan_sum > 0: parts.append(f"주차 {gugan_sum:,.0f}")
        if bridge_sum > 0: parts.append(f"브릿지 {bridge_sum:,.0f}")
        lines.append(f"  ({' + '.join(parts)})")
    for r in gugan_res:
        if r['prize'] > 0:
            lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
            for d in r.get('prize_details', []):
                lines.append(f"    · {d['label']}: {d['amount']:,.0f}원")
    for r in bridge_res:
        if r['prize'] > 0:
            if r['type'] == '브릿지2':
                lines.append(f"  {r['name']}: {r['prize']:,.0f}원 (당월 {int(r.get('curr_req',100000)//10000)}만 가동 시)")
            elif r['type'] == '주차브릿지':
                w3l = r.get('w3_label', '3주')
                w4l = r.get('w4_label', '4주')
                lines.append(f"  {r['name']}: {r['prize']:,.0f}원 ({w4l} 동일 가동 시)")
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


# ═══════════════════════════════════════════════════════
# 시상 카드 HTML (모바일 카드 뷰용)
# ═══════════════════════════════════════════════════════
def _prize_detail_sub_html(details):
    """시상금 항목이 2개 이상일 때 상세 내역 HTML."""
    if len(details) <= 1:
        return ""
    h = ""
    for d in details:
        h += (f'<div class="m-row">'
              f'<span class="m-label" style="padding-left:10px;font-size:11px;">· {d["label"]}</span>'
              f'<span class="m-val" style="font-size:11px;">{d["amount"]:,.0f}원</span></div>')
    return h


def build_prize_card_html(results, total):
    """시상 결과를 모바일 카드 뷰용 HTML로 변환."""
    if not results:
        return ""
    gugan_res = [r for r in results if r['category'] == 'weekly' and r['type'] == '구간']
    bridge_res = [r for r in results if r['category'] == 'weekly' and '브릿지' in r['type']]
    cumul_res = [r for r in results if r['category'] == 'cumulative']
    cumul_sum = sum(r['prize'] for r in cumul_res)
    gugan_sum = sum(r['prize'] for r in gugan_res)
    bridge_sum = sum(r['prize'] for r in bridge_res)

    h = '<div style="margin-top:8px; padding:10px; background:#fff8f0; border-radius:10px; border:1px solid #ffd4a8;">'
    h += f'<div style="font-weight:800;color:#d9232e;font-size:15px;margin-bottom:2px;">💰 총 시상금: {total:,.0f}원</div>'
    if cumul_sum > 0 or gugan_sum > 0 or bridge_sum > 0:
        parts = []
        if cumul_sum > 0: parts.append(f"누계 {cumul_sum:,.0f}")
        if gugan_sum > 0: parts.append(f"주차 {gugan_sum:,.0f}")
        if bridge_sum > 0: parts.append(f"브릿지 {bridge_sum:,.0f}")
        h += f'<div style="font-size:11px;color:#888;margin-bottom:6px;">({" + ".join(parts)})</div>'

    if gugan_res:
        h += '<div style="font-size:11px;color:#4e5968;font-weight:700;margin-top:4px;">📌 주차 시상</div>'
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
            elif r['type'] == '주차브릿지':
                w3l = r.get('w3_label', '3주')
                w4l = r.get('w4_label', '4주')
                tier_txt = f"{r.get('tier',0):,.0f}원" if r.get('tier', 0) > 0 else "미달성"
                label = f"{r['name']}<br><span style='font-size:10px;color:#888;'>({w4l} 동일 가동 시)</span>"
                h += f'<div class="m-row"><span class="m-label">{label}</span><span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                h += f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:11px;">· {w3l} 실적 (구간: {tier_txt})</span><span class="m-val" style="font-size:11px;">{r.get("val_w3",0):,.0f}원</span></div>'
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
