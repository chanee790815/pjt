"""STEP 2: 부지 정보 — API 연동 전 구조·표시 (자동 인허가 판정 없음)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from solar_design.utils import empty_land_info, get_secret


def fetch_vworld_land_attr(lat: float, lon: float) -> tuple[dict | None, str]:
    """
    VWorld 토지특성/필지 API 연동 예정.
    1차: 키 없으면 None. 경계·PNU는 별도 WFS 연동 필요.
    """
    key = get_secret("VWORLD_API_KEY")
    if not key:
        return None, "VWorld API 키 미설정 — 토지정보 자동 취합은 2차에서 연동"
    # 실제 엔드포인트는 VWorld 문서 기준으로 2차 구현
    return None, "VWorld 토지정보 API는 2차 개발에서 연결합니다."


def merge_site_land_info(site: dict) -> dict:
    info = empty_land_info()
    road = site.get("address_road") or ""
    jibun = site.get("address_jibun") or ""
    info["소재지"] = road or jibun or "정보 없음"
    info["지번"] = jibun or "추가 확인 필요"
    lat, lon = site.get("lat"), site.get("lon")
    if lat is not None and lon is not None:
        fetched, msg = fetch_vworld_land_attr(lat, lon)
        if fetched:
            info.update(fetched)
            info["데이터_출처"] = "VWorld"
        else:
            info["데이터_출처"] = msg
    else:
        info["데이터_출처"] = "좌표 없음"
    site["land_info"] = info
    return site


def render_land_info_panel(site: dict | None) -> None:
    st.markdown('<p class="sd-panel-title">📋 부지·필지 정보</p>', unsafe_allow_html=True)
    if not site:
        st.info("부지를 검색해 목록에 추가하세요.")
        return

    if st.button("토지정보 갱신(가능 범위)", key="sd_refresh_land"):
        merge_site_land_info(site)

    info = site.get("land_info") or empty_land_info()
    rows = [
        ("소재지", info.get("소재지")),
        ("지번", info.get("지번")),
        ("지목", info.get("지목")),
        ("필지 면적(㎡)", info.get("필지_면적_m2") or "정보 없음"),
        ("용도지역", info.get("용도지역")),
        ("용도지구", info.get("용도지구")),
        ("국토계획법상 지역·지구", info.get("국토계획법_지역지구")),
        ("기타 법령 지역·지구", info.get("기타법령_지역지구")),
        ("공시지가", info.get("공시지가")),
        ("도로 접면", info.get("도로_접면")),
        ("지형·경사", info.get("지형_경사")),
    ]
    for label, val in rows:
        st.markdown(f"**{label}**  \n{val}")

    st.markdown("**법령상 검토 참고** (자동 확정 아님)")
    for line in info.get("인허가_법령상_제한") or ["(연동 전) 용도지역·농지·산지 등은 공공 API·유권해석 확인 필요"]:
        st.markdown(f"- {line}")

    st.markdown("**담당자 확인사항**")
    for line in info.get("인허가_담당자_확인") or []:
        st.markdown(f"- {line}")

    if info.get("데이터_출처"):
        st.caption(f"출처: {info['데이터_출처']}")

    if site.get("boundary_geojson"):
        st.success("필지 경계: 공인 데이터 로드됨")
    else:
        st.markdown(
            '<p class="sd-warn">⚠ 필지 경계 미표시 — 지적 WFS/API 연동 전까지 '
            "임의 경계를 그리지 않습니다.</p>",
            unsafe_allow_html=True,
        )
