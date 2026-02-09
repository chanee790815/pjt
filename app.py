## [PMS Revision History]
## 수정 일자: 2026-02-09
## 버전: Rev. 0.3
## 업데이트 요약:
## 1. 주간 주요 사항(Weekly Highlight) 기능: 프로젝트별 핵심 이슈 기록창 추가
## 2. 대시보드 연동: 메인 장표 요약표에 프로젝트별 '주간 현황' 컬럼 추가 (한 줄 출력)
## 3. 데이터 구조 최적화: 시트의 비고란과 별도로 프로젝트 단위의 상태 메시지 관리

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.3", page_icon="🏗️", layout="wide")

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 인증 실패: {e}"); return None

# --- [기능] 프로젝트 추가/삭제 로직 ---
def create_new_project(sh, name):
    try:
        if name in [s.title for s in sh.worksheets()]: return False, "이미 존재함"
        ws = sh.add_worksheet(title=name, rows="100", cols="20")
        # 헤더에 '주간현황'을 관리할 수 있는 메타데이터 영역을 예약 (A100 셀 등을 활용하거나 별도 규칙 적용)
        # v0.3에서는 첫 번째 행의 비고란 등을 활용하거나 별도 관리를 위해 첫 행에 가이드라인 삽입
        ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고(주간현황)", "진행률", "담당자"])
        return True, "성공"
    except Exception as e: return False, str(e)

# --- 메인 로직 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    pjt_list_raw = [s.title for s in sh.worksheets()]
    
    st.sidebar.title("📁 PMO 프로젝트 센터")
    menu_list = ["🏠 전체 대시보드"] + pjt_list_raw
    selected_pjt = st.sidebar.selectbox("🎯 메뉴 선택", menu_list)

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (주간 현황 한줄 보기 추가)
    # ---------------------------------------------------------
    if selected_pjt == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        summary_data = []
        for pjt_name in pjt_list_raw:
            ws = sh.worksheet(pjt_name)
            df = pd.DataFrame(ws.get_all_records())
            
            if not df.empty:
                df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                # '주간 현황' 추출: 시트의 가장 첫 번째 행(데이터상 0번)의 '비고'란을 주간 리포트로 활용하는 규칙
                weekly_update = df.iloc[0]['비고(주간현황)'] if '비고(주간현황)' in df.columns else "업데이트 없음"
                
                summary_data.append({
                    "프로젝트명": pjt_name,
                    "진척률(%)": round(df['진행률'].mean(), 1),
                    "주간 주요 현황": weekly_update, # 이 내용이 메인에 한줄로 나옵니다
                    "전체 공정": len(df),
                    "업데이트일": datetime.date.today().strftime("%m-%d")
                })
        
        if summary_data:
            sum_df = pd.DataFrame(summary_data)
            
            # 지표 현황
            c1, c2, c3 = st.columns(3)
            c1.metric("총 프로젝트", f"{len(pjt_list_raw)}개")
            c2.metric("평균 공정률", f"{round(sum_df['진척률(%)'].mean(), 1)}%")
            
            st.divider()
            
            # 메인 요약 장표 (한 줄 요약 포함)
            st.subheader("📋 프로젝트별 주간 브리핑")
            st.dataframe(sum_df[["프로젝트명", "진척률(%)", "주간 주요 현황", "업데이트일"]], 
                         use_container_width=True, hide_index=True)
            
            # 진척률 차트
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True), use_container_width=True)

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트 상세 및 주간 현황 업데이트
    # ---------------------------------------------------------
    else:
        ws = sh.worksheet(selected_pjt)
        df_raw = pd.DataFrame(ws.get_all_records())
        st.title(f"🏗️ {selected_pjt}")

        tab1, tab2, tab3 = st.tabs(["📊 공정표", "📝 일정 등록", "⚙️ 주간 현황 및 관리"])

        with tab1:
            # (기존 차트 및 테이블 로직 동일)
            st.subheader("📈 Gantt Chart")
            st.dataframe(df_raw)

        with tab2:
            st.subheader("📝 신규 일정 등록")
            # (기존 등록 폼 동일)

        with tab3:
            # [신규 기능] 주간 주요 사항 업데이트 섹션
            st.subheader("📢 주간 주요 현황 업데이트")
            current_highlight = ""
            if not df_raw.empty:
                current_highlight = df_raw.iloc[0]['비고(주간현황)'] if '비고(주간현황)' in df_raw.columns else ""
            
            with st.form("weekly_form"):
                new_highlight = st.text_input("이번 주 핵심 이슈 (메인 대시보드 노출용)", value=current_highlight)
                if st.form_submit_button("현황 업데이트"):
                    # 시트의 2행(데이터 첫 줄) F열(비고란)에 주간 현황 저장
                    ws.update_acell("F2", new_highlight)
                    st.success("주간 현황이 메인 장표에 반영되었습니다!"); time.sleep(1); st.rerun()
            
            st.divider()
            st.subheader("🛠️ 개별 공정 수정/삭제")
            # (기존 수정/삭제 로직 동일)
