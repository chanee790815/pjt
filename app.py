import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

# 1. 페이지 설정 (반응형의 핵심: layout="wide")
st.set_page_config(
    page_title="나만의 금시세",  # 아이콘 이름 자동 설정용
    page_icon="💰", 
    layout="wide",            # 'centered' -> 'wide'로 변경 (아이패드/PC용)
    initial_sidebar_state="collapsed"
)

# 2. CSS 스타일 주입 (기기별 폰트 크기 및 여백 최적화)
st.markdown("""
    <style>
    /* 모바일에서 메트릭(숫자) 글씨 크기 키우기 */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
    /* 탭 글씨 크기 키우기 */
    button[data-baseweb="tab"] {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    /* 모바일 좌우 여백 줄이기 */
    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 함수: 데이터 가져오기 ---
@st.cache_data(ttl=300) # 5분마다 캐시 갱신 (속도 향상)
def get_financial_data():
    tickers = {
        'Gold_Intl_USD': 'GC=F',
        'Exchange_Rate': 'KRW=X',
        'SP500': '^GSPC',
        'Nasdaq': '^IXIC',      # 나스닥 추가
        'Trans_Avg': '^DJT',
        'US_10Y': '^TNX'
    }
    result = {}
    for key, ticker_symbol in tickers.items():
        try:
            df = yf.Ticker(ticker_symbol).history(period="5d")
            if not df.empty:
                result[key] = df['Close'].iloc[-1]
            else:
                result[key] = 0.0
        except:
            result[key] = 0.0
    return result

def get_krx_gold_price():
    url = "https://finance.naver.com/marketindex/goldDetail.naver"
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_str = soup.select_one("em.no_up")
        if not price_str: price_str = soup.select_one("em.no_down")
        if not price_str: price_str = soup.select_one("em.no_today")
        
        if price_str:
            return float(price_str.get_text(strip=True).replace(',', ''))
        return 0.0
    except:
        return 0.0

# --- 메인 화면 구성 ---
st.title("💰 Market Dashboard")
st.caption(f"Last Update: {time.strftime('%m-%d %H:%M')} (5분 주기)")

if st.button('새로고침 🔄', use_container_width=True): # 버튼도 꽉 차게
    st.rerun()

with st.spinner('데이터 수신 중...'):
    macro_data = get_financial_data()
    krx_gold = get_krx_gold_price()
    
    # 계산 로직
    intl_gold_usd = macro_data.get('Gold_Intl_USD', 0)
    exchange_rate = macro_data.get('Exchange_Rate', 1300)
    
    if intl_gold_usd > 0 and exchange_rate > 0:
        intl_gold_krw_g = (intl_gold_usd * exchange_rate) / 31.1034768
        spread = ((krx_gold - intl_gold_krw_g) / intl_gold_krw_g) * 100 if krx_gold > 0 else 0
    else:
        intl_gold_krw_g = 0
        spread = 0

    # --- [섹션 1] 하이라이트 (금 시세) ---
    st.subheader("📊 Gold Spread (Kim-P)")
    
    # 컨테이너를 사용하여 박스처럼 묶음
    with st.container(border=True):
        # PC에서는 3칸, 모바일에서는 자동 줄바꿈
        col1, col2, col3 = st.columns([1, 1, 1.2]) 
        
        with col1:
            st.metric("KRX 국내시세 (g)", f"{krx_gold:,.0f}원")
        with col2:
            st.metric("국제 이론가 (g)", f"{intl_gold_krw_g:,.0f}원")
        with col3:
            st.metric(
                "괴리율 (Spread)", 
                f"{spread:.2f}%", 
                delta=f"{spread:.2f}%", 
                delta_color="inverse"
            )
            
        # 메시지 박스
        if spread > 1.0:
            st.warning(f"⚠️ 국내가 {spread:.1f}% 더 비쌉니다.")
        elif spread < -0.5:
            st.success("✅ 국내가 더 저렴합니다 (역프리미엄).")

    # --- [섹션 2] 시장 지표 (탭 구성) ---
    st.markdown("### 🌍 Global Market")
    
    tab1, tab2 = st.tabs(["🇺🇸 미 증시/금리", "🚛 경기/물동량"])
    
    with tab1:
        # PC에선 4개 나란히, 모바일에선 2개씩 2줄로 보이게 됨
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("환율 (USD)", f"{exchange_rate:,.1f}원")
        c2.metric("S&P 500", f"{macro_data.get('SP500', 0):,.0f}")
        c3.metric("나스닥", f"{macro_data.get('Nasdaq', 0):,.0f}")
        c4.metric("미국채 10년", f"{macro_data.get('US_10Y', 0):.2f}%")
        
    with tab2:
        c_a, c_b = st.columns(2)
        with c_a:
             st.metric("다우 운송지수", f"{macro_data.get('Trans_Avg', 0):,.0f}")
        with c_b:
             st.caption("운송지수는 실물 경기의 선행 지표입니다. (Dow Jones Trans.)")
             
        # 차트 그리기 (반응형으로 자동 조절됨)
        try:
            chart_data = yf.Ticker('^DJT').history(period='1mo')['Close']
            st.line_chart(chart_data)
        except:
            st.write("차트 데이터 로딩 실패")
