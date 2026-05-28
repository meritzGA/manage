"""
prize_utils.py — 시상금 조회 유틸리티 (v2: 엑셀 값 직접 조회)

[핵심 원칙]
  시책율·시상금은 회사가 엑셀에 이미 계산해서 내려보내기 때문에, 앱은 절대
  자체 계산(tier 기반 추정, 곱셈 등)을 하지 않고 엑셀에 찍힌 값을 그대로
  가져온다. 이렇게 하면 매주 시책율/구간 금액이 바뀌어도 config 수정이
  필요 없고, 숫자가 꼬일 일도 없다.

[감지되는 엑셀 컬럼 패턴]
  주차별 시상:    실적_{N}주차, 추가13회예정금_{N}주대상, 추가13회예정금_{N}주
                  서브: 추가13회예정금_{N}주대상_{상품|상품추가|유퍼}
                  연속주차: 추가13회예정금_{A}_{B}주대상 → {B}주차에 편입
  월누계:         추가13회예정금_월대상 + 추가13회예정금계
  월 브릿지:      브릿지실적_{A}월, 브릿지실적_{B}월, 브릿지시상금,
                  브릿지부족금액_{B}월, 브릿지실적목표_{B}월
  월 연속가동:    연속가동실적_{A}월 / _{B}월, 연속가동시상금, 부족금액/목표
  주차연속가동:   주차연속가동대상, _3주실적/_4주실적, _3주구간/_4주구간,
                  _실적목표, _실적부족액, 추가13회예정금_주차연속가동
"""
import re
import pandas as pd


# ──────────────────────────────────────────────────────────────
# 기본 유틸
# ──────────────────────────────────────────────────────────────
def clean_key(val):
    if pd.isna(val) or str(val).strip().lower() == "nan":
        return ""
    s = str(val).strip().replace(" ", "").upper()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _safe_float(val):
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


# 시상금 항목 라벨 (회사 명명규칙 반영)
_DEFAULT_LABELS = {
    "base": "인보험 기본",
    "상품": "상품 추가",
    "상품추가": "상품 추가2",
    "유퍼간편": "유퍼스트",
}
# 대상/시상 suffix 매핑 — 대상 컬럼은 '_유퍼' 지만 시상 컬럼은 '_유퍼간편'
_SUFFIX_MAP = {"상품": "상품", "상품추가": "상품추가", "유퍼": "유퍼간편"}


# ──────────────────────────────────────────────────────────────
# 컬럼 패턴 자동 감지
# ──────────────────────────────────────────────────────────────
def detect_prize_structure(columns, labels=None):
    """엑셀 컬럼 집합을 받아 시상 구조를 dict로 반환."""
    cols = set(columns)
    labels = labels or _DEFAULT_LABELS

    wp = re.compile(r"^추가13회예정금_(\d+)주대상$")
    sp = re.compile(r"^추가13회예정금_(\d+)주대상_(.+)$")
    mp = re.compile(r"^추가13회예정금_(\d+)_(\d+)주대상$")

    detected = {}   # {주차번호: [{label, elig_col, prize_col}, ...]}

    for c in sorted(cols):
        m = wp.match(c)
        if m:
            w = int(m.group(1))
            pc = f"추가13회예정금_{w}주"
            if pc in cols:
                detected.setdefault(w, []).append({
                    "label": labels.get("base", "인보험 기본"),
                    "elig":  c,
                    "prize": pc,
                })
        m2 = sp.match(c)
        if m2:
            w, sfx = int(m2.group(1)), m2.group(2)
            mapped = _SUFFIX_MAP.get(sfx, sfx)
            pc = f"추가13회예정금_{w}주_{mapped}"
            if pc in cols:
                detected.setdefault(w, []).append({
                    "label": labels.get(mapped, labels.get(sfx, sfx)),
                    "elig":  c,
                    "prize": pc,
                })
        m3 = mp.match(c)
        if m3:
            a, b = int(m3.group(1)), int(m3.group(2))
            pc = f"추가13회예정금_{a}_{b}주"
            if pc in cols:
                detected.setdefault(b, []).append({
                    "label": f"{labels.get('base', '인보험 기본')} ({a}주 연속)",
                    "elig":  c,
                    "prize": pc,
                })

    weeks = {}
    for w in sorted(detected.keys()):
        pf = f"실적_{w}주차"
        weeks[w] = {
            "perf":  pf if pf in cols else None,
            "items": detected[w],
        }

    # 월 누계
    cumul = None
    if "추가13회예정금_월대상" in cols and "추가13회예정금계" in cols:
        cumul = {
            "elig":  "추가13회예정금_월대상",
            "prize": "추가13회예정금계",
        }

    # 월 브릿지
    bridge = None
    if "브릿지시상금" in cols:
        bm = sorted({int(m.group(1))
                     for c in cols
                     for m in [re.match(r"^브릿지실적_(\d+)월$", c)] if m})
        pm = bm[0] if len(bm) >= 1 else None
        cm = bm[1] if len(bm) >= 2 else None
        bridge = {
            "prev":      f"브릿지실적_{pm}월" if pm else None,
            "curr":      f"브릿지실적_{cm}월" if cm else None,
            "prize":     "브릿지시상금",
            "shortfall": f"브릿지부족금액_{cm}월" if cm and f"브릿지부족금액_{cm}월" in cols else None,
            "target":    f"브릿지실적목표_{cm}월" if cm and f"브릿지실적목표_{cm}월" in cols else None,
            "lp":        f"{pm}월" if pm else "",
            "lc":        f"{cm}월" if cm else "",
        }

    # 월 연속가동
    consec = None
    if "연속가동시상금" in cols:
        cm2 = sorted({int(m.group(1))
                      for c in cols
                      for m in [re.match(r"^연속가동실적_(\d+)월$", c)] if m})
        pm2 = cm2[0] if len(cm2) >= 1 else None
        cmb = cm2[1] if len(cm2) >= 2 else None
        consec = {
            "prev":      f"연속가동실적_{pm2}월" if pm2 else None,
            "curr":      f"연속가동실적_{cmb}월" if cmb else None,
            "prize":     "연속가동시상금",
            "shortfall": f"연속가동부족금액_{cmb}월" if cmb and f"연속가동부족금액_{cmb}월" in cols else None,
            "target":    f"연속가동실적목표_{cmb}월" if cmb and f"연속가동실적목표_{cmb}월" in cols else None,
            "lp":        f"{pm2}월" if pm2 else "",
            "lc":        f"{cmb}월" if cmb else "",
        }

    # 주차연속가동 (3~4주 동일 가동)
    weekly_consec = None
    if "주차연속가동대상" in cols:
        weekly_consec = {
            "target_col": "주차연속가동대상",
            "perf_3w":    "주차연속가동_3주실적" if "주차연속가동_3주실적" in cols else None,
            "perf_4w":    "주차연속가동_4주실적" if "주차연속가동_4주실적" in cols else None,
            "tier_3w":    "주차연속가동_3주구간" if "주차연속가동_3주구간" in cols else None,
            "tier_4w":    "주차연속가동_4주구간" if "주차연속가동_4주구간" in cols else None,
            "target":     "주차연속가동_실적목표" if "주차연속가동_실적목표" in cols else None,
            "shortfall":  "주차연속가동_실적부족액" if "주차연속가동_실적부족액" in cols else None,
            "prize":      "추가13회예정금_주차연속가동" if "추가13회예정금_주차연속가동" in cols else None,
        }

    return {
        "weeks":         weeks,
        "cumul":         cumul,
        "bridge":        bridge,
        "consec":        consec,
        "weekly_consec": weekly_consec,
    }


# ──────────────────────────────────────────────────────────────
# 설계사 1명의 시상금 조회 (계산 X, 엑셀 값 그대로)
# ──────────────────────────────────────────────────────────────
def calculate_prize_for_code(target_code, prize_config, df_src):
    """
    엑셀에서 시상금 값을 직접 조회.

    prize_config 파라미터는 호환성을 위해 유지하나 실제로는 사용하지 않음.
    구조는 df_src 컬럼에서 자동 감지된다.

    Returns:
        (results, total) — results 의 각 항목 type:
            '구간'         — 주차별 시상
            '월브릿지'     — 월 브릿지 / 월 연속가동 (공통 렌더링)
            '주차연속'     — 주차연속가동 (3~4주 동일 가동)
            '누계'         — 월 누계
    """
    if df_src is None or df_src.empty:
        return [], 0

    code_col = "대리점설계사조직코드"
    if code_col not in df_src.columns:
        return [], 0

    ps = detect_prize_structure(df_src.columns)

    # 설계사 매칭 (clean key 기반)
    safe_code = clean_key(str(target_code))
    _ck = "_pclean_대리점설계사조직코드"
    if _ck not in df_src.columns:
        df_src[_ck] = df_src[code_col].apply(clean_key)
    match = df_src[df_src[_ck] == safe_code]
    if match.empty:
        return [], 0
    row = match.iloc[0]

    results = []

    # ── 주차별 시상 ──────────────────────────────────────────
    for w in sorted(ps["weeks"].keys()):
        info = ps["weeks"][w]
        perf = _safe_float(row.get(info["perf"], 0)) if info["perf"] else 0
        details = []
        has_eligible = False
        for it in info["items"]:
            elig = _safe_float(row.get(it["elig"], 0))
            if elig == 0:
                continue
            has_eligible = True
            amt = _safe_float(row.get(it["prize"], 0))
            if amt > 0:
                details.append({"label": it["label"], "amount": amt})
        prize = sum(d["amount"] for d in details)
        if details or perf > 0 or has_eligible:
            results.append({
                "name":          f"{w}주차 시상",
                "category":      "weekly",
                "type":          "구간",
                "val":           perf,
                "prize":         prize,
                "prize_details": details,
            })

    # ── 월 연속가동 (브릿지보다 먼저) ────────────────────────
    if ps.get("consec"):
        c = ps["consec"]
        cp = _safe_float(row.get(c["prize"], 0))
        vp = _safe_float(row.get(c["prev"], 0)) if c["prev"] else 0
        vc = _safe_float(row.get(c["curr"], 0)) if c["curr"] else 0
        sf = _safe_float(row.get(c["shortfall"], 0)) if c.get("shortfall") else 0
        tgt = _safe_float(row.get(c["target"], 0)) if c.get("target") else 0
        if vp > 0 or vc > 0 or cp > 0:
            results.append({
                "name":          f"연속가동 시상 ({c['lp']}~{c['lc']})",
                "category":      "weekly",
                "type":          "월브릿지",
                "val_prev":      vp,
                "val_curr":      vc,
                "prize":         cp,
                "shortfall":     sf,
                "target":        tgt,
                "label_prev":    c["lp"],
                "label_curr":    c["lc"],
                "prize_details": [{"label": "연속가동 시상금", "amount": cp}] if cp > 0 else [],
            })

    # ── 월 브릿지 ────────────────────────────────────────────
    if ps.get("bridge"):
        b = ps["bridge"]
        bp = _safe_float(row.get(b["prize"], 0))
        vp = _safe_float(row.get(b["prev"], 0)) if b["prev"] else 0
        vc = _safe_float(row.get(b["curr"], 0)) if b["curr"] else 0
        sf = _safe_float(row.get(b["shortfall"], 0)) if b.get("shortfall") else 0
        tgt = _safe_float(row.get(b["target"], 0)) if b.get("target") else 0
        if vp > 0 or vc > 0 or bp > 0:
            results.append({
                "name":          f"브릿지 시상 ({b['lp']}~{b['lc']})",
                "category":      "weekly",
                "type":          "월브릿지",
                "val_prev":      vp,
                "val_curr":      vc,
                "prize":         bp,
                "shortfall":     sf,
                "target":        tgt,
                "label_prev":    b["lp"],
                "label_curr":    b["lc"],
                "prize_details": [{"label": "브릿지 시상금", "amount": bp}] if bp > 0 else [],
            })

    # ── 주차연속가동 (3~4주) ─────────────────────────────────
    if ps.get("weekly_consec"):
        wc = ps["weekly_consec"]
        tgt_val = _safe_float(row.get(wc["target_col"], 0))
        if tgt_val != 0:  # 대상자만
            perf_3w = _safe_float(row.get(wc["perf_3w"], 0)) if wc.get("perf_3w") else 0
            perf_4w = _safe_float(row.get(wc["perf_4w"], 0)) if wc.get("perf_4w") else 0
            tier_3w = _safe_float(row.get(wc["tier_3w"], 0)) if wc.get("tier_3w") else 0
            tier_4w = _safe_float(row.get(wc["tier_4w"], 0)) if wc.get("tier_4w") else 0
            sf = _safe_float(row.get(wc["shortfall"], 0)) if wc.get("shortfall") else 0
            prize_amt = _safe_float(row.get(wc["prize"], 0)) if wc.get("prize") else 0
            has_prize = wc.get("prize") is not None
            if perf_3w > 0 or perf_4w > 0 or prize_amt > 0:
                results.append({
                    "name":      "주차연속가동 (3~4주)",
                    "category":  "weekly",
                    "type":      "주차연속",
                    "perf_3w":   perf_3w,
                    "perf_4w":   perf_4w,
                    "tier_3w":   tier_3w,
                    "tier_4w":   tier_4w,
                    "shortfall": sf,
                    "prize":     prize_amt,
                    "has_prize": has_prize,
                })

    # ── 월 누계 ──────────────────────────────────────────────
    if ps.get("cumul"):
        cm = ps["cumul"]
        elig = _safe_float(row.get(cm["elig"], 0))
        if elig != 0:
            amt = _safe_float(row.get(cm["prize"], 0))
            if amt > 0:
                results.append({
                    "name":          "월 누계 시상",
                    "category":      "cumulative",
                    "type":          "누계",
                    "val":           0,
                    "prize":         amt,
                    "prize_details": [{"label": "월 누계", "amount": amt}],
                })

    total = sum(r["prize"] for r in results)
    return results, total


# ──────────────────────────────────────────────────────────────
# 카톡 복사 텍스트 생성
# ──────────────────────────────────────────────────────────────
def format_prize_clip_text(results, total):
    if not results:
        return ""

    lines = ["", f"💰 예상 시상금: {total:,.0f}원"]

    for r in results:
        t = r["type"]

        if t == "구간":
            if r["prize"] > 0 or r.get("val", 0) > 0:
                lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
                for d in r.get("prize_details", []):
                    lines.append(f"    · {d['label']}: {d['amount']:,.0f}원")

        elif t == "월브릿지":
            lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
            lines.append(f"    {r['label_prev']} 실적: {r['val_prev']:,.0f}원")
            lines.append(f"    {r['label_curr']} 실적: {r['val_curr']:,.0f}원")
            if r.get("shortfall", 0) > 0 and r.get("target", 0) > 0:
                lines.append(
                    f"    🎯 목표 {r['target']:,.0f}원까지 {r['shortfall']:,.0f}원 부족"
                )

        elif t == "주차연속":
            if r.get("has_prize") and r["prize"] > 0:
                lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
            elif r.get("has_prize"):
                lines.append(f"  {r['name']}: 0원 (추후 확정)")
            else:
                lines.append(f"  {r['name']}: 추후 확정")
            tier3 = f"{r['tier_3w']:,.0f}원 구간" if r.get("tier_3w", 0) > 0 else "미달성"
            lines.append(f"    3주 실적: {r['perf_3w']:,.0f}원 ({tier3})")
            if r.get("perf_4w", 0) > 0:
                lines.append(f"    4주 실적: {r['perf_4w']:,.0f}원")
            if r.get("shortfall", 0) > 0:
                lines.append(f"    🚀 목표까지 {r['shortfall']:,.0f}원 부족")

        elif t == "누계":
            lines.append(f"  {r['name']}: {r['prize']:,.0f}원")
            for d in r.get("prize_details", []):
                lines.append(f"    · {d['label']}: {d['amount']:,.0f}원")

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# 시상금 상세 카드 HTML (모바일 카드뷰 내부에 삽입됨)
# ──────────────────────────────────────────────────────────────
def _prize_detail_sub_html(details):
    """시상금 항목이 2개 이상일 때 상세 내역 HTML."""
    if len(details) <= 1:
        return ""
    h = ""
    for d in details:
        h += (
            f'<div class="m-row"><span class="m-label" '
            f'style="padding-left:10px;font-size:11px;">· {d["label"]}</span>'
            f'<span class="m-val" style="font-size:11px;">{d["amount"]:,.0f}원</span></div>'
        )
    return h


def build_prize_card_html(results, total):
    if not results:
        return ""

    gugan   = [r for r in results if r["type"] == "구간"]
    bridges = [r for r in results if r["type"] == "월브릿지"]
    wconsec = [r for r in results if r["type"] == "주차연속"]
    cumuls  = [r for r in results if r["type"] == "누계"]

    gugan_sum  = sum(r["prize"] for r in gugan)
    bridge_sum = sum(r["prize"] for r in bridges)
    wcon_sum   = sum(r["prize"] for r in wconsec)
    cumul_sum  = sum(r["prize"] for r in cumuls)

    h = (
        '<div style="margin-top:8px; padding:10px; background:#fff8f0; '
        'border-radius:10px; border:1px solid #ffd4a8;">'
    )
    h += (
        f'<div style="font-weight:800;color:#d9232e;font-size:15px;margin-bottom:2px;">'
        f'💰 총 시상금: {total:,.0f}원</div>'
    )

    parts = []
    if gugan_sum > 0:  parts.append(f"주차 {gugan_sum:,.0f}")
    if bridge_sum > 0: parts.append(f"브릿지 {bridge_sum:,.0f}")
    if wcon_sum > 0:   parts.append(f"주차연속 {wcon_sum:,.0f}")
    if cumul_sum > 0:  parts.append(f"누계 {cumul_sum:,.0f}")
    if parts:
        h += f'<div style="font-size:11px;color:#888;margin-bottom:6px;">({" + ".join(parts)})</div>'

    # 주차 시상
    if gugan:
        h += '<div style="font-size:11px;color:#4e5968;font-weight:700;margin-top:4px;">📌 주차 시상</div>'
        for r in gugan:
            pz = f"{r['prize']:,.0f}원" if r["prize"] > 0 else "0원"
            h += (
                f'<div class="m-row"><span class="m-label">{r["name"]}</span>'
                f'<span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
            )
            h += _prize_detail_sub_html(r.get("prize_details", []))

    # 월 브릿지/연속가동
    if bridges:
        h += '<div style="font-size:11px;color:#d4380d;font-weight:700;margin-top:4px;">🌉 월 브릿지 / 연속가동</div>'
        for r in bridges:
            pz = f"{r['prize']:,.0f}원" if r["prize"] > 0 else "0원"
            h += (
                f'<div class="m-row"><span class="m-label">{r["name"]}</span>'
                f'<span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
            )
            lp, lc = r.get("label_prev", "전월"), r.get("label_curr", "당월")
            h += (
                f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:11px;">'
                f'· {lp} 실적</span><span class="m-val" style="font-size:11px;">{r["val_prev"]:,.0f}원</span></div>'
            )
            h += (
                f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:11px;">'
                f'· {lc} 실적</span><span class="m-val" style="font-size:11px;">{r["val_curr"]:,.0f}원</span></div>'
            )
            if r.get("shortfall", 0) > 0 and r.get("target", 0) > 0:
                h += (
                    f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:10px;color:#888;">'
                    f'🎯 목표 {r["target"]:,.0f}원까지 {r["shortfall"]:,.0f}원 부족</span>'
                    f'<span class="m-val"></span></div>'
                )

    # 주차연속가동
    if wconsec:
        h += '<div style="font-size:11px;color:#c05621;font-weight:700;margin-top:4px;">🔥 주차연속가동 (3~4주)</div>'
        for r in wconsec:
            if r.get("has_prize") and r["prize"] > 0:
                pz = f"{r['prize']:,.0f}원"
            elif r.get("has_prize"):
                pz = "0원"
            else:
                pz = "추후 확정"
            h += (
                f'<div class="m-row"><span class="m-label">{r["name"]}</span>'
                f'<span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
            )
            tier3 = f"{r['tier_3w']:,.0f}원 구간" if r.get("tier_3w", 0) > 0 else "미달성"
            h += (
                f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:11px;">'
                f'· 3주 실적 ({tier3})</span>'
                f'<span class="m-val" style="font-size:11px;">{r.get("perf_3w", 0):,.0f}원</span></div>'
            )
            if r.get("perf_4w", 0) > 0:
                h += (
                    f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:11px;">'
                    f'· 4주 실적</span>'
                    f'<span class="m-val" style="font-size:11px;">{r["perf_4w"]:,.0f}원</span></div>'
                )
            if r.get("shortfall", 0) > 0:
                h += (
                    f'<div class="m-row"><span class="m-label" style="padding-left:10px;font-size:10px;color:#888;">'
                    f'🚀 목표까지 {r["shortfall"]:,.0f}원 부족</span>'
                    f'<span class="m-val"></span></div>'
                )

    # 월 누계
    if cumuls:
        h += '<div style="font-size:11px;color:#2B6CB0;font-weight:700;margin-top:4px;">📈 월 누계</div>'
        for r in cumuls:
            pz = f"{r['prize']:,.0f}원" if r["prize"] > 0 else "0원"
            h += (
                f'<div class="m-row"><span class="m-label">{r["name"]}</span>'
                f'<span class="m-val" style="color:#d9232e;font-weight:700;">{pz}</span></div>'
            )
            h += _prize_detail_sub_html(r.get("prize_details", []))

    h += "</div>"
    return h
