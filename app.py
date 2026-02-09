## [PMS Revision History]
## 버전: Rev. 0.5.1 (Full Recovery)
## 업데이트 요약:
## 1. 🔐 로그인 보안: Password 인증 (Secrets 연동)
## 2. 🏠 통합 대시보드: 프로젝트별 주간 현황 브리핑 및 진척률 비교
## 3. 📊 차트 최적화: 시작일 순 정렬 및 차트 상단 년-월 표시 (side="top")
## 4. 🛠️ 프로젝트 관리: 신규 추가, 이름 변경, 삭제 기능 통합

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.5.1", page_icon="🏗️", layout="wide")

# --- [보안] 로그인 체크 함수 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.title("🏗️ PM 통합 공정 관리 시스템")
    st.subheader("보안을 위해 비밀번호를 입력해 주세요.")
    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log In"):
            if password == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 비밀번호가 틀렸습니다.")
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
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 인증 오류: {e}"); return None

# --- [기능] 프로젝트 관리 로직 ---
def create_new_project(sh, name):
    try:
        if name in [s.title for s in sh.worksheets()]: return False, "이미 존재하는 이름입니다."
        ws = sh.add_worksheet(title=name, rows="100", cols="20")
        ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        return True, "성공"
    except Exception as e: return False, str(e)

def rename_project(sh, old_name, new_name):
    try:
        if not new_name or new_name in [s.title for s in sh.worksheets()]: return False, "이름 오류 또는 중복"
        sh.worksheet(old_name).update_title(new_name)
        return True, "성공"
    except Exception as e: return False, str(e)

# --- 메인 실행 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = sh.worksheets()
    pjt_names = [s.title for s in all_ws]
    
    # [사이드바]
    st.sidebar.title("📁 PMO 프로젝트 센터")
    if st.sidebar.button("🔓 로그아웃"):
        st.session_state["password_correct"] = False
        st.rerun()
    
    menu = ["🏠 전체 대시보드"] + pjt_names
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)
    
    with st.sidebar.expander("➕ 프로젝트 신규 추가"):
        new_pjt = st.text_input("새 프로젝트명")
        if st.button("시트 생성"):
            if new_pjt:
                ok, msg = create_new_project(sh, new_pjt); (st.success("완료") if ok else st.error(msg)); time.sleep(1); st.rerun()

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드
    # ---------------------------------------------------------
    if selected == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        summary = []
        for ws in all_ws:
            try:
                df = pd.DataFrame(ws.get_all_records())
                prog = round(pd.to_numeric(df['진행률'], errors='coerce').mean(), 1) if not df.empty else 0
                note = df.iloc[0]['비고'] if not df.empty and '비고' in df.columns else "-"
                summary.append({"프로젝트명": ws.title, "진척률(%)": prog, "주간 주요 현황": note})
            except: continue
        
        if summary:
            sum_df = pd.DataFrame(summary)
            st.dataframe(sum_df, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True), use_container_width=True)

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트
    # ---------------------------------------------------------
    else:
        target_ws = sh.worksheet(selected)
        df_raw = pd.DataFrame(target_ws.get_all_records())
        st.title(f"🏗️ {selected}")
        t1, t2, t3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 현황 및 관리"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                # 시작일 기준 정렬
                df = df.sort_values(by='시작일', ascending=True)

                # 마일스톤
                ms = df[df['대분류'] == 'MILESTONE'].dropna(subset=['시작일'])
                if not ms.empty:
                    cols = st.columns(len(ms))
                    for i, (_, r) in enumerate(ms.iterrows()):
                        cols[i].metric(r['구분'], f"D{(r['시작일'].date()-datetime.date.today()).days:+d}")

                # Gantt 차트 (년-월 상단 표시)
                chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig.update_yaxes(autorange="reversed")
                    fig.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    fig.update_layout(height=500, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("데이터가 없습니다.")

        with t2:
            with st.form("in_f"):
                c1,c2,c3 = st.columns(3)
                sd=c1.date_input("시작일"); ed=c2.date_input("종료일"); cat=c3.selectbox("대분류", ["인허가", "설계", "토목", "전기", "MILESTONE"])
                name=st.text_input("공정명"); stat=st.selectbox("상태", ["예정","진행중","완료","지연"]); pct=st.number_input("진행률",0,100,0); note=st.text_area("비고")
                if st.form_submit_button("저장"):
                    target_ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, "PM팀"])
                    st.success("완료"); time.sleep(1); st.rerun()

        with t3:
            st.subheader("📢 주간 현황 업데이트")
            curr = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            with st.form("up_f"):
                new_t = st.text_input("주간 이슈", value=curr)
                if st.form_submit_button("반영"):
                    target_ws.update_acell("F2", new_t); st.success("반영됨"); time.sleep(1); st.rerun()
            st.divider()
            c_ren, c_del = st.columns(2)
            with c_ren:
                new_n = st.text_input("새 프로젝트명", value=selected)
                if st.button("명칭 변경"):
                    ok, m = rename_project(sh, selected, new_n); (st.success("변경됨") if ok else st.error(m)); time.sleep(1); st.rerun()
            with c_del:
                conf = st.checkbox(f"'{selected}' 삭제 확인")
                if st.button("시트 삭제", type="primary"):
                    if conf and len(all_ws)>1: sh.del_worksheet(target_ws); st.warning("삭제됨"); time.sleep(1); st.rerun()
