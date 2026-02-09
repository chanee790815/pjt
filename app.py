## [PMS Revision History]
## 버전: Rev. 0.6.5 (Instant Sync)
## 업데이트 요약:
## 1. 🔄 자동 새로고침 강화: 시트 반영 즉시 캐시를 비우고 최신 데이터를 다시 로드
## 2. ⚡ 반영 속도 최적화: 수정 버튼 클릭 시 즉각적인 피드백 메시지 제공
## 3. 🛡️ 데이터 정합성: 반영 후 st.rerun()을 통해 상단 표와 차트를 최신화

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# (중략: 페이지 설정 및 로그인/인증 로직은 기존과 동일)

# --- [수정] 데이터 로드 함수에 캐시 무효화 로직 추가 ---
def get_pjt_data(worksheet):
    """시트에서 최신 데이터를 읽어옵니다."""
    return pd.DataFrame(worksheet.get_all_records())

client = get_client()
if client:
    sh = client.open('pms_db')
    # (중략: 사이드바 및 메뉴 구성 로직)

    # ---------------------------------------------------------
    # CASE 2: 상세 관리 (실시간 동기화 수정본)
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        
        # [핵심] 페이지 로딩 시 마다 최신 데이터를 명시적으로 가져옴
        df_raw = get_pjt_data(target_ws)
        
        st.title(f"🏗️ {p_name} 상세 관리")
        t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정등록", "📢 현황업데이트", "📜 과거기록조회"])

        with t1:
            if not df_raw.empty:
                # (중략: 간트 차트 및 상단 표 출력 로직)
                st.dataframe(df_raw, use_container_width=True)
                
                # [빠른 수정 섹션]
                with st.expander("🔍 특정 공정 정보 빠르게 수정하기", expanded=True):
                    edit_idx = st.selectbox("수정할 공정의 행(Index) 번호를 선택하세요", df_raw.index)
                    selected_row = df_raw.iloc[edit_idx]
                    
                    with st.form(f"quick_edit_{edit_idx}"):
                        st.write(f"**선택된 공정:** {selected_row['구분']}")
                        c1, c2, c3 = st.columns([2, 5, 2])
                        new_s = c1.selectbox("상태", ["예정", "진행중", "완료", "지연"], 
                                           index=["예정", "진행중", "완료", "지연"].index(selected_row['진행상태']))
                        new_n = c2.text_input("비고 수정", value=selected_row['비고'])
                        new_p = c3.number_input("진행률(%)", 0, 100, int(selected_row['진행률']))
                        
                        if st.form_submit_button("시트에 반영"):
                            with st.spinner('시트에 데이터를 반영 중입니다...'):
                                # 1. 구글 시트 업데이트
                                target_ws.update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                                
                                # 2. [중요] 구글 서버 반영 시간을 위한 아주 짧은 대기
                                time.sleep(0.5) 
                                
                                # 3. 성공 메시지 및 즉시 새로고침
                                st.success("✅ 반영되었습니다! 최신 정보를 불러옵니다.")
                                time.sleep(0.5)
                                st.rerun() # 앱을 다시 실행하여 상단 get_pjt_data를 재호출함

        # (중략: t2, t3, t4 로직은 기존과 동일하되 업데이트 시 위와 같이 st.rerun() 적용)
