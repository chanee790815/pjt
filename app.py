## [PMS Revision History]
## 버전: Rev. 0.4
## 업데이트 요약:
## 1. ➕ 프로젝트 신규 추가 기능: 사이드바에서 새 프로젝트 시트 즉시 생성
## 2. 주간 현황 동기화: 메인 대시보드와 개별 프로젝트 현황 업데이트 로직 최적화
## 3. 안정성: 시트가 비어있거나 생성 직후 데이터가 없을 때의 예외 처리 강화

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.4", page_icon="🏗️", layout="wide")

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

# --- [기능] 새 프로젝트(시트) 생성 ---
def create_new_project(sh, name):
    try:
        existing_sheets = [s.title for s in sh.worksheets()]
        if name in existing_sheets: return False, "이미 존재하는 이름입니다."
        # 새 시트 생성 및 표준 헤더 입력
        ws = sh.add_worksheet(title=name, rows="100", cols="20")
        ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        return True, "성공"
    except Exception as e: return False, str(e)

# --- 메인 로직 시작 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = sh.worksheets()
    pjt_list = [s.title for s in all_ws]
    
    # [사이드바]
    st.sidebar.title("📁 PMO 프로젝트 센터")
    
    # 1. 프로젝트 선택 메뉴
    menu_options = ["🏠 전체 대시보드"] + pjt_list
    selected_pjt = st.sidebar.selectbox("🎯 메뉴 선택", menu_options)
    
    st.sidebar.divider()

    # 2. [핵심 추가] 프로젝트 신규 추가 기능
    with st.sidebar.expander("➕ 프로젝트 신규 추가", expanded=False):
        new_pjt_name = st.text_input("신규 프로젝트명 입력", placeholder="예: 당진 솔라 PJT")
        if st.button("신규 프로젝트 생성"):
            if new_pjt_name:
                with st.spinner("구글 시트 생성 중..."):
                    ok, msg = create_new_project(sh, new_pjt_name)
                    if ok:
                        st.success(f"'{new_pjt_name}' 생성 완료!")
                        time.sleep(1)
                        st.rerun()
                    else: st.error(msg)
            else: st.warning("이름을 입력해 주세요.")

    st.sidebar.divider()
    st.sidebar.info(f"접속 중: **{selected_pjt}**")

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드
    # ---------------------------------------------------------
    if selected_pjt == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        summary_list = []
        
        for ws in all_ws:
            try:
                data = ws.get_all_records()
                df = pd.DataFrame(data)
                p_name = ws.title
                prog = 0
                note = "현황 없음"
                
                if not df.empty:
                    if '진행률' in df.columns:
                        df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                        prog = round(df['진행률'].mean(), 1)
                    if '비고' in df.columns and len(df) > 0:
                        note = df.iloc[0]['비고'] if df.iloc[0]['비고'] else "업데이트 예정"
                
                summary_list.append({"프로젝트명": p_name, "진척률(%)": prog, "주간 주요 현황": note})
            except: continue

        if summary_list:
            sum_df = pd.DataFrame(summary_list)
            m1, m2 = st.columns(2)
            m1.metric("총 프로젝트", f"{len(pjt_list)}개")
            m2.metric("평균 진척률", f"{round(sum_df['진척률(%)'].mean(), 1)}%")
            
            st.subheader("📋 프로젝트별 주간 브리핑")
            st.dataframe(sum_df, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True), use_container_width=True)

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트 상세 관리
    # ---------------------------------------------------------
    else:
        ws = sh.worksheet(selected_pjt)
        df_raw = pd.DataFrame(ws.get_all_records())
        st.title(f"🏗️ {selected_pjt} 상세 관리")

        tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 주간 현황 및 수정"])

        with tab1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                
                # 차트 출력
                chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    st.plotly_chart(px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태"), use_container_width=True)
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("💡 등록된 데이터가 없습니다. 일정 등록을 먼저 진행해 주세요.")

        with tab2:
            st.subheader("📝 신규 일정 등록")
            with st.form("in_form"):
                c1, c2, c3 = st.columns(3)
                sd = c1.date_input("시작일", datetime.date.today())
                ed = c2.date_input("종료일", datetime.date.today() + datetime.timedelta(days=30))
                cat = c3.selectbox("대분류", ["인허가", "설계", "토목공사", "전기공사", "MILESTONE"])
                name = st.text_input("공정명")
                stat = st.selectbox("상태", ["예정", "진행중", "완료", "지연"])
                pct = st.number_input("진행률(%)", 0, 100, 0)
                note = st.text_area("비고")
                if st.form_submit_button("저장하기"):
                    ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, "PM팀"])
                    st.success("저장 완료!"); time.sleep(1); st.rerun()

        with tab3:
            st.subheader("📢 주간 현황 업데이트")
            curr_note = df_raw.iloc[0]['비고'] if not df_raw.empty and '비고' in df_raw.columns else ""
            with st.form("weekly_up"):
                new_note = st.text_input("메인 장표용 주간 이슈", value=curr_note)
                if st.form_submit_button("현황 반영"):
                    ws.update_acell("F2", new_note)
                    st.success("반영되었습니다!"); time.sleep(1); st.rerun()
