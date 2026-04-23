"""
render.py — HTML 테이블 렌더링 모듈

매니저 화면에서 사용하는 반응형 HTML 테이블 (데스크탑: 표, 모바일: 카드)
+ 카톡 복사 + 시상금 상세 조회 기능을 한 HTML 문자열로 생성한다.
"""
import uuid
import base64 as _b64
import json
import pandas as pd
import streamlit as st

from prize_utils import build_prize_card_html, format_prize_clip_text


def render_html_table(df, col_groups=None, prize_data_map=None):
    """DataFrame을 틀 고정 + 그룹 헤더 + 정렬 + 반응형 HTML 테이블로 변환"""
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

    GROUP_COLORS = [
        '#2B6CB0', '#2F855A', '#9B2C2C', '#6B46C1',
        '#B7791F', '#2C7A7B', '#C05621', '#702459',
    ]

    col_to_group = {}
    group_color_map = {}
    for gi, grp in enumerate(col_groups):
        color = GROUP_COLORS[gi % len(GROUP_COLORS)]
        group_color_map[grp['name']] = color
        for c in grp['cols']:
            col_to_group[c] = grp['name']

    columns = list(df.columns)

    group_mid = {}
    for gname in set(col_to_group.values()):
        indices = [i for i, c in enumerate(columns) if col_to_group.get(c) == gname]
        if indices:
            group_mid[gname] = indices[len(indices) // 2]

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
        if i >= freeze_count: return ""
        c = "col-freeze"
        if i == freeze_count - 1: c += " col-freeze-last"
        return c

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
    .perf-table thead th {{
        background-color: #4e5968; color: #fff; font-weight: 700;
        text-align: center; border: 1px solid #3d4654;
        position: sticky; z-index: 2; white-space: nowrap;
    }}
    .perf-table .rg th {{ top: 0; height: {grp_h}px; padding: 4px 6px; cursor: default; }}
    .perf-table .rg .ge {{ background: #4e5968; border-bottom-color: #4e5968; }}
    .perf-table .rg .gc {{ border-left: none; border-right: none; }}
    .perf-table .rg .gc-first {{ border-left: 1px solid #3d4654; border-right: none; }}
    .perf-table .rg .gc-last {{ border-left: none; border-right: 1px solid #3d4654; }}
    .perf-table .rg .gc-solo {{ border-left: 1px solid #3d4654; border-right: 1px solid #3d4654; }}
    .perf-table .rc th .grp-bar {{
        display: none;
        height: 4px; border-radius: 2px;
        margin: 0 auto 3px auto; width: 80%;
    }}
    .perf-table .rc th {{
        top: {grp_h if has_groups else 0}px; height: {col_h}px;
        padding: 6px 10px; cursor: pointer; user-select: none;
    }}
    .perf-table thead th:hover {{ background-color: #3d4654; }}
    .sa {{ margin-left: 3px; font-size: 10px; opacity: 0.5; }}
    .sa.active {{ opacity: 1; }}
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

    @media (max-width: 1200px) {{
        .perf-table {{ font-size: {max(10, 13 - num_cols // 3)}px; }}
        .perf-table thead th, .perf-table tbody td {{ padding: 5px 6px; }}
    }}
    @media (max-width: 768px) {{
        .perf-table-wrap {{ max-height: 75vh; border-radius: 8px; }}
        .perf-table {{ font-size: {mob_font}px; }}
        .perf-table thead th {{ padding: 4px 5px; }}
        .perf-table tbody td {{ padding: 4px 5px; }}
        .perf-table .rg {{ display: none; }}
        .perf-table .rc th {{ top: 0 !important; padding: 5px 5px 4px 5px; }}
        .perf-table .rc th .grp-bar {{ display: block; }}
        .sa {{ font-size: 8px; margin-left: 1px; }}
        .col-freeze-last {{ box-shadow: 2px 0 3px rgba(0,0,0,0.12); }}
    }}
    @media (max-width: 480px) {{
        .perf-table {{ font-size: {max(8, mob_font - 1)}px; }}
        .perf-table thead th, .perf-table tbody td {{ padding: 3px 3px; }}
        .perf-table .rc th {{ padding: 4px 3px 3px 3px; }}
        .perf-table .rc th .grp-bar {{ height: 3px; margin-bottom: 2px; }}
    }}

    .desktop-view {{ display: block; }}
    .mobile-view {{ display: none; }}

    @media (max-width: 768px) {{
        .desktop-view {{ display: none !important; }}
        .mobile-view {{ display: block !important; }}
    }}

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

    html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    html += '<div class="desktop-view">'
    html += f'<div class="perf-table-wrap" id="wrap_{table_id}"><table class="perf-table" id="{table_id}"><thead>'

    if has_groups:
        html += '<tr class="rg">'
        for i, col in enumerate(columns):
            gname, is_first, is_last, is_text = group_info[i]
            f_cls = fc(i)
            if gname is None:
                html += f'<th class="ge {f_cls}" data-col="{i}"></th>'
            else:
                gc = group_color_map.get(gname, '#364152')
                if is_first and is_last: b_cls = "gc-solo"
                elif is_first: b_cls = "gc-first"
                elif is_last: b_cls = "gc-last"
                else: b_cls = "gc"
                text = gname if is_text else ""
                html += f'<th class="{b_cls} {f_cls}" style="background:{gc};" data-col="{i}">{text}</th>'
        html += '<th class="ge" data-col="-1"></th>'
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
    html += '</div>'

    # ══════════════════════════════════════════
    # 📋 각 행별 클립보드 텍스트 생성
    # ══════════════════════════════════════════
    columns = list(df.columns)

    name_col = None
    name_keywords = ['설계사명', '성명', '이름', '팀장명']
    for c in columns:
        if any(kw in c for kw in name_keywords):
            name_col = c
            break

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

    col_to_grp = {}
    for grp in col_groups:
        for c in grp['cols']:
            col_to_grp[c] = grp['name']

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
        name_parts = []
        for c in clip_name_cols:
            v = str(row[c]) if not pd.isna(row[c]) else ''
            if v.strip() and v != '0':
                name_parts.append(v.strip())
        person_line = ' '.join(name_parts)
        if person_line and not person_line.endswith('님'):
            person_line += ' 팀장님'

        lines = []
        if data_date:
            lines.append(f"📅 {data_date} 기준")
        lines.append(f"👤 {person_line}")

        normal_lines = []
        goal_lines = []
        for c in data_cols:
            if '코드' in c or '번호' in c:
                continue
            val = str(row[c]) if not pd.isna(row[c]) else ''
            if not val.strip() or val == '0':
                continue

            if '부족금액' in c:
                goal_lines.append(f"  🔴 {c}: {val}")
            elif '다음목표' in c:
                goal_lines.append(f"  🎯 {c}: {val}")
            else:
                normal_lines.append(f"  ▸ {c}: {val}")

        if normal_lines:
            lines.append("")
            lines.extend(normal_lines)
        if goal_lines:
            lines.append("")
            lines.extend(goal_lines)

        if prize_data_map and row_idx in prize_data_map:
            p_results, p_total = prize_data_map[row_idx]
            prize_text = format_prize_clip_text(p_results, p_total)
            if prize_text:
                lines.append(prize_text)

        if clip_footer:
            lines.append("")
            lines.append(clip_footer)

        clip_texts.append('\n'.join(lines))

    clip_json_bytes = json.dumps(clip_texts, ensure_ascii=False).encode('utf-8')
    clip_b64 = _b64.b64encode(clip_json_bytes).decode('ascii')

    # 💰 시상금 HTML 데이터 (행별)
    prize_htmls = []
    for row_idx in range(len(df)):
        if prize_data_map and row_idx in prize_data_map:
            p_results, p_total = prize_data_map[row_idx]
            p_gugan   = [r for r in p_results if r['type'] == '구간']
            p_bridge  = [r for r in p_results if r['type'] == '월브릿지']
            p_wconsec = [r for r in p_results if r['type'] == '주차연속']
            p_cumul   = [r for r in p_results if r['category'] == 'cumulative']

            p_gugan_sum  = sum(r['prize'] for r in p_gugan)
            p_bridge_sum = sum(r['prize'] for r in p_bridge)
            p_wcon_sum   = sum(r['prize'] for r in p_wconsec)
            p_cumul_sum  = sum(r['prize'] for r in p_cumul)

            ph = f'<div style="padding:5px;">'
            ph += f'<div style="font-weight:800;color:#d9232e;font-size:18px;margin-bottom:4px;">💰 총 시상금: {p_total:,.0f}원</div>'

            parts = []
            if p_gugan_sum > 0:  parts.append(f"주차 {p_gugan_sum:,.0f}")
            if p_bridge_sum > 0: parts.append(f"브릿지 {p_bridge_sum:,.0f}")
            if p_wcon_sum > 0:   parts.append(f"주차연속 {p_wcon_sum:,.0f}")
            if p_cumul_sum > 0:  parts.append(f"누계 {p_cumul_sum:,.0f}")
            if parts:
                ph += f'<div style="color:#888;font-size:13px;margin-bottom:12px;">({" + ".join(parts)})</div>'

            # 주차 시상
            if p_gugan:
                ph += '<div style="font-size:12px;color:#4e5968;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">📌 주차 시상</div>'
                for r in p_gugan:
                    pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
                    ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#555;">{r["name"]}</span><span style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                    if len(r.get('prize_details', [])) > 1:
                        for d in r.get('prize_details', []):
                            ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#aaa;font-size:11px;">· {d["label"]}</span><span style="color:#aaa;font-size:11px;">{d["amount"]:,.0f}원</span></div>'

            # 월 브릿지 / 연속가동
            if p_bridge:
                ph += '<div style="font-size:12px;color:#d4380d;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">🌉 월 브릿지 / 연속가동</div>'
                for r in p_bridge:
                    pz = f"{r['prize']:,.0f}원" if r['prize'] > 0 else "0원"
                    lp, lc = r.get('label_prev', '전월'), r.get('label_curr', '당월')
                    ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#555;">{r["name"]}</span><span style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                    ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#888;font-size:11px;">· {lp} 실적</span><span style="color:#888;font-size:11px;">{r.get("val_prev",0):,.0f}원</span></div>'
                    ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#888;font-size:11px;">· {lc} 실적</span><span style="color:#888;font-size:11px;">{r.get("val_curr",0):,.0f}원</span></div>'
                    if r.get('shortfall', 0) > 0 and r.get('target', 0) > 0:
                        ph += f'<div style="padding:2px 0 2px 8px;font-size:10px;color:#888;">🎯 목표 {r["target"]:,.0f}원까지 {r["shortfall"]:,.0f}원 부족</div>'

            # 주차연속가동 (3~4주)
            if p_wconsec:
                ph += '<div style="font-size:12px;color:#c05621;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">🔥 주차연속가동 (3~4주)</div>'
                for r in p_wconsec:
                    if r.get('has_prize') and r['prize'] > 0:
                        pz = f"{r['prize']:,.0f}원"
                    elif r.get('has_prize'):
                        pz = "0원"
                    else:
                        pz = "추후 확정"
                    tier3 = f"{r.get('tier_3w',0):,.0f}원 구간" if r.get('tier_3w', 0) > 0 else "미달성"
                    ph += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#555;">{r["name"]}</span><span style="color:#d9232e;font-weight:700;">{pz}</span></div>'
                    ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#888;font-size:11px;">· 3주 실적 ({tier3})</span><span style="color:#888;font-size:11px;">{r.get("perf_3w",0):,.0f}원</span></div>'
                    if r.get('perf_4w', 0) > 0:
                        ph += f'<div style="display:flex;justify-content:space-between;padding:2px 0 2px 12px;"><span style="color:#888;font-size:11px;">· 4주 실적</span><span style="color:#888;font-size:11px;">{r["perf_4w"]:,.0f}원</span></div>'
                    if r.get('shortfall', 0) > 0:
                        ph += f'<div style="padding:2px 0 2px 8px;font-size:10px;color:#888;">🚀 목표까지 {r["shortfall"]:,.0f}원 부족</div>'

            # 월 누계
            if p_cumul:
                ph += '<div style="font-size:12px;color:#2B6CB0;font-weight:700;margin:8px 0 4px;border-bottom:1px solid #eee;padding-bottom:4px;">📈 월 누계</div>'
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
        name_parts_card = []
        for c in clip_name_cols:
            v = str(row[c]) if not pd.isna(row[c]) else ''
            if v.strip() and v != '0':
                name_parts_card.append(v.strip())
        person_card = ' '.join(name_parts_card) if name_parts_card else ''

        name_val = str(row.get(name_col, '')) if name_col else (person_card or '')
        num_val = str(row.get('순번', row_idx + 1)) if '순번' in columns else str(row_idx + 1)

        html += f'<div class="m-card">'

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

        html += '<div class="m-card-body">'

        html += f'<div class="m-copy-wrap"><button class="m-copy-btn" onclick="copyClip({row_idx}, this, event)">📋 카톡 보내기</button>'
        if prize_data_map and row_idx in prize_data_map:
            html += f'<button class="m-copy-btn" onclick="showPrize({row_idx}, event)" style="background:#fff3e0;color:#d9232e;border:1px solid #ffd4a8;margin-top:4px;">💰 시상금 상세 조회</button>'
        html += '</div>'

        for c in clip_name_cols:
            if c == name_col:
                continue
            val = str(row[c]) if not pd.isna(row[c]) else ''
            if val.strip() and val != '0':
                html += f'<div class="m-row"><span class="m-label">{c}</span><span class="m-val">{val}</span></div>'

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

        if prize_data_map and row_idx in prize_data_map:
            p_results, p_total = prize_data_map[row_idx]
            html += build_prize_card_html(p_results, p_total)

        html += '</div></div>'

    html += '</div>'

    # ── 복사 팝업 오버레이 ──
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

    # 데이터를 hidden div에 저장 (script 태그 사용 시 </script> 충돌 방지)
    html += f'<div id="__clipB64" style="display:none">{clip_b64}</div>\n'
    html += f'<div id="__prizeB64" style="display:none">{prize_b64}</div>\n'

    html += f"""
    <script>
    var FC_DESKTOP = {freeze_count};
    var FC = FC_DESKTOP;
    var clipData = [];
    var prizeHtml = [];
    var _jsOk = false;

    function isMobile() {{ return window.innerWidth <= 768; }}

    function _loadData() {{
        try {{
            var ce = document.getElementById('__clipB64');
            var pe = document.getElementById('__prizeB64');
            if (!ce || !pe) {{ console.error('Data elements not found'); return; }}
            clipData = JSON.parse(_b64dec(ce.textContent.trim()));
            prizeHtml = JSON.parse(_b64dec(pe.textContent.trim()));
            _jsOk = true;
        }} catch(e) {{
            console.error('Data load error:', e);
            _jsOk = false;
        }}
    }}
    function _b64dec(b64) {{
        try {{
            var bin = atob(b64);
            var bytes = new Uint8Array(bin.length);
            for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
            return new TextDecoder('utf-8').decode(bytes);
        }} catch(e) {{
            return decodeURIComponent(escape(atob(b64)));
        }}
    }}

    function copyClip(idx, btn, evt) {{
        evt.stopPropagation();
        if (!_jsOk) {{ alert('데이터를 불러오지 못했습니다. 새로고침 해주세요.'); return; }}
        var text = clipData[idx];
        if (!text) {{ alert('복사할 내용이 없습니다.'); return; }}
        if (isMobile() && navigator.share) {{
            navigator.share({{ text: text }}).then(function() {{
                _showBtn(btn, true);
            }}).catch(function() {{
                _showOverlay(text);
            }});
            return;
        }}
        _showOverlay(text);
    }}
    function _showOverlay(text) {{
        var ov = document.getElementById('clip-overlay');
        var ta = document.getElementById('clip-ta');
        ta.value = text;
        ov.style.display = 'flex';
        setTimeout(function() {{ ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length); }}, 100);
    }}
    function doCopyOverlay() {{
        var ta = document.getElementById('clip-ta');
        var text = ta.value;
        if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function() {{
                _overlayDone(true);
            }}).catch(function() {{
                _tryCmdCopy(ta, text);
            }});
            return;
        }}
        _tryCmdCopy(ta, text);
    }}
    function _tryCmdCopy(ta, text) {{
        ta.readOnly = false;
        ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length);
        var ok = false;
        try {{ ok = document.execCommand('copy'); }} catch(e) {{}}
        if (ok) {{ _overlayDone(true); }}
        else {{ _overlayDone(false); ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length); }}
    }}
    function _overlayDone(ok) {{
        var btn = document.getElementById('clip-copy-btn');
        if (ok) {{
            btn.textContent = '✅ 복사 완료!';
            btn.style.background = '#22C55E'; btn.style.color = '#fff';
            setTimeout(function() {{
                document.getElementById('clip-overlay').style.display = 'none';
                btn.textContent = '📋 복사하기';
                btn.style.background = '#FEE500'; btn.style.color = '#3C1E1E';
            }}, 1200);
        }} else {{
            btn.textContent = '⚠️ Ctrl+C로 직접 복사하세요';
            btn.style.background = '#f59e0b'; btn.style.color = '#fff';
        }}
    }}
    function _showBtn(btn, ok) {{
        var orig = btn.innerHTML;
        btn.classList.add('copied');
        btn.innerHTML = '✅ 복사 완료!';
        setTimeout(function() {{ btn.classList.remove('copied'); btn.innerHTML = orig; }}, 1500);
    }}

    function showPrize(idx, evt) {{
        if (evt) evt.stopPropagation();
        if (!_jsOk) {{ alert('데이터를 불러오지 못했습니다. 새로고침 해주세요.'); return; }}
        var h = prizeHtml[idx];
        if (!h) {{ alert('시상금 데이터가 없습니다.'); return; }}
        document.getElementById('prize-content').innerHTML = h;
        document.getElementById('prize-overlay').style.display = 'flex';
    }}

    function applyFreeze() {{
        var t = document.getElementById("{table_id}");
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

    var ss = {{}};
    function sortTable(th) {{
        var t = document.getElementById("{table_id}");
        var tb = t.querySelector("tbody");
        var rows = Array.from(tb.querySelectorAll("tr"));
        var ci = parseInt(th.getAttribute("data-col"));
        if (isNaN(ci)) return;
        var asc = ss[ci] !== true; ss = {{}}; ss[ci] = asc;
        rows.sort(function(a, b) {{
            var aT = (a.cells[ci] ? a.cells[ci].textContent : '').trim();
            var bT = (b.cells[ci] ? b.cells[ci].textContent : '').trim();
            var aN = parseFloat(aT.replace(/,/g,"")), bN = parseFloat(bT.replace(/,/g,""));
            if (aT === "" && bT === "") return 0;
            if (aT === "") return 1; if (bT === "") return -1;
            if (!isNaN(aN) && !isNaN(bN)) return asc ? aN - bN : bN - aN;
            return asc ? aT.localeCompare(bT,'ko') : bT.localeCompare(aT,'ko');
        }});
        rows.forEach(function(r) {{ tb.appendChild(r); }});
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

    window.addEventListener('load', function() {{
        _loadData();
        applyFreeze();
        autoResize();
    }});
    window.addEventListener('resize', function() {{ applyFreeze(); autoResize(); }});
    </script>
    """
    return html
