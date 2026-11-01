"""STEP 1: 부지 검색 — Juso / Kakao (키 있을 때만 실제 호출)."""

from __future__ import annotations

import requests
import streamlit as st

from solar_design.utils import get_secret


def search_juso(
    keyword: str, page: int = 1, count: int = 50
) -> tuple[list[dict], str | None, int]:
    """도로명주소 API. (결과 목록, 오류, 전체 건수)"""
    key = get_secret("JUSO_API_KEY") or get_secret("JUSO_CONFIRM_KEY")
    if not key:
        return [], "JUSO API 키가 설정되지 않았습니다. (Secrets: JUSO_API_KEY)", 0
    if not keyword.strip():
        return [], "검색어를 입력하세요.", 0
    count = max(1, min(int(count), 100))
    url = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
    params = {
        "confmKey": key,
        "currentPage": str(page),
        "countPerPage": str(count),
        "keyword": keyword.strip(),
        "resultType": "json",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        common = (data.get("results") or {}).get("common") or {}
        if str(common.get("errorCode", "0")) not in ("0", "E0000"):
            return [], f"Juso 오류: {common.get('errorMessage', common.get('errorCode'))}", 0
        total = int(common.get("totalCount") or 0)
        juso_list = (data.get("results") or {}).get("juso") or []
        out = []
        for j in juso_list:
            out.append(
                {
                    "road": j.get("roadAddr", ""),
                    "jibun": j.get("jbnAddr", "") or j.get("jibunAddr", ""),
                    "zip": j.get("zipNo", ""),
                    "adm_cd": j.get("admCd", ""),
                    "bd_mgt_sn": j.get("bdMgtSn", ""),
                    "source": "juso",
                    "raw": j,
                }
            )
        return out, None, total
    except Exception as e:
        return [], f"Juso 요청 실패: {e}", 0


def search_kakao_address(keyword: str, page: int = 1, size: int = 30) -> tuple[list[dict], str | None]:
    """Kakao 주소 검색 (지번·도로명)."""
    key = get_secret("KAKAO_REST_API_KEY")
    if not key:
        return [], None
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {key}"}
    try:
        r = requests.get(
            url,
            headers=headers,
            params={"query": keyword.strip(), "size": size, "page": page},
            timeout=15,
        )
        r.raise_for_status()
        docs = (r.json().get("documents") or [])
        out = []
        for d in docs:
            out.append(
                {
                    "road": d.get("road_address_name") or "",
                    "jibun": d.get("address_name", ""),
                    "place_name": "",
                    "lat": float(d.get("y")) if d.get("y") else None,
                    "lon": float(d.get("x")) if d.get("x") else None,
                    "source": "kakao_address",
                    "raw": d,
                }
            )
        return out, None
    except Exception as e:
        return [], f"Kakao address 실패: {e}"


def geocode_kakao(query: str) -> tuple[float | None, float | None, str | None]:
    """Kakao 로컬 API — 주소 → WGS84."""
    key = get_secret("KAKAO_REST_API_KEY")
    if not key:
        return None, None, "KAKAO_REST_API_KEY 미설정"
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {key}"}
    try:
        r = requests.get(url, headers=headers, params={"query": query.strip()}, timeout=15)
        r.raise_for_status()
        docs = (r.json().get("documents") or [])
        if not docs:
            return None, None, "좌표를 찾지 못했습니다."
        d0 = docs[0]
        return float(d0["y"]), float(d0["x"]), None
    except Exception as e:
        return None, None, f"Kakao geocode 실패: {e}"


def search_kakao_keyword(keyword: str) -> tuple[list[dict], str | None]:
    """Kakao 키워드 검색 (Juso 없을 때 보조)."""
    key = get_secret("KAKAO_REST_API_KEY")
    if not key:
        return [], "KAKAO_REST_API_KEY 미설정"
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {key}"}
    try:
        r = requests.get(
            url,
            headers=headers,
            params={"query": keyword.strip(), "size": 15},
            timeout=15,
        )
        r.raise_for_status()
        docs = (r.json().get("documents") or [])
        out = []
        for d in docs:
            out.append(
                {
                    "road": d.get("road_address_name") or d.get("address_name", ""),
                    "jibun": d.get("address_name", ""),
                    "place_name": d.get("place_name", ""),
                    "lat": float(d.get("y")) if d.get("y") else None,
                    "lon": float(d.get("x")) if d.get("x") else None,
                    "source": "kakao_keyword",
                    "raw": d,
                }
            )
        return out, None
    except Exception as e:
        return [], f"Kakao keyword 실패: {e}"


def _dedupe_results(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        key = f"{it.get('road')}|{it.get('jibun')}"
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def geocode_kakao_reverse(lat: float, lon: float) -> tuple[str, str]:
    """좌표 → (도로명, 지번) Kakao."""
    key = get_secret("KAKAO_REST_API_KEY")
    if not key:
        return "", ""
    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    headers = {"Authorization": f"KakaoAK {key}"}
    try:
        r = requests.get(
            url, headers=headers, params={"x": lon, "y": lat}, timeout=15
        )
        r.raise_for_status()
        docs = (r.json().get("documents") or [])
        if not docs:
            return "", ""
        d0 = docs[0]
        road = (d0.get("road_address") or {}).get("address_name") or ""
        jibun = (d0.get("address") or {}).get("address_name") or ""
        return road, jibun
    except Exception:
        return "", ""


def resolve_coordinates(item: dict) -> tuple[float | None, float | None, str | None]:
    if item.get("lat") is not None and item.get("lon") is not None:
        return item["lat"], item["lon"], None
    q = item.get("road") or item.get("jibun") or item.get("place_name") or ""
    if not q:
        return None, None, "주소 정보 없음"
    return geocode_kakao(q)


def render_site_search_panel() -> dict | None:
    """검색 UI. 선택 시 {road, jibun, lat, lon} 또는 None."""
    st.markdown('<p class="sd-panel-title">🔍 부지 검색</p>', unsafe_allow_html=True)
    st.caption(
        "지번만 검색하면 전국 동명리가 섞입니다. **시·군·구 + 리·지번** 권장 "
        "(예: `합천군 가야면 어량리 7`, `경남 합천 어량리 123`)"
    )
    keyword = st.text_input(
        "도로명·지번·장소 검색",
        placeholder="예: 경상남도 합천군 가야면 어량리 7",
        key="sd_search_keyword",
    )
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        do_search = st.button("검색", type="primary", use_container_width=True, key="sd_search_btn")
    with c2:
        use_juso = st.checkbox("Juso 우선", value=True, key="sd_use_juso")
    with c3:
        merge_kakao = st.checkbox("Kakao 병합", value=True, key="sd_merge_kakao")

    if "sd_juso_total" not in st.session_state:
        st.session_state.sd_juso_total = 0
    if "sd_last_query" not in st.session_state:
        st.session_state.sd_last_query = ""

    page = 1
    if (
        keyword.strip()
        and st.session_state.sd_last_query == keyword.strip()
        and st.session_state.get("sd_juso_total", 0) > 100
    ):
        max_page = max(1, (st.session_state.sd_juso_total + 99) // 100)
        page = st.number_input("Juso 페이지", min_value=1, max_value=max_page, value=1, key="sd_juso_page")

    run_search = bool(do_search and keyword)
    if (
        keyword.strip()
        and st.session_state.sd_last_query == keyword.strip()
        and page > 1
        and not do_search
    ):
        run_search = True

    results: list[dict] = []
    err_msg = None
    total = 0
    if run_search and keyword:
        if do_search:
            st.session_state.sd_last_query = keyword.strip()
        if use_juso:
            results, err_msg, total = search_juso(keyword, page=page, count=100)
            st.session_state.sd_juso_total = total
        if merge_kakao and get_secret("KAKAO_REST_API_KEY"):
            kaddr, kerr = search_kakao_address(keyword)
            if kaddr:
                results = _dedupe_results(results + kaddr)
            if not results and kerr:
                err_msg = err_msg or kerr
        if not results:
            kkw, kerr2 = search_kakao_keyword(keyword)
            if kkw:
                results = _dedupe_results(results + kkw)
            if kerr2 and not err_msg:
                err_msg = kerr2
        if run_search:
            st.session_state.sd_search_results = results
        if err_msg and not results:
            st.warning(err_msg)
        elif not results:
            st.info("검색 결과가 없습니다. 시·군·구를 포함해 다시 검색해 보세요.")
        elif total > len(results):
            st.info(f"Juso 전체 **{total}건** — 현재 페이지 **{len(results)}건** (100건 초과 시 페이지 번호 변경)")

    results = st.session_state.get("sd_search_results") or results
    selected = None
    if results:
        labels = []
        for i, r in enumerate(results):
            road = r.get("road") or "(도로명 없음)"
            jibun = r.get("jibun") or ""
            labels.append(f"{i+1}. {road} | {jibun}")
        pick = st.selectbox("검색 결과 선택", ["선택"] + labels, key="sd_pick_result")
        if pick != "선택":
            idx = labels.index(pick)
            selected = results[idx]
            lat, lon, geo_err = resolve_coordinates(selected)
            if geo_err:
                st.warning(
                    f"좌표: {geo_err} — Secrets에 **KAKAO_REST_API_KEY** 를 넣어야 "
                    "정확한 위치·지도가 표시됩니다."
                )
            elif lat is not None:
                st.success(f"위치: lat {lat:.6f}, lon {lon:.6f}")
                selected = {**selected, "lat": lat, "lon": lon}

    st.divider()
    st.caption("API 없이 좌표만 지정 (테스트·임시)")
    m1, m2 = st.columns(2)
    with m1:
        manual_lat = st.number_input("위도", value=35.5665, format="%.6f", key="sd_manual_lat")
    with m2:
        manual_lon = st.number_input("경도", value=128.1657, format="%.6f", key="sd_manual_lon")
    if st.button("현재 좌표를 부지로 추가", key="sd_add_manual"):
        return {
            "road": keyword or "수동 입력",
            "jibun": "",
            "lat": manual_lat,
            "lon": manual_lon,
            "source": "manual",
        }

    if selected and st.button("선택 주소를 부지 목록에 추가", type="primary", key="sd_add_selected"):
        if selected.get("lat") is None:
            lat, lon, geo_err = resolve_coordinates(selected)
            if lat is None:
                st.error(geo_err or "좌표를 구할 수 없습니다.")
                return None
            selected = {**selected, "lat": lat, "lon": lon}
        return selected
    return None
