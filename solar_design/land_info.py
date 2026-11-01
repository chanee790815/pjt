"""STEP 2: 부지 정보 — VWorld 연속지적도·역지오코딩."""

from __future__ import annotations

import streamlit as st

from solar_design.utils import empty_land_info
from solar_design.vworld_client import get_parcel_at_point, reverse_parcel_address


def fetch_vworld_land_attr(lat: float, lon: float) -> tuple[dict | None, str, dict | None]:
    """
    Returns: (land_info_updates, message, extra_site_fields)
    extra_site_fields: boundary_geojson, pnu 등 site에 병합할 값
    """
    parcel, err = get_parcel_at_point(lon, lat)
    extra: dict = {}
    if not parcel:
        rev, _ = reverse_parcel_address(lon, lat)
        msg = err or "VWorld 필지 조회 실패"
        if rev:
            return {"소재지": rev, "지번": rev}, msg, extra
        return None, msg, extra

    props = parcel.get("properties") or {}
    jibun = parcel.get("jibun") or props.get("addr") or ""
    addr = parcel.get("addr") or jibun
    area = parcel.get("area_m2")
    jiga = props.get("jiga")
    gosi = ""
    if props.get("gosi_year") and props.get("gosi_month"):
        gosi = f"{props['gosi_year']}-{props['gosi_month']}"
    jiga_txt = "정보 없음"
    if jiga not in (None, ""):
        try:
            jiga_txt = f"{int(float(jiga)):,}원/㎡ ({gosi})" if gosi else f"{int(float(jiga)):,}원/㎡"
        except (TypeError, ValueError):
            jiga_txt = str(jiga)

    updates = {
        "소재지": addr or "정보 없음",
        "지번": jibun or "추가 확인 필요",
        "지목": "정보 없음",
        "필지_면적_m2": round(area, 1) if area else None,
        "용도지역": "정보 없음",
        "용도지구": "정보 없음",
        "국토계획법_지역지구": "정보 없음",
        "기타법령_지역지구": "정보 없음",
        "공시지가": jiga_txt,
        "데이터_출처": "VWorld LP_PA_CBND_BUBUN",
    }
    extra["boundary_geojson"] = parcel.get("geojson")
    extra["boundary_source"] = "VWorld LP_PA_CBND_BUBUN"
    extra["pnu"] = parcel.get("pnu") or ""
    return updates, "OK", extra


def merge_site_land_info(site: dict) -> dict:
    info = empty_land_info()
    road = site.get("address_road") or ""
    jibun = site.get("address_jibun") or ""
    info["소재지"] = road or jibun or "정보 없음"
    info["지번"] = jibun or "추가 확인 필요"
    lat, lon = site.get("lat"), site.get("lon")
    if lat is not None and lon is not None:
        fetched, msg, extra = fetch_vworld_land_attr(float(lat), float(lon))
        if fetched:
            info.update(fetched)
        if extra.get("boundary_geojson"):
            site["boundary_geojson"] = extra["boundary_geojson"]
            site["boundary_source"] = extra.get("boundary_source", "")
            site["pnu"] = extra.get("pnu", "")
        if msg != "OK":
            info["데이터_출처"] = msg if not fetched else info.get("데이터_출처", "")
        elif not info.get("데이터_출처"):
            info["데이터_출처"] = "VWorld"
    else:
        info["데이터_출처"] = "좌표 없음 — Kakao REST 키로 주소→좌표 후 갱신"
    site["land_info"] = info
    return site


def render_land_info_panel(site: dict | None) -> None:
    st.markdown('<p class="sd-panel-title">📋 부지·필지 정보</p>', unsafe_allow_html=True)
    if not site:
        st.info("부지를 검색해 목록에 추가하세요.")
        return

    if st.button("토지정보·필지경계 갱신", key="sd_refresh_land"):
        merge_site_land_info(site)
        st.rerun()

    info = site.get("land_info") or empty_land_info()
    rows = [
        ("소재지", info.get("소재지")),
        ("지번", info.get("지번")),
        ("PNU", site.get("pnu") or "—"),
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
        st.success("필지 경계: VWorld 지적 데이터 로드됨 (지도에 표시)")
    else:
        st.markdown(
            '<p class="sd-warn">⚠ 필지 경계 없음 — 정확한 좌표(Kakao) 후 '
            "「토지정보·필지경계 갱신」을 누르세요.</p>",
            unsafe_allow_html=True,
        )
