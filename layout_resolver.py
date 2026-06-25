"""
layout_resolver.py — stage config + 실제 df → "두 축(주차 / 기간)" 레이아웃으로 정규화

[이 모듈이 푸는 문제]
  1) config가 참조하지만 df엔 없는 '죽은 컬럼'을 렌더 전에 제거
     (예: 주차연속가동_3주실적, 추가13회예정금_1_2주, 추가13회예정금_5주 …)
  2) 브릿지·연속가동을 '주차 축'에서 떼어내 '기간(월 페어) 축'으로 분리
  3) config에 박힌 고정 주차/월을 무시하고, 실제 값이 있는 주차/월페어만 노출
     → 5주차 데이터가 없으면 5주 칼럼이 자동으로 안 뜸

[사용]
  auto_loader.auto_load() 결과(result['config'], result['df_merged'])를 받아
  build_layout(df, config) 로 'layout' dict를 만들어 view에 넘긴다.
"""
import re
import pandas as pd

MAX_WEEK = 6


# ──────────────────────────────────────────────────────────────
# 값 판정 헬퍼
# ──────────────────────────────────────────────────────────────
def _num(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(0)


def col_exists(df, col):
    return bool(col) and col in df.columns


def col_has_value(df, col):
    """컬럼이 존재하고, 0이 아닌 값이 하나라도 있으면 True."""
    if not col_exists(df, col):
        return False
    try:
        return bool((_num(df[col]).abs() > 0).any())
    except Exception:
        # 텍스트 컬럼 등 숫자화 불가 → 비어있지 않은 셀이 있으면 값 있음으로 간주
        return bool(df[col].astype(str).str.strip().replace("nan", "").ne("").any())


def resolve_col(df, item):
    """admin_cols item의 실제 사용 컬럼(col → 없으면 fallback_col)을 반환. 둘 다 없으면 None."""
    col = item.get("col", "")
    if col_exists(df, col):
        return col
    fb = item.get("fallback_col", "")
    if col_exists(df, fb):
        return fb
    return None


# ──────────────────────────────────────────────────────────────
# 축(axis) 분류 — 이름만 보고 주차 / 기간 판정
# ──────────────────────────────────────────────────────────────
PERIOD_PAT = re.compile(r"(브릿지|연속가동)")
WEEK_PAT = re.compile(r"(\d+)\s*주")


def classify_axis(*names):
    """주어진 이름들 중 하나라도 브릿지/연속가동이면 'period', 아니면 'weekly'."""
    for n in names:
        if n and PERIOD_PAT.search(str(n)):
            return "period"
    return "weekly"


def week_of(*names):
    """이름에서 'N주'를 뽑아 주차 번호 반환. 없으면 None."""
    for n in names:
        if not n:
            continue
        m = WEEK_PAT.search(str(n))
        if m:
            return int(m.group(1))
    return None


# ──────────────────────────────────────────────────────────────
# 실제 데이터에서 활성 주차 / 기간(월 페어) 탐지
# ──────────────────────────────────────────────────────────────
def detect_active_weeks(df, max_week=MAX_WEEK):
    """실적_N주차에 값이 있는 주차 목록."""
    return [w for w in range(1, max_week + 1) if col_has_value(df, f"실적_{w}주차")]


def detect_period_tracks(df):
    """
    브릿지·연속가동 트랙을 실제 컬럼에서 탐지.
    반환: [{kind, label, cols:{prev,curr,prize,goal,short,target}}, ...]
    """
    cols = set(df.columns)
    tracks = []

    for kind in ("브릿지", "연속가동"):
        # 1) 단일 월 컬럼  예: 브릿지실적_5월 / 브릿지실적_6월
        months = sorted({
            int(m.group(1))
            for c in cols
            for m in [re.match(rf"^{kind}실적_(\d+)월$", c)]
            if m
        })
        # 인접한 (이전월, 당월) 페어만 트랙으로
        for i in range(len(months) - 1):
            prev_m, curr_m = months[i], months[i + 1]
            prev_c = f"{kind}실적_{prev_m}월"
            curr_c = f"{kind}실적_{curr_m}월"
            if not (col_has_value(df, prev_c) or col_has_value(df, curr_c)):
                continue
            tracks.append({
                "kind": kind,
                "label": f"{kind} {prev_m}→{curr_m}월",
                "cols": {
                    "prev":   prev_c,
                    "curr":   curr_c,
                    "prize":  _first_existing(df, f"{kind}시상금"),
                    "goal":   _first_existing(df, f"{kind}실적목표_{curr_m}월"),
                    "short":  _first_existing(df, f"{kind}부족금액_{curr_m}월"),
                },
            })

        # 2) 롤링 페어 컬럼  예: 브릿지실적_6_7월 (차월 브릿지 형성 중)
        for c in cols:
            m = re.match(rf"^{kind}실적_(\d+)_(\d+)월$", c)
            if not m or not col_has_value(df, c):
                continue
            a, b = int(m.group(1)), int(m.group(2))
            tracks.append({
                "kind": kind,
                "label": f"{kind} {a}→{b}월 (형성중)",
                "cols": {
                    "curr":   c,
                    "prize":  _first_existing(df, f"{kind}시상금"),
                    "goal":   _first_existing(df, f"{kind}실적목표_{a}_{b}월"),
                    "short":  _first_existing(df, f"{kind}실적부족액_{a}_{b}월",
                                                  f"{kind}부족금액_{a}_{b}월"),
                },
            })
    return tracks


def _first_existing(df, *cands):
    for c in cands:
        if col_exists(df, c):
            return c
    return None


# ──────────────────────────────────────────────────────────────
# admin_cols / prize_config 정리 (죽은 컬럼 제거 + 축 분리)
# ──────────────────────────────────────────────────────────────
def split_admin_cols(df, admin_cols, active_weeks):
    """admin_cols를 weekly/period로 가르고, 죽은 컬럼·비활성 주차는 dropped로."""
    weekly, period, dropped = [], [], []
    for item in admin_cols:
        used = resolve_col(df, item)
        disp = item.get("display_name", item.get("col", ""))
        if used is None:
            dropped.append({"display": disp, "col": item.get("col", ""),
                            "reason": "df에 컬럼 없음"})
            continue
        axis = classify_axis(item.get("col", ""), disp)
        if axis == "weekly":
            wk = week_of(disp, item.get("col", ""))
            if wk is not None and wk not in active_weeks:
                dropped.append({"display": disp, "col": used,
                                "reason": f"{wk}주차 값 없음"})
                continue
            weekly.append({**item, "_used_col": used})
        else:
            period.append({**item, "_used_col": used})
    return weekly, period, dropped


def prune_prize_config(df, prize_config, active_weeks):
    """prize_config 블록별로 죽은 prize_item 제거 + 축 분류. 살아있는 item 0개면 블록 제거."""
    weekly_blocks, period_blocks, dropped = [], [], []
    for blk in prize_config:
        name = blk.get("name", "")
        axis = classify_axis(name, blk.get("type", ""), blk.get("col_val", ""))

        kept_items = []
        for it in blk.get("prize_items", []):
            cp = it.get("col_prize", "")
            if col_exists(df, cp):
                kept_items.append(it)
            else:
                dropped.append({"block": name, "item": it.get("label", ""),
                                "col_prize": cp, "reason": "시상금 컬럼 없음"})

        # 주차 블록인데 해당 주차가 비활성이면 통째로 제외
        if axis == "weekly":
            wk = week_of(name, blk.get("col_val", ""))
            if wk is not None and wk not in active_weeks:
                dropped.append({"block": name, "item": "(블록 전체)",
                                "reason": f"{wk}주차 값 없음"})
                continue

        if not kept_items:
            # 시상 item이 하나도 안 살아남은 빈 블록 → 제거
            dropped.append({"block": name, "item": "(블록 전체)",
                            "reason": "유효 시상 item 없음"})
            continue

        new_blk = {**blk, "prize_items": kept_items, "_axis": axis}
        (weekly_blocks if axis == "weekly" else period_blocks).append(new_blk)
    return weekly_blocks, period_blocks, dropped


# ──────────────────────────────────────────────────────────────
# col_groups를 활성 주차/실재 컬럼 기준으로 재구성
# ──────────────────────────────────────────────────────────────
def rebuild_col_groups(col_groups, weekly_display, period_display):
    """원본 col_groups에서 살아남은 display만 남기고, 주차/기간으로 분리."""
    weekly_g, period_g = [], []
    wk_set, pd_set = set(weekly_display), set(period_display)
    for g in col_groups:
        cols = g.get("cols", [])
        wk_cols = [c for c in cols if c in wk_set]
        pd_cols = [c for c in cols if c in pd_set]
        if wk_cols:
            weekly_g.append({"name": g.get("name", ""), "cols": wk_cols})
        if pd_cols:
            period_g.append({"name": g.get("name", ""), "cols": pd_cols})
    return weekly_g, period_g


# ──────────────────────────────────────────────────────────────
# 메인: build_layout
# ──────────────────────────────────────────────────────────────
def build_layout(df, config):
    """
    config(auto_loader 결과) + df_merged → 두 축 레이아웃 dict.

    반환:
      {
        'active_weeks': [1,2,3,4],
        'weekly': {'admin_cols', 'col_groups', 'prize_config', 'col_order'},
        'period': {'tracks', 'admin_cols', 'col_groups', 'prize_config'},
        'dropped': {'admin_cols':[...], 'prize_items':[...]},
      }
    """
    admin_cols   = config.get("admin_cols", [])
    prize_config = config.get("prize_config", [])
    col_groups   = config.get("col_groups", [])
    col_order    = config.get("col_order", [])

    active_weeks = detect_active_weeks(df)
    period_tracks = detect_period_tracks(df)

    wk_cols, pd_cols, dropped_cols = split_admin_cols(df, admin_cols, active_weeks)
    wk_blocks, pd_blocks, dropped_items = prune_prize_config(df, prize_config, active_weeks)

    wk_display = [c.get("display_name", c.get("col", "")) for c in wk_cols]
    pd_display = [c.get("display_name", c.get("col", "")) for c in pd_cols]
    wk_groups, pd_groups = rebuild_col_groups(col_groups, wk_display, pd_display)

    # 주차 col_order: 원본 순서 유지하되 살아남은 것만 (맞춤분류 + 공통 텍스트는 weekly 쪽에)
    wk_order = [c for c in col_order if c in wk_display or c in (
        "맞춤분류", "대리점지사명", "팀장님 코드", "팀장님 이름", "전월 실적")]

    return {
        "active_weeks": active_weeks,
        "weekly": {
            "admin_cols":   wk_cols,
            "col_groups":   wk_groups,
            "prize_config": wk_blocks,
            "col_order":    wk_order,
        },
        "period": {
            "tracks":       period_tracks,
            "admin_cols":   pd_cols,
            "col_groups":   pd_groups,
            "prize_config": pd_blocks,
        },
        "dropped": {
            "admin_cols":  dropped_cols,
            "prize_items": dropped_items,
        },
    }
