"""VWorld 오픈API (2D 데이터·주소) — Streamlit 서버 호출."""

from __future__ import annotations

import math
import time
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


def _domain_candidates(*, allow_fallback: bool = True) -> list[str]:
    primary = _vworld_domain()
    if not allow_fallback:
        return [primary] if primary else ["pmteampjt26.streamlit.app"]
    cands = [primary, "pmteampjt26.streamlit.app"]
    out: list[str] = []
    for c in cands:
        if c and c not in out:
            out.append(c)
    return out


LAST_VWORLD_ERROR: str = ""

_HTTP_ATTEMPTS = 3
_READ_TIMEOUT = 25

_VWORLD_HEADERS = {
    "User-Agent": "PM-SolarDesign/1.0 (Streamlit)",
    "Accept": "application/json",
    "Connection": "close",
}


def _friendly_request_error(exc: BaseException) -> str:
    raw = str(exc)
    if "RemoteDisconnected" in raw or "Connection aborted" in raw:
        return (
            "VWorld 서버가 연결을 끊었습니다 (일시적). "
            "30초~1분 후 「일괄 조회」를 다시 시도하세요."
        )
    if "502" in raw or "503" in raw or "504" in raw:
        return "VWorld 게이트웨이 일시 오류 — 잠시 후 재시도"
    if "timed out" in raw.lower() or "timeout" in raw.lower():
        return "VWorld 응답 시간 초과 — 재시도"
    return raw[:200]


def _http_get_json(
    url: str,
    params: dict,
    *,
    timeout: int | None = None,
    max_attempts: int | None = None,
) -> tuple[dict | None, str | None]:
    """502·연결 끊김 시 짧게 재시도."""
    read_timeout = timeout if timeout is not None else _READ_TIMEOUT
    attempts = max_attempts if max_attempts is not None else _HTTP_ATTEMPTS
    last_err = ""
    for attempt in range(attempts):
        try:
            r = requests.get(
                url,
                params=params,
                timeout=(8, read_timeout),
                headers=_VWORLD_HEADERS,
            )
            if r.status_code in (502, 503, 504):
                last_err = f"{r.status_code} Server Error (VWorld 일시 오류)"
                time.sleep(0.8 + attempt * 0.5)
                continue
            r.raise_for_status()
            return r.json(), None
        except requests.exceptions.HTTPError as e:
            last_err = _friendly_request_error(e)
            time.sleep(0.8 + attempt * 0.5)
            continue
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.Timeout,
        ) as e:
            last_err = _friendly_request_error(e)
            time.sleep(1.0 + attempt * 0.6)
            continue
        except Exception as e:
            return None, _friendly_request_error(e)
    return None, last_err or "VWorld 요청 실패"


def _parse_vworld_error(body: dict) -> str:
    resp = body.get("response") or {}
    err = resp.get("error") or {}
    return (
        err.get("text")
        or err.get("message")
        or resp.get("status")
        or "UNKNOWN"
    )


def _get_data_feature(
    params: dict,
    *,
    primary_domain_only: bool = False,
    max_http_attempts: int | None = None,
) -> tuple[dict | None, str | None]:
    """domain 후보를 순서대로 시도."""
    global LAST_VWORLD_ERROR
    key = _vworld_key()
    if not key:
        LAST_VWORLD_ERROR = "VWORLD_API_KEY 미설정"
        return None, LAST_VWORLD_ERROR

    domains = (
        _domain_candidates(allow_fallback=False)
        if primary_domain_only
        else _domain_candidates()
    )
    last_err = ""
    for domain in domains:
        p = {**params, "key": key, "domain": domain}
        body, req_err = _http_get_json(
            VWORLD_DATA_URL, p, max_attempts=max_http_attempts
        )
        if not body:
            last_err = req_err or "요청 실패"
            continue
        resp = body.get("response") or {}
        st_code = resp.get("status", "")
        if st_code == "OK":
            LAST_VWORLD_ERROR = ""
            return body, None
        if st_code == "NOT_FOUND":
            last_err = "NOT_FOUND"
            continue
        last_err = _parse_vworld_error(body)
    LAST_VWORLD_ERROR = last_err or "VWorld data API 실패"
    if "domain" in LAST_VWORLD_ERROR.lower() or "인증" in LAST_VWORLD_ERROR:
        LAST_VWORLD_ERROR += " → Secrets: VWORLD_DOMAIN = pmteampjt26.streamlit.app"
    return None, LAST_VWORLD_ERROR


def get_pnu_at_point(lon: float, lat: float) -> tuple[str | None, str | None]:
    key = _vworld_key()
    if not key:
        return None, "VWORLD_API_KEY 미설정"
    domain = _domain_candidates(allow_fallback=False)[0]
    params = {
        "service": "address",
        "request": "getPnu",
        "version": "2.0",
        "point": f"{lon},{lat}",
        "crs": "epsg:4326",
        "format": "json",
        "key": key,
        "domain": domain,
    }
    body, req_err = _http_get_json(VWORLD_ADDR_URL, params, timeout=15, max_attempts=3)
    if not body:
        for domain in _domain_candidates()[1:]:
            params["domain"] = domain
            body, req_err = _http_get_json(
                VWORLD_ADDR_URL, params, timeout=15, max_attempts=2
            )
            if body:
                break
    if not body:
        return None, req_err or "주소 API HTTP 실패"
    resp = body.get("response") or {}
    if resp.get("status") != "OK":
        return None, _parse_vworld_error(body) if body else str(resp.get("status"))
    result = resp.get("result") or {}
    if isinstance(result, list) and result:
        result = result[0]
    pnu = (result.get("pnu") or result.get("id") or "").strip()
    return (pnu, None) if pnu else (None, "PNU 결과 없음 (좌표가 필지 밖일 수 있음)")


def get_parcel_by_point_direct(
    lon: float,
    lat: float,
    *,
    max_http_attempts: int = 3,
) -> tuple[dict | None, str | None]:
    """getPnu 없이 2D데이터 좌표→필지 (주소 API 502 우회)."""
    body, err = _get_data_feature(
        {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN",
            "format": "json",
            "geometry": "true",
            "size": "1",
            "crs": "EPSG:4326",
            "geomFilter": f"POINT({lon} {lat})",
        },
        primary_domain_only=True,
        max_http_attempts=max_http_attempts,
    )
    if not body:
        return None, err
    fc = (body.get("response", {}).get("result") or {}).get("featureCollection")
    feats = (fc or {}).get("features") or []
    if not feats:
        return None, "좌표 위치에 필지 없음 (geomFilter)"
    return _feature_to_parcel(feats[0], fc), None


def get_parcel_by_pnu(
    pnu: str,
    *,
    primary_domain_only: bool = False,
    max_http_attempts: int | None = None,
) -> tuple[dict | None, str | None]:
    body, err = _get_data_feature(
        {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN",
            "format": "json",
            "geometry": "true",
            "size": "1",
            "attrFilter": f"pnu:=:{pnu}",
        },
        primary_domain_only=primary_domain_only,
        max_http_attempts=max_http_attempts,
    )
    if not body:
        return None, err
    fc = (body.get("response", {}).get("result") or {}).get("featureCollection")
    feats = (fc or {}).get("features") or []
    if not feats:
        return None, "PNU 필지 없음"
    return _feature_to_parcel(feats[0], fc), None


def _jimok_from_props(props: dict) -> str:
    for key in (
        "lndcgrCodeNm",
        "lndcgr_nm",
        "jimok",
        "land_gb",
        "lndpcl_ar",
    ):
        val = props.get(key)
        if val and key != "lndpcl_ar":
            return str(val).strip()
    return ""


def _feature_to_parcel(f0: dict, fc: dict) -> dict:
    props = f0.get("properties") or {}
    geom = f0.get("geometry")
    area = _polygon_area_m2(geom) if geom else None
    if area is None and props.get("lndpcl_ar"):
        try:
            area = float(props["lndpcl_ar"])
        except (TypeError, ValueError):
            pass
    return {
        "pnu": props.get("pnu") or "",
        "jibun": props.get("jibun") or props.get("addr") or "",
        "addr": props.get("addr") or "",
        "jiga": props.get("jiga"),
        "jimok": _jimok_from_props(props),
        "geojson": fc,
        "area_m2": area,
        "properties": props,
    }


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
    body, err = _get_data_feature(
        {
            "service": "data",
            "request": "GetFeature",
            "data": layer,
            "format": "json",
            "geometry": "false",
            "size": str(size),
            "crs": "EPSG:4326",
            "geomFilter": f"POINT({lon} {lat})",
        }
    )
    if not body:
        return [], err
    fc = (body.get("response", {}).get("result") or {}).get("featureCollection") or {}
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
    """용도지역 — 1개 레이어만 시도 (속도)."""
    feats, _ = _get_features_at_point("LT_L_UQ111", lon, lat)
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
            return {
                "용도지역": zone or "정보 없음",
                "용도지구": district or "정보 없음",
                "properties": props,
            }, None
    return None, None


def get_parcel_minimal(lon: float, lat: float) -> tuple[dict | None, str | None]:
    """
    1필지 성공 확인용 — API 2회만 (getPnu + PNU로 경계), 도메인 1개·재시도 최소.
    """
    if not _vworld_key():
        return None, "VWORLD_API_KEY 미설정"
    pnu, err = get_pnu_at_point(lon, lat)
    if not pnu:
        if err and ("502" in str(err) or "503" in str(err) or "504" in str(err)):
            parcel, err_b = get_parcel_by_point_direct(lon, lat, max_http_attempts=3)
            if parcel:
                return parcel, None
            return None, f"getPnu: {err} / 좌표직접: {err_b or '실패'}"
        return None, err or "PNU 조회 실패"
    parcel, err2 = get_parcel_by_pnu(
        pnu,
        primary_domain_only=True,
        max_http_attempts=2,
    )
    if parcel:
        return parcel, None
    return None, err2 or "필지 경계(GetFeature) 실패"


def diagnose_vworld_one_parcel(lon: float, lat: float) -> tuple[list[str], dict | None]:
    """단계별 메시지 + 성공 시 parcel dict. 2D Data 먼저(주소 API 502 우회)."""
    lines: list[str] = []
    key = _vworld_key()
    if not key:
        lines.append("❌ VWORLD_API_KEY 없음 (Secrets 확인)")
        return lines, None

    from solar_design import __version__ as sd_ver

    lines.append(f"모듈 버전 **{sd_ver}** (0.1.2 미만이면 GitHub 코드 재업로드)")
    lines.append(f"✓ Secrets에 VWORLD 키 있음 · domain={_vworld_domain()}")
    lines.append(f"좌표: lon={lon}, lat={lat}")

    lines.append("**① 2D Data** 좌표→필지경계 (getPnu 생략, LP_PA_CBND)…")
    parcel, err_d = get_parcel_by_point_direct(lon, lat, max_http_attempts=4)
    if parcel:
        pnu_b = parcel.get("pnu") or "—"
        area = parcel.get("area_m2")
        lines.append(
            f"✓ ① 성공 · PNU={pnu_b} · 면적≈{area}㎡"
            if area
            else f"✓ ① 성공 · PNU={pnu_b}"
        )
        return lines, parcel
    lines.append(f"❌ ① 2D Data 실패: {err_d or LAST_VWORLD_ERROR}")
    lines.append("→ 개발키 **2D Data API** 체크 · domain 일치 · 1~2분 후 재시도")

    lines.append("**② 주소 API** getPnu (보조)…")
    pnu, err = get_pnu_at_point(lon, lat)
    if not pnu:
        err_txt = err or "알 수 없음"
        lines.append(f"❌ ② getPnu 실패: {err_txt}")
        if "502" in str(err_txt) or "503" in str(err_txt):
            lines.append(
                "→ 502는 VWorld **주소 API 게이트웨이** 일시 오류. "
                "① 2D Data만으로도 경계는 가능 — ① 실패 원인을 먼저 해결."
            )
        return lines, None
    lines.append(f"✓ ② PNU: {pnu}")

    parcel, err2 = get_parcel_by_pnu(
        pnu,
        primary_domain_only=True,
        max_http_attempts=3,
    )
    if not parcel:
        lines.append(f"❌ ③ PNU→경계 실패: {err2 or LAST_VWORLD_ERROR}")
        return lines, None

    area = parcel.get("area_m2")
    lines.append(f"✓ ③ 필지 경계 OK · 면적≈{area}㎡" if area else "✓ ③ 필지 경계 OK")
    return lines, parcel


def get_parcel_at_point(lon: float, lat: float) -> tuple[dict | None, str | None]:
    """
    연속지적도 LP_PA_CBND_BUBUN — 좌표 → PNU → 경계.
    주소 getPnu를 먼저 시도해 GetFeature 호출 수를 줄임 (Cloud 연결 안정).
    """
    if not _vworld_key():
        return None, "VWORLD_API_KEY 미설정"

    parcel, err = get_parcel_by_point_direct(lon, lat, max_http_attempts=3)
    if parcel:
        return parcel, None
    last_err = err

    parcel, err = get_parcel_minimal(lon, lat)
    if parcel:
        return parcel, None
    if err:
        last_err = err

    body, err2 = _get_data_feature(
        {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN",
            "format": "json",
            "geometry": "true",
            "size": "1",
            "crs": "EPSG:4326",
            "geomFilter": f"POINT({lon} {lat})",
        },
        primary_domain_only=True,
        max_http_attempts=2,
    )
    if body:
        fc = (body.get("response", {}).get("result") or {}).get("featureCollection")
        feats = (fc or {}).get("features") or []
        if feats:
            return _feature_to_parcel(feats[0], fc), None
    if err2:
        last_err = err2

    return None, _friendly_request_error(
        Exception(last_err or LAST_VWORLD_ERROR or "필지 경계 조회 실패 (VWORLD_DOMAIN·2D데이터 API 확인)")
    )


def reverse_parcel_address(lon: float, lat: float) -> tuple[str | None, str | None]:
    """좌표 → 지번 주소 (PARCEL)."""
    key = _vworld_key()
    if not key:
        return None, None
    domain = _domain_candidates(allow_fallback=False)[0]
    params = {
        "service": "address",
        "request": "getAddress",
        "version": "2.0",
        "crs": "epsg:4326",
        "point": f"{lon},{lat}",
        "type": "PARCEL",
        "format": "json",
        "key": key,
        "domain": domain,
    }
    body, _ = _http_get_json(VWORLD_ADDR_URL, params, timeout=15)
    if not body:
        return None, None
    resp = body.get("response") or {}
    if resp.get("status") != "OK":
        return None, None
    result = resp.get("result") or []
    if not result:
        return None, None
    item = result[0]
    text = item.get("text") or item.get("structure", {}).get("level4L") or ""
    return text.strip() or None, None
