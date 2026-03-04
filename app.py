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
import streamlit.components.v1 as components

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.22", page_icon="🏗️", layout="wide")

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
    
    /* 박스 디자인 (반투명 회색 배경) 및 자동 줄바꿈 최적화 */
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 10px 12px; border-radius: 6px; margin-top: 4px; font-size: 12.5px; line-height: 1.6; border: 1px solid rgba(128, 128, 128, 0.2); white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    
    /* 태그 및 뱃지 */
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
    /* 컴팩트 버튼 디자인 */
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
    /* 모바일 세로 모드에서 버튼이 밑으로 떨어지는 현상 강제 차단 */
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
        .metric-container { flex-wrap: wrap; }
    }

    /* ========================================================= */
    /* [보고서 인쇄/PDF 최적화 CSS] */
    /* ========================================================= */
    @media print {
        /* 불필요한 UI 숨기기 */
        header[data-testid="stHeader"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
        .footer { display: none !important; }
        iframe { display: none !important; } /* 인쇄 버튼 자체 숨김 */
        button { display: none !important; } /* 화면 내 다른 버튼들 숨김 */
        
        /* 여백 최소화 및 배경색 강제 인쇄 설정 */
        .block-container { max-width: 100% !important; padding: 10px !important; margin: 0 !important; }
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        
        /* 카드가 페이지 중간에 잘리는 것 방지 */
        div[data-testid="stContainer"] { page-break-inside: avoid; }
    }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.22) | PDF/보고서 인쇄 기능 추가</div>
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
        creds = Credentials.from_service_account_info(
            key_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 클라우드 연결 실패: {e}")
        return None

# -------------------------------
# [성능 개선] 구글 시트 읽기 캐시
# -------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_all_values(spreadsheet_name: str, worksheet_name: str):
    """지정 워크시트 전체 데이터를 5분간 캐싱"""
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    return safe_api_call(ws.get_all_values)

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_all_records(spreadsheet_name: str, worksheet_name: str):
    """get_all_records 결과를 5분간 캐싱"""
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    return safe_api_call(ws.get_all_records)

@st.cache_data(ttl=300, show_spinner=False)
def cached_get_head(spreadsheet_name: str, worksheet_name: str, max_rows: int = 200):
    """
    대시보드용: 상단 N행(A1~J{max_rows})만 읽어서 평균 진척 계산
    → 프로젝트별 행이 많아져도 속도 유지
    """
    client = get_client()
    if client is None:
        return []
    sh = safe_api_call(client.open, spreadsheet_name)
    ws = safe_api_call(sh.worksheet, worksheet_name)
    rng = f"A1:J{max_rows}"
    return safe_api_call(ws.get, rng)

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

def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

def render_print_button():
    """자바스크립트를 이용해 브라우저 인쇄(PDF 저장) 창을 띄우는 버튼"""
    components.html(
        """
        <script>
            function printApp() {
                window.parent.print();
            }
        </script>
        <style>
            body { margin: 0; padding: 0; background-color: transparent; }
            .print-btn {
                float: right;
                background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #dee2e6;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
                cursor: pointer;
                font-family: sans-serif;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                transition: all 0.2s;
            }
            .print-btn:hover {
                background-color: #e9ecef;
                border-color: #ced4da;
            }
        </style>
        <button class="print-btn" onclick="printApp()">🖨️ PDF 저장 / 인쇄</button>
        """,
        height=40
    )

# ---------------------------------------------------------
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("📊 통합 대시보드 (현황 브리핑)")
    with col_btn:
        st.write("") # 줄맞춤 여백
        render_print_button()
    
    dashboard_data = []
    
    with st.spinner("프로젝트 데이터를 분석 중입니다..."):
        for p_name in pjt_list:
            try:
                # ★ 성능 개선: 전체가 아니라 상단 일부만 + 캐시 사용
                data = cached_get_head('pms_db', p_name, max_rows=200)
                
                pm_name = "미지정"
                this_w = "금주 실적 미입력"
                next_w = "차주 계획 미입력"
                
                if len(data) > 0:
                    header = data[0][:7]
                    df = pd.DataFrame(
                        [r[:7] for r in data[1:]],
                        columns=header
                    ) if len(data) > 1 else pd.DataFrame(columns=header)
                    
                    if len(data) > 1 and len(data[1]) > 7 and str(data[1][7]).strip(): pm_name = str(data[1][7]).strip()
                    if len(data) > 1 and len(data[1]) > 8 and str(data[1][8]).strip(): this_w = str(data[1][8]).strip()
                    if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip(): next_w = str(data[1][9]).strip()
                else:
                    df = pd.DataFrame()

                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                    avg_plan = round(
                        df.apply(
                            lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')),
                            axis=1
                        ).mean(), 1
                    )
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
                
                dashboard_data.append({
                    "p_name": p_name,
                    "pm_name": pm_name,
                    "this_w": this_w,
                    "next_w": next_w,
                    "avg_act": avg_act,
                    "avg_plan": avg_plan,
                    "status_ui": status_ui,
                    "b_style": b_style
                })
            except Exception as e:
                # 개별 프로젝트 오류는 무시하고 계속
                pass

    all_pms = sorted(list(set([d["pm_name"] for d in dashboard_data])))
    
    f_col1, f_col2 = st.columns([1, 3])
    with f_col1:
        selected_pm = st.selectbox("👤 담당자 조회", ["전체"] + all_pms)
        
    if selected_pm != "전체":
        filtered_data = [d for d in dashboard_data if d["pm_name"] == selected_pm]
    else:
        filtered_data = dashboard_data

    total_cnt = len(filtered_data)
    normal_cnt = len([d for d in filtered_data if d['status_ui'] == "🟢 정상"])
    delay_cnt = len([d for d in filtered_data if d['status_ui'] == "🔴 지연"])
    done_cnt = len([d for d in filtered_data if d['status_ui'] == "🔵 완료"])

    with f_col2:
        st.markdown(f"""
            <div class="metric-container" style="display: flex; gap: 10px; align-items: center; height: 100%; padding-top: 28px;">
                <div style="background: rgba(128,128,128,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">
                    📊 조회된 프로젝트: <span style="color: #2196f3; font-size: 15px;">{total_cnt}</span>건
                </div>
                <div style="background: rgba(33,150,243,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #1976d2;">
                    🟢 정상: {normal_cnt}건
                </div>
                <div style="background: rgba(244,67,54,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #d32f2f;">
                    🔴 지연: {delay_cnt}건
                </div>
                <div style="background: rgba(76,175,80,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #388e3c;">
                    🔵 완료: {done_cnt}건
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    st.divider()

    if total_cnt == 0:
        st.info("선택된 담당자의 프로젝트가 없습니다.")
    else:
        cols = st.columns(2)
        for idx, d in enumerate(filtered_data):
            with cols[idx % 2]:
                with st.container(border=True):
                    h_col1, h_col2 = st.columns([7.5, 2.5], gap="small")
                    
                    with h_col1:
                        st.markdown(f"""
                            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 2px;">
                                <h4 style="font-weight:700; margin:0; font-size:clamp(13.5px, 3.5vw, 16px); word-break:keep-all; line-height:1.2;">
                                    🏗️ {d['p_name']}
                                </h4>
                                <span class="pm-tag" style="margin:0;">PM: {d['pm_name']}</span>
                                <span class="status-badge {d['b_style']}" style="margin:0;">{d['status_ui']}</span>
                            </div>
                        """, unsafe_allow_html=True)
                        
                    with h_col2:
                        st.button("🔍 상세", key=f"btn_go_{d['p_name']}", on_click=navigate_to_project, args=(d['p_name'],), use_container_width=True)
                    
                    this_w_html = str(d['this_w']).replace('\n', '<br>')
                    next_w_html = str(d['next_w']).replace('\n', '<br>')

                    st.markdown(f'''
                        <div style="margin-bottom:4px; margin-top:2px;">
                            <p style="font-size:12.5px; opacity: 0.7; margin-top:0; margin-bottom:4px;">계획: {d['avg_plan']}% | 실적: {d['avg_act']}%</p>
                            <div class="weekly-box" style="margin-top:0;">
                                <div style="margin-bottom: 8px;"><b>[금주]</b><br>{this_w_html}</div>
                                <div><b>[차주]</b><br>{next_w_html}</div>
                            </div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    st.progress(min(1.0, max(0.0, d['avg_act']/100)))

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("🏗️ 프로젝트 상세 관리")
    with col_btn:
        st.write("")
        render_print_button()
    
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list, key="selected_pjt")
    
    if selected_pjt != "선택":
        # ★ 성능 개선: 전체 데이터도 캐시 사용
        data = cached_get_all_values('pms_db', selected_pjt)
        
        current_pm = ""
        this_val = ""
        next_val = ""
        
        if len(data) > 0:
            header = data[0][:7]
            df = pd.DataFrame([r[:7] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
            
            if len(data) > 1 and len(data[1]) > 7: current_pm = str(data[1][7]).strip()
            if len(data) > 1 and len(data[1]) > 8: this_val = str(data[1][8]).strip()
            if len(data) > 1 and len(data[1]) > 9: next_val = str(data[1][9]).strip()
        else:
            df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"])

        if '시작일' in df.columns:
            df['시작일'] = df['시작일'].astype(str).str.split().str[0].replace('nan', '')
        if '종료일' in df.columns:
            df['종료일'] = df['종료일'].astype(str).str.split().str[0].replace('nan', '')

        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)

        ws = safe_api_call(sh.worksheet, selected_pjt)

        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1:
            new_pm = st.text_input("프로젝트 담당 PM (H2 셀)", value=current_pm)
        with col_pm2:
            st.write("")
            if st.button("PM 성함 저장"):
                safe_api_call(ws.update, 'H2', [[new_pm]])
                # 데이터 변경 후 캐시 무효화
                cached_get_all_values.clear()
                cached_get_head.clear()
                st.success("PM이 업데이트되었습니다!")
        
        st.divider()

        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        
        with tab1:
            try:
                cdf = df.copy()
                original_len = len(cdf)
                
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일'])
                
                dropped_len = original_len - len(cdf)
                if dropped_len > 0:
                    st.warning(f"⚠️ 날짜 형식 오류(예: 2월 30일 등 존재하지 않는 날짜)로 인해 {dropped_len}개의 항목이 차트에서 제외되었습니다.")
                
                if not cdf.empty:
                    cdf = cdf.reset_index(drop=True)
                    
                    if '대분류' in cdf.columns:
                        cdf['대분류'] = cdf['대분류'].astype(str).replace({'nan': '미지정', '': '미지정'})
                    if '구분' not in cdf.columns:
                        cdf['구분'] = '내용 없음'
                        
                    cdf['진행률'] = pd.to_numeric(cdf['진행률'], errors='coerce').fillna(0).astype(float)
                    
                    cdf['구분_고유'] = cdf.apply(lambda r: f"{r.name + 1}. {str(r['구분']).strip()}", axis=1)
                    
                    def calc_text_width(text):
                        return sum(2 if ord(c) > 127 else 1 for c in str(text))
                    
                    max_width = cdf['구분_고유'].apply(calc_text_width).max()
                    
                    cdf['구분_고유'] = cdf['구분_고유'].apply(
                        lambda x: str(x) + "&nbsp;" * int((max_width - calc_text_width(x)) * 2.5)
                    )
                    
                    cdf['duration'] = (cdf['종료일'] - cdf['시작일']).dt.total_seconds() * 1000
                    cdf['duration'] = cdf['duration'].apply(lambda d: 86400000.0 if d <= 0 else d)
                    
                    cdf['시작일_str'] = cdf['시작일'].dt.strftime('%Y-%m-%d')
                    cdf['종료일_str'] = cdf['종료일'].dt.strftime('%Y-%m-%d')
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        base=cdf['시작일'],
                        x=cdf['duration'],
                        y=[cdf['대분류'].tolist(), cdf['구분_고유'].tolist()],
                        orientation='h',
                        marker=dict(
                            color=cdf['진행률'],
                            colorscale='RdYlGn',
                            cmin=0,
                            cmax=100,
                            showscale=True,
                            colorbar=dict(title="진행률(%)")
                        ),
                        customdata=cdf[['시작일_str', '종료일_str', '대분류', '구분']].values,
                        hovertemplate="<b>[%{customdata[2]}] %{customdata[3]}</b><br>시작일: %{customdata[0]}<br>종료일: %{customdata[1]}<br>진행률: %{marker.color}%<extra></extra>"
                    ))
                    
                    today_ms = pd.Timestamp.now().normalize().timestamp() * 1000
                    fig.add_vline(
                        x=today_ms,
                        line_width=2.5,
                        line_color="purple", 
                        annotation_text="오늘",
                        annotation_position="top",
                        annotation_font=dict(color="purple", size=13, weight="bold")
                    )
                    
                    fig.update_xaxes(
                        type="date",             
                        dtick="M1",              
                        tickformat="%y.%-m",     
                        tickangle=0,             
                        showgrid=True,           
                        gridwidth=1,
                        gridcolor='rgba(200, 200, 200, 0.6)',
                        showline=True, linewidth=1, linecolor='rgba(200, 200, 200, 0.6)', mirror=True,
                        title_text=""
                    )
                    
                    fig.update_yaxes(
                        autorange="reversed",
                        type="multicategory",    
                        categoryorder="trace",   
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='rgba(200, 200, 200, 0.6)',
                        showline=True, linewidth=1, linecolor='rgba(200, 200, 200, 0.6)', mirror=True,
                        dividercolor='rgba(150, 150, 150, 0.8)',
                        dividerwidth=1,
                        title_text=""
                    )
                    
                    fig.update_layout(
                        height=max(400, len(cdf) * 35),
                        plot_bgcolor='white',  
                        paper_bgcolor='white',
                        margin=dict(l=10, r=20, t=40, b=20)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("차트를 그릴 수 있는 유효한 날짜 데이터가 부족합니다. 편집기에서 날짜를 확인해 주세요.")
            except Exception as e:
                st.error(f"차트를 그리는 중 세부 오류가 발생했습니다: {e}")

        with tab2:
            try:
                sdf = df.copy()
                sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
                sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    min_d, max_d = sdf['시작일'].min(), sdf['종료일'].max()
                    d_range = pd.date_range(min_d, max_d, freq='W-MON').date.tolist()
                    p_trend = [
                        sdf.apply(
                            lambda r: calc_planned_progress(r['시작일'], r['종료일'], d),
                            axis=1
                        ).mean()
                        for d in d_range
                    ]
                    a_prog = pd.to_numeric(sdf['진행률'], errors='coerce').fillna(0).mean()
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(
                        x=[d.strftime("%Y-%m-%d") for d in d_range],
                        y=p_trend,
                        mode='lines+markers',
                        name='계획'
                    ))
                    fig_s.add_trace(go.Scatter(
                        x=[datetime.date.today().strftime("%Y-%m-%d")],
                        y=[a_prog],
                        mode='markers',
                        name='현재 실적',
                        marker=dict(size=12, color='red', symbol='star')
                    ))
                    fig_s.update_layout(title="진척률 추이 (S-Curve)", yaxis_title="진척률(%)")
                    st.plotly_chart(fig_s, use_container_width=True)
            except:
                pass

        with tab3:
            st.subheader("📋 최근 주간 업무 이력")
            try:
                # weekly_history는 시스템 시트라 캐시 사용
                h_data = cached_get_all_records('pms_db', 'weekly_history')
                h_df = pd.DataFrame(h_data)
                if not h_df.empty:
                    h_df['프로젝트명'] = h_df['프로젝트명'].astype(str).str.strip()
                    p_match = h_df[h_df['프로젝트명'] == selected_pjt.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        
                        hist_this_w = str(latest.get('금주업무', latest.get('주요현황', '-'))).replace('\n', '<br>')
                        hist_next_w = str(latest.get('차주업무', '-')).replace('\n', '<br>')
                        
                        st.markdown(f"""
                        <div class="history-box">
                            <p style="font-size:14px; opacity: 0.7; margin-bottom:10px;">📅 <b>최종 보고일:</b> {latest.get('날짜', '-')}</p>
                            <div style="margin-bottom:12px;"><b>✔️ 금주 주요 업무:</b><br>{hist_this_w}</div>
                            <div><b>🔜 차주 주요 업무:</b><br>{hist_next_w}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("아직 등록된 주간 업무 기록이 없습니다.")
            except:
                st.warning("이력 데이터를 불러오는 중 오류가 발생했습니다.")

            st.divider()

            st.subheader("📝 주간 업무 작성 및 동기화 (I2, J2 셀 & 히스토리)")
            
            st.info("💡 우측 하단 모서리를 마우스로 드래그하면 입력 창의 크기를 자유롭게 늘리거나 줄일 수 있습니다.")
            with st.form("weekly_sync_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 (I2)", value=this_val, height=250)
                in_next = st.text_area("🔜 차주 주요 업무 (J2)", value=next_val, height=250)
                if st.form_submit_button("시트 데이터 업데이트 및 이력 저장"):
                    safe_api_call(ws.update, 'I2', [[in_this]])
                    safe_api_call(ws.update, 'J2', [[in_next]])
                    try:
                        h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                        safe_api_call(
                            h_ws.append_row,
                            [
                                datetime.date.today().strftime("%Y-%m-%d"),
                                selected_pjt,
                                in_this,
                                in_next,
                                st.session_state.user_id
                            ]
                        )
                        # weekly_history 변경 후 캐시 무효화
                        cached_get_all_records.clear()
                    except:
                        pass
                    # 프로젝트 시트 데이터도 변경되므로 관련 캐시 무효화
                    cached_get_all_values.clear()
                    cached_get_head.clear()
                    st.success("성공적으로 업데이트 및 저장되었습니다!")
                    time.sleep(1)
                    st.rerun()

        st.write("---")
        st.subheader("📝 상세 공정표 편집 (A~G열 전용)")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        
        if st.button("💾 변경사항 전체 저장"):
            full_data = []
            header_7 = edited.columns.values.tolist()[:7]
            while len(header_7) < 7: header_7.append("")
            
            full_data.append(header_7 + ["PM", "금주", "차주"])
            
            edited_rows = edited.fillna("").astype(str).values.tolist()
            if len(edited_rows) > 0:
                for i, r in enumerate(edited_rows):
                    r_7 = r[:7]
                    while len(r_7) < 7: r_7.append("")
                    
                    if i == 0:
                        r_7.extend([new_pm, in_this, in_next])
                    else:
                        r_7.extend([new_pm, "", ""])
                        
                    full_data.append(r_7)
            else:
                full_data.append([""] * 7 + [new_pm, in_this, in_next])
                
            safe_api_call(ws.clear)
            safe_api_call(ws.update, 'A1', full_data)
            # 저장 후 관련 캐시 전체 무효화
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("데이터가 완벽하게 저장되었습니다!")
            time.sleep(1)
            st.rerun()

# 3. 일 발전량 및 일조 분석
def view_solar(sh):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("☀️ 일 발전량 및 일조 분석")
    with col_btn:
        st.write("")
        render_print_button()
        
    try:
        # ★ 성능 개선: Solar_DB 전체도 캐시 사용
        raw = cached_get_all_records('pms_db', 'Solar_DB')
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
                sel_loc = st.selectbox("조회 지역 선택", locs)
            with f2:
                default_start = datetime.date(2025, 1, 1)
                default_end = datetime.date(2025, 12, 31)
                dr = st.date_input("조회 기간", [default_start, default_end])
        
        mask = (df_db['지점'] == sel_loc)
        if len(dr) == 2:
            mask = mask & (df_db['날짜'].dt.date >= dr[0]) & (df_db['날짜'].dt.date <= dr[1])
        
        f_df = df_db[mask].sort_values('날짜')

        if not f_df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("평균 발전 시간", f"{f_df['발전시간'].mean():.2f} h")
            m2.metric("평균 일사량", f"{f_df['일사량합계'].mean():.2f} MJ/m²")
            m3.metric("검색 데이터 수", f"{len(f_df)} 건")

            # --- [핵심] 일사량(막대), 발전시간(선), 예측추세(빨간선) 혼합 차트 ---
            fig_solar = go.Figure()
            
            # 1. 일사량합계 (주황색 막대) - 1차 Y축
            fig_solar.add_trace(go.Bar(
                x=f_df['날짜'], 
                y=f_df['일사량합계'], 
                name='일사량 (기상청)', 
                marker_color='rgba(255, 165, 0, 0.6)', 
                yaxis='y1'
            ))
            
            # 2. 실제 발전시간 (파란색 선) - 2차 Y축
            fig_solar.add_trace(go.Scatter(
                x=f_df['날짜'], 
                y=f_df['발전시간'], 
                name='실제 발전시간', 
                mode='lines+markers', 
                line=dict(color='rgba(33, 150, 243, 1)', width=2), 
                marker=dict(size=4),
                yaxis='y2'
            ))
            
            # 3. 예측 발전시간 추세 (빨간색 두꺼운 선) - 2차 Y축
            f_df['예측_발전시간'] = (f_df['일사량합계'] / 3.6) * 0.8
            f_df['예측_추세선'] = f_df['예측_발전시간'].rolling(window=14, min_periods=1, center=True).mean()
            
            fig_solar.add_trace(go.Scatter(
                x=f_df['날짜'], 
                y=f_df['예측_추세선'], 
                name='예측 발전량 (Trend)', 
                mode='lines', 
                line=dict(color='red', width=4), 
                yaxis='y2'
            ))

            fig_solar.update_layout(
                title=f"[{sel_loc}] 일사량 및 실제/예측 발전시간 추이 비교",
                xaxis=dict(title="날짜"),
                yaxis=dict(
                    title=dict(text="일사량 (MJ/m²)", font=dict(color="orange")), 
                    tickfont=dict(color="orange")
                ),
                yaxis2=dict(
                    title=dict(text="발전시간 (h)", font=dict(color="blue")), 
                    tickfont=dict(color="blue"), 
                    anchor="free", 
                    overlaying="y", 
                    side="right"
                ),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig_solar, use_container_width=True)
            # --------------------------------------------------------------------------------

            st.subheader("📊 검색 결과 상세 내역")
            
            output_solar = io.BytesIO()
            with pd.ExcelWriter(output_solar, engine='openpyxl') as writer:
                export_df = f_df.copy()
                export_df['날짜'] = export_df['날짜'].dt.strftime('%Y-%m-%d')
                export_df.to_excel(writer, index=False, sheet_name='발전량_검색결과')
            
            col_down1, col_down2 = st.columns([8, 2])
            with col_down2:
                st.download_button(
                    label="📥 데이터 엑셀 다운로드",
                    data=output_solar.getvalue(),
                    file_name=f"일일발전량_조회결과_{datetime.date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            st.dataframe(f_df, use_container_width=True)
        else:
            st.warning("조건에 맞는 데이터가 없습니다.")

    except Exception as e:
        st.error(f"분석 데이터를 불러올 수 없습니다: {e}")

# 4. 경영지표 KPI
def view_kpi(sh):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("📉 경영 실적 및 KPI")
    with col_btn:
        st.write("")
        render_print_button()
        
    try:
        # ★ 성능 개선: KPI도 캐시 사용
        df = pd.DataFrame(cached_get_all_records('pms_db', 'KPI'))
        st.table(df)
        if not df.empty and '실적' in df.columns:
            st.plotly_chart(px.pie(df, values='실적', names=df.columns[0], title="항목별 실적 비중"))
    except:
        st.warning("KPI 시트를 찾을 수 없습니다.")

# 5. 마스터 관리
def view_project_admin(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.title("⚙️ 마스터 관리")
    with col_btn:
        st.write("")
        render_print_button()
        
    t1, t2, t3, t4, t5 = st.tabs(["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 업로드", "📥 다운로드"])
    
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            new_ws = safe_api_call(sh.add_worksheet, title=new_n, rows="100", cols="20")
            safe_api_call(new_ws.append_row, ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "PM", "금주", "차주"])
            # 프로젝트 목록 변경 → 캐시 무효화
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("생성 완료!")
            st.rerun()
            
    with t2:
        target = st.selectbox("수정 대상", ["선택"] + pjt_list, key="ren")
        new_name = st.text_input("변경할 이름")
        if st.button("이름 변경") and target != "선택" and new_name:
            ws = safe_api_call(sh.worksheet, target)
            safe_api_call(ws.update_title, new_name)
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("수정 완료!")
            st.rerun()

    with t3:
        target_del = st.selectbox("삭제 대상", ["선택"] + pjt_list, key="del")
        conf = st.checkbox("영구 삭제에 동의합니다.")
        if st.button("삭제 수행") and target_del != "선택" and conf:
            ws = safe_api_call(sh.worksheet, target_del)
            safe_api_call(sh.del_worksheet, ws)
            cached_get_all_values.clear()
            cached_get_head.clear()
            st.success("삭제 완료!")
            st.rerun()

    with t4:
        st.info("💡 엑셀 파일 내의 '시트 이름'이 구글 시트의 '프로젝트명'과 일치하면 한 번에 모두 업데이트됩니다.")
        file = st.file_uploader("통합 엑셀 파일 업로드", type=['xlsx'])
        
        if file and st.button("🔄 일괄 동기화 (자동 매칭)"):
            try:
                all_sheets = pd.read_excel(file, sheet_name=None, engine='openpyxl')
                
                updated_count = 0
                skipped_sheets = []
                
                with st.spinner("데이터를 매칭하여 일괄 업데이트 중입니다..."):
                    for sheet_name, df_up in all_sheets.items():
                        s_name = sheet_name.strip()
                        
                        if s_name in pjt_list:
                            ws = safe_api_call(sh.worksheet, s_name)
                            df_up = df_up.fillna("").astype(str)
                            
                            safe_api_call(ws.clear)
                            safe_api_call(ws.update, [df_up.columns.values.tolist()] + df_up.values.tolist())
                            updated_count += 1
                        else:
                            skipped_sheets.append(s_name)
                
                # 일괄 업데이트 후 캐시 무효화
                cached_get_all_values.clear()
                cached_get_head.clear()

                if updated_count > 0:
                    st.success(f"🎉 총 {updated_count}개의 프로젝트가 성공적으로 일괄 업데이트되었습니다!")
                else:
                    st.warning("⚠️ 일치하는 시트 이름이 없어 업데이트된 항목이 없습니다.")
                    
                if skipped_sheets:
                    st.caption(f"건너뛴 시트 (이름 불일치 또는 시스템 시트): {', '.join(skipped_sheets)}")
                    
            except Exception as e:
                st.error(f"파일 처리 중 오류가 발생했습니다: {e}")

    with t5:
        if st.button("📚 통합 백업 엑셀 생성"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for p in pjt_list:
                    try:
                        data = cached_get_all_values('pms_db', p)
                        if not data:
                            continue
                        pd.DataFrame(data[1:], columns=data[0]).to_excel(writer, index=False, sheet_name=p[:31])
                    except:
                        pass
            st.download_button("📥 통합 파일 받기", output.getvalue(), f"Backup_{datetime.date.today()}.xlsx")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = safe_api_call(client.open, 'pms_db')
            sys_names = ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'Control_Center', 'Dashboard_Control', '통합 대시보드']
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
            
            if "selected_menu" not in st.session_state:
                st.session_state.selected_menu = "통합 대시보드"
            if "selected_pjt" not in st.session_state:
                st.session_state.selected_pjt = "선택"
            
            st.sidebar.title("📁 PMO 메뉴")
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "마스터 설정"], key="selected_menu")
            
            if menu == "통합 대시보드":
                view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세":
                view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석":
                view_solar(sh)
            elif menu == "경영지표(KPI)":
                view_kpi(sh)
            elif menu == "마스터 설정":
                view_project_admin(sh, pjt_list)
            
            if st.sidebar.button("로그아웃"):
                st.session_state.logged_in = False
                st.rerun()
        except Exception as e:
            st.error(f"서버 접속이 지연되고 있습니다. 잠시 후 새로고침 해주세요.")
