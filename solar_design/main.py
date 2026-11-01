"""태양광 설계 지원 — 메인 UI (PM app.py에서 호출)."""

from __future__ import annotations

import json

import streamlit as st

from solar_design.auto_layout import handle_map_click, render_auto_layout_panel
from solar_design.land_info import merge_site_land_info, render_land_info_panel
from solar_design.site_search import render_site_search_panel
from solar_design.utils import (
    SESSION_ACTIVE_SITE_ID,
    api_status_line,
    default_site,
    diagnose_secrets_for_solar,
    get_active_site,
    get_secret,
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

    if map_style == "위성":
        tile_url = (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        )
        m = folium.Map(
            location=[lat, lon],
            zoom_start=17,
            tiles=tile_url,
            attr="Esri World Imagery",
        )
    else:
        m = folium.Map(location=[lat, lon], zoom_start=17, tiles="OpenStreetMap")

    folium.Marker(
        [lat, lon],
        popup=site.get("address_road") or site.get("address_jibun") or "선택 부지",
        icon=folium.Icon(color="green", icon="info-sign"),
    ).add_to(m)

    if boundary:
        try:
            gj = boundary if isinstance(boundary, dict) else json.loads(boundary)
            gj_layer = folium.GeoJson(
                gj,
                name="필지 경계",
                style_function=lambda _: {
                    "fillColor": "#66bb6a",
                    "color": "#2e7d32",
                    "weight": 2,
                    "fillOpacity": 0.25,
                },
            )
            gj_layer.add_to(m)
            try:
                m.fit_bounds(gj_layer.get_bounds())
            except Exception:
                pass
        except Exception as e:
            st.warning(f"경계 GeoJSON 표시 실패: {e}")
    else:
        st.caption("필지 경계: 「토지정보·필지경계 갱신」 후 표시 · **필지 안 클릭** → 자동 배치")

    layout = site.get("layout") or {}
    lgj = layout.get("layout_geojson")
    if layout.get("ok") and lgj:
        folium.GeoJson(
            lgj,
            name="모듈(참고)",
            style_function=lambda _: {
                "fillColor": "#1565c0",
                "color": "#0d47a1",
                "weight": 1,
                "fillOpacity": 0.45,
            },
        ).add_to(m)

    map_state = st_folium(
        m,
        width=None,
        height=480,
        returned_objects=["last_clicked"],
        key="sd_folium_map",
    )
    if map_state and map_state.get("last_clicked"):
        clk = map_state["last_clicked"]
        if clk.get("lat") is not None and clk.get("lng") is not None:
            last = st.session_state.get("sd_last_map_click")
            cur = (round(clk["lat"], 6), round(clk["lng"], 6))
            if last != cur:
                st.session_state["sd_last_map_click"] = cur
                handle_map_click(float(clk["lng"]), float(clk["lat"]))
                st.rerun()

    msg = st.session_state.pop("sd_map_click_msg", None)
    if msg:
        st.success(msg)


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
        layout = site.get("layout") or {}
        if layout.get("ok"):
            st.markdown("---")
            st.markdown("**예상 설비 (자동 배치·참고)**")
            st.metric("모듈", f"{layout.get('module_count', 0):,} 장")
            st.metric("DC 용량", f"{layout.get('capacity_kW', 0):,.1f} kW")
            st.caption(f"{layout.get('capacity_MWp', 0):.3f} MWp · {layout.get('module_model', '')}")
        else:
            st.caption("필지 클릭 또는 왼쪽 「배치 계산」 후 표시")
    else:
        st.info("활성 부지 없음")
    st.markdown("---")
    st.markdown("**향후** 그림자·일조 · AC/인버터 · 발전량")


def view_solar_design() -> None:
    """Streamlit 페이지 진입점."""
    render_solar_design_css()
    st.title("☀ 태양광 설계 지원")
    st.caption(api_status_line())

    juso_ok = bool(get_secret("JUSO_API_KEY") or get_secret("JUSO_CONFIRM_KEY"))

    with st.expander("API 키 설정 안내", expanded=not juso_ok):
        if not get_secret("KAKAO_REST_API_KEY"):
            st.warning(
                "**Kakao REST 키 미설정** — Juso 검색만 되고 **좌표·지도 위치가 부정확**할 수 있습니다. "
                "VWorld 필지 경계는 **정확한 lat/lon** 이 있어야 합니다."
            )
        for line in diagnose_secrets_for_solar():
            st.markdown(line)
        st.markdown("---")
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

    phase = st.radio(
        "1차 화면",
        ["부지 검색·선정", "부지 정보 확인", "자동 배치·용량", "기자재 미리보기"],
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
        merge_site_land_info(site)[0]
        sites = get_sites()
        sites.append(site)
        set_sites(sites)
        st.session_state[SESSION_ACTIVE_SITE_ID] = site["id"]
        st.success("부지가 목록에 추가되었습니다.")
        st.rerun()

    _render_parcel_list()
    active = get_active_site()
    step = 3 if active and (active.get("layout") or {}).get("ok") else 1
    if phase == "부지 정보 확인":
        step = max(step, 2)
    render_step_wizard(current=step)

    left, center, right = st.columns([1, 1.6, 1])

    with left:
        if phase == "자동 배치·용량":
            render_auto_layout_panel(active)
        elif phase == "부지 정보 확인":
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
