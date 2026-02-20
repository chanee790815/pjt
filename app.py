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
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.5", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; color: #212529; padding: 12px 15px; border-radius: 10px; border: 1px solid #eee; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .pjt-card h4 { color: #222222 !important; font-weight: 700; margin-top: 0; margin-bottom: 2px; font-size: 15px; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .weekly-box { background-color: #f8f9fa; padding: 8px 10px; border-radius: 6px; margin-top: 4px; font-size: 12px; line-height: 1.4; color: #333; border: 1px solid #edf0f2; white-space: pre-wrap; }
    .history-box { background-color: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    .pm-tag { background-color: #e7f5ff; color: #1971c2; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 8px; border: 1px solid #a5d8ff; vertical-align: middle; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.5) | 대시보드 카드 레이아웃 컴팩트화 완료</div>
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
                ws = safe_api_call(sh.worksheet, p_name)
                # 단 1번의 API 호출로 모든 데이터를 가져옴 (429 에러 방지)
                data = safe_api_call(ws.get_all_values)
                
                pm_name = "미지정"
                this_w = "금주 실적 미입력"
                next_w = "차주 계획 미입력"
                
                if len(data) > 0:
                    header = data[0][:8]
                    df = pd.DataFrame([r[:8] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
                    
                    # I1(8), J2(9), K2(10) 인덱스로 직접 추출
                    if len(data[0]) > 8 and str(data[0][8]).strip(): pm_name = str(data[0][8]).strip()
                    if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip(): this_w = str(data[1][9]).strip()
                    if len(data) > 1 and len(data[1]) > 10 and str(data[1][10]).strip(): next_w = str(data[1][10]).strip()
                else:
                    df = pd.DataFrame()

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
                        <h4>🏗️ {p_name} <span class="pm-tag">PM: {pm_name}</span> <span style="font-size:13px; font-weight:normal; float:right;">{status_ui}</span></h4>
                        <p style="font-size:12px; color:#666; margin-top:0; margin-bottom:4px;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                        <div class="weekly-box"><b>[금주]</b> {this_w}<br><b>[차주]</b> {next_w}</div>
                    </div>
                ''', unsafe_allow_html=True)
                st.progress(min(1.0, max(0.0, avg_act/100)))
            except Exception as e:
                st.warning(f"'{p_name}' 데이터를 로드하지 못했습니다.")

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = safe_api_call(sh.worksheet, selected_pjt)
        data = safe_api_call(ws.get_all_values)
        
        # 데이터 분리 (A~H열은 공정표, I/J/K는 메타데이터)
        current_pm = ""
        this_val = ""
        next_val = ""
        
        if len(data) > 0:
            header = data[0][:8]
            df = pd.DataFrame([r[:8] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
            if len(data[0]) > 8: current_pm = str(data[0][8]).strip()
            if len(data) > 1 and len(data[1]) > 9: this_val = str(data[1][9]).strip()
            if len(data) > 1 and len(data[1]) > 10: next_val = str(data[1][10]).strip()
        else:
            df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])

        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)

        # 상단 PM 입력부
        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1:
            new_pm = st.text_input("프로젝트 담당 PM (I1 셀)", value=current_pm)
        with col_pm2:
            st.write("")
            if st.button("PM 성함 저장"):
                safe_api_call(ws.update, 'I1', [[new_pm]])
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
                            <p style="font-size:14px; color:#555; margin-bottom:10px;">📅 <b>최종 보고일:</b> {latest.get('날짜', '-')}</p>
                            <p style="margin-bottom:12px;"><b>✔️ 금주 주요 업무:</b><br>{latest.get('금주업무', latest.get('주요현황', '-'))}</p>
                            <p style="margin-bottom:0;"><b>🔜 차주 주요 업무:</b><br>{latest.get('차주업무', '-')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else: st.info("아직 등록된 주간 업무 기록이 없습니다.")
            except: st.warning("이력 데이터를 불러오는 중 오류가 발생했습니다.")

            st.divider()

            st.subheader("📝 주간 업무 작성 및 동기화 (J2, K2 셀 & 히스토리)")
            with st.form("weekly_sync_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 (J2)", value=this_val, height=120)
                in_next = st.text_area("🔜 차주 주요 업무 (K2)", value=next_val, height=120)
                if st.form_submit_button("시트 데이터 업데이트 및 이력 저장"):
                    safe_api_call(ws.update, 'J2', [[in_this]])
                    safe_api_call(ws.update, 'K2', [[in_next]])
                    try:
                        h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                        safe_api_call(h_ws.append_row, [datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                    except: pass
                    st.success("성공적으로 업데이트 및 저장되었습니다!"); time.sleep(1); st.rerun()

        st.write("---")
        st.subheader("📝 상세 공정표 편집 (A~H열 전용)")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 변경사항 전체 저장"):
            # A~H 편집 내용과 I, J, K 메타데이터를 하나의 배열로 병합하여 안전하게 저장
            full_data = []
            header_8 = edited.columns.values.tolist()[:8]
            while len(header_8) < 8: header_8.append("")
            full_data.append(header_8 + [new_pm]) # Row 1
            
            edited_rows = edited.fillna("").astype(str).values.tolist()
            if len(edited_rows) > 0:
                for i, r in enumerate(edited_rows):
                    r_8 = r[:8]
                    while len(r_8) < 8: r_8.append("")
                    if i == 0:
                        r_8.extend(["", in_this, in_next]) # Row 2에 주간업무 삽입
                    full_data.append(r_8)
            else:
                full_data.append([""] * 8 + ["", in_this, in_next])
                
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
            safe_api_call(new_ws.append_row, ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
            st.success("생성 완료!"); st.rerun()
            
    with t2:
        target = st.selectbox("수정 대상", ["선택"] + pjt_list, key="ren")
        new_name = st.text_input("변경할 이름")
        if st.button("이름 변경") and target != "선택" and new_name:
            ws = safe_api_call(sh.worksheet, target)
            safe_api_call(ws.update_title, new_name)
            st.success("수정 완료!"); st.rerun()

    with t3:
        target_del = st.selectbox("삭제 대상", ["선택"] + pjt_list, key="del")
        conf = st.checkbox("영구 삭제에 동의합니다.")
        if st.button("삭제 수행") and target_del != "선택" and conf:
            ws = safe_api_call(sh.worksheet, target_del)
            safe_api_call(sh.del_worksheet, ws)
            st.success("삭제 완료!"); st.rerun()

    with t4:
        target_up = st.selectbox("업로드 대상", ["선택"] + pjt_list, key="up")
        file = st.file_uploader("엑셀 파일", type=['xlsx'])
        if target_up != "선택" and file and st.button("동기화"):
            df_up = pd.read_excel(file).fillna("").astype(str)
            ws = safe_api_call(sh.worksheet, target_up)
            safe_api_call(ws.clear)
            safe_api_call(ws.update, [df_up.columns.values.tolist()] + df_up.values.tolist())
            st.success("완료!")

    with t5:
        if st.button("📚 통합 백업 엑셀 생성"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for p in pjt_list:
                    try:
                        ws = safe_api_call(sh.worksheet, p)
                        data = safe_api_call(ws.get_all_values)
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
            sh = safe_api_call(client.open, 'pms_db')
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
        except Exception as e: st.error(f"서버 접속이 지연되고 있습니다. 잠시 후 새로고침 해주세요.")
