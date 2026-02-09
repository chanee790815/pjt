import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.3.2", page_icon="🏗️", layout="wide")

# --- 구글 시트 연결 함수 ---
@st.cache_resource
def get_client():
    try:
        if "gcp_service_account" not in st.secrets:
            return None
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 인증 오류: {e}")
        return None

client = get_client()

# --- 메인 실행 ---
if client:
    try:
        sh = client.open('pms_db')
        all_sheets = sh.worksheets()
        pjt_names = [s.title for s in all_sheets]
        
        st.sidebar.title("📁 PMO 프로젝트 센터")
        menu = ["🏠 전체 대시보드"] + pjt_names
        selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)
        
        st.sidebar.divider()
        st.sidebar.info(f"접속 중: **{selected}**")

        # ---------------------------------------------------------
        # CASE 1: 전체 대시보드 (안정성 강화 버전)
        # ---------------------------------------------------------
        if selected == "🏠 전체 대시보드":
            st.title("📊 프로젝트 통합 대시보드")
            
            summary_list = []
            with st.spinner('데이터 취합 중...'):
                for ws in all_sheets:
                    try:
                        # 데이터 로드 (첫 행 헤더 포함)
                        data = ws.get_all_records()
                        temp_df = pd.DataFrame(data)
                        
                        p_name = ws.title
                        prog = 0
                        note = "현황 없음"
                        count = 0
                        
                        if not temp_df.empty:
                            # 진행률 숫자 변환 및 평균 계산
                            if '진행률' in temp_df.columns:
                                temp_df['진행률'] = pd.to_numeric(temp_df['진행률'], errors='coerce').fillna(0)
                                prog = round(temp_df['진행률'].mean(), 1)
                            # 첫 번째 행의 비고를 주간 현황으로
                            if '비고' in temp_df.columns and len(temp_df) > 0:
                                note = temp_df.iloc[0]['비고'] if temp_df.iloc[0]['비고'] else "업데이트 예정"
                            count = len(temp_df)
                            
                        summary_list.append({
                            "프로젝트명": p_name,
                            "진척률(%)": prog,
                            "주간 주요 현황": note,
                            "공정수": count
                        })
                    except Exception:
                        # 개별 시트 오류 시 건너뜀
                        continue
            
            if summary_list:
                sum_df = pd.DataFrame(summary_list)
                
                # 상단 대시보드 지표
                c1, c2, c3 = st.columns(3)
                c1.metric("총 프로젝트", f"{len(pjt_names)}개")
                c2.metric("평균 진척률", f"{round(sum_df['진척률(%)'].mean(), 1)}%")
                c3.metric("최고 진척", sum_df.loc[sum_df['진척률(%)'].idxmax(), '프로젝트명'])
                
                st.divider()
                
                # 주간 현황 테이블 (한 줄씩 요약)
                st.subheader("📋 프로젝트별 주간 브리핑")
                st.dataframe(sum_df[["프로젝트명", "진척률(%)", "주간 주요 현황"]], use_container_width=True, hide_index=True)
                
                # 비교 차트
                st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True), use_container_width=True)
            else:
                st.info("표시할 데이터가 없습니다.")

        # ---------------------------------------------------------
        # CASE 2: 개별 프로젝트 (차트 복구 및 입력)
        # ---------------------------------------------------------
        else:
            target_ws = sh.worksheet(selected)
            df_raw = pd.DataFrame(target_ws.get_all_records())
            
            st.title(f"🏗️ {selected}")
            t1, t2, t3 = st.tabs(["📊 공정표", "📝 일정 등록", "⚙️ 현황 관리"])
            
            with t1:
                if not df_raw.empty:
                    # 날짜 처리
                    df = df_raw.copy()
                    df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                    df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                    
                    # 마일스톤
                    ms = df[df['대분류'] == 'MILESTONE'].dropna(subset=['시작일'])
                    if not ms.empty:
                        cols = st.columns(len(ms))
                        for i, (_, row) in enumerate(ms.iterrows()):
                            dday = (row['시작일'].date() - datetime.date.today()).days
                            cols[i].metric(row['구분'], f"D{dday:+d}")
                    
                    # Gantt 차트
                    chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                    if not chart_df.empty:
                        st.plotly_chart(px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태"), use_container_width=True)
                    
                    st.dataframe(df_raw, use_container_width=True)
                else:
                    st.info("데이터를 등록해 주세요.")

            with t2:
                with st.form("in_f"):
                    c1,c2,c3 = st.columns(3)
                    sd=c1.date_input("시작일"); ed=c2.date_input("종료일"); cat=c3.selectbox("대분류", ["인허가", "설계", "토목", "전기", "MILESTONE"])
                    name=st.text_input("공정명"); stat=st.selectbox("상태", ["예정","진행중","완료","지연"]); pct=st.number_input("진행률",0,100,0); pic=st.text_input("담당"); note=st.text_area("비고")
                    if st.form_submit_button("저장"):
                        target_ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, pic])
                        st.success("저장 완료"); time.sleep(1); st.rerun()

            with t3:
                st.subheader("📢 주간 현황 업데이트")
                curr = df_raw.iloc[0]['비고'] if not df_raw.empty and '비고' in df_raw.columns else ""
                with st.form("up_f"):
                    new_txt = st.text_input("메인 장표용 주간 이슈", value=curr)
                    if st.form_submit_button("반영하기"):
                        target_ws.update_acell("F2", new_txt)
                        st.success("업데이트 완료"); time.sleep(1); st.rerun()
                
                st.divider()
                if st.button("🗑️ 이 프로젝트(시트) 삭제"):
                    if len(all_sheets) > 1:
                        sh.del_worksheet(target_ws)
                        st.warning("삭제되었습니다."); time.sleep(1); st.rerun()
                    else: st.error("마지막 시트는 삭제 불가")

    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
