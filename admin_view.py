"""
admin_view.py — 새 관리자 뷰 (자동 로드 상태 + stage 오버라이드)

기존 관리자 섹션 1~9번 (파일 업로드, 표시 항목 관리, 시상금 설정 등)을
모두 제거하고, 자동 감지된 상태를 보여주는 "읽기 전용 + 오버라이드" 화면.
"""
import os
import pickle
import streamlit as st
import auto_loader as al

ADMIN_PASSWORD = "wolf7998"  # 필요 시 변경


def _do_admin_auth():
    """관리자 로그인 처리. 통과하지 않으면 st.stop()."""
    if st.session_state.get('admin_authenticated', False):
        return
    with st.form("admin_login_form_v2"):
        pw = st.text_input("🔒 관리자 비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if pw == ADMIN_PASSWORD:
                st.session_state['admin_authenticated'] = True
                st.rerun()
            else:
                st.error("❌ 비밀번호가 일치하지 않습니다.")
    st.stop()


def _apply_autoload_result(result):
    """auto_load() 결과를 session_state에 주입."""
    st.session_state['df_merged'] = result['df_merged']
    for k, v in result['config'].items():
        st.session_state[k] = v
    st.session_state['_autoload_info'] = {
        'detected_stage': result['detected_stage'],
        'current_month':  result['current_month'],
        'files':          result['files'],
    }


def render_admin_view():
    """관리자 상태 화면 메인 렌더링."""
    st.title("⚙️ 관리자 상태 화면 (자동 모드)")
    _do_admin_auth()

    al_info = st.session_state.get('_autoload_info', {})

    # ─────────────────────────────────────────────────
    # 1. 자동 로드 상태
    # ─────────────────────────────────────────────────
    st.header("1. 📂 자동 로드 상태")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("데이터 기준일", st.session_state.get('data_date', '-'))
    with c2:
        cm = al_info.get('current_month', '-')
        st.metric("감지된 월", f"{cm}월" if isinstance(cm, int) else str(cm))
    with c3:
        stage = al_info.get('detected_stage', '-')
        override = st.session_state.get('_stage_override')
        if override and override != stage:
            st.metric("적용 Stage", f"{override}", delta=f"(자동: {stage})")
        else:
            st.metric("적용 Stage", stage)

    st.markdown("**로드된 파일:**")
    files = al_info.get('files', {}) or {}
    if not files:
        st.warning("파일 정보가 없습니다.")
    else:
        for key, fp in files.items():
            fname = os.path.basename(fp) if fp else '(없음)'
            st.markdown(f"- `{key}` → `{fname}`")

    df = st.session_state.get('df_merged')
    if df is not None and hasattr(df, 'shape'):
        n_rows = len(df)
        n_cols = len(df.columns)
        st.caption(f"병합 결과: **{n_rows:,}**행 × **{n_cols}**열")

    # ─────────────────────────────────────────────────
    # 2. Stage 수동 오버라이드
    # ─────────────────────────────────────────────────
    st.header("2. 🎛️ Stage 수동 오버라이드")
    st.caption("자동 감지가 틀렸을 때만 사용합니다. 오버라이드는 세션 중에만 유지되며, "
               "앱을 새로고침하면 다시 자동 감지로 돌아갑니다.")

    available = al.list_available_stages()
    options = ['(자동 감지 사용)'] + available

    current_override = st.session_state.get('_stage_override', '')
    default_idx = 0
    if current_override and current_override in options:
        default_idx = options.index(current_override)

    selected = st.selectbox("Stage 선택", options, index=default_idx, key="stage_override_select")

    if st.button("🔄 Stage 재적용", type="primary"):
        force = None if selected == '(자동 감지 사용)' else selected
        if force:
            st.session_state['_stage_override'] = force
        else:
            st.session_state.pop('_stage_override', None)

        with st.spinner("다시 로드 중..."):
            result = al.auto_load(force_stage=force)
        if 'error' in result:
            st.error(f"❌ {result['error']}")
        else:
            _apply_autoload_result(result)
            st.success(f"✅ '{selected}' 적용 완료")
            st.rerun()

    # ─────────────────────────────────────────────────
    # 3. 현재 적용된 설정 요약 (읽기 전용)
    # ─────────────────────────────────────────────────
    st.header("3. 📋 현재 적용된 설정 요약")
    st.caption("설정 수정은 `config/base.json` 또는 `config/stages/<stage>.json` 파일을 직접 편집 후 git push.")

    with st.expander(f"📄 표시 항목 ({len(st.session_state.get('admin_cols', []))}개)", expanded=False):
        for item in st.session_state.get('admin_cols', []):
            orig = item.get('col', '')
            disp = item.get('display_name', orig)
            fb = item.get('fallback_col', '')
            fb_text = f" (대체: `{fb}`)" if fb else ""
            st.markdown(f"- `{orig}` → **[{disp}]**{fb_text}")

    with st.expander(f"🎯 목표 구간 ({len(st.session_state.get('admin_goals', []))}개)", expanded=False):
        goals = st.session_state.get('admin_goals', [])
        if goals:
            for g in goals:
                t = g.get('target_col', '')
                tiers = g.get('tiers', [])
                tiers_disp = [f"{int(x)//10000}만" if x % 10000 == 0 else f"{x:,.0f}" for x in tiers]
                st.markdown(f"- **{t}**: {', '.join(tiers_disp)}")
        else:
            st.caption("(설정 없음)")

    with st.expander(f"🏷️ 맞춤 분류 ({len(st.session_state.get('admin_categories', []))}개)", expanded=False):
        for c in st.session_state.get('admin_categories', []):
            conds = c.get('conditions', [])
            cond_strs = [f"`{x.get('col','')}` {x.get('cond','')}" for x in conds]
            st.markdown(f"- **[{c.get('name','')}]** ← {' AND '.join(cond_strs)}")

    with st.expander(f"📋 화면 표시 순서 ({len(st.session_state.get('col_order', []))}개)", expanded=False):
        for i, c in enumerate(st.session_state.get('col_order', []), 1):
            st.markdown(f"{i}. {c}")

    with st.expander(f"📊 그룹 헤더 ({len(st.session_state.get('col_groups', []))}개)", expanded=False):
        for g in st.session_state.get('col_groups', []):
            st.markdown(f"- **[{g.get('name','')}]** : {', '.join(g.get('cols', []))}")

    p_cfgs = st.session_state.get('prize_config', [])
    w_cnt = sum(1 for c in p_cfgs if c.get('category') == 'weekly')
    c_cnt = sum(1 for c in p_cfgs if c.get('category') == 'cumulative')
    with st.expander(
        f"💰 시상금 시책 ({len(p_cfgs)}개: 주차/브릿지 {w_cnt} · 누계 {c_cnt})",
        expanded=False
    ):
        for i, p in enumerate(p_cfgs, 1):
            icon = '📌' if p.get('category') == 'weekly' else '📈'
            st.markdown(f"{icon} [{i}] **{p.get('name','')}** ({p.get('type','')})")

    with st.expander("📝 카톡 하단 인사말", expanded=False):
        st.code(st.session_state.get('clip_footer', ''), language=None)

    # ─────────────────────────────────────────────────
    # 4. 설정 백업 다운로드
    # ─────────────────────────────────────────────────
    st.header("4. 💾 현재 설정 백업")
    st.caption("현재 적용된 설정을 pkl로 내려받아 보관합니다.")

    cfg_keys = [
        'manager_col', 'manager_col2', 'manager_name_col',
        'merge_key1_col', 'merge_key2_col', 'merge_key3_col',
        'admin_cols', 'admin_goals', 'admin_categories',
        'col_order', 'col_groups', 'prize_config',
        'clip_footer', 'data_date',
    ]
    cfg_dump = {k: st.session_state.get(k) for k in cfg_keys}

    try:
        pkl_bytes = pickle.dumps(cfg_dump)
        fname_date = str(st.session_state.get('data_date', '')).replace('.', '')
        st.download_button(
            "⬇️ 백업 pkl 다운로드",
            pkl_bytes,
            file_name=f"meritz_config_backup_{fname_date}.pkl",
            mime="application/octet-stream",
        )
    except Exception as e:
        st.error(f"백업 생성 실패: {e}")
