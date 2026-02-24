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
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.15", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    /* 메인 제목 반응형 최적화 */
    h1 {
        font-size: clamp(1.5rem, 6vw, 2.5rem) !important; 
        word-break: keep-all !important; 
        line-height: 1.3 !important;
    }
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(128, 128, 128, 0.15); backdrop-filter: blur(5px); text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    
    /* 박스 디자인 (반투명 회색 배경) */
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 8px 10px; border-radius: 6px; margin-top: 4px; font-size: 12px; line-height: 1.4; border: 1px solid rgba(128, 128, 128, 0.2); white-space: pre-wrap; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    
    /* 태그 및 뱃지 */
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
    /* [핵심] 컴팩트 버튼 디자인 */
    div[data-testid="stButton"] button {
        min-height: 26px !important;
        height: 26px !important;
        padding: 0px 4px !important;
        font-size: 11.5px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        margin: 0 !important;
        margin-top: 2px !important;
        width: 100% !important;
    }
    
    /* 진행바 마진 최적화 */
    div[data-testid="stProgressBar"] { margin-bottom: 0px !important; margin-top: 5px !important; }
    
    /* ========================================================= */
    /* [중요] 모바일 세로 모드에서 버튼이 밑으로 떨어지는 현상 강제 차단 */
    /* ========================================================= */
    @media (max-width: 768px) {
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important; /* 강제 가로 배치 */
            flex-wrap: nowrap !important;   /* 줄바꿈 금지 */
            align-items: flex-start !important; /* 위쪽 정렬 */
            gap: 5px !important;
        }
        /* 제목 부분 영역 확보 */
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            width: calc(100% - 80px) !important;
            flex: 1 1 auto !important;
            min-width: 0 !important;
        }
        /* 버튼 부분 영역 고정 */
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
            width: 75px !important;
            flex: 0 0 75px !important;
            min-width: 75px !important;
        }
    }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.15) | 담당자(H열) 삭제 및 PM 데이터 매핑 완료</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def safe_api_call(func, *args, **kwargs):
    """API 할당량 초과(429) 방지를 위한 자동 재시도 함수"""
    retries = 5
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and i < retries - 1:
                time.sleep(2 ** i)
                continue
            else:
                raise e

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

# 콜백 함수: 하이퍼링크처럼 상세페이지로 부드럽게 이동
def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    cols = st.columns(2)
    for idx, p_name in enumerate(pjt_list):
        with cols[idx % 2]:
            with st.container(border=True):
                try:
                    ws = safe_api_call(sh.worksheet, p_name)
                    data = safe_api_call(ws.get_all_values)
                    
                    pm_name = "미지정"
                    this_w = "금주 실적 미입력"
                    next_w = "차주 계획 미입력"
                    
                    if len(data) > 0:
                        # [수정됨] 이제 A~G (7개 열)만 공정 데이터로 읽어옵니다.
                        header = data[0][:7]
                        df = pd.DataFrame([r[:7] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
                        
                        # [수정됨] 담당자가 빠졌으므로 PM은 H열(index 7), 금주는 I열(index 8), 차주는 J열(index 9)입니다.
                        if len(data) > 1 and len(data[1]) > 7 and str(data[1][7]).strip(): pm_name = str(data[1][7]).strip()
                        if len(data) > 1 and len(data[1]) > 8 and str(data[1][8]).strip(): this_w = str(data[1][8]).strip()
                        if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip(): next_w = str(data[1][9]).strip()
                    else:
                        df = pd.DataFrame()

                    if not df.empty and '진행률' in df.columns:
                        avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                        avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1)
                    else:
                        avg_act = 0.0; avg_plan = 0.0
                    
                    status_ui = "🟢 정상"
                    b_style = "status-normal"
                    if (avg_plan - avg_act) >= 10:
                        status_ui = "🔴 지연"
                        b_style = "status-delay"
                    elif avg_act >= 100: 
                        status_ui = "🔵 완료"
                        b_style = "status-done"
                    
                    h_col1, h_col2 = st.columns([7.5, 2.5], gap="small")
                    
                    with h_col1:
                        st.markdown(f"""
                            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 2px;">
                                <h4 style="font-weight:700; margin:0; font-size:clamp(13.5px, 3.5vw, 16px); word-break:keep-all; line-height:1.2;">
                                    🏗️ {p_name}
                                </h4>
                                <span class="pm-tag" style="margin:0;">PM: {pm_name}</span>
                                <span class="status-badge {b_style}" style="margin:0;">{status_ui}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        
                    with h_col2:
                        st.button(
                            "🔍 상세", 
                            key=f"btn_go_{p_name}", 
                            on_click=navigate_to_project, 
                            args=(p_name,), 
                            use_container_width=True
                        )
                    
                    st.markdown(f'''
                        <div style="margin-bottom:4px; margin-top:2px;">
                            <p style="font-size:12.5px; opacity: 0.7; margin-top:0; margin-bottom:4px;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                            <div class="weekly-box" style="margin-top:0;"><b>[금주]</b> {this_w}<br><b>[차주]</b> {next_w}</div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    st.progress(min(1.0, max(0.0, avg_act/100)))
                    
                except Exception as e:
                    st.warning(f"'{p_name}' 데이터를 로드하지 못했습니다.")

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list, key="selected_pjt")
    
    if selected_pjt != "선택":
        ws = safe_api_call(sh.worksheet, selected_pjt)
        data = safe_api_call(ws.get_all_values)
        
        current_pm = ""
        this_val = ""
        next_val = ""
        
        if len(data) > 0:
            # [수정됨] 편집 표의 헤더는 A~G (7개)
            header = data[0][:7]
            df = pd.DataFrame([r[:7] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
            
            # [수정됨] 인덱스 조정: H(7), I(8), J(9)
            if len(data) > 1 and len(data[1]) > 7: current_pm = str(data[1][7]).strip()
            if len(data) > 1 and len(data[1]) > 8: this_val = str(data[1][8]).strip()
            if len(data) > 1 and len(data[1]) > 9: next_val = str(data[1][9]).strip()
        else:
            df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"])

        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)

        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1:
            # [수정됨] H2 셀에서 PM 이름을 받아옵니다.
            new_pm = st.text_input("프로젝트 담당 PM (H2 셀)", value=current_pm)
        with col_pm2:
            st.write("")
            if st.button("PM 성함 저장"):
                safe_api_call(ws.update, 'H2', [[new_pm]])
                st.success("PM이 업데이트되었습니다!")
        
        st.divider()

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

        with tab2:
            try:
                sdf = df.copy()
                sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
                sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    min_d, max_d = sdf['시작일'].min(), sdf['종료일'].max()
                    d_range = pd.date_range(min_d, max_d, freq='W-MON').date.tolist()
                    p_trend = [sdf.apply(lambda r: calc_planned_progress(r['시작일'], r['종료일'], d), axis=1).mean() for d in d_range]
                    a_prog = pd.to_numeric(sdf['진행률'], errors='coerce').fillna(0).mean()
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=[d.strftime("%Y-%m-%d") for d in d_range], y=p_trend, mode='lines+markers', name='계획'))
                    fig_s.add_trace(go.Scatter(x=[datetime.date.today().strftime("%Y-%m-%d")], y=[a_prog], mode='markers', name='현재 실적', marker=dict(size=12, color='red', symbol='star')))
                    fig_s.update_layout(title="진척률 추이 (S-Curve)", yaxis_title="진척률(%)")
                    st.plotly_chart(fig_s, use_container_width=True)
            except: pass

        with tab3:
            st.subheader("📋 최근 주간 업무 이력")
            try:
                h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                h_data = safe_api_call(h_ws.get_all_records)
                h_df = pd.DataFrame(h_data)
                if not h_df.empty:
                    h_df['프로젝트명'] = h_df['프로젝트명'].astype(str).str.strip()
                    p_match = h_df[h_df['프로젝트명'] == selected_pjt.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        st.markdown(f"""
                        <div class="history-box">
                            <p style="font-size:14px; opacity: 0.7; margin-bottom:10px;">📅 <b>최종 보고일:</b> {latest.get('날짜', '-')}</p>
                            <p style="margin-bottom:12px;"><b>✔️ 금주 주요 업무:</b><br>{latest.get('금주업무', latest.get('주요현황', '-'))}</p>
                            <p style="margin-bottom:0;"><b>🔜 차주 주요 업무:</b><br>{latest.get('차주업무', '-')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else: st.info("아직 등록된 주간 업무 기록이 없습니다.")
            except: st.warning("이력 데이터를 불러오는 중 오류가 발생했습니다.")

            st.divider()

            # [수정됨] I2, J2 셀 업데이트
            st.subheader("📝 주간 업무 작성 및 동기화 (I2, J2 셀 & 히스토리)")
            with st.form("weekly_sync_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 (I2)", value=this_val, height=120)
                in_next = st.text_area("🔜 차주 주요 업무 (J2)", value=next_val, height=120)
                if st.form_submit_button("시트 데이터 업데이트 및 이력 저장"):
                    safe_api_call(ws.update, 'I2', [[in_this]])
                    safe_api_call(ws.update, 'J2', [[in_next]])
                    try:
                        h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                        safe_api_call(h_ws.append_row, [datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                    except: pass
                    st.success("성공적으로 업데이트 및 저장되었습니다!"); time.sleep(1); st.rerun()

        st.write("---")
        # [수정됨] 편집 영역은 A~G열입니다.
        st.subheader("📝 상세 공정표 편집 (A~G열 전용)")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 변경사항 전체 저장"):
            full_data = []
            header_7 = edited.columns.values.tolist()[:7]
            while len(header_7) < 7: header_7.append("")
            
            # [수정됨] 첫 행 헤더 구성 (A~G + H:PM, I:금주, J:차주)
            full_data.append(header_7 + ["PM", "금주", "차주"])
            
            edited_rows = edited.fillna("").astype(str).values.tolist()
            if len(edited_rows) > 0:
                for i, r in enumerate(edited_rows):
                    r_7 = r[:7]
                    while len(r_7) < 7: r_7.append("")
                    if i == 0:
                        # [수정됨] 첫 번째 데이터 행에 PM, 금주, 차주 내용을 추가
                        r_7.extend([new_pm, in_this, in_next])
                    else:
                        # [수정됨] 나머지 행은 H열에 PM 이름만 채워줍니다.
                        r_7.extend([new_pm])
                    full_data.append(r_7)
            else:
                full_data.append([""] * 7 + [new_pm, in_this, in_next])
                
            safe_api_call(ws.clear)
            safe_api_call(ws.update, 'A1', full_data)
            st.success("데이터가 완벽하게 저장되었습니다!"); time.sleep(1); st.rerun()

# 3. 일 발전량 및 일조 분석
def view_solar(sh):
    st.title("☀️ 일 발전량 및 일조 분석")
    try:
        db_ws = safe_api_call(sh.worksheet, 'Solar_DB')
        raw = safe_api_call(db_ws.get_all_records)
        if not raw:
            st.info("데이터가 없습니다.")
            return
        
        df_db = pd.DataFrame(raw)
        df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
        df_db['발전시간'] = pd.to_numeric(df_db['발전시간'], errors='coerce').fillna(0)
        df_db['일사량합계'] = pd.to_numeric(df_db['일사량합계'], errors='coerce').fillna(0)
        df_db = df_db.dropna(subset=['날짜'])

        with st.expander("🔍 발전량 상세 검색 필터", expanded=True):
            f1, f2 = st.columns(2)
            with f1:
                locs = sorted(df_db['지점'].unique().tolist())
                sel_locs = st.multiselect("조회 지역 선택", locs, default=locs[:3] if len(locs)>3 else locs)
            with f2:
                default_start = datetime.date(2025, 1, 1)
                default_end = datetime.date(2025, 12, 31)
                dr = st.date_input("조회 기간", [default_start, default_end])
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
        st.error("분석 데이터를 불러올 수 없습니다.")

# 4. 경영지표 KPI
def view_kpi(sh):
    st.title("📉 경영 실적 및 KPI")
    try:
        ws = safe_api_call(sh.worksheet, 'KPI')
        df = pd.DataFrame(safe_api_call(ws.get_all_records))
        st.table(df)
        if not df.empty and '실적' in df.columns:
            st.plotly_chart(px.pie(df, values='실적', names=df.columns[0], title="항목별 실적 비중"))
    except: st.warning("KPI 시트를 찾을 수 없습니다.")

# 5. 마스터 관리
def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 관리")
    t1, t2, t3, t4, t5 = st.tabs(["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 업로드", "📥 다운로드"])
    
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            new_ws = safe_api_call(sh.add_worksheet, title=new_n, rows="100", cols="20")
            # [수정됨] 신규 시트 생성 시 기본 헤더 구성 변경
            safe_api_call(new_ws.append_row, ["시작일", "종료
