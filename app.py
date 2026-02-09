## [PMS Revision History]
## 버전: Rev. 0.5.3 (Data Sync Stability)
## 업데이트 요약:
## 1. 🔐 멀티 계정 로그인: Secrets [passwords] 연동 및 접속자 이름 유지
## 2. 🛡️ 데이터 로드 안정화: get_all_records() 오류 방지 및 데이터 타입 강제 변환
## 3. 📊 개별 공정표 복구: 시작일 순 정렬 및 년-월 상단 표시 로직 재통합

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.5.3", page_icon="🏗️", layout="wide")

# --- [인증] 멀티 계정 체크 함수 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.title("🏗️ PM 통합 공정 관리 시스템")
    st.subheader("계정 정보를 입력해 주세요.")
    
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.success(f"{user_id}님 환영합니다!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
    return False

if not check_password():
    st.stop()

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 연결 오류: {e}"); return None

# --- 메인 실행 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = sh.worksheets()
    pjt_names = [s.title for s in all_ws]
    
    # [사이드바]
    st.sidebar.title("📁 PMO 프로젝트 센터")
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}**")
    if st.sidebar.button("🔓 로그아웃"):
        st.session_state["password_correct"] = False
        st.rerun()
    
    st.sidebar.divider()
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)
    
    # 신규 프로젝트 추가 (사이드바)
    with st.sidebar.expander("➕ 프로젝트 신규 추가"):
        new_pjt = st.text_input("새 프로젝트명")
        if st.button("시트 생성"):
            if new_pjt and new_pjt not in pjt_names:
                ws = sh.add_worksheet(title=new_pjt, rows="100", cols="20")
                ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                st.success("생성 완료!"); time.sleep(1); st.rerun()
            else: st.error("이름 중복 또는 미입력")

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드
    # ---------------------------------------------------------
    if selected == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        summary = []
        for ws in all_ws:
            try:
                data = ws.get_all_records()
                if not data: continue
                df = pd.DataFrame(data)
                prog = round(pd.to_numeric(df['진행률'], errors='coerce').mean(), 1)
                note = df.iloc[0]['비고'] if '비고' in df.columns else "-"
                summary.append({"프로젝트명": ws.title, "진척률(%)": prog, "주간 주요 현황": note})
            except: continue
        
        if summary:
            sum_df = pd.DataFrame(summary)
            st.dataframe(sum_df, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True), use_container_width=True)
        else:
            st.info("데이터가 있는 프로젝트가 없습니다.")

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트 (데이터 연동 핵심 수정)
    # ---------------------------------------------------------
    else:
        target_ws = sh.worksheet(selected)
        data_raw = target_ws.get_all_records()
        df_raw = pd.DataFrame(data_raw)
        
        st.title(f"🏗️ {selected} 상세 관리")
        t1, t2, t3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 현황 및 관리"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                # 날짜 및 진행률 타입 강제 변환
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                
                # 정렬 로직
                df = df.sort_values(by='시작일', ascending=True)

                # Gantt 차트 (상단 년-월 표시)
                chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig.update_yaxes(autorange="reversed")
                    fig.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    fig.update_layout(height=500, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("💡 해당 프로젝트에 등록된 공정이 없습니다. '일정 등록' 탭을 이용해 주세요.")

        with t2:
            st.subheader("📝 일정 등록")
            with st.form("in_f"):
                c1,c2,c3 = st.columns(3)
                sd=c1.date_input("시작일"); ed=c2.date_input("종료일"); cat=c3.selectbox("대분류", ["인허가", "설계", "토목", "전기", "MILESTONE"])
                name=st.text_input("공정명"); stat=st.selectbox("상태", ["예정","진행중","완료","지연"]); pct=st.number_input("진행률",0,100,0); note=st.text_area("비고")
                if st.form_submit_button("저장"):
                    target_ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, st.session_state['user_id']])
                    st.success("저장 완료!"); time.sleep(1); st.rerun()

        with t3:
            st.subheader("📢 주간 현황 및 명칭 관리")
            curr_note = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            with st.form("up_f"):
                new_t = st.text_input("주간 주요 이슈", value=curr_note)
                if st.form_submit_button("반영"):
                    target_ws.update_acell("F2", new_t); st.success("반영됨"); time.sleep(1); st.rerun()
            
            st.divider()
            new_name = st.text_input("프로젝트 명칭 변경", value=selected)
            if st.button("명칭 수정"):
                if new_name != selected:
                    target_ws.update_title(new_name); st.success("수정됨"); time.sleep(1); st.rerun()
            
            if st.button("🗑️ 이 프로젝트 삭제", type="primary"):
                if len(all_ws) > 1:
                    sh.del_worksheet(target_ws); st.warning("삭제됨"); time.sleep(1); st.rerun()
