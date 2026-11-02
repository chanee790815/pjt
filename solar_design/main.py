"""태양광 설계 지원 — 메인 UI (PM app.py에서 호출)."""

from __future__ import annotations

import json

import streamlit as st

from solar_design.auto_layout import handle_map_click, render_auto_layout_panel
from solar_design.land_info import render_land_info_panel
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
    all_sites = get_sites()

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

    for s in all_sites:
        slat, slon = s.get("lat"), s.get("lon")
        if slat is None or slon is None:
            continue
        is_active = site and s.get("id") == site.get("id")
        folium.CircleMarker(
            location=[float(slat), float(slon)],
            radius=8 if is_active else 5,
            color="#2e7d32" if is_active else "#757575",
            fill=True,
            fill_opacity=0.8,
            popup=(s.get("address_jibun") or s.get("address_road") or s.get("id")),
        ).add_to(m)

    bounds_layer = None
    bboxes: list[list[float]] = []
    gj_active = site.get("boundary_geojson")
    if gj_active:
        try:
            gj_obj = gj_active if isinstance(gj_active, dict) else json.loads(gj_active)
            if isinstance(gj_obj.get("bbox"), list) and len(gj_obj["bbox"]) >= 4:
                bboxes.append(gj_obj["bbox"])
            bounds_layer = folium.GeoJson(
                gj_obj,
                name=site.get("address_jibun") or site.get("id"),
                style_function=lambda _: {
                    "fillColor": "#66bb6a",
                    "color": "#2e7d32",
                    "weight": 3,
                    "fillOpacity": 0.35,
                },
            )
            bounds_layer.add_to(m)
        except Exception:
            pass

    if bboxes:
        min_lon = min(b[0] for b in bboxes)
        min_lat = min(b[1] for b in bboxes)
        max_lon = max(b[2] for b in bboxes)
        max_lat = max(b[3] for b in bboxes)
        try:
            m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
        except Exception:
            pass
    elif bounds_layer:
        try:
            m.fit_bounds(bounds_layer.get_bounds())
        except Exception:
            pass
    elif site:
        folium.Marker(
            [lat, lon],
            popup=site.get("address_road") or site.get("address_jibun") or "선택 부지",
            icon=folium.Icon(color="green", icon="info-sign"),
        ).add_to(m)

    boundary = site.get("boundary_geojson")
    if not boundary:
        st.caption("필지 경계: 갱신 또는 **지도 클릭**으로 조회 · 클릭 시 부지 추가+배치")

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

    map_key = f"sd_map_{site.get('id', 'none')}"
    map_state = st_folium(
        m,
        width=None,
        height=480,
        returned_objects=["last_clicked"],
        key=map_key,
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
    level = st.session_state.pop("sd_map_click_level", "success")
    if msg:
        if level == "warning":
            st.warning(msg)
        else:
            st.success(msg)


def _render_parcel_list() -> None:
    sites = get_sites()
    if not sites:
        return
    st.markdown("**선택 필지 목록** (복수 선택 구조)")

    c1, c2 = st.columns([2, 1])
    with c1:
        bulk = st.button(
            "📍 목록 필지 경계·배치 일괄 조회",
            type="primary",
            use_container_width=True,
            key="sd_bulk_boundary",
        )
    with c2:
        st.caption("체크된 필지만 · VWorld")

    if bulk:
        from solar_design.land_info import refresh_listed_sites_boundaries

        with st.spinner("VWorld 필지 경계 조회 중…"):
            result = refresh_listed_sites_boundaries(
                sites, only_selected=True, run_layout=True, force=False
            )
        set_sites(sites)
        if result["ok"]:
            msg = (
                f"경계 표시 {result['ok']}건 / 대상 {result['total']}건 "
                f"(실패 {result['fail']}건"
            )
            if result.get("skip"):
                msg += f", 캐시·기존 {result['skip']}건"
            msg += ")"
            st.success(msg)
        else:
            st.warning(f"경계 0건 — VWorld 502·DOMAIN 확인 (대상 {result['total']}건)")
        for line in result.get("errors") or []:
            st.caption(f"· {line}")
        st.rerun()

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
    try:
        from solar_design import __version__ as _sdv

        st.caption(f"solar_design **{_sdv}** — 테스트에 `0.1.2` 표시되면 최신 코드 반영됨")
    except Exception:
        pass

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
        from solar_design.permit_review import enrich_permit_review

        info = site["land_info"]
        info["소재지"] = site["address_road"] or site["address_jibun"] or "정보 없음"
        info["지번"] = site["address_jibun"] or "추가 확인 필요"
        info["데이터_출처"] = "Juso/Kakao (VWorld는 「갱신」 또는 일괄 조회)"
        enrich_permit_review(info)
        sites = get_sites()
        sites.append(site)
        set_sites(sites)
        st.session_state[SESSION_ACTIVE_SITE_ID] = site["id"]
        st.success(
            "부지가 목록에 추가되었습니다. "
            "필지 경계·토지정보는 「갱신」 또는 「일괄 조회」를 눌러 주세요."
        )
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
