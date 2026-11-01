"""STEP 2: 부지 정보 — VWorld + 인허가 검토 참고."""

from __future__ import annotations

import streamlit as st

from solar_design.permit_review import enrich_permit_review
from solar_design.utils import empty_land_info
from solar_design.vworld_client import (
    get_land_attrs_at_point,
    get_land_use_at_point,
    get_parcel_at_point,
    reverse_parcel_address,
)


def fetch_vworld_land_attr(lat: float, lon: float) -> tuple[dict | None, str, dict | None]:
    """
    Returns: (land_info_updates, message, extra_site_fields)
    """
    notes: list[str] = []
    parcel, err = get_parcel_at_point(lon, lat)
    extra: dict = {}

    if not parcel:
        rev, _ = reverse_parcel_address(lon, lat)
        msg = err or "VWorld 필지 조회 실패"
        base = {"소재지": rev or "정보 없음", "지번": rev or "추가 확인 필요"} if rev else None
        if base:
            base = enrich_permit_review({**empty_land_info(), **base})
        return base, msg, extra

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

    jimok = "정보 없음"
    lnd, _ = get_land_attrs_at_point(lon, lat)
    if lnd and lnd.get("지목"):
        jimok = lnd["지목"]
        notes.append("LT_C_LNDPARCEL")
    else:
        notes.append("지목: LT_C_LNDPARCEL 미조회")

    yongdo, yongdo_gu = "정보 없음", "정보 없음"
    lu, _ = get_land_use_at_point(lon, lat)
    if lu:
        yongdo = lu.get("용도지역") or yongdo
        yongdo_gu = lu.get("용도지구") or yongdo_gu
        notes.append("용도지역 레이어")
    else:
        notes.append("용도지역: 추가 레이어 연동 예정")

    updates = {
        "소재지": addr or "정보 없음",
        "지번": jibun or "추가 확인 필요",
        "지목": jimok,
        "필지_면적_m2": round(area, 1) if area else None,
        "용도지역": yongdo,
        "용도지구": yongdo_gu,
        "국토계획법_지역지구": yongdo_gu if yongdo_gu != "정보 없음" else "정보 없음",
        "기타법령_지역지구": "정보 없음",
        "공시지가": jiga_txt,
        "데이터_출처": "VWorld (" + ", ".join(notes) + ")",
    }
    enrich_permit_review(updates)

    extra["boundary_geojson"] = parcel.get("geojson")
    extra["boundary_source"] = "VWorld LP_PA_CBND_BUBUN"
    extra["pnu"] = parcel.get("pnu") or ""
    return updates, "OK", extra


def merge_site_land_info(site: dict) -> tuple[dict, str | None]:
    """site 갱신 후 (site, 오류메시지)"""
    info = empty_land_info()
    road = site.get("address_road") or ""
    jibun = site.get("address_jibun") or ""
    info["소재지"] = road or jibun or "정보 없음"
    info["지번"] = jibun or "추가 확인 필요"
    err_out = None
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
            err_out = msg
            if not fetched or info.get("데이터_출처", "").startswith("VWorld"):
                pass
            info["데이터_출처"] = msg if msg != "OK" else info.get("데이터_출처", "")
        if msg != "OK" and fetched:
            info["데이터_출처"] = (info.get("데이터_출처") or "") + f" / 참고: {msg}"
        elif msg == "OK" and not info.get("데이터_출처"):
            info["데이터_출처"] = "VWorld"
        if not fetched and msg != "OK":
            enrich_permit_review(info)
    else:
        info["데이터_출처"] = "좌표 없음"
        enrich_permit_review(info)
    site["land_info"] = info
    return site, err_out


def render_land_info_panel(site: dict | None) -> None:
    st.markdown('<p class="sd-panel-title">📋 부지·필지 정보</p>', unsafe_allow_html=True)
    if not site:
        st.info("부지를 검색해 목록에 추가하세요.")
        return

    if st.button("토지정보·필지경계·인허가 참고 갱신", key="sd_refresh_land"):
        _, err = merge_site_land_info(site)
        if err and err != "OK":
            st.warning(err)
        elif site.get("boundary_geojson"):
            st.success("갱신 완료 — 필지 경계·토지정보 반영")
        else:
            st.warning("주소만 반영됨. VWorld 경계 실패 — 아래 출처·Secrets 확인")
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

    st.markdown("---")
    st.markdown("**인허가 검토 (참고 — 자동 확정 아님)**")
    if info.get("인허가_자동판정"):
        st.caption(info["인허가_자동판정"])

    st.markdown("*법령상 검토 참고*")
    for line in info.get("인허가_법령상_제한") or []:
        st.markdown(f"- {line}")

    st.markdown("*담당자 확인사항*")
    for line in info.get("인허가_담당자_확인") or []:
        st.markdown(f"- {line}")

    if info.get("데이터_출처"):
        st.caption(f"출처: {info['데이터_출처']}")

    if site.get("boundary_geojson"):
        st.success("필지 경계: VWorld 지적 데이터 (지도 표시)")
    else:
        st.markdown(
            '<p class="sd-warn">⚠ 필지 경계 없음 — 「갱신」 후에도 없으면 '
            "VWORLD_DOMAIN·좌표를 확인하세요.</p>",
            unsafe_allow_html=True,
        )
