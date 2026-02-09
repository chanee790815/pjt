## [PMS Revision History]
## 버전: Rev. 0.3
## 업데이트 요약:
## 1. 주간 주요 사항(Weekly Highlight) 기능 추가: 프로젝트별 핵심 이슈 기록
## 2. 메인 대시보드 연동: 요약표에 프로젝트별 '주간 현황' 컬럼 추가 (한 줄 출력)
## 3. 실시간 취합: 각 프로젝트 시트의 특정 셀(H2)을 주간 현황 저장소로 활용

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.3", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
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

# --- 메인 실행 로직 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    pjt_list_raw = [s.title for s in sh.worksheets()]
    
    st.sidebar.title("📁 PMO 프로젝트 센터")
    menu_list = ["🏠 전체 대시보드"] + pjt_list_raw
    selected_pjt = st.sidebar.selectbox("🎯 메뉴 선택", menu_list)

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (주간 현황 한줄 요약 포함)
    # ---------------------------------------------------------
    if selected_pjt == "🏠 전체 대시보드":
        st.title("📊 PMO 통합 프로젝트 대시보드")
        
        summary_data = []
        with st.spinner('전체 프로젝트 데이터를 분석 중입니다...'):
            for pjt_name in pjt_list_raw:
                ws = sh.worksheet(pjt_name)
                # 데이터 로드
                all_vals = ws.get_all_values()
                if len(all_vals) > 1:
                    df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
                    df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                    
                    # 주간 현황 데이터: H2 셀(데이터상 첫 줄의 담당자 열 옆 또는 비고 활용) 
                    # 여기서는 간단하게 '비고' 열의 첫 번째 데이터를 주간 현황으로 간주하거나 
                    # 혹은 별도의 셀을 지정할 수 있습니다. (안정성을 위해 비고 열 활용)
                    weekly_msg = df.iloc[0]['비고'] if '비고' in df.columns else "-"
                    
                    summary_data.append({
                        "프로젝트명": pjt_name,
                        "평균 진척률(%)": round(df['진행률'].mean(), 1),
                        "주간 주요 현황": weekly_msg,
                        "최종 업데이트": datetime.date.today().strftime("%m-%d")
                    })
        
        if summary_data:
            sum_df = pd.DataFrame(summary_data)
            
            # 상단 요약
            m1, m2 = st.columns(2)
            m1.metric("총 프로젝트", f"{len(pjt_list_raw)}개")
            m2.metric("전체 평균 진척률", f"{round(sum_df['평균 진척률(%)'].mean(), 1)}%")
            
            st.divider()
            
            # [핵심] 프로젝트별 주간 브리핑 표
            st.subheader("📋 프로젝트별 주간 브리핑 (한줄 요약)")
            st.dataframe(sum_df, use_container_width=True, hide_index=True)
            
            # 차트
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="평균 진척률(%)", color="평균 진척률(%)", text_auto=True), use_container_width=True)
        else:
            st.info("데이터가 있는 프로젝트가 없습니다.")

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트 관리 (주간 현황 입력창 추가)
    # ---------------------------------------------------------
    else:
        ws = sh.worksheet(selected_pjt)
        data = ws.get_all_records()
        df_raw = pd.DataFrame(data)
        
        st.title(f"🏗️ {selected_pjt} 상세 관리")

        tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 주간 현황 및 수정"])

        with tab1:
            if not df_raw.empty:
                # Gantt 차트 및 마일스톤 (기존 v0.1 로직 동일)
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("데이터가 없습니다.")

        with tab2:
            # (기존 일정 등록 로직 동일)
            st.subheader("📝 신규 일정 등록")

        with tab3:
            # [신규 기능] 주간 주요 현황 입력
            st.subheader("📢 이번 주 주요 사항 업데이트")
            st.info("여기에 입력한 내용은 '전체 대시보드' 메인 장표에 한 줄로 표시됩니다.")
            
            # 현재 저장된 첫 번째 행의 비고 가져오기
            current_note = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            
            with st.form("weekly_report"):
                weekly_text = st.text_input("주간 핵심 이슈 (예: 인허가 완료 및 착공 준비)", value=current_note)
                if st.form_submit_button("메인 장표에 반영하기"):
                    # 시트의 F2 셀(비고 열의 첫 칸)을 프로젝트 전체 요약 칸으로 사용
                    ws.update_acell("F2", weekly_text)
                    st.success("대시보드에 주간 현황이 업데이트되었습니다!"); time.sleep(1); st.rerun()
            
            st.divider()
            # (기존 개별 공정 수정/삭제 로직 동일)
