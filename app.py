import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.1", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.1 Default: Seosan/2026) | 데이터 출처: 기상청 API & 구글 클라우드</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def check_login():
    if st.session_state.get("logged_in", False): return True
    
    st.title("🏗️ PM 통합 관리 시스템 (v4.1)")
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
    except: return None

def get_safe_float(value):
    try:
        if value == '' or value is None: return 0.0
        return float(value)
    except (ValueError, TypeError): return 0.0

# [계획 진척률 자동 계산 로직]
def calc_planned_progress(start, end, target_date=None):
    if target_date is None:
        target_date = datetime.date.today()
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
# [SECTION 2] 각 기능별 뷰(View) 함수
# ---------------------------------------------------------

def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (계획/실적 연동)")
    st.info(f"현재 관리 중인 현장: {len(pjt_list)}개")
    
    # 주간업무 기록 불러오기
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
    except:
        hist_df = pd.DataFrame()
        
    try:
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                
                # 계획 및 실적 진척률 계산
                avg_act = 0.0
                avg_plan = 0.0
                if not df.empty and '진행률' in df.columns and '시작일' in df.columns and '종료일' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').mean(), 1)
                    plans = df.apply(lambda row: calc_planned_progress(row['시작일'], row['종료일']), axis=1)
                    avg_plan = round(plans.mean(), 1)
                
                # 지연 상태 경고등 로직
                delay_diff = avg_plan - avg_act
                status_icon = "🟢 정상"
                card_class = "pjt-card risk-normal"
                if delay_diff >= 10:
                    status_icon = f"🔴 {delay_diff:.1f}% 지연경고"
                    card_class = "pjt-card risk-high"
                elif delay_diff >= 5:
                    status_icon = f"🟡 {delay_diff:.1f}% 지연주의"
                elif avg_act == 100:
                    status_icon = "🔵 완료"
                    
                # [NEW] 주간업무 요약 추출 로직
                weekly_text = "<span style='color:#999'>등록된 주간업무가 없습니다. (상세페이지에서 입력)</span>"
                if not hist_df.empty and '프로젝트명' in hist_df.columns:
                    row = hist_df[hist_df['프로젝트명'] == p_name]
                    if not row.empty:
                        latest = row.iloc[-1]
                        this_week = str(latest.get('금주업무', '')).strip()
                        next_week = str(latest.get('차주업무', '')).strip()
                        
                        lines = []
                        if this_week and this_week != 'nan':
                            lines.append(f"✔️ <b>[금주]</b> {this_week[:40]}{'...' if len(this_week)>40 else ''}")
                        if next_week and next_week != 'nan':
                            lines.append(f"🔜 <b>[차주]</b> {next_week[:40]}{'...' if len(next_week)>40 else ''}")
                        
                        if lines:
                            weekly_text = "<br>".join(lines)
                        else:
                            # 구버전 호환용
                            last_status = str(latest.get('주요현황', '')).strip()
                            if last_status and last_status != 'nan':
                                weekly_text = f"💡 <b>[현황]</b> {last_status[:40]}"
                
                # UI 카드 렌더링 (주간업무 패널 추가)
                st.markdown(f'''
                <div class="{card_class}">
                    <h4>🏗️ {p_name} <span style="font-size:14px; float:right;">{status_icon}</span></h4>
                    <p style="margin-bottom: 8px; font-size: 13px; color: #666;">계획: <b>{avg_plan}%</b> &nbsp;|&nbsp; 실적: <b>{avg_act}%</b></p>
                    <div style="background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-bottom: 12px; font-size: 13px; line-height: 1.5; color: #333;">
                        {weekly_text}
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                st.progress(avg_act/100, text=f"현재 실적: {avg_act}%")
    except Exception as e: st.error(f"대시보드 로드 오류: {e}")

# 리스크 및 이슈 트래킹 뷰
def view_risk_dashboard(sh, pjt_list):
    st.title("🚨 리스크 및 이슈 트래킹")
    st.markdown("전체 프로젝트 중 **'비고'란에 이슈가 작성되어 있고 완료되지 않은 공정**들을 한눈에 모니터링합니다.")
    
    all_issues = []
    with st.spinner("전체 현장 리스크 데이터를 수집 중입니다..."):
        for p_name in pjt_list:
            try:
                df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                if not df.empty and '비고' in df.columns and '진행률' in df.columns:
                    df['비고'] = df['비고'].astype(str).str.strip()
                    df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                    issues_df = df[(df['비고'] != "") & (df['비고'] != "-") & (df['진행률'] < 100)].copy()
                    if not issues_df.empty:
                        issues_df.insert(0, '현장명', p_name)
                        all_issues.append(issues_df)
            except Exception as e:
                pass
                
    if all_issues:
        final_issues = pd.concat(all_issues, ignore_index=True)
        display_cols = ['현장명', '대분류', '구분', '종료일', '진행률', '비고', '담당자']
        final_issues = final_issues[[c for c in display_cols if c in final_issues.columns]]
        st.error(f"⚠️ 현재 모니터링이 필요한 오픈 이슈가 총 {len(final_issues)}건 있습니다.")
        st.dataframe(final_issues, use_container_width=True)
    else:
        st.success("🎉 현재 등록된 오픈 이슈/리스크가 없습니다!")

def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리 & 주간보고")
    selected_pjt = st.selectbox("관리할 현장을 선택하세요", ["선택"] + pjt_list)
    
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty and '시작일' in df.columns:
            # [NEW] 주간업무 탭 추가 (3개의 탭으로 구성)
            tab_gantt, tab_scurve, tab_weekly = st.tabs(["📊 간트 차트", "📈 계획 대비 실적 (S-Curve)", "📝 주간 업무 보고"])
            
            with tab_gantt:
                try:
                    chart_df = df.copy()
                    chart_df['시작일'] = pd.to_datetime(chart_df['시작일'], errors='coerce')
                    chart_df['종료일'] = pd.to_datetime(chart_df['종료일'], errors='coerce')
                    chart_df = chart_df.dropna(subset=['시작일', '종료일'])
                    y_col = '대분류' if '대분류' in chart_df.columns else chart_df.columns[0]
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y=y_col, color="진행률", color_continuous_scale='RdYlGn', range_color=[0, 100])
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                except: st.caption("간트차트 생성 실패 (날짜 형식 확인)")

            with tab_scurve:
                try:
                    df_sc = df.copy()
                    df_sc['시작일'] = pd.to_datetime(df_sc['시작일'], errors='coerce').dt.date
                    df_sc['종료일'] = pd.to_datetime(df_sc['종료일'], errors='coerce').dt.date
                    df_sc = df_sc.dropna(subset=['시작일', '종료일'])
                    
                    if not df_sc.empty:
                        min_date = df_sc['시작일'].min()
                        max_date = df_sc['종료일'].max()
                        today = datetime.date.today()
                        date_range = pd.date_range(start=min_date, end=max_date, freq='W-MON').date.tolist()
                        if min_date not in date_range: date_range.insert(0, min_date)
                        if max_date not in date_range: date_range.append(max_date)
                        
                        planned_trend = [df_sc.apply(lambda row: calc_planned_progress(row['시작일'], row['종료일'], d), axis=1).mean() for d in date_range]
                        actual_prog = pd.to_numeric(df_sc['진행률'], errors='coerce').mean()
                        
                        # [오류수정]: Plotly에서 int/date 연산 충돌 방지를 위해 명시적 문자열로 변환
                        x_vals = [d.strftime("%Y-%m-%d") for d in date_range]
                        today_str = today.strftime("%Y-%m-%d")
                        
                        fig_sc = go.Figure()
                        fig_sc.add_trace(go.Scatter(x=x_vals, y=planned_trend, mode='lines+markers', name='계획 진척률', line=dict(color='gray', width=3)))
                        fig_sc.add_trace(go.Scatter(x=[today_str], y=[actual_prog], mode='markers', name='현재 실적', marker=dict(color='blue', size=12, symbol='star')))
                        fig_sc.add_vline(x=today_str, line_dash="dash", line_color="red", annotation_text="Today")
                        fig_sc.update_layout(title="전체 공정 S-Curve 및 현재 실적 비교", yaxis_title="진척률 (%)", yaxis=dict(range=[0, 105]))
                        st.plotly_chart(fig_sc, use_container_width=True)
                        st.info(f"📅 **오늘({today_str}) 기준 요약:** 전체 계획 **{calc_planned_progress(min_date, max_date):.1f}%** 대비 현재 실적 **{actual_prog:.1f}%**")
                except Exception as e:
                    st.caption(f"S-Curve 생성 실패: {e}")

            # [NEW] 📝 주간 업무 보고 작성 및 저장 로직
            with tab_weekly:
                st.subheader("📝 주간 주요 업무 보고 작성")
                st.markdown("대시보드에 노출될 이 현장의 **금주 및 차주 주요 업무**를 작성해주세요.")
                
                # [오류수정]: 무조건 add_worksheet 하던 것을 안전한 get 및 핸들링 로직으로 전면 수정
                try:
                    hist_ws = sh.worksheet('weekly_history')
                except gspread.WorksheetNotFound:
                    hist_ws = sh.add_worksheet('weekly_history', 1000, 10)
                    hist_ws.append_row(['프로젝트명', '업데이트일자', '금주업무', '차주업무'])
                
                try:
                    headers = hist_ws.row_values(1)
                    if not headers:
                        headers = ['프로젝트명', '업데이트일자', '금주업무', '차주업무']
                        hist_ws.append_row(headers)
                    else:
                        if '금주업무' not in headers:
                            hist_ws.update_cell(1, len(headers)+1, '금주업무')
                            headers.append('금주업무')
                        if '차주업무' not in headers:
                            hist_ws.update_cell(1, len(headers)+1, '차주업무')
                            headers.append('차주업무')
                except Exception as e:
                    # 일시적인 통신에러 방어용 기본 헤더
                    headers = ['프로젝트명', '업데이트일자', '금주업무', '차주업무']
                
                # 기존 입력값(최신) 가져오기
                try:
                    hist_df = pd.DataFrame(hist_ws.get_all_records())
                    exist_this, exist_next = "", ""
                    if not hist_df.empty and '프로젝트명' in hist_df.columns:
                        p_hist = hist_df[hist_df['프로젝트명'] == selected_pjt]
                        if not p_hist.empty:
                            exist_this = str(p_hist.iloc[-1].get('금주업무', ''))
                            exist_next = str(p_hist.iloc[-1].get('차주업무', ''))
                            if exist_this == 'nan': exist_this = ""
                            if exist_next == 'nan': exist_next = ""
                except:
                    exist_this, exist_next = "", ""
                        
                # 입력 폼
                with st.form("weekly_form"):
                    this_week_input = st.text_area("✔️ 금주 주요 업무 (이번 주에 진행한 핵심 내용)", value=exist_this, height=100, placeholder="예) 모듈 입고 완료, 하부 구조물 1구역 조립 완료")
                    next_week_input = st.text_area("🔜 차주 주요 업무 (다음 주에 진행할 핵심 내용)", value=exist_next, height=100, placeholder="예) 인버터 결선 작업 시작 및 사용전 검사 서류 접수")
                    
                    if st.form_submit_button("주간업무 저장 및 대시보드 반영", use_container_width=True):
                        row_data = [''] * len(headers)
                        if '프로젝트명' in headers: row_data[headers.index('프로젝트명')] = selected_pjt
                        if '업데이트일자' in headers: row_data[headers.index('업데이트일자')] = datetime.date.today().strftime("%Y-%m-%d")
                        if '금주업무' in headers: row_data[headers.index('금주업무')] = this_week_input
                        if '차주업무' in headers: row_data[headers.index('차주업무')] = next_week_input
                        
                        hist_ws.append_row(row_data)
                        st.success("✅ 주간 업무가 성공적으로 업데이트되었습니다! 통합 대시보드에서 확인해보세요.")
                        time.sleep(1.5)
                        st.rerun()

            # 데이터 수정 Grid (하단에 배치)
            st.write("---")
            st.write("📝 데이터(공정표) 상세 수정 (셀 더블클릭)")
            edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            if st.button("💾 데이터 저장하기", use_container_width=True):
                edited = edited.fillna("")
                edited = edited.astype(str)
                ws.clear(); ws.update([edited.columns.values.tolist()] + edited.values.tolist())
                st.success("저장되었습니다!"); time.sleep(1); st.rerun()

def view_solar(sh):
    st.title("📅 일 발전량 분석")
    with st.expander("📥 기상청 데이터 수집 도구"):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn_map = {127:"충주", 108:"서울", 131:"청주", 159:"부산", 112:"인천", 119:"수원", 129:"서산(당진)"}
        stn_id = c1.selectbox("수집 지점", list(stn_map.keys()), format_func=lambda x: stn_map[x], index=6)
        year = c2.selectbox("수집 연도", list(range(2026, 2019, -1)), index=1)
        if c3.button("🚀 데이터 동기화 실행", use_container_width=True):
            with st.spinner("데이터 요청 중..."):
                try:
                    db_ws = sh.worksheet('Solar_DB')
                    start, end = f"{year}0101", f"{year}1231"
                    if int(year) >= datetime.date.today().year: end = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey=ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe&numOfRows=366&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start}&endDt={end}'
                    res = requests.get(url, timeout=30).json()
                    items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    rows = [[i['tm'], stn_map[stn_id], round(get_safe_float(i.get('sumGsr', 0)) / 3.6, 2), get_safe_float(i.get('sumGsr', 0))] for i in items]
                    if rows:
                        all_val = db_ws.get_all_values()
                        if len(all_val) > 1:
                            df = pd.DataFrame(all_val[1:], columns=all_val[0])
                            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
                            df = df.loc[~((df['날짜'].dt.year == int(year)) & (df['지점'] == stn_map[stn_id]))].dropna(subset=['날짜'])
                            df['날짜'] = df['날짜'].dt.strftime('%Y-%m-%d')
                            db_ws.clear(); db_ws.append_row(all_val[0]); db_ws.append_rows(df.values.tolist())
                        db_ws.append_rows(rows); st.success("✅ 수집 완료!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"오류: {e}")

    col1, col2 = st.columns(2)
    sel_stn = col1.selectbox("분석 지점", ["충주", "서울", "인천", "수원", "서산(당진)", "청주", "부산"], index=4)
    sel_year = col2.selectbox("분석 연도", list(range(2026, 2019, -1)), index=1)
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            target = df.loc[(df['날짜'].dt.year == int(sel_year)) & (df['지점'] == sel_stn)].copy()
            if not target.empty:
                st.metric(f"{sel_year}년 {sel_stn} 평균 발전시간", f"{round(pd.to_numeric(target['발전시간']).mean(), 2)} h")
                m_avg = target.groupby(target['날짜'].dt.month)['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='날짜', y='발전시간', labels={'날짜':'월'}, color_discrete_sequence=['#ffca28']), use_container_width=True)
    except: pass

def view_kpi(sh):
    st.title("📉 전사 경영지표 (KPI)")
    try:
        df = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        st.dataframe(df, use_container_width=True)
    except: st.error("KPI 시트 존재 안함.")

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 프로젝트 설정 (마스터 관리)")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ 신규 등록", "✏️ 이름 수정", "🗑️ 삭제", "🔄 엑셀 동기화", "📥 엑셀 다운로드"])
    
    with tab1:
        new_pjt_name = st.text_input("새 프로젝트 명칭")
        if st.button("프로젝트 생성", type="primary", use_container_width=True):
            if new_pjt_name and new_pjt_name not in pjt_list:
                try:
                    sh.add_worksheet(title=new_pjt_name, rows="100", cols="20")
                    sh.worksheet(new_pjt_name).append_row(["대분류", "구분", "작업명", "시작일", "종료일", "진행상태", "비고", "진행률", "담당자"])
                    st.success(f"✅ '{new_pjt_name}' 생성 완료!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(e)
            else: st.warning("유효한 이름 입력 필요")
            
    with tab2:
        target_pjt = st.selectbox("이름을 변경할 프로젝트", ["선택"] + pjt_list)
        new_name_input = st.text_input("변경할 새 이름")
        if st.button("이름 변경 실행", use_container_width=True):
            if target_pjt != "선택" and new_name_input:
                try:
                    sh.worksheet(target_pjt).update_title(new_name_input)
                    st.success("✅ 변경 완료!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(e)
                
    with tab3:
        del_pjt = st.selectbox("삭제할 프로젝트", ["선택"] + pjt_list)
        if st.button("프로젝트 영구 삭제", type="primary", use_container_width=True) and st.checkbox("영구 삭제 확인"):
            if del_pjt != "선택":
                try:
                    sh.del_worksheet(sh.worksheet(del_pjt))
                    st.success("🗑️ 삭제 완료"); time.sleep(1); st.rerun()
                except Exception as e: st.error(e)
                
    with tab4:
        st.markdown("#### 🔄 엑셀 파일 업로드 & 구글 시트 동기화")
        sync_pjt = st.selectbox("업데이트할 프로젝트", ["선택"] + pjt_list)
        uploaded_file = st.file_uploader("엑셀 파일(.xlsx, .xlsm)", type=['xlsx', 'xls', 'xlsm'])
        if sync_pjt != "선택" and uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file).fillna("").astype(str)
                st.dataframe(df.head(), use_container_width=True)
                if st.button(f"🚀 '{sync_pjt}' 덮어쓰기", type="primary"):
                    with st.spinner('업데이트 중...'):
                        ws = sh.worksheet(sync_pjt)
                        ws.clear() 
                        ws.update([df.columns.values.tolist()] + df.values.tolist())
                        st.success("🎉 동기화 완료!"); time.sleep(1.5); st.rerun()
            except Exception as e: st.error(e)

    with tab5:
        st.markdown("#### 📥 엑셀 데이터 다운로드")
        colA, colB = st.columns(2)
        
        with colA:
            st.info("개별 현장 다운로드")
            dl_pjt = st.selectbox("선택", ["선택"] + pjt_list, label_visibility="collapsed")
            if dl_pjt != "선택":
                try:
                    df = pd.DataFrame(sh.worksheet(dl_pjt).get_all_records())
                    if not df.empty:
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name=dl_pjt[:31])
                        st.download_button(f"📊 '{dl_pjt}' 다운로드", data=output.getvalue(), file_name=f"{dl_pjt}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
                except Exception as e: st.error(e)
                
        with colB:
            st.warning("📚 마스터(전체) 데이터 일괄 다운로드")
            if st.button("전체 프로젝트 엑셀로 백업하기", use_container_width=True):
                with st.spinner("모든 시트를 하나로 병합 중입니다... (10~20초 소요)"):
                    try:
                        master_output = io.BytesIO()
                        with pd.ExcelWriter(master_output, engine='openpyxl') as writer:
                            for p_name in pjt_list:
                                try:
                                    p_df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                                    safe_sheet_name = p_name.replace("/", "").replace("\\", "")[:31]
                                    if not p_df.empty:
                                        p_df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
                                except: pass
                        st.download_button("📥 Master.xlsx 다운로드 준비완료! (Click)", data=master_output.getvalue(), file_name=f"Master_Data_{datetime.date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    except Exception as e:
                        st.error(f"마스터 백업 실패: {e}")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (Router)
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'conflict']]
        
        st.sidebar.title("📁 PMO 메뉴")
        st.sidebar.info(f"User: {st.session_state['user_id']}")
        
        menu_options = ["통합 대시보드", "리스크 현황(Risk)", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "프로젝트 설정"]
        menu = st.sidebar.radio("메뉴 선택", menu_options, index=0)
        
        st.sidebar.markdown("---")
        if st.sidebar.button("로그아웃"):
            st.session_state["logged_in"] = False; st.rerun()

        if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
        elif menu == "리스크 현황(Risk)": view_risk_dashboard(sh, pjt_list)
        elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
        elif menu == "일 발전량 분석": view_solar(sh)
        elif menu == "경영지표(KPI)": view_kpi(sh)
        elif menu == "프로젝트 설정": view_project_admin(sh, pjt_list)
