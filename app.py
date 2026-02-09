## [PMS Revision History]
## 버전: Rev. 0.3.1 (차트 복구 및 주간 현황 통합)
## 업데이트 요약:
## 1. 개별 프로젝트 차트(Gantt) 출력 로직 복구 및 강화
## 2. 메인 대시보드 내 프로젝트별 '주간 주요 현황' 브리핑 기능 유지
## 3. MILESTONE과 일반 공정을 분리하여 가독성 증대

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.3.1", page_icon="🏗️", layout="wide")

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
    # CASE 1: 전체 대시보드 (주간 현황 요약표 포함)
    # ---------------------------------------------------------
    if selected_pjt == "🏠 전체 대시보드":
        st.title("📊 PMO 통합 프로젝트 대시보드")
        
        summary_data = []
        with st.spinner('전체 현황을 집계 중입니다...'):
            for pjt_name in pjt_list_raw:
                ws = sh.worksheet(pjt_name)
                df = pd.DataFrame(ws.get_all_records())
                
                if not df.empty:
                    df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                    # 비고(F열)의 첫 번째 행 데이터를 주간 요약으로 사용
                    weekly_msg = df.iloc[0]['비고'] if '비고' in df.columns else "-"
                    
                    summary_data.append({
                        "프로젝트명": pjt_name,
                        "진척률(%)": round(df['진행률'].mean(), 1),
                        "주간 주요 현황": weekly_msg,
                        "전체 공정수": len(df)
                    })
        
        if summary_data:
            sum_df = pd.DataFrame(summary_data)
            
            # 상단 핵심 지표
            m1, m2, m3 = st.columns(3)
            m1.metric("관리 프로젝트", f"{len(pjt_list_raw)}개")
            m2.metric("평균 진척률", f"{round(sum_df['진척률(%)'].mean(), 1)}%")
            m3.metric("최고 진척", sum_df.loc[sum_df['진척률(%)'].idxmax(), '프로젝트명'])
            
            st.divider()
            
            # 주간 브리핑 장표
            st.subheader("📋 프로젝트별 주간 브리핑")
            st.dataframe(sum_df, use_container_width=True, hide_index=True)
            
            # 진척률 비교 차트
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True, title="프로젝트별 진척도 비교"), use_container_width=True)
        else:
            st.info("데이터가 포함된 프로젝트가 없습니다.")

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트 상세 관리
    # ---------------------------------------------------------
    else:
        ws = sh.worksheet(selected_pjt)
        df_raw = pd.DataFrame(ws.get_all_records())
        st.title(f"🏗️ {selected_pjt} 상세 현황")

        tab1, tab2, tab3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 주간 현황 및 관리"])

        with tab1:
            if not df_raw.empty:
                df = df_raw.copy()
                # 날짜 변환 (에러 시 NaT 처리)
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                
                # 1. 마일스톤 섹션
                ms = df[df['대분류'] == 'MILESTONE'].dropna(subset=['시작일'])
                if not ms.empty:
                    st.subheader("🚩 핵심 마일스톤")
                    cols = st.columns(len(ms))
                    for i, (_, row) in enumerate(ms.iterrows()):
                        d_day = (row['시작일'].date() - datetime.date.today()).days
                        cols[i].metric(row['구분'], f"D{d_day:+d}", str(row['시작일'].date()))
                
                st.divider()

                # 2. Gantt 차트 섹션 (날짜가 정상인 데이터만)
                chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    st.subheader("📈 프로젝트 타임라인 (Gantt)")
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig.update_yaxes(autorange="reversed")
                    fig.update_layout(height=450, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("💡 일반 공정 데이터가 없어 차트를 표시할 수 없습니다.")

                # 3. 상세 테이블
                st.subheader("📋 전체 데이터 리스트")
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("입력된 데이터가 없습니다. '일정 등록' 탭을 이용해 주세요.")

        with tab2:
            st.subheader("📝 신규 일정 등록")
            with st.form("add_form"):
                c1, c2, c3 = st.columns(3)
                sd = c1.date_input("시작일")
                ed = c2.date_input("종료일")
                cat = c3.selectbox("대분류", ["인허가", "설계", "토목공사", "전기공사", "MILESTONE"])
                name = st.text_input("공정명 (구분)")
                stat = st.selectbox("진행상태", ["예정", "진행중", "완료", "지연"])
                pct = st.number_input("진행률 (%)", 0, 100, 0)
                pic = st.text_input("담당자")
                note = st.text_area("비고")
                if st.form_submit_button("시트에 저장"):
                    ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, pic])
                    st.success("저장되었습니다!"); time.sleep(1); st.rerun()

        with tab3:
            st.subheader("📢 주간 현황 업데이트 (메인 대시보드용)")
            current_note = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            with st.form("weekly_msg"):
                new_msg = st.text_input("메인 장표에 표시할 이번 주 이슈", value=current_note)
                if st.form_submit_button("현황 반영하기"):
                    ws.update_acell("F2", new_msg) # F열(비고)의 첫 칸 업데이트
                    st.success("대시보드에 반영되었습니다."); time.sleep(1); st.rerun()
            
            st.divider()
            st.subheader("🛠️ 데이터 관리 (수정 및 삭제)")
            if not df_raw.empty:
                df_raw['sel'] = df_raw['구분'] + " (" + df_raw['시작일'].astype(str) + ")"
                target = st.selectbox("수정 대상 선택", df_raw['sel'].tolist())
                idx = df_raw[df_raw['sel'] == target].index[0]
                row = df_raw.iloc[idx]
                with st.form("edit_form"):
                    u_stat = st.selectbox("상태 변경", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                    u_pct = st.number_input("진행률 변경", 0, 100, int(row['진행률']))
                    u_note = st.text_area("비고 수정", value=row['비고'])
                    if st.form_submit_button("업데이트 완료"):
                        ws.update(f"E{idx+2}:G{idx+2}", [[u_stat, u_note, u_pct]])
                        st.success("수정되었습니다."); time.sleep(1); st.rerun()
