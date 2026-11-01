"""태양광 설계 지원 — 메인 UI (PM app.py에서 호출)."""

from __future__ import annotations

import json

import streamlit as st

from solar_design.land_info import merge_site_land_info, render_land_info_panel
from solar_design.site_search import render_site_search_panel
from solar_design.utils import (
    SESSION_ACTIVE_SITE_ID,
    api_status_line,
    default_site,
    get_active_site,
    get_sites,
    render_solar_design_css,
    render_step_wizard,
    set_sites,
)


def _render_map(site: dict | None, map_style: str) -> None:
    st.markdown('<p class="sd-panel-title">🗺 지도</p>', unsafe_allow_html=True)
    if site is None or site.get("lat") is None or site.get("lon") is None:
        st.info("좌표가 있는 부지를 선택하면 지도에 표시됩니다.")
        return

    lat, lon = float(site["lat"]), float(site["lon"])
    boundary = site.get("boundary_geojson")

    try:
        import folium
        from streamlit_folium import st_folium
    except ImportError:
        st.error("지도 표시에 folium, streamlit-folium 이 필요합니다. requirements.txt 참고.")
        st.code(f"위치: {lat}, {lon}")
        return

    m = folium.Map(location=[lat, lon], zoom_start=17, tiles=None)
    if map_style == "위성":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="위성",
        ).add_to(m)
        folium.TileLayer("OpenStreetMap", name="일반").add_to(m)
    else:
        folium.TileLayer("OpenStreetMap", name="일반").add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="위성",
        ).add_to(m)

    folium.Marker(
        [lat, lon],
        popup=site.get("address_road") or site.get("address_jibun") or "선택 부지",
        icon=folium.Icon(color="green", icon="info-sign"),
    ).add_to(m)

    if boundary:
        try:
            gj = boundary if isinstance(boundary, dict) else json.loads(boundary)
            folium.GeoJson(gj, name="필지 경계").add_to(m)
        except Exception as e:
            st.warning(f"경계 GeoJSON 표시 실패: {e}")
    else:
        st.caption("필지 경계: 미연동 (마커만 표시)")

    folium.LayerControl().add_to(m)
    st_folium(m, width=None, height=480, returned_objects=[])


def _render_parcel_list() -> None:
    sites = get_sites()
    if not sites:
        return
    st.markdown("**선택 필지 목록** (복수 선택 구조)")
    for i, s in enumerate(sites):
        c1, c2, c3 = st.columns([3, 1, 1])
        label = (s.get("address_road") or s.get("address_jibun") or s.get("id"))[:40]
        with c1:
            sel = st.checkbox(label, value=s.get("selected", True), key=f"sd_sel_{s['id']}")
            s["selected"] = sel
        with c2:
            if st.button("활성", key=f"sd_act_{s['id']}"):
                st.session_state[SESSION_ACTIVE_SITE_ID] = s["id"]
                st.rerun()
        with c3:
            if st.button("삭제", key=f"sd_del_{s['id']}"):
                sites.pop(i)
                set_sites(sites)
                st.rerun()
    set_sites(sites)


def _render_design_summary(site: dict | None) -> None:
    st.markdown('<p class="sd-panel-title">📐 설계 개요</p>', unsafe_allow_html=True)
    selected = [s for s in get_sites() if s.get("selected")]
    st.metric("선택 필지 수", len(selected))
    if site:
        st.markdown(
            f"<div class='sd-card'>"
            f"<b>활성 부지</b><br/>"
            f"{site.get('address_road') or site.get('address_jibun') or '-'}<br/>"
            f"lat/lon: {site.get('lat')}, {site.get('lon')}"
            f"</div>",
            unsafe_allow_html=True,
        )
        area = (site.get("land_info") or {}).get("필지_면적_m2")
        st.metric("필지 면적(㎡)", area if area else "—")
    else:
        st.info("활성 부지 없음")
    st.markdown("---")
    st.markdown("**향후 연동**")
    st.markdown("- 필지 경계·면적 (VWorld WFS 등)")
    st.markdown("- 장애물·진입도로·직접 그리기")
    st.markdown("- 모듈 자동 배치 → 용량 산출")


def view_solar_design() -> None:
    """Streamlit 페이지 진입점."""
    render_solar_design_css()
    st.title("☀ 태양광 설계 지원")
    st.caption(api_status_line())

    with st.expander("API 키 설정 안내", expanded=False):
        st.markdown(
            """
            **`.streamlit/secrets.toml`** 또는 환경변수:

            | 키 | 용도 |
            |----|------|
            | `JUSO_API_KEY` | [도로명주소 API](https://business.juso.go.kr) confmKey |
            | `KAKAO_REST_API_KEY` | [Kakao Developers](https://developers.kakao.com) REST (주소→좌표) |
            | `VWORLD_API_KEY` | [VWorld](https://www.vworld.kr) — 2차 토지·필지경계 |

            ```toml
            JUSO_API_KEY = "발급키"
            KAKAO_REST_API_KEY = "발급키"
            VWORLD_API_KEY = "발급키"
            ```
            """
        )

    render_step_wizard(current=1)

    phase = st.radio(
        "1차 화면",
        ["부지 검색·선정", "부지 정보 확인", "기자재 미리보기"],
        horizontal=True,
        key="sd_phase",
    )

    add_payload = render_site_search_panel()
    if add_payload and add_payload.get("lat") is not None:
        site = default_site(
            road=add_payload.get("road", ""),
            jibun=add_payload.get("jibun", ""),
            lat=add_payload["lat"],
            lon=add_payload["lon"],
        )
        merge_site_land_info(site)
        sites = get_sites()
        sites.append(site)
        set_sites(sites)
        st.session_state[SESSION_ACTIVE_SITE_ID] = site["id"]
        st.success("부지가 목록에 추가되었습니다.")
        st.rerun()

    _render_parcel_list()
    active = get_active_site()

    left, center, right = st.columns([1, 1.6, 1])

    with left:
        if phase == "부지 정보 확인":
            render_land_info_panel(active)
        elif phase == "기자재 미리보기":
            from solar_design.equipment import render_equipment_preview

            render_equipment_preview()
        else:
            render_land_info_panel(active)

    with center:
        map_style = st.radio(
            "지도 종류",
            ["일반", "위성"],
            horizontal=True,
            key="sd_map_style_radio",
        )
        _render_map(active, map_style)

    with right:
        _render_design_summary(active)
