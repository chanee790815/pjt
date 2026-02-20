import streamlit as st
import pandas as pd
import datetime
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.2", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .weekly-box { background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; line-height: 1.6; color: #333; border: 1px solid #edf0f2; white-space: pre-wrap; }
    .history-box { background-color: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    .pm-tag { background-color: #f1f3f5; color: #495057; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-left: 10px; border: 1px solid #dee2e6; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.2) | 발전량 분석 엔진 복구 및 인코딩 오류 해결</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def check_login():
    if st.session_state.get("logged_in", False): return True
    st.title("🏗️ PM 통합 관리 시스템")
    with st.form("login"):
        u_id = st.text_input("ID")
        u_pw = st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 클라우드 연결 실패: {e}")
        return None

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: target_date = datetime.date.today()
    try:
        s = pd.to_datetime(start).date()
        e = pd.to_datetime(end).date()
        if pd.isna(s) or pd.isna(e): return 0.0
        if target_date < s: return 0.0
        if target_date > e: return 100.0
        total_days = (e - s).days
        if total_days <= 0: return 100.0
        passed_days = (target_date - s).days
        return min(100.0, max(0.0, (passed_days / total_days) * 100))
    except: return 0.0

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    cols = st.columns(2)
    for idx, p_name in enumerate(pjt_list):
        with cols[idx % 2]:
            try:
                ws = sh.worksheet(p_name)
                data = ws.get_all_values()
                df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 0 else pd.DataFrame()
                
                # I1: PM 이름, J2: 금주 업무, K2: 차주 업무
                pm_name = ws.acell('I1').value or "미지정"
                this_w = ws.acell('J2').value or "내용 없음"
                next_w = ws.acell('K2').value or "계획 없음"
                
                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                    avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1)
                else:
                    avg_act = 0.0; avg_plan = 0.0
                
                status_ui = "🟢 정상"
                c_style = "pjt-card risk-normal"
                if (avg_plan - avg_act) >= 10:
                    status_ui = "🔴 지연"
                    c_style = "pjt-card risk-high"
                elif avg_act >= 100: status_ui = "🔵 완료"
                
                st.markdown(f'''
                    <div class="{c_style}">
                        <h4>🏗️ {p_name} <span class="pm-tag">PM: {pm_name}</span> <span style="font-size:14px; float:right;">{status_ui}</span></h4>
                        <p style="font-size:13px; color:#666;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                        <div class="weekly-box"><b>[금주]</b> {this_w}<br><b>[차주]</b> {next_w}</div>
                    </div>
                ''', unsafe_allow_html=True)
                st.progress(min(1.0, max(0.0, avg_act/100)))
            except: pass

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        
        # 1) 담당 PM 편집 (I1 셀)
        current_pm = ws.acell('I1').value or ""
        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1:
            new_pm = st.text_input("프로젝트 담당 PM (I1 셀)", value=current_pm)
        with col_pm2:
            st.write("")
            if st.button("PM 성함 저장"):
                ws.update('I1', [[new_pm]])
                st.success("PM 정보가 업데이트되었습니다!")
        
        st.divider()

        # 데이터 로드
        data = ws.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 0 else pd.DataFrame()
        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)

        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        
        with tab1:
            try:
                cdf = df.copy()
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일'])
                if not cdf.empty:
                    fig = px.timeline(cdf, x_start="시작일", x_end="종료일", y="대분류", color="진행률", 
                                     color_continuous_scale='RdYlGn', range_color=[0, 100])
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
            except: st.warning("차트를 표시할 데이터가 부족합니다.")

        with tab3:
            st.subheader("📋 주간 업무 실시간 동기화 (J2, K2 셀)")
            this_val = ws.acell('J2').value or ""
            next_val = ws.acell('K2').value or ""
            with st.form("weekly_sync_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 (J2)", value=this_val, height=120)
                in_next = st.text_area("🔜 차주 주요 업무 (K2)", value=next_val, height=120)
                if st.form_submit_button("시트 데이터 업데이트"):
                    ws.update('J2', [[in_this]])
                    ws.update('K2', [[in_next]])
                    st.success("저장되었습니다!"); time.sleep(1); st.rerun()

        st.write("---")
        st.subheader("📝 상세 공정표 편집")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 변경사항 저장"):
            ws.clear()
            ws.update([edited.columns.values.tolist()] + edited.fillna("").astype(str).values.tolist())
            ws.update('I1', [[new_pm]]) # 보존
            ws.update('J2', [[in_this]])
            ws.update('K2', [[in_next]])
            st.success("데이터가 저장되었습니다!")

# 3. [복원] 일 발전량 및 일조 분석 검색
def view_solar(sh):
    st.title("☀️ 일 발전량 및 일조 분석")
    try:
        db_ws = sh.worksheet('Solar_DB')
        raw = db_ws.get_all_records()
        if not raw:
            st.info("데이터가 없습니다.")
            return
        
        df_db = pd.DataFrame(raw)
        df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
        df_db['발전시간'] = pd.to_numeric(df_db['발전시간'], errors='coerce').fillna(0)
        df_db['일사량합계'] = pd.to_numeric(df_db['일사량합계'], errors='coerce').fillna(0)
        df_db = df_db.dropna(subset=['날짜'])

        # 필터 레이아웃
        with st.expander("🔍 발전량 상세 검색 필터", expanded=True):
            f1, f2 = st.columns(2)
            with f1:
                locs = sorted(df_db['지점'].unique().tolist())
                sel_locs = st.multiselect("조회 지역 선택", locs, default=locs[:3] if len(locs)>3 else locs)
            with f2:
                dr = st.date_input("조회 기간", [df_db['날짜'].min().date(), df_db['날짜'].max().date()])

        mask = (df_db['지점'].isin(sel_locs))
        if len(dr) == 2:
            mask = mask & (df_db['날짜'].dt.date >= dr[0]) & (df_db['날짜'].dt.date <= dr[1])
        
        f_df = df_db[mask].sort_values('날짜')

        if not f_df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("평균 발전 시간", f"{f_df['발전시간'].mean():.2f} h")
            m2.metric("최대 발전량 지역", f_df.loc[f_df['발전시간'].idxmax(), '지점'])
            m3.metric("검색 데이터 수", f"{len(f_df)} 건")

            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(px.line(f_df, x='날짜', y='발전시간', color='지점', title="일별 발전 시간 추이"), use_container_width=True)
            with c2:
                avg_comp = f_df.groupby('지점')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(avg_comp, x='지점', y='발전시간', color='발전시간', title="지역별 평균 효율 비교"), use_container_width=True)
            
            st.subheader("📊 검색 결과 상세 내역")
            st.dataframe(f_df, use_container_width=True)
        else:
            st.warning("조건에 맞는 데이터가 없습니다.")

    except Exception as e:
        st.error(f"분석 엔진 로드 실패: {e}")

# 4. 경영지표 KPI
def view_kpi(sh):
    st.title("📉 경영 실적 및 KPI")
    try:
        df = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        st.table(df)
        if not df.empty and '실적' in df.columns:
            st.plotly_chart(px.pie(df, values='실적', names=df.columns[0], title="항목별 실적 비중"))
    except: st.warning("KPI 시트를 찾을 수 없습니다.")

# 5. 마스터 관리 (CRUD 복구)
def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 관리")
    t1, t2, t3, t4, t5 = st.tabs(["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 업로드", "📥 다운로드"])
    
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            new_ws = sh.add_worksheet(title=new_n, rows="100", cols="20")
            new_ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자", "금주업무", "PM", "차주업무"])
            st.success("생성 완료!"); st.rerun()
            
    with t2:
        target = st.selectbox("수정 대상", ["선택"] + pjt_list, key="ren")
        new_name = st.text_input("변경할 이름")
        if st.button("이름 변경") and target != "선택" and new_name:
            sh.worksheet(target).update_title(new_name)
            st.success("수정 완료!"); st.rerun()

    with t3:
        target_del = st.selectbox("삭제 대상", ["선택"] + pjt_list, key="del")
        conf = st.checkbox("영구 삭제에 동의합니다.")
        if st.button("삭제 수행") and target_del != "선택" and conf:
            sh.del_worksheet(sh.worksheet(target_del))
            st.success("삭제 완료!"); st.rerun()

    with t4:
        target_up = st.selectbox("업로드 대상", ["선택"] + pjt_list, key="up")
        file = st.file_uploader("엑셀 파일", type=['xlsx'])
        if target_up != "선택" and file and st.button("동기화"):
            df_up = pd.read_excel(file).fillna("").astype(str)
            ws = sh.worksheet(target_up); ws.clear()
            ws.update([df_up.columns.values.tolist()] + df_up.values.tolist())
            st.success("완료!")

    with t5:
        if st.button("📚 통합 백업 엑셀 생성"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for p in pjt_list:
                    try:
                        data = sh.worksheet(p).get_all_values()
                        pd.DataFrame(data[1:], columns=data[0]).to_excel(writer, index=False, sheet_name=p[:31])
                    except: pass
            st.download_button("📥 통합 파일 받기", output.getvalue(), f"Backup_{datetime.date.today()}.xlsx")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            sys_names = ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'Control_Center', 'Dashboard_Control', '통합 대시보드']
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
            
            st.sidebar.title("📁 PMO 메뉴")
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "마스터 설정"])
            
            if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            elif menu == "경영지표(KPI)": view_kpi(sh)
            elif menu == "마스터 설정": view_project_admin(sh, pjt_list)
            
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"DB 연결 실패: {e}")
