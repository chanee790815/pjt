import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.4.3", page_icon="🏗️", layout="wide")

# --- [인증] 로그인 체크 함수 ---
def check_password():
    """사용자가 올바른 비밀번호를 입력했는지 확인"""
    def password_entered():
        """비밀번호 확인 로직"""
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            st.session_state["logged_in_user"] = st.session_state["username"] # 로그인 유저 저장
            del st.session_state["password"]  
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 최초 로그인 화면
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 PMO 시스템 인증")
            st.text_input("사용자 ID", on_change=password_entered, key="username")
            st.text_input("비밀번호", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # 인증 실패 시 화면
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 PMO 시스템 인증")
            st.text_input("사용자 ID", on_change=password_entered, key="username")
            st.text_input("비밀번호", type="password", on_change=password_entered, key="password")
            st.error("😕 ID 또는 비밀번호가 틀렸습니다.")
        return False
    else:
        return True

# --- [연동] 구글 시트 연결 함수 ---
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
        st.error(f"🚨 구글 인증 오류: {e}")
        return None

# --- [기능] 프로젝트 관리 로직 ---
def create_new_project(sh, name):
    try:
        if name in [s.title for s in sh.worksheets()]: return False, "이미 존재하는 프로젝트명입니다."
        ws = sh.add_worksheet(title=name, rows="100", cols="20")
        ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        return True, "성공"
    except Exception as e: return False, str(e)

def rename_project(sh, old_name, new_name):
    try:
        if not new_name: return False, "새 이름을 입력하세요."
        if new_name in [s.title for s in sh.worksheets()]: return False, "이미 사용 중인 이름입니다."
        ws = sh.worksheet(old_name)
        ws.update_title(new_name)
        return True, "성공"
    except Exception as e: return False, str(e)

# --- 메인 실행부 ---
if check_password():
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            all_sheets = sh.worksheets()
            pjt_names = [s.title for s in all_sheets]
            
            # [사이드바]
            st.sidebar.title("📁 PMO 프로젝트 센터")
            st.sidebar.write(f"👤 접속: **{st.session_state.get('logged_in_user')}**님")
            
            if st.sidebar.button("로그아웃"):
                st.session_state["password_correct"] = False
                st.rerun()

            st.sidebar.divider()
            menu = ["🏠 전체 대시보드"] + pjt_names
            selected = st.sidebar.selectbox("🎯 메뉴 선택", menu)

            # 프로젝트 추가 기능 (관리자 권한 예시: admin만 보이게 설정 가능)
            with st.sidebar.expander("➕ 프로젝트 신규 추가"):
                new_pjt = st.text_input("새 프로젝트명", key="add_pjt")
                if st.button("시트 생성"):
                    if new_pjt:
                        ok, msg = create_new_project(sh, new_pjt)
                        if ok: st.success("생성 완료!"); time.sleep(1); st.rerun()
                        else: st.error(msg)

            # ---------------------------------------------------------
            # CASE 1: 전체 대시보드
            # ---------------------------------------------------------
            if selected == "🏠 전체 대시보드":
                st.title("📊 프로젝트 통합 대시보드")
                summary_list = []
                with st.spinner('전체 현황을 집계 중...'):
                    for ws in all_sheets:
                        try:
                            data = ws.get_all_records()
                            temp_df = pd.DataFrame(data)
                            prog, note, count = 0, "현황 없음", 0
                            if not temp_df.empty:
                                if '진행률' in temp_df.columns:
                                    temp_df['진행률'] = pd.to_numeric(temp_df['진행률'], errors='coerce').fillna(0)
                                    prog = round(temp_df['진행률'].mean(), 1)
                                if '비고' in temp_df.columns:
                                    note = temp_df.iloc[0]['비고'] if temp_df.iloc[0]['비고'] else "업데이트 예정"
                                count = len(temp_df)
                            summary_list.append({"프로젝트명": ws.title, "진척률(%)": prog, "주간 주요 현황": note, "공정수": count})
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

            # ---------------------------------------------------------
            # CASE 2: 개별 프로젝트 관리 (적서리 등)
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
                        df = df.sort_values(by='시작일', ascending=False) # 시작일 빠른 순 정렬
                        chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                        if not chart_df.empty:
                            st.plotly_chart(px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태"), use_container_width=True)
                        st.dataframe(df_raw, use_container_width=True)
                    else: st.info("💡 등록된 공정이 없습니다.")

                with t2:
                    with st.form("reg_form"):
                        c1,c2,c3 = st.columns(3)
                        sd=c1.date_input("시작일"); ed=c2.date_input("종료일")
                        cat=c3.selectbox("대분류", ["인허가", "설계", "토목공사", "전기공사", "MILESTONE"])
                        name=st.text_input("공정명")
                        stat=st.selectbox("상태", ["예정","진행중","완료","지연"])
                        pct=st.number_input("진행률(%)",0,100,0)
                        note=st.text_area("비고")
                        if st.form_submit_button("저장하기"):
                            target_ws.append_row([str(sd), str(ed), cat, name, stat, note, pct, st.session_state["logged_in_user"]])
                            st.success("저장 완료!"); time.sleep(1); st.rerun()

                with t3:
                    st.subheader("📢 주간 현황 업데이트")
                    curr = df_raw.iloc[0]['비고'] if not df_raw.empty and '비고' in df_raw.columns else ""
                    with st.form("week_form"):
                        new_txt = st.text_input("메인 장표용 주간 이슈", value=curr)
                        if st.form_submit_button("현황 반영하기"):
                            target_ws.update_acell("F2", new_txt)
                            st.success("업데이트 완료!"); time.sleep(1); st.rerun()
                    
                    st.divider()
                    st.subheader("🛠️ 프로젝트 설정")
                    col_rename, col_delete = st.columns(2)
                    
                    with col_rename:
                        st.write("**[🏷️ 명칭 변경]**")
                        with st.form("rename_form"):
                            new_name_input = st.text_input("새 이름", value=selected)
                            if st.form_submit_button("수정"):
                                if new_name_input != selected:
                                    ok, msg = rename_project(sh, selected, new_name_input)
                                    if ok: st.success("변경 완료!"); time.sleep(1); st.rerun()
                                    else: st.error(msg)

                    with col_delete:
                        st.write("**[🗑️ 프로젝트 삭제]**")
                        confirm_del = st.checkbox(f"'{selected}' 영구 삭제 확인")
                        if st.button("시트 삭제", type="primary"):
                            if confirm_del:
                                if len(all_sheets) > 1:
                                    sh.del_worksheet(target_ws)
                                    st.warning("삭제됨"); time.sleep(1); st.rerun()
                                else: st.error("최소 1개의 시트는 유지해야 합니다.")

        except Exception as e:
            st.error(f"데이터 통신 오류: {e}")


