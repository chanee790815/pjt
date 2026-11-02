"""필지 조회 결과 — 세션 캐시 + site에 이미 있는 데이터 재사용."""

from __future__ import annotations

from solar_design.utils import (
    empty_land_info,
    get_cached_vworld_parcel,
    get_cached_vworld_parcel_by_pnu,
    store_vworld_parcel_cache,
)


def site_has_vworld_data(site: dict) -> bool:
    """경계 GeoJSON이 있을 때만 VWorld 재조회 생략."""
    return bool(site.get("boundary_geojson"))


def parcel_dict_from_site(site: dict) -> dict | None:
    gj = site.get("boundary_geojson")
    if not gj:
        pnu = (site.get("pnu") or "").strip()
        if pnu:
            return get_cached_vworld_parcel_by_pnu(pnu)
        return None
    li = site.get("land_info") or {}
    return {
        "pnu": site.get("pnu") or "",
        "jibun": li.get("지번") or site.get("address_jibun") or "",
        "addr": li.get("소재지") or site.get("address_road") or "",
        "jimok": li.get("지목") if li.get("지목") != "정보 없음" else "",
        "geojson": gj,
        "area_m2": li.get("필지_면적_m2"),
        "properties": {},
    }


def hydrate_parcel_from_site_or_cache(
    site: dict, lat: float, lon: float
) -> dict | None:
    hit = get_cached_vworld_parcel(lat, lon)
    if hit:
        return hit
    pnu = (site.get("pnu") or "").strip()
    if pnu:
        hit = get_cached_vworld_parcel_by_pnu(pnu)
        if hit:
            return hit
    if site_has_vworld_data(site):
        parcel = parcel_dict_from_site(site)
        if parcel:
            store_vworld_parcel_cache(lat, lon, parcel)
        return parcel
    return None
