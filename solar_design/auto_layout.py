"""④ 모듈 자동 배치·예상 용량 (필지 경계 기준, 참고용)."""

from __future__ import annotations

import json
import math
from typing import Any

import streamlit as st

from solar_design.utils import load_json_data


def default_module_spec() -> dict:
    modules = [m for m in load_json_data("modules.json") if m.get("사용_여부", True)]
    if not modules:
        return {
            "제조사": "예시",
            "모델명": "Generic-645",
            "정격출력_Wp": 645,
            "가로_mm": 2384,
            "세로_mm": 1303,
        }
    return modules[0]


def _rings_from_geojson(gj: dict) -> list[list[tuple[float, float]]]:
    rings: list[list[tuple[float, float]]] = []

    def add_geom(g: dict) -> None:
        t = g.get("type")
        c = g.get("coordinates")
        if not c:
            return
        if t == "Polygon":
            rings.append([(float(p[0]), float(p[1])) for p in c[0]])
        elif t == "MultiPolygon":
            for poly in c:
                rings.append([(float(p[0]), float(p[1])) for p in poly[0]])

    if gj.get("type") == "FeatureCollection":
        for f in gj.get("features") or []:
            if f.get("geometry"):
                add_geom(f["geometry"])
    elif gj.get("type") == "Feature":
        add_geom(gj.get("geometry") or {})
    else:
        add_geom(gj)
    return rings


def _point_in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def _point_in_geojson(lon: float, lat: float, gj: dict) -> bool:
    for ring in _rings_from_geojson(gj):
        if _point_in_ring(lon, lat, ring):
            return True
    return False


def _meters_to_deg(lat: float, meters: float) -> tuple[float, float]:
    dlat = meters / 111_320.0
    dlon = meters / (111_320.0 * math.cos(math.radians(lat)))
    return dlon, dlat


def _dist_point_to_segment_m(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float, lat_ref: float
) -> float:
    mx_per_lon, mx_per_lat = _meters_to_deg(lat_ref, 1.0)
    x1m, y1m = x1 * mx_per_lon, y1 * mx_per_lat
    x2m, y2m = x2 * mx_per_lon, y2 * mx_per_lat
    pxm, pym = px * mx_per_lon, py * mx_per_lat
    dx, dy = x2m - x1m, y2m - y1m
    if dx == 0 and dy == 0:
        return math.hypot(pxm - x1m, pym - y1m)
    t = max(0, min(1, ((pxm - x1m) * dx + (pym - y1m) * dy) / (dx * dx + dy * dy)))
    projx = x1m + t * dx
    projy = y1m + t * dy
    return math.hypot(pxm - projx, pym - projy)


def _min_dist_to_boundary_m(lon: float, lat: float, ring: list[tuple[float, float]]) -> float:
    if len(ring) < 2:
        return 0.0
    dmin = float("inf")
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        d = _dist_point_to_segment_m(lon, lat, x1, y1, x2, y2, lat)
        dmin = min(dmin, d)
    return dmin


def _ring_bbox(ring: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return min(lons), min(lats), max(lons), max(lats)


def _approx_ring_area_m2(ring: list[tuple[float, float]]) -> float:
    if len(ring) < 3:
        return 0.0
    lat0 = sum(p[1] for p in ring) / len(ring)
    mx_lon, mx_lat = _meters_to_deg(lat0, 1.0)
    xs = [(p[0] - ring[0][0]) * mx_lon for p in ring]
    ys = [(p[1] - ring[0][1]) * mx_lat for p in ring]
    area = 0.0
    for i in range(len(xs)):
        j = (i + 1) % len(xs)
        area += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(area) / 2.0


def compute_auto_layout(
    boundary_geojson: dict,
    *,
    module: dict | None = None,
    setback_m: float = 2.0,
    gap_m: float = 0.25,
) -> dict[str, Any]:
    module = module or default_module_spec()
    wp = int(module.get("정격출력_Wp") or 600)
    w_m = float(module.get("가로_mm") or 2278) / 1000.0
    h_m = float(module.get("세로_mm") or 1134) / 1000.0
    pitch_x = w_m + gap_m
    pitch_y = h_m + gap_m

    rings = _rings_from_geojson(boundary_geojson)
    if not rings:
        return {"ok": False, "message": "필지 경계 GeoJSON 없음"}

    ring = max(rings, key=len)
    min_lon, min_lat, max_lon, max_lat = _ring_bbox(ring)
    lat_mid = (min_lat + max_lat) / 2
    dlon_step, dlat_step = _meters_to_deg(lat_mid, pitch_x)[0], _meters_to_deg(lat_mid, pitch_y)[1]

    centers: list[tuple[float, float]] = []
    lon = min_lon + dlon_step * 0.5
    while lon <= max_lon:
        lat = min_lat + dlat_step * 0.5
        while lat <= max_lat:
            if _point_in_ring(lon, lat, ring):
                if _min_dist_to_boundary_m(lon, lat, ring) >= setback_m:
                    centers.append((lon, lat))
            lat += dlat_step
        lon += dlon_step

    count = len(centers)
    capacity_kw = count * wp / 1000.0
    parcel_area = _approx_ring_area_m2(ring)

    hw_lon, hh_lat = _meters_to_deg(lat_mid, w_m / 2)
    module_features = []
    for lon, lat in centers:
        module_features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [lon - hw_lon, lat - hh_lat],
                            [lon + hw_lon, lat - hh_lat],
                            [lon + hw_lon, lat + hh_lat],
                            [lon - hw_lon, lat + hh_lat],
                            [lon - hw_lon, lat - hh_lat],
                        ]
                    ],
                },
                "properties": {"type": "module", "Wp": wp},
            }
        )

    util = (count * w_m * h_m / parcel_area * 100) if parcel_area > 0 else 0
    return {
        "ok": True,
        "message": "참고용 자동 배치 (그림자·경사·장애물 미반영)",
        "module_count": count,
        "module_wp": wp,
        "module_model": module.get("모델명", ""),
        "module_maker": module.get("제조사", ""),
        "capacity_kW": round(capacity_kw, 2),
        "capacity_MWp": round(capacity_kw / 1000, 3),
        "parcel_area_m2": round(parcel_area, 1) if parcel_area else None,
        "coverage_pct": round(util, 1),
        "setback_m": setback_m,
        "layout_geojson": {"type": "FeatureCollection", "features": module_features},
    }


def apply_layout_to_site(site: dict, *, setback_m: float = 2.0) -> dict:
    gj = site.get("boundary_geojson")
    if not gj:
        site["layout"] = {
            "ok": False,
            "message": "필지 경계 없음 — 「토지정보·필지경계 갱신」 먼저",
        }
        return site["layout"]
    if isinstance(gj, str):
        gj = json.loads(gj)
    layout = compute_auto_layout(gj, setback_m=setback_m)
    site["layout"] = layout
    return layout


def find_site_at_click(sites: list[dict], lon: float, lat: float) -> dict | None:
    for s in sites:
        gj = s.get("boundary_geojson")
        if not gj:
            continue
        if isinstance(gj, str):
            gj = json.loads(gj)
        if _point_in_geojson(lon, lat, gj):
            return s
    return None


def handle_map_click(lon: float, lat: float) -> None:
    """지도 클릭 → VWorld 필지 조회·목록 추가(또는 기존 PNU)·자동 배치."""
    from solar_design.land_info import merge_site_land_info
    from solar_design.site_search import geocode_kakao_reverse
    from solar_design.utils import SESSION_ACTIVE_SITE_ID, default_site, get_sites, set_sites
    from solar_design.vworld_client import get_parcel_at_point, reverse_parcel_address

    sites = get_sites()
    target = find_site_at_click(sites, lon, lat)

    if target is None:
        road, jibun = geocode_kakao_reverse(lat, lon)
        if not jibun and not road:
            rev, _ = reverse_parcel_address(lon, lat)
            jibun = rev or ""
        target = default_site(road=road, jibun=jibun, lat=lat, lon=lon)
        site_err = merge_site_land_info(target)[1]
        pnu = (target.get("pnu") or "").strip()
        if pnu:
            existing = next((s for s in sites if (s.get("pnu") or "").strip() == pnu), None)
            if existing:
                existing["lat"] = lat
                existing["lon"] = lon
                site_err = merge_site_land_info(existing)[1]
                target = existing
            else:
                sites.append(target)
        else:
            sites.append(target)
    else:
        target["lat"] = lat
        target["lon"] = lon
        site_err = merge_site_land_info(target)[1]

    st.session_state[SESSION_ACTIVE_SITE_ID] = target["id"]
    setback = float(st.session_state.get("sd_layout_setback", 2.0))
    apply_layout_to_site(target, setback_m=setback)
    set_sites(sites)

    lay = target.get("layout") or {}
    label = target.get("address_jibun") or target.get("address_road") or "필지"
    if lay.get("ok"):
        st.session_state["sd_map_click_msg"] = (
            f"추가·갱신: {label} — 모듈 {lay.get('module_count', 0):,}장 · "
            f"{lay.get('capacity_kW', 0):,.1f} kW ({lay.get('capacity_MWp', 0):.3f} MWp)"
        )
        st.session_state["sd_map_click_level"] = "success"
    else:
        detail = site_err or lay.get("message", "배치 실패")
        st.session_state["sd_map_click_msg"] = f"{label} — {detail}"
        st.session_state["sd_map_click_level"] = "warning"


def render_auto_layout_panel(site: dict | None) -> None:
    st.markdown('<p class="sd-panel-title">⚡ 자동 배치·예상 용량</p>', unsafe_allow_html=True)
    if not site:
        st.info("부지를 선택하세요.")
        return
    setback = st.slider("경계 이격(m)", 1.0, 5.0, 2.0, 0.5, key="sd_layout_setback")
    if st.button("활성 필지 배치 계산", type="primary", key="sd_calc_layout"):
        apply_layout_to_site(site, setback_m=setback)
        st.rerun()
    st.caption("지도 **클릭** → 해당 위치 필지 조회·목록 추가·자동 배치 (VWorld + Kakao)")

    layout = site.get("layout") or {}
    if not layout.get("ok"):
        st.warning(layout.get("message") or "배치 미계산")
        return
    st.metric("모듈 수(장)", f"{layout.get('module_count', 0):,}")
    st.metric("예상 DC 용량", f"{layout.get('capacity_kW', 0):,.1f} kW")
    st.metric("예상 용량", f"{layout.get('capacity_MWp', 0):.3f} MWp")
    st.caption(
        f"{layout.get('module_maker')} {layout.get('module_model')} "
        f"({layout.get('module_wp')} Wp) · 점유(참고) {layout.get('coverage_pct')}%"
    )


def render_auto_layout() -> None:
    from solar_design.utils import get_active_site

    render_auto_layout_panel(get_active_site())
