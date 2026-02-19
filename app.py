import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import io  # 엑셀 파일 변환을 위해 추가된 라이브러리

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v3.1.4", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    </style>
    <div class="footer">시스템 상태: 정상 (v3.1.4 Default: Seosan/2025) | 데이터 출처: 기상청 API & 구글 클라우드</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def check_login():
    if st.session_state.get("logged_in", False): return True
    
    st.title("🏗️ PM 통합 관리 시스템 (v3.1.4)")
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

# ---------------------------------------------------------
# [SECTION 2] 각 기능별 뷰(View) 함수
# ---------------------------------------------------------

def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드")
    st.info(f"현재 관리 중인 현장: {len(pjt_list)}개")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                p_df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
                last_status = "업데이트 대기 중"
                if not hist_df.empty:
                    row = hist_df[hist_df['프로젝트명'] == p_name]
                    if not row.empty: last_status = row.iloc[-1]['주요현황']
                st.markdown(f'<div class="pjt-card"><h4>🏗️ {p_name}</h4><p style="font-size:14px; color:#666;">{last_status}</p></div>', unsafe_allow_html=True)
                st.progress(prog/100, text=f"진척률: {prog}%")
    except Exception as e: st.error(f"대시보드 로드 오류: {e}")

def view_solar(sh):
    st.title("📅 일 발전량 분석")
    
    # 1. 데이터 수집 도구
    with st.expander("📥 기상청 데이터 수집 도구", expanded=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn_map = {127:"충주", 108:"서울", 131:"청주", 159:"부산", 112:"인천", 119:"수원", 129:"서산(당진)"}
        
        stn_id = c1.selectbox("수집 지점", list(stn_map.keys()), format_func=lambda x: stn_map[x], index=6)
        year = c2.selectbox("수집 연도", list(range(2026, 2019, -1)), index=1)
        
        if c3.button("🚀 데이터 동기화 실행", use_container_width=True):
            with st.spinner(f"{stn_map[stn_id]} 데이터 요청 중... (최대 30초)"):
                try:
                    db_ws = sh.worksheet('Solar_DB')
                    start, end = f"{year}0101", f"{year}1231"
                    if int(year) >= datetime.date.today().year: end = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey=ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe&numOfRows=366&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start}&endDt={end}'
                    res = requests.get(url, timeout=30).json()
                    items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    rows = []
                    for i in items:
                        gsr_val = get_safe_float(i.get('sumGsr', 0))
                        gen_val = round(gsr_val / 3.6, 2)
                        rows.append([i['tm'], stn_map[stn_id], gen_val, gsr_val])
                    if rows:
                        all_val = db_ws.get_all_values()
                        if len(all_val) > 1:
                            df = pd.DataFrame(all_val[1:], columns=all_val[0])
                            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
                            df = df.loc[~((df['날짜'].dt.year == int(year)) & (df['지점'] == stn_map[stn_id]))].dropna(subset=['날짜'])
                            df['날짜'] = df['날짜'].dt.strftime('%Y-%m-%d')
                            db_ws.clear(); db_ws.append_row(all_val[0]); db_ws.append_rows(df.values.tolist())
                        db_ws.append_rows(rows); st.success(f"✅ {year}년 {stn_map[stn_id]} 데이터 {len(rows)}건 수집 완료!"); time.sleep(1); st.rerun()
                    else: st.warning("수집된 데이터가 없습니다.")
                except Exception as e: st.error(f"오류 발생: {e}")

    # 2. 분석 차트
    st.subheader("📊 연간 발전 효율 차트")
    col1, col2 = st.columns(2)
    
    sel_stn = col1.selectbox("분석 지점", ["충주", "서울", "인천", "수원", "서산(당진)", "청주", "부산"], index=4)
    sel_year = col2.selectbox("분석 연도", list(range(2026, 2019, -1)), index=1)
    
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            target = df.loc[(df['날짜'].dt.year == int(sel_year)) & (df['지점'] == sel_stn)].copy()
            if not target.empty:
                avg = round(pd.to_numeric(target['발전시간']).mean(), 2)
                st.metric(f"{sel_year}년 {sel_stn} 평균", f"{avg} h")
                target['월'] = target['날짜'].dt.month
                m_avg = target.groupby('월')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', color_discrete_sequence=['#ffca28']), use_container_width=True)
            else: st.warning("해당 조건의 데이터가 없습니다. 위 도구에서 먼저 수집해주세요.")
    except: st.warning("데이터베이스 로드 실패")

def view_project_detail(sh, pjt_list):
    st.title("🏗️ 개별 프로젝트 상세 관리")
    selected_pjt = st.selectbox("관리할 현장을 선택하세요", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        if not df.empty and '시작일' in df.columns:
            try:
                chart_df = df.copy()
                chart_df['시작일'] = pd.to_datetime(chart_df['시작일'], errors='coerce')
                chart_df['종료일'] = pd.to_datetime(chart_df['종료일'], errors='coerce')
                chart_df = chart_df.dropna(subset=['시작일', '종료일'])
                y_col = '대분류' if '대분류' in chart_df.columns else chart_df.columns[0]
                fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y=y_col, color="진행률", color_continuous_scale='RdYlGn', range_color=[0, 100])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            except: st.caption("차트 생성 실패 (날짜 확인 필요)")
        st.write("📝 데이터 수정")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 저장하기", use_container_width=True):
            edited = edited.fillna("")
            edited = edited.astype(str)
            ws.clear(); ws.update([edited.columns.values.tolist()] + edited.values.tolist())
            st.success("저장되었습니다!"); time.sleep(1); st.rerun()

def view_kpi(sh):
    st.title("📉 전사 경영지표 (KPI)")
    try:
        df = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        st.dataframe(df, use_container_width=True)
    except: st.error("KPI 시트가 존재하지 않습니다.")

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 프로젝트 설정 (마스터 관리)")
    
    # 동기화 및 다운로드 탭 포함 5개 구성
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ 신규 등록", "✏️ 이름 수정", "🗑️ 삭제", "🔄 엑셀 동기화", "📥 엑셀 다운로드"])
    
    with tab1:
        new_pjt_name = st.text_input("새 프로젝트 명칭")
        if st.button("프로젝트 생성", type="primary", use_container_width=True):
            if new_pjt_name and new_pjt_name not in pjt_list:
                try:
                    sh.add_worksheet(title=new_pjt_name, rows="100", cols="20")
                    ws = sh.worksheet(new_pjt_name)
                    ws.append_row(["대분류", "구분", "작업명", "시작일", "종료일", "진행률", "담당자", "비고"])
                    st.success(f"✅ '{new_pjt_name}' 생성 완료!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"생성 실패: {e}")
            else: st.warning("유효한 이름을 입력해주세요.")
            
    with tab2:
        target_pjt = st.selectbox("이름을 변경할 프로젝트", ["선택"] + pjt_list, key="rename_sel")
        new_name_input = st.text_input("변경할 새 이름", key="rename_input")
        if st.button("이름 변경 실행", use_container_width=True):
            if target_pjt != "선택" and new_name_input:
                try:
                    ws = sh.worksheet(target_pjt)
                    ws.update_title(new_name_input)
                    st.success(f"✅ 변경 완료!"); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"변경 실패: {e}")
                
    with tab3:
        del_pjt = st.selectbox("삭제할 프로젝트 선택", ["선택"] + pjt_list, key="del_sel")
        confirm_del = st.checkbox("데이터 영구 삭제를 확인했습니다.")
        if st.button("프로젝트 영구 삭제", type="primary", use_container_width=True):
            if del_pjt != "선택" and confirm_del:
                try:
                    ws = sh.worksheet(del_pjt)
                    sh.del_worksheet(ws)
                    st.success(f"🗑️ 삭제되었습니다."); time.sleep(1); st.rerun()
                except Exception as e: st.error(f"삭제 실패: {e}")
                
    with tab4:
        st.markdown("#### 🔄 엑셀 파일 업로드 & 구글 시트 동기화")
        st.info("로컬에서 작성한 엑셀 파일로 특정 프로젝트의 데이터를 일괄 덮어쓰기 합니다.")
        
        sync_pjt = st.selectbox("데이터를 업데이트할 프로젝트 선택", ["선택"] + pjt_list, key="sync_sel")
        uploaded_file = st.file_uploader("엑셀 파일(.xlsx, .xlsm)을 업로드하세요", type=['xlsx', 'xls', 'xlsm'])
        
        if sync_pjt != "선택" and uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)
                df = df.fillna("")
                df = df.astype(str) 
                
                st.write(f"**미리보기 ({len(df)}행 감지됨):**")
                st.dataframe(df.head(10), use_container_width=True)
                
                if st.button(f"🚀 '{sync_pjt}' 프로젝트 구글 시트 덮어쓰기", type="primary"):
                    with st.spinner('구글 스프레드시트 업데이트 중... (기존 데이터는 삭제됩니다)'):
                        ws = sh.worksheet(sync_pjt)
                        ws.clear() 
                        ws.update([df.columns.values.tolist()] + df.values.tolist())
                        
                        st.success(f"🎉 '{sync_pjt}' 데이터 동기화가 완료되었습니다!")
                        time.sleep(1.5)
                        st.rerun()
                        
            except Exception as e:
                st.error(f"엑셀 파일 처리 중 오류가 발생했습니다: {e}")

    with tab5:
        st.markdown("#### 📥 구글 시트 데이터 엑셀 다운로드")
        st.info("웹(구글 시트)에 저장된 최신 프로젝트 데이터를 엑셀 파일로 내려받습니다.")
        
        dl_pjt = st.selectbox("다운로드할 프로젝트 선택", ["선택"] + pjt_list, key="dl_sel")
        
        if dl_pjt != "선택":
            with st.spinner("엑셀 파일을 생성하는 중..."):
                try:
                    ws = sh.worksheet(dl_pjt)
                    df = pd.DataFrame(ws.get_all_records())
                    
                    if not df.empty:
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name=dl_pjt)
                        excel_data = output.getvalue()
                        
                        st.success(f"✅ '{dl_pjt}' 엑셀 파일 준비 완료!")
                        
                        st.download_button(
                            label=f"📊 '{dl_pjt}' 엑셀 파일 다운로드 (Click)",
                            data=excel_data,
                            file_name=f"{dl_pjt}_최신데이터.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True
                        )
                    else:
                        st.warning("해당 프로젝트에 다운로드할 데이터가 없습니다.")
                except Exception as e:
                    st.error(f"다운로드 준비 중 오류가 발생했습니다: {e}")

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
        
        menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "일 발전량 분석", "프로젝트 상세", "경영지표(KPI)", "프로젝트 설정"], index=0)
        st.sidebar.markdown("---")
        if st.sidebar.button("로그아웃"):
            st.session_state["logged_in"] = False; st.rerun()

        if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
        elif menu == "일 발전량 분석": view_solar(sh)
        elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
        elif menu == "경영지표(KPI)": view_kpi(sh)
        elif menu == "프로젝트 설정": view_project_admin(sh, pjt_list)
