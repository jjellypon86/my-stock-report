import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas_ta as ta
from anthropic import Anthropic

# 1. API 키 설정 (보안 유지)
api_key = st.secrets.get("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# 페이지 설정
st.set_page_config(page_title="실시간 AI 퀀트 리포트", layout="wide")
st.title("📈 실시간 AI+퀀트 투자 리포트")
st.caption("Claude 4.5 Sonnet 기반 전문가용 분석 솔루션")

# 2. 뉴스 수집 (비용 절감을 위해 상위 10개만 추출)
def get_stock_news():
    url = "https://news.google.com/rss/search?q=주식+시장+전망+OR+급등주&hl=ko&gl=KR&ceid=KR:ko"
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        news_list = [f"- {item.find('title').text}" for item in root.findall('.//item')[:10]]
        return "\n".join(news_list)
    except:
        return "뉴스를 가져오지 못했습니다."

# 3. 시장 지수 수집 (아까 성공한 로직 기반 안정화)
def get_market_data():
    indices = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11", "S&P500": "^GSPC", "나스닥": "^IXIC"}
    data_summary = ""
    for name, ticker in indices.items():
        try:
            # auto_adjust=True로 데이터 구조 단순화
            df = yf.download(ticker, period="60d", interval="1d", progress=False, auto_adjust=True)
            if not df.empty:
                rsi_series = ta.rsi(df['Close'], length=14)
                
                # 데이터가 어떤 형태든 마지막 숫자만 정확히 추출 (가장 안전한 방법)
                last_close = float(df['Close'].values[-1])
                last_rsi = float(rsi_series.values[-1])
                
                data_summary += f"{name}: 현재가 {last_close:.2f}, RSI {last_rsi:.1f}\n"
        except:
            continue
    return data_summary

# 4. 분석 실행
if st.button("🚀 전문가 리포트 생성 시작"):
    with st.spinner("데이터 분석 중... 잠시만 기다려 주세요."):
        news_context = get_stock_news()
        market_context = get_market_data()
        
        # [전문가용 프롬프트] 가독성 향상 및 출력 토큰 절약 설계
        prompt = f"""너는 15년 경력의 수석 퀀트 애널리스트다. 아래 데이터를 분석해라.
        
        [시장 지표]
        {market_context}
        [주요 뉴스]
        {news_context}
        
        [작성 규칙]
        1. 인사말, 서론 생략. 바로 본론 표(Table)부터 시작해라.
        2. [시장 상황], [특징주/전략], [리스크] 세 섹션으로 구성해라.
        3. 투자의견은 '매수/매도/관망' 중 하나로 제시하고 이유를 1줄 요약해라.
        4. 전문가답게 핵심 위주로 800토큰 이내로 간결하게 써라. 한국어 사용."""

        try:
            message = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            st.markdown("---")
            st.markdown(message.content[0].text)
            st.success("✅ 분석이 완료되었습니다. (비용 최적화 모드)")
        except Exception as e:
            st.error(f"AI 호출 오류: {e}")

# 사이드바 (운영 정보)
with st.sidebar:
    st.info("💡 운영 팁")
    st.write("- 뉴스 10개 제한으로 입력 비용 절감")
    st.write("- 표 형식 출력으로 가독성 및 출력 비용 최적화")
    st.write(f"- 현재 잔액: $4.66 내외")
