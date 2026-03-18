import streamlit as st
import os
import requests
import xml.etree.ElementTree as ET
import yfinance as yf
import pandas_ta as ta
from anthropic import Anthropic

# 1. 환경 설정 및 API 키 로드
api_key = st.secrets.get("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key)

# 웹 페이지 설정
st.set_page_config(page_title="AI+퀀트 투자 리포트", layout="wide")
st.title("📈 실시간 AI+퀀트 투자 리포트")
st.caption("15년 경력 퀀트 애널리스트 수준의 정밀 분석 (Claude 4.5 Sonnet 최적화)")

# 2. 뉴스 수집 함수 (최적화: 상위 10개로 제한)
def get_stock_news():
    url = "https://news.google.com/rss/search?q=주식+시장+전망+OR+급등주&hl=ko&gl=KR&ceid=KR:ko"
    response = requests.get(url)
    root = ET.fromstring(response.content)
    news_list = []
    for item in root.findall('.//item')[:10]:  # 토큰 절약을 위해 10개로 제한
        news_list.append(f"- {item.find('title').text}")
    return "\n".join(news_list)

# 3. 주요 지수 데이터 수집 (퀀트 지표 추가)
def get_market_data():
    indices = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11", "S&P500": "^GSPC", "나스닥": "^IXIC"}
    data_summary = ""
    for name, ticker in indices.items():
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if not df.empty:
            df['RSI'] = ta.rsi(df['Close'], length=14)
            last_close = df['Close'].iloc[-1]
            last_rsi = df['RSI'].iloc[-1]
            data_summary += f"{name}: 현재가 {last_close:.2f}, RSI {last_rsi:.1f}\n"
    return data_summary

# 4. 분석 실행 버튼
if st.button("🚀 전문가 모드 리포트 생성 시작"):
    with st.spinner("데이터 수집 및 AI 퀀트 분석 중..."):
        try:
            news_context = get_stock_news()
            market_context = get_market_data()
            
            # 전문가용 정밀 프롬프트 (비용 효율화 버전)
            prompt = f"""너는 15년 경력의 수석 퀀트 애널리스트다. 아래 데이터를 바탕으로 투자 리포트를 작성해라.
            
            [데이터 소스]
            시장 지표: {market_context}
            주요 뉴스: {news_context}
            
            [작성 규칙 - 엄격 준수]
            1. 인사말, 서론, 결론 요약 생략. 바로 본론 표부터 시작한다.
            2. 가독성을 위해 반드시 'Markdown 표'를 사용해라.
            3. [섹션 1: 시장 상황 분석], [섹션 2: 오늘의 특징주 및 전략], [섹션 3: 리스크 점검] 순서로 작성.
            4. 모든 분석은 매수/매도/관망 중 하나로 투자의견을 제시하고 기술적 근거를 1줄 요약해라.
            5. 핵심 위주로 800토큰 이내로 간결하게 작성하여 비용을 절감해라.
            6. 한국어로 작성해라."""

            # Claude 4.5 호출
            message = client.messages.create(
                model="claude-3-5-sonnet-20240620", # 현재 안정적인 Sonnet 모델 사용 (4.5 대응 가능)
                max_tokens=1000,
                temperature=0, # 객관성 유지를 위해 0으로 설정
                messages=[{"role": "user", "content": prompt}]
            )
            
            st.markdown("---")
            st.markdown(message.content[0].text)
            st.success("✅ 분석 완료 (비용 최적화 적용됨)")
            
        except Exception as e:
            st.error(f"오류 발생: {e}")
            st.info("Manage app -> Logs에서 상세 원인을 확인하세요.")

# 사이드바 정보
with st.sidebar:
    st.info("### 💰 비용 방어 운영 모드")
    st.write("- 뉴스 10개 제한 (Input 절감)")
    st.write("- 응답 800토큰 제한 (Output 절감)")
    st.write("- 수치 데이터(RSI) 기반 객관적 분석")
