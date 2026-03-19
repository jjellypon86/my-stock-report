import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas_ta as ta
import datetime
from dotenv import load_dotenv
from anthropic import Anthropic
from pykrx import stock as krx

# 1. 인프라 설정
st.set_page_config(page_title="AI 투자 리포트", page_icon="📈", layout="centered")
load_dotenv()
api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# 2. 뉴스 수집 (비즈니스 + IT 기술)
def get_headlines():
    urls = [
        "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=ko&gl=KR&ceid=KR:ko"
    ]
    all_headlines = []
    for url in urls:
        try:
            root = ET.fromstring(requests.get(url, timeout=5).content)
            all_headlines.extend([item.find('title').text for item in root.findall('.//item')[:15]])
        except: continue
    sorted_headlines = sorted(list(set(all_headlines))) 
    return "\n".join([f"{i + 1}. {title}" for i, title in enumerate(sorted_headlines)])

# 3. 시장 지수 분석 (코스피/코스닥)
def get_market_context():
    indices = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}
    summary = ""
    for name, ticker in indices.items():
        try:
            df = yf.download(ticker, period="60d", progress=False)
            if not df.empty:
                rsi = float(ta.rsi(df['Close'], length=14).iloc[-1])
                price = float(df['Close'].iloc[-1])
                summary += f"{name}: {price:.2f} (RSI: {rsi:.1f}) / "
        except: continue
    return summary if summary else "시장 지수 일시적 수집 불가"

# 4. [핵심] 절대 뻗지 않는 실시간 시세 검증 (pykrx 1순위)
def verify_realtime_price(ticker_code):
    try:
        # 최근 3영업일(주말 대비) 날짜 구하기
        today = datetime.datetime.now()
        dates_to_check = [(today - datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(4)]
        
        # 최신 날짜부터 역순으로 시세 확인
        for date_str in dates_to_check:
            df = krx.get_market_ohlcv_by_date(date_str, date_str, ticker_code)
            if not df.empty and int(df['종가'].iloc[0]) > 0:
                price = int(df['종가'].iloc[0])
                return price, f"{ticker_code} (KRX 실시간)"
                
    except Exception as e:
        # pykrx마저 실패하면 yfinance로 최후의 시도
        try:
            stock = yf.Ticker(f"{ticker_code}.KQ")
            df = stock.history(period="1d")
            if not df.empty:
                return float(df['Close'].iloc[-1]), f"{ticker_code}.KQ"
        except: pass
    
    return None, None

# --- UI 화면 및 실행 ---
st.title("📊 실시간 AI+퀀트 투자 리포트")
st.markdown("야후 파이낸스 장애를 우회하여 **KRX 직접 연결**로 실시간 시세를 검증합니다.")

if st.button("🚀 무장애 1픽 분석 시작"):
    with st.spinner("데이터 분석 및 KRX 시세 동기화 중..."):
        try:
            news_data = get_headlines()
            market_context = get_market_context()

            # [STEP 1] 뉴스 분석 -> 종목 코드 추출
            selector_prompt = f"아래 뉴스를 보고 오늘 급등할 종목 1개의 '6자리 숫자 코드'만 출력해. (예: 108490)\n뉴스: {news_data}"
            selection = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": selector_prompt}]
            )
            discovered_ticker = selection.content[0].text.strip()
            
            # 숫자 6자리가 아닐 경우를 대비한 정제
            import re
            numbers = re.findall(r'\d{6}', discovered_ticker)
            if not numbers:
                st.error("AI가 유효한 6자리 종목 코드를 추출하지 못했습니다. 다시 시도해 주세요.")
                st.stop()
            clean_ticker = numbers[0]

            # [STEP 2] 파이썬이 실시간 시세 주입 (환각/404 원천 차단)
            real_price, full_symbol = verify_realtime_price(clean_ticker)

            if not real_price:
                st.error(f"❌ 종목({clean_ticker})의 실시간 시세를 가져올 수 없습니다. 시스템을 중단하여 API 비용을 보호합니다.")
                st.stop()

            # [STEP 3] 검증된 데이터로 리포트 생성
            final_prompt = f"""
            너는 대한민국 수석 퀀트다. 아래 실시간 데이터를 바탕으로 리포트를 작성해라.
            현재가 정보는 반드시 제공된 {real_price}원만 사용하고, 네 지식을 절대 쓰지 마.

            [시장 데이터]: {market_context}
            [대상 종목]: {full_symbol} / 현재가: {real_price:,.0f}원
            [뉴스 데이터]: {news_data}

            [출력 요구사항]:
            1. 📰 메인 뉴스 제목: 파급력 큰 3가지
            2. 💡 인사이트: 뉴스 이면의 의도 분석
            3. 🚀 1주일 내 5% 급등 기대 종목 Top 1: (종목명/목표가/손절가)
            4. 🎯 추천 이유: 기술적 지표와 {real_price:,.0f}원 기준의 상승 여력 분석
            5. 🏁 최종 실행 가이드: 내일 오전 구체적 대응 전략
            """

            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": final_prompt}]
            )

            st.markdown("---")
            st.markdown(response.content[0].text)
            st.success(f"✅ {full_symbol} (현재가: {real_price:,.0f}원) 분석 및 시세 동기화 완료")

        except Exception as e:
            st.error(f"❌ 분석 중 오류가 발생했습니다: {e}")
