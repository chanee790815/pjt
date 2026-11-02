"""STEP 3 이후: 기자재 모델 (1차는 JSON 조회·구조 검증)."""

from __future__ import annotations

import streamlit as st

from solar_design.utils import SESSION_MODULE_MODEL, load_json_data


def render_equipment_preview() -> None:
    st.markdown('<p class="sd-panel-title">⚙ 기자재 (미리보기)</p>', unsafe_allow_html=True)
    modules = [m for m in load_json_data("modules.json") if m.get("사용_여부", True)]
    inverters = [i for i in load_json_data("inverters.json") if i.get("사용_여부", True)]
    st.caption(f"모듈 {len(modules)}종 · 인버터 {len(inverters)}종 (data/*.json)")

    if modules:
        labels = [
            f"{m.get('제조사', '')} {m.get('모델명', '')} ({m.get('정격출력_Wp', '')} Wp)"
            for m in modules
        ]
        default_idx = 0
        prev = st.session_state.get(SESSION_MODULE_MODEL)
        if prev:
            for i, m in enumerate(modules):
                if m.get("모델명") == prev:
                    default_idx = i
                    break
        pick = st.selectbox("자동 배치에 사용할 모듈", labels, index=default_idx, key="sd_module_pick")
        sel = modules[labels.index(pick)]
        st.session_state[SESSION_MODULE_MODEL] = sel.get("모델명", "")
        st.markdown(
            f"**{sel.get('제조사', '')}** {sel.get('모델명', '')} · "
            f"{sel.get('가로_mm', '?')}×{sel.get('세로_mm', '?')} mm"
        )
        st.caption("「자동 배치·용량」에서 배치 계산 시 위 모듈이 적용됩니다.")
    else:
        st.warning("modules.json에 사용 가능한 모듈이 없습니다.")

    if inverters:
        with st.expander("인버터 목록 (참고)", expanded=False):
            for inv in inverters[:5]:
                st.markdown(
                    f"- **{inv.get('제조사', '')}** {inv.get('모델명', '')} "
                    f"{inv.get('정격용량_kW', '')} kW"
                )
    st.info("관리자 등록 화면은 3차 개발 예정.")


def placeholder_not_implemented(title: str) -> None:
    st.warning(f"「{title}」 기능은 이번 1차 범위에 포함되지 않았습니다.")
