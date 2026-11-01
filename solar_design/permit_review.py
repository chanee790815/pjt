"""인허가 검토 — 공공 API·지목 기반 참고만 (자동 승인/불허 없음)."""

from __future__ import annotations


def enrich_permit_review(land_info: dict) -> dict:
    """필지정보(지목·면적·용도 등)로 법령 참고·담당자 확인 목록 보강."""
    jimok = str(land_info.get("지목") or "").strip()
    area = land_info.get("필지_면적_m2")
    yongdo = str(land_info.get("용도지역") or "")
    yongdo_gu = str(land_info.get("용도지구") or "")

    legal: list[str] = []

    if jimok and jimok not in ("정보 없음", "—"):
        if any(x in jimok for x in ("전", "답", "과수", "목장")):
            legal.append(
                "지목상 농지(전·답 등)에 해당할 수 있음 → 농지법·농지 전용 등 관할청 확인"
            )
        if any(x in jimok for x in ("임야", "림")):
            legal.append(
                "지목상 임야에 해당할 수 있음 → 산지관리법(산지 전·변경) 해당 여부 확인"
            )
        if "대" in jimok:
            legal.append("지목「대」— 국토계획법상 허용 행위·신재생 설치 기준(지역 조례) 확인")
    else:
        legal.append("지목 미확인 — 등기·토지대장·지적 조회로 지목 확인 후 인허가 검토")

    if yongdo and yongdo not in ("정보 없음", "—"):
        legal.append(f"용도지역「{yongdo}」상 태양광(발전설비) 허용·조건 — 지역 조례·지침 확인")
    else:
        legal.append("용도지역 미연동 — 토지이용계획·용도지역 확인서(관할 시·군·구) 필수")

    if yongdo_gu and yongdo_gu not in ("정보 없음", "—"):
        legal.append(f"용도지구「{yongdo_gu}」별 추가 제한(경관·고도·준공업 등) 확인")

    if isinstance(area, (int, float)) and area > 0:
        if area >= 3300:
            legal.append(
                f"필지 면적 약 {area:,.0f}㎡ — 규모에 따른 개발행위·건축·환경 영향 검토 구간일 수 있음"
            )

    legal.extend(
        [
            "국토계획법·건축법·신재생에너지법·전기사업법 등 **허가·신고 요건은 설비 용량·부지 규모에 따라 달라짐**",
            "본 화면은 법률 자문·인허가 가능 여부 확정이 아님",
        ]
    )

    staff = [
        "관할 시·군·구: 토지이용계획·용도지역·지구 최종 확인",
        "농지·산지 해당 시: 해당 법령 절차 및 협의 기관",
        "개발행위허가·건축허가(해당 시) 및 신재생에너지 설치·전기 인입 협의",
        "가축분뇨·환경·문화재·군사시설·항공 장애물 등 **주변 제한구역** 조회",
        "소유권·저당·임차 등 **권리관계** 및 사업주·지역주민 협의",
    ]

    land_info["인허가_법령상_제한"] = legal
    land_info["인허가_담당자_확인"] = staff
    land_info["인허가_자동판정"] = "해당 없음 (담당자 검토 필수)"
    return land_info
