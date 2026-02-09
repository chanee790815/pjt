## [PMS Revision History]
## 버전: Rev. 0.4.2
## 업데이트 요약:
## 1. 🏷️ 프로젝트 명칭 변경 기능 추가: 개별 프로젝트 관리 탭에서 시트 이름 수정 가능
## 2. 안정성 강화: 명칭 변경 시 사이드바 메뉴 및 데이터 즉시 동기화
## 3. 예외 처리: 중복된 이름이나 빈 이름으로 변경 방지 로직 포함

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.4.2", page_icon="🏗️", layout="wide")

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

# --- [기능] 프로젝트 추가/삭제/이름변경 로직 ---
def create_new_project(sh, name):
    try:
        if name in [s.title for s in sh.worksheets()]: return False, "이미 존재하는 프로젝트명입니다."
        ws = sh.add_worksheet(title=name, rows="100", cols="20")
        ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        return True, "성공"
    except Exception as e: return False, str(e)

def rename_project(sh, old_name, new_name):
    try:
        if not new_name: return False, "새 이름을 입력해 주세요."
        if new_name in [s.title for s in sh.worksheets()]: return False, "이미 사용 중인 이름입니다."
        ws = sh.worksheet(old_name)
        ws.update_title(new_name)
        return True, "성공"
    except Exception as e: return False, str(e)

# --- 메인 실행 로직 ---
client = get_client()
if client:
    try:
        sh = client.open('pms_db')
        all_sheets = sh.worksheets()
        pjt_names = [s.title for s in all_sheets]
        
        # [사이드바]
        st.sidebar.title("📁 PMO 프로젝트 센터")
        menu = ["🏠 전체 대시보드"] + pjt_names
        selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)
        
        st.sidebar.divider()

        # [신규 추가 기능]
        with st.sidebar.expander("➕ 프로젝트 신규 추가"):
            new_pjt = st.text_input("새 프로젝트명", key="add_pjt")
            if st.button("시트 생성"):
                if new_pjt:
                    ok, msg = create_new_project(sh, new_pjt)
                    if ok:
                        st.success("생성 완료!"); time.sleep(1); st.rerun()
                    else: st.error(msg)
        
        st.sidebar.divider()
        st.sidebar.info(f"접속 중: **{selected}**")

        # ---------------------------------------------------------
        # CASE 1: 전체 대시보드
        # ---------------------------------------------------------
        if selected == "🏠 전체 대시보드":
            st.title("📊 프로젝트 통합 대시보드")
            summary_list = []
            
            with st.spinner('데이터를 집계 중입니다...'):
                for ws in all_sheets:
                    try:
                        data = ws.get_all_records()
                        temp_df = pd.DataFrame(data)
                        p_name = ws.title
                        prog, note, count = 0, "현황 없음", 0
                        
                        if not temp_df.empty:
                            if '진행률' in temp_df.columns:
                                temp_df['진행률'] = pd.to_numeric(temp_df['진행률'], errors='coerce').fillna(0)
                                prog = round(temp_df['진행률'].mean(), 1)
                            if '비고' in temp_df.columns:
                                note = temp_df.iloc[0]['비고'] if temp_df.iloc[0]['비고'] else "업데이트 예정"
                            count = len(temp_df)
                            
                        summary_list.append({"프로젝트명": p_name, "진척률(%)": prog, "주간 주요 현황": note, "공정수": count})
                    except: continue

            if summary_list:
                sum_df = pd.DataFrame(summary_list)
                c1, c2, c3 = st.columns(3)
                c1.metric("총 프로젝트", f"{len(pjt_names)}개")
                c2.metric("평균 진척률", f"{round(sum_df['진척률(%)'].mean(), 1)}%")
                c3.metric("최고 진척", sum_df.loc[sum_df['진척률(%)'].idxmax(), '프로젝트명'])
                
                st.divider()
                st.subheader("📋 프로젝트별 주간 브리핑")
                st.dataframe(sum_df[["프로젝트명", "진척률(%)", "주간 주요 현황"]], use_container_width=True, hide_index=True)
                st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률(%)", color="진척률(%)", text_auto=True), use_container_width=True)
            else:
                st.info("분석할 데이터가 없습니다.")

        # ---------------------------------------------------------
        # CASE 2: 개별 프로젝트 관리
        # ---------------------------------------------------------
        else:
            target_ws = sh.worksheet(selected)
            df_raw = pd.DataFrame(target_ws.get_all_records())
            st.title(f"🏗️ {selected}")
            t1, t2, t3 = st.tabs(["📊 공정표", "📝 일정 등록", "⚙️ 현황 및 관리"])
            
            with t1:
                if not df_raw.empty:
                    df = df_raw.copy()
                    df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                    df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                    chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                    if not chart_df.empty:
                        st.plotly_chart(px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태"), use_container_width=True)
                    st.dataframe(df_raw, use_container_width=True)
                else:
                    st.info("💡 등록된 공정이 없습니다.")

            with t2:
                with st.form("reg_form"):
                    c1,c2,c3 = st.columns(3)
                    sd=c1.date_input("시작일"); ed=c2.date_input("종료일"); cat=c3.selectbox("대분류", ["인허가", "설계", "토목공사", "전기공사", "MILESTONE"])
                    name=st.text_input("공정명"); stat=st.selectbox("상태", ["예정","진행중","완료","지연"]); pct=st.number_input("진행률(%)",0,100,0); note=st.text_area("비고")
                    if st.form_submit_button("저장하기"):
                        target_ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, "PM팀"])
                        st.success("저장 완료!"); time.sleep(1); st.rerun()

            with t3:
                # 1. 주간 현황 업데이트
                st.subheader("📢 주간 현황 업데이트")
                curr = df_raw.iloc[0]['비고'] if not df_raw.empty and '비고' in df_raw.columns else ""
                with st.form("week_form"):
                    new_txt = st.text_input("메인 장표용 주간 이슈", value=curr)
                    if st.form_submit_button("현황 반영하기"):
                        target_ws.update_acell("F2", new_txt)
                        st.success("업데이트 완료!"); time.sleep(1); st.rerun()
                
                st.divider()

                # 2. 프로젝트 명칭 변경 및 삭제 섹션
                st.subheader("🛠️ 프로젝트 설정")
                
                col_rename, col_delete = st.columns(2)
                
                with col_rename:
                    st.write("**[🏷️ 명칭 변경]**")
                    with st.form("rename_form"):
                        new_name_input = st.text_input("변경할 새 이름", value=selected)
                        if st.form_submit_button("이름 수정"):
                            if new_name_input != selected:
                                ok, msg = rename_project(sh, selected, new_name_input)
                                if ok:
                                    st.success(f"'{new_name_input}'으로 변경되었습니다.")
                                    time.sleep(1); st.rerun()
                                else: st.error(msg)
                            else: st.warning("현재와 동일한 이름입니다.")

                with col_delete:
                    st.write("**[🗑️ 프로젝트 삭제]**")
                    confirm_del = st.checkbox(f"'{selected}' 프로젝트 영구 삭제")
                    if st.button("해당 시트 삭제", type="primary"):
                        if confirm_del:
                            if len(all_sheets) > 1:
                                sh.del_worksheet(target_ws)
                                st.warning("삭제되었습니다."); time.sleep(1); st.rerun()
                            else: st.error("마지막 시트는 삭제할 수 없습니다.")
                        else: st.info("삭제하려면 위 체크박스를 선택하세요.")

    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
