## [PMS Revision History]
## 버전: Rev. 0.7.7 (Performance & API Stability)
## 업데이트 요약:
## 1. 🚀 API 호출 최적화: 시트 목록 조회 로직에 st.cache_data 적용하여 연속 클릭 시 발생하는 API Quota Error 방지
## 2. 🛡️ 초기화 로직 강화: 시스템 시트(weekly_history) 생성 및 확인 과정을 안정적인 함수 구조로 개편
## 3. 🔄 내비게이션 유지: 대시보드 버튼 클릭 시 상세 페이지로 즉시 이동하는 기능 완벽 유지
## 4. 📱 모바일 UI 및 보안: 기존의 모바일 최적화 및 다중 계정 로그인 로직 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.7.7", page_icon="🏗️", layout="wide")

# --- [UI] 모바일 대응 커스텀 CSS ---
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    @media (max-width: 640px) {
        .main .block-container {
            padding-top: 0.8rem !important; 
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        .main .block-container h1 {
            font-size: 1.25rem !important;
            line-height: 1.3 !important;
            margin-bottom: 1rem !important;
        }
        .stButton button {
            height: 48px !important;
            font-size: 15px !important;
            font-weight: 600 !important;
        }
    }
    .stButton button {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
        background-color: white;
    }
    .stButton button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- [보안] 로그인 및 로그아웃 체크 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True
    
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
    return False

def logout():
    st.session_state["password_correct"] = False
    st.session_state["user_id"] = None
    st.session_state["selected_menu"] = "🏠 전체 대시보드"
    if "nav_menu" in st.session_state:
        del st.session_state["nav_menu"]
    st.rerun()

if not check_password():
    st.stop()

# --- 구글 시트 연결 및 캐싱 로직 ---
@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(
            key_dict, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 API 인증 오류: {e}"); return None

# 시트 목록을 불러오는 과정을 캐싱하여 연속 클릭 시 에러 방지 (1분 유지)
@st.cache_data(ttl=60)
def get_project_list(_client):
    try:
        sh = _client.open('pms_db')
        forbidden = ['weekly_history', 'conflict', 'Sheet1']
        all_ws = [ws.title for ws in sh.worksheets() if not any(k in ws.title for k in forbidden)]
        return all_ws
    except:
        return []

client = get_client()

if client:
    try:
        sh = client.open('pms_db')
        
        # 캐싱된 프로젝트 리스트 사용
        pjt_names = get_project_list(client)
        
        # 시스템 시트(weekly_history) 초기화 로직 (안전한 에러 핸들링)
        try:
            hist_ws = sh.worksheet('weekly_history')
        except gspread.exceptions.WorksheetNotFound:
            # 시트가 없는 경우에만 새로 생성
            hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
            hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])
        except Exception as e:
            # 기타 API 오류 발생 시 캐시된 리소스를 사용하거나 경고 표시
            st.warning("주간 기록을 불러오는 중 API 지연이 발생했습니다. 잠시 후 새로고침해 주세요.")
            hist_ws = None

        if "selected_menu" not in st.session_state:
            st.session_state["selected_menu"] = "🏠 전체 대시보드"

        # 사이드바 구성
        st.sidebar.title("📁 PMO 센터")
        st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}** 님")
        
        menu = ["🏠 전체 대시보드"] + pjt_names
        
        if st.session_state["selected_menu"] not in menu:
            st.session_state["selected_menu"] = "🏠 전체 대시보드"
            
        selected = st.sidebar.selectbox(
            "🎯 메뉴 선택", 
            menu, 
            index=menu.index(st.session_state["selected_menu"]), 
            key="nav_menu"
        )
        st.session_state["selected_menu"] = selected

        with st.sidebar.expander("➕ 프로젝트 추가"):
            new_name = st.text_input("새 프로젝트 명칭")
            if st.button("시트 생성"):
                if new_name and new_name not in pjt_names:
                    new_ws = sh.add_worksheet(title=new_name, rows="100", cols="20")
                    new_ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                    st.cache_data.clear() # 새 프로젝트 생성 시 캐시 삭제
                    st.success(f"'{new_name}' 생성 완료!"); time.sleep(1); st.rerun()

        st.sidebar.markdown("---")
        if st.sidebar.button("🔓 로그아웃"):
            logout()

        # ---------------------------------------------------------
        # CASE 1: 전체 대시보드
        # ---------------------------------------------------------
        if st.session_state["selected_menu"] == "🏠 전체 대시보드":
            st.title("📊 프로젝트 통합 대시보드")
            
            # 히스토리 데이터 로드 (에러 방지용 빈 데이터프레임 처리)
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])
            if hist_ws:
                try:
                    hist_data = pd.DataFrame(hist_ws.get_all_records())
                except: pass

            summary = []
            for name in pjt_names:
                try:
                    ws = sh.worksheet(name)
                    data = ws.get_all_records()
                    p_df = pd.DataFrame(data)
                    prog = 0
                    if not p_df.empty and '진행률' in p_df.columns:
                        prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                    
                    note = "최신 브리핑 데이터가 없습니다."
                    if not hist_data.empty:
                        latest = hist_data[hist_data['프로젝트명'] == name].tail(1)
                        if not latest.empty: note = latest.iloc[0]['주요현황']
                    
                    summary.append({"프로젝트명": name, "진척률": prog, "최신현황": note})
                except: continue
            
            if summary:
                st.divider()
                for idx, row in enumerate(summary):
                    with st.container():
                        if st.button(f"📂 {row['프로젝트명']}", key=f"btn_{idx}", use_container_width=True):
                            st.session_state["selected_menu"] = row['프로젝트명']
                            st.session_state["nav_menu"] = row['프로젝트명']
                            st.rerun()
                        
                        c1, c2 = st.columns([4, 6])
                        c1.markdown(f"**진척률: {row['진척률']}%**")
                        c2.progress(float(row['진척률'] / 100))
                        st.info(f"{row['최신현황']}")
                    st.write("")
                
                st.divider()
                sum_df = pd.DataFrame(summary)
                fig_main = px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True, title="프로젝트별 진도율 비교")
                st.plotly_chart(fig_main, use_container_width=True, config={'staticPlot': True})

        # ---------------------------------------------------------
        # CASE 2: 프로젝트 상세 관리
        # ---------------------------------------------------------
        else:
            p_name = st.session_state["selected_menu"]
            target_ws = sh.worksheet(p_name)
            data_all = target_ws.get_all_records()
            df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
            
            st.title(f"🏗️ {p_name} 관리")
            t1, t2, t3, t4 = st.tabs(["📊 공정표", "📝 등록", "📢 현황보고", "📜 히스토리"])

            with t1:
                if not df_raw.empty:
                    df = df_raw.copy()
                    df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                    df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                    df = df.sort_values(by='시작일', ascending=True)
                    
                    chart_df = df[df['대분류']!='MILESTONE'].dropna(subset=['시작일', '종료일'])
                    if not chart_df.empty:
                        fig_detail = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                        fig_detail.update_yaxes(autorange="reversed")
                        fig_detail.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                        st.plotly_chart(fig_detail, use_container_width=True, config={'staticPlot': True})
                    
                    st.subheader("📋 전체 공정 리스트")
                    st.dataframe(df_raw, use_container_width=True)
                    
                    with st.expander("🔍 특정 항목 빠르게 수정"):
                        edit_idx = st.selectbox("수정할 행 번호 선택", df_raw.index)
                        with st.form(f"quick_edit_{edit_idx}"):
                            row = df_raw.iloc[edit_idx]
                            col1, col2 = st.columns(2)
                            new_s = col1.selectbox("상태 변경", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                            new_p = col2.number_input("진행률(%)", 0, 100, int(row['진행률']))
                            new_n = st.text_input("비고 수정", value=row['비고'])
                            if st.form_submit_button("시트에 반영"):
                                target_ws.update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                                st.toast("업데이트 성공!"); time.sleep(0.5); st.rerun()

            with t2:
                st.subheader("📝 신규 일정 등록")
                with st.form("new_schedule_form"):
                    c1, c2 = st.columns(2)
                    sd = c1.date_input("시작일")
                    ed = c2.date_input("종료일")
                    cat = st.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "기타"])
                    name = st.text_input("상세 공정명")
                    stat = st.selectbox("초기 상태", ["예정", "진행중", "완료"])
                    pct = st.number_input("초기 진행률(%)", 0, 100, 0)
                    if st.form_submit_button("공정표에 추가"):
                        target_ws.append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                        st.success("새 일정이 추가되었습니다."); time.sleep(0.5); st.rerun()

            with t3:
                st.subheader("📢 주간 현황 보고 업데이트")
                with st.form("update_report_form"):
                    new_status = st.text_area("이번 주 주요 활동 및 이슈 사항을 입력하세요.")
                    if st.form_submit_button("저장 및 대시보드 반영"):
                        if hist_ws:
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            hist_ws.append_row([timestamp, p_name, new_status, st.session_state['user_id']])
                            st.success("현황이 저장되었습니다."); time.sleep(0.5); st.rerun()
                        else:
                            st.error("히스토리 시트 연결에 실패했습니다. 잠시 후 시도해 주세요.")

            with t4:
                st.subheader("📜 과거 기록 조회")
                if hist_ws:
                    h_data = pd.DataFrame(hist_ws.get_all_records())
                    if not h_data.empty:
                        filtered_h = h_data[h_data['프로젝트명'] == p_name].iloc[::-1]
                        if filtered_h.empty:
                            st.info("아직 기록된 히스토리가 없습니다.")
                        else:
                            for _, hr in filtered_h.iterrows():
                                with st.expander(f"📅 {hr['날짜']} | 작성자: {hr['작성자']}"):
                                    st.write(hr['주요현황'])
                else:
                    st.info("과거 기록을 불러올 수 없습니다.")
                                
    except Exception as e:
        st.error("🚨 구글 시트('pms_db')를 열 수 없습니다.")
        st.info(f"""
        **해결 방법:**
        1. 구글 스프레드시트 이름이 정확히 **pms_db** 인지 확인하세요.
        2. 아래의 서비스 계정 이메일을 복사하여, 구글 시트의 **[공유]** 버튼을 누르고 **편집자** 권한으로 추가해 주세요.
        
        **서비스 계정 이메일:**
        `{st.secrets["gcp_service_account"]["client_email"]}`
        """)
        st.warning(f"상세 에러 내용: {e}")
