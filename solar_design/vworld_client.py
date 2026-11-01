"""VWorld 오픈API (2D 데이터·주소) — Streamlit 서버 호출."""

from __future__ import annotations

import math
from typing import Any

import requests

from solar_design.utils import get_secret

VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
VWORLD_ADDR_URL = "https://api.vworld.kr/req/address"


def _vworld_key() -> str:
    return get_secret("VWORLD_API_KEY") or get_secret("VWORLD_KEY")


def _vworld_domain() -> str:
    d = get_secret("VWORLD_DOMAIN") or get_secret("VWORLD_SERVICE_DOMAIN")
    if d:
        return d.replace("https://", "").replace("http://", "").rstrip("/")
    return "pmteampjt26.streamlit.app"


def _ring_area_m2_approx(ring: list) -> float | None:
    """WGS84 경위도 링 면적 근사(㎡). 소필지용."""
    if len(ring) < 3:
        return None
    lat0 = sum(p[1] for p in ring) / len(ring)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    xs = [(p[0] - ring[0][0]) * m_per_deg_lon for p in ring]
    ys = [(p[1] - ring[0][1]) * m_per_deg_lat for p in ring]
    area = 0.0
    for i in range(len(xs)):
        j = (i + 1) % len(xs)
        area += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(area) / 2.0


def _polygon_area_m2(geom: dict) -> float | None:
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None
    if gtype == "Polygon":
        return _ring_area_m2_approx(coords[0])
    if gtype == "MultiPolygon" and coords:
        total = 0.0
        for poly in coords:
            a = _ring_area_m2_approx(poly[0])
            if a:
                total += a
        return total if total > 0 else None
    return None


def _get_features_at_point(
    layer: str, lon: float, lat: float, *, size: int = 1
) -> tuple[list[dict], str | None]:
    key = _vworld_key()
    if not key:
        return [], "VWORLD_API_KEY 미설정"
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": layer,
        "key": key,
        "domain": _vworld_domain(),
        "format": "json",
        "geometry": "false",
        "size": str(size),
        "crs": "EPSG:4326",
        "geomFilter": f"POINT({lon} {lat})",
    }
    try:
        r = requests.get(VWORLD_DATA_URL, params=params, timeout=20)
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        return [], str(e)
    resp = body.get("response") or {}
    if resp.get("status") not in ("OK",):
        if resp.get("status") == "NOT_FOUND":
            return [], None
        err = resp.get("error") or {}
        return [], err.get("text") or resp.get("status")
    fc = (resp.get("result") or {}).get("featureCollection") or {}
    return fc.get("features") or [], None


def get_land_attrs_at_point(lon: float, lat: float) -> tuple[dict | None, str | None]:
    """연속지적 속성 LT_C_LNDPARCEL — 지목 등."""
    feats, err = _get_features_at_point("LT_C_LNDPARCEL", lon, lat)
    if not feats:
        return None, err
    props = feats[0].get("properties") or {}
    jimok = (
        props.get("lndcgrCodeNm")
        or props.get("lndcgr_nm")
        or props.get("jimok")
        or props.get("land_gb")
        or ""
    )
    return {
        "지목": str(jimok).strip() if jimok else "",
        "properties": props,
    }, None


def get_land_use_at_point(lon: float, lat: float) -> tuple[dict | None, str | None]:
    """용도지역 등(레이어 제공 시). 실패 시 None."""
    for layer in ("LT_L_UQ111", "LT_L_UQ141", "LT_L_SPBD"):
        feats, err = _get_features_at_point(layer, lon, lat)
        if feats:
            props = feats[0].get("properties") or {}
            zone = (
                props.get("uname")
                or props.get("uqcgr_nm")
                or props.get("zoneName")
                or props.get("zone_nm")
                or props.get("use_regn_nm")
                or ""
            )
            district = props.get("district_nm") or props.get("uqcgr_nm2") or ""
            if zone or district:
                return {"용도지역": zone or "정보 없음", "용도지구": district or "정보 없음", "properties": props}, None
    return None, None


def get_parcel_at_point(lon: float, lat: float) -> tuple[dict | None, str | None]:
    """
    연속지적도 LP_PA_CBND_BUBUN — 좌표 교차 필지 1건.
    반환 dict: pnu, jibun, addr, geojson(FeatureCollection), area_m2, properties
    """
    key = _vworld_key()
    if not key:
        return None, "VWORLD_API_KEY 미설정"

    params = {
        "service": "data",
        "request": "GetFeature",
        "data": "LP_PA_CBND_BUBUN",
        "key": key,
        "domain": _vworld_domain(),
        "format": "json",
        "geometry": "true",
        "size": "1",
        "crs": "EPSG:4326",
        "geomFilter": f"POINT({lon} {lat})",
    }
    try:
        r = requests.get(VWORLD_DATA_URL, params=params, timeout=20)
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        return None, f"VWorld 연속지적도 요청 실패: {e}"

    resp = body.get("response") or {}
    status = resp.get("status", "")
    if status == "NOT_FOUND":
        return None, "해당 좌표에 필지가 없습니다. 좌표를 확인하거나 VWORLD_DOMAIN Secrets 확인."
    if status != "OK":
        err = resp.get("error") or {}
        msg = err.get("text") or err.get("message") or status
        if "domain" in str(msg).lower() or "인증" in str(msg):
            msg += " — Secrets에 VWORLD_DOMAIN = pmteampjt26.streamlit.app 추가"
        return None, f"VWorld 오류: {msg}"

    fc = (resp.get("result") or {}).get("featureCollection")
    feats = (fc or {}).get("features") or []
    if not feats:
        return None, "필지 feature 없음"

    f0 = feats[0]
    props = f0.get("properties") or {}
    geom = f0.get("geometry")
    area = _polygon_area_m2(geom) if geom else None

    parcel = {
        "pnu": props.get("pnu") or "",
        "jibun": props.get("jibun") or props.get("addr") or "",
        "addr": props.get("addr") or "",
        "jiga": props.get("jiga"),
        "geojson": fc,
        "area_m2": area,
        "properties": props,
    }
    return parcel, None


def reverse_parcel_address(lon: float, lat: float) -> tuple[str | None, str | None]:
    """좌표 → 지번 주소 (PARCEL)."""
    key = _vworld_key()
    if not key:
        return None, None
    params = {
        "service": "address",
        "request": "getAddress",
        "version": "2.0",
        "crs": "epsg:4326",
        "point": f"{lon},{lat}",
        "type": "PARCEL",
        "format": "json",
        "key": key,
        "domain": _vworld_domain(),
    }
    try:
        r = requests.get(VWORLD_ADDR_URL, params=params, timeout=15)
        r.raise_for_status()
        body = r.json()
        resp = body.get("response") or {}
        if resp.get("status") != "OK":
            return None, None
        result = resp.get("result") or []
        if not result:
            return None, None
        item = result[0]
        text = item.get("text") or item.get("structure", {}).get("level4L") or ""
        return text.strip() or None, None
    except Exception:
        return None, None
