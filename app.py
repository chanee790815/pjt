import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 시스템", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("🚨 Streamlit Secrets 설정 확인이 필요합니다.")
            return None
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 인증 실패: {e}")
        return None

# --- [기능] 프로젝트 추가/삭제 로직 ---
def create_new_project(sh, name):
    try:
        if name in [s.title for s in sh.worksheets()]: return False, "이미 있는 이름입니다."
        ws = sh.add_worksheet(title=name, rows="100", cols="20")
        ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        return True, "성공"
    except Exception as e: return False, str(e)

def delete_project(sh, name):
    try:
        if len(sh.worksheets()) <= 1: return False, "마지막 시트는 삭제 불가합니다."
        sh.del_worksheet(sh.worksheet(name))
        return True, "성공"
    except Exception as e: return False, str(e)

# --- 메인 로직 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    # 실시간 시트 목록 가져오기
    pjt_list = [s.title for s in sh.worksheets()]
    
    # 사이드바 관리 메뉴
    st.sidebar.title("📁 PMO 프로젝트 센터")
    selected_pjt = st.sidebar.selectbox("🎯 관리 프로젝트 선택", pjt_list)
    
    st.sidebar.divider()
    
    # [복구된 기능] 프로젝트 목록 관리
    with st.sidebar.expander("🛠️ 프로젝트 목록 관리"):
        st.write("**[추가]**")
        new_name = st.text_input("새 프로젝트명", key="add_pjt")
        if st.button("신규 시트 생성"):
            if new_name:
                ok, msg = create_new_project(sh, new_name)
                if ok: st.success("생성 완료!"); time.sleep(1); st.rerun()
                else: st.error(msg)
        
        st.divider()
        st.write("**[삭제]**")
        del_name = st.selectbox("삭제 대상 선택", pjt_list, key="del_pjt")
        confirm = st.checkbox(f"'{del_name}' 영구 삭제 확인")
        if st.button("시트 삭제"):
            if confirm:
                ok, msg = delete_project(sh, del_name)
                if ok: st.warning("삭제 완료!"); time.sleep(1); st.rerun()
                else: st.error(msg)
    
    st.sidebar.divider()
    st.sidebar.info(f"현재 접속: **{selected_pjt}**")

    # 데이터 로드
    ws = sh.worksheet(selected_pjt)
    data = ws.get_all_records()
    df_raw = pd.DataFrame(data)

    st.title(f"🏗️ {selected_pjt} 공정 관리")

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 관리 및 수정"])

    with tab1:
        if not df_raw.empty:
            df = df_raw.copy()
            df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
            df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
            
            # 마일스톤
            ms = df[df['대분류'] == 'MILESTONE'].dropna(subset=['시작일'])
            if not ms.empty:
                st.subheader("🚩 핵심 마일스톤")
                cols = st.columns(len(ms))
                for i, (_, row) in enumerate(ms.iterrows()):
                    d_day = (row['시작일'].date() - datetime.date.today()).days
                    cols[i].metric(row['구분'], f"D{d_day:+d}", str(row['시작일'].date()))
            
            st.divider()
            
            # 차트
            chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
            if not chart_df.empty:
                fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("데이터를 등록하면 차트가 표시됩니다.")
            
            st.subheader("📋 전체 데이터")
            st.dataframe(df_raw, use_container_width=True)
        else:
            st.info("시트가 비어있습니다. '일정 등록' 탭을 이용하세요.")

    with tab2:
        st.subheader(f"📝 {selected_pjt} 일정 등록")
        with st.form("add_form"):
            c1, c2, c3 = st.columns(3)
            s_d = c1.date_input("시작일")
            e_d = c2.date_input("종료일")
            cat = c3.selectbox("대분류", ["인허가", "설계", "토목공사", "전기공사", "MILESTONE"])
            name = st.text_input("공정명")
            stat = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
            pct = st.number_input("진행률(%)", 0, 100, 0)
            pic = st.text_input("담당자")
            note = st.text_area("비고")
            if st.form_submit_button("저장"):
                ws.append_row([str(s_d), str(e_d), cat, name, stat, note, pct, pic])
                st.success("저장되었습니다!"); time.sleep(1); st.rerun()

    with tab3:
        st.subheader("⚙️ 수정 및 삭제")
        if not df_raw.empty:
            df_raw['select'] = df_raw['구분'] + " (" + df_raw['시작일'].astype(str) + ")"
            target = st.selectbox("항목 선택", df_raw['select'].tolist())
            idx = df_raw[df_raw['select'] == target].index[0]
            row = df_raw.iloc[idx]
            with st.form("edit_form"):
                st.write(f"수정 중: {row['구분']}")
                new_stat = st.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                new_pct = st.number_input("진행률", 0, 100, int(row['진행률']))
                u_btn, d_btn = st.columns(2)
                if u_btn.form_submit_button("수정"):
                    ws.update(f"E{idx+2}:G{idx+2}", [[new_stat, row['비고'], new_pct]])
                    st.success("수정 완료"); time.sleep(1); st.rerun()
                if d_btn.form_submit_button("삭제"):
                    ws.delete_rows(idx+2)
                    st.error("삭제 완료"); time.sleep(1); st.rerun()
