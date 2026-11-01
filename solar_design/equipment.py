"""STEP 3 이후: 기자재 모델 (1차는 JSON 조회·구조 검증)."""

from __future__ import annotations

import streamlit as st

from solar_design.utils import load_json_data


def render_equipment_preview() -> None:
    st.markdown('<p class="sd-panel-title">⚙ 기자재 (미리보기)</p>', unsafe_allow_html=True)
    modules = load_json_data("modules.json")
    inverters = load_json_data("inverters.json")
    st.caption(f"모듈 {len(modules)}종 · 인버터 {len(inverters)}종 (data/*.json)")
    if modules:
        m0 = modules[0]
        st.markdown(
            f"예: **{m0.get('제조사','')}** {m0.get('모델명','')} "
            f"{m0.get('정격출력_Wp','')} Wp"
        )
    st.info("관리자 등록 화면은 3차 개발 예정.")


def placeholder_not_implemented(title: str) -> None:
    st.warning(f"「{title}」 기능은 이번 1차 범위에 포함되지 않았습니다.")
