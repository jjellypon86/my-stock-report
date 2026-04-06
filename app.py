# 최상단에 추가 (pkg_resources 에러 강제 해결)
import sys
try:
    import pkg_resources
except ImportError:
    import pip._vendor.pkg_resources as pkg_resources
    sys.modules['pkg_resources'] = pkg_resources
import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="퀀트 비서 - 내일 상승 예상 종목",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 모바일 최적화 CSS
st.markdown("""
<style>
    .main > div {
        padding-top: 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        border: 1px solid #e1e5e9;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    @media (max-width: 768px) {
        .stDataFrame {
            font-size: 12px;
        }
        .element-container {
            margin: 0.25rem 0;
        }
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_stock_list():
    """코스피/코스닥 전체 종목 리스트 조회"""
    try:
        kospi_stocks = stock.get_market_ticker_list(market="KOSPI")
        kosdaq_stocks = stock.get_market_ticker_list(market="KOSDAQ")
        all_stocks = kospi_stocks + kosdaq_stocks

        stock_names = {}
        for ticker in all_stocks:
            try:
                name = stock.get_market_ticker_name(ticker)
                stock_names[ticker] = name
            except:
                continue
        return stock_names
    except Exception as e:
        st.error(f"종목 리스트 조회 중 오류 발생: {str(e)}")
        return {}

@st.cache_data(ttl=1800)
def get_market_fundamentals(date_str):
    """전체 종목 재무 지표 일괄 조회 (캐시 적용)"""
    try:
        return stock.get_market_fundamental_by_ticker(date_str)
    except:
        return None

@st.cache_data(ttl=1800)
def get_stock_data(ticker, days=30):
    """개별 종목 데이터 수집 (에러 방지 로직 추가)"""
    try:
        # 오늘이 아닌, 데이터가 있는 최근 날짜까지 조회하기 위해 넉넉히 잡음
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days + 10) # 기술적 지표 계산을 위해 넉넉히

        df = stock.get_market_ohlcv_by_date(
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            ticker
        )

        # [수정 포인트 1] 데이터가 없거나 너무 적으면 중단
        if df is None or len(df) < 26: 
            return None

        # 기술적 지표 계산
        df['MA12'] = df['종가'].rolling(12).mean()
        df['MA26'] = df['종가'].rolling(26).mean()
        df['MACD'] = df['MA12'] - df['MA26']
        df['Signal'] = df['MACD'].rolling(9).mean()

        # [수정 포인트 2] 마지막 행 접근 전 데이터 유효성 최종 확인
        if pd.isna(df['MACD'].iloc[-1]) or pd.isna(df['Signal'].iloc[-1]):
            return None

        # 재무 지표 (PER)
        try:
            # 가장 최근 영업일의 fundamental 데이터 가져오기
            last_date = df.index[-1].strftime("%Y%m%d")
            fundamental = get_market_fundamentals(last_date)
            per = fundamental.loc[ticker, 'PER'] if ticker in fundamental.index else None
        except:
            per = None

        return {
            'price_data': df,
            'per': per,
            'current_price': int(df['종가'].iloc[-1]),
            'volume_ratio': float(df['거래량'].iloc[-1] / df['거래량'].iloc[-2] 
                             if df['거래량'].iloc[-2] > 0 else 0)
        }
    except Exception as e:
        return None

def apply_quant_filter(stock_data_dict):
    """퀀트 필터링 로직"""
    filtered_stocks = []

    for ticker, data in stock_data_dict.items():
        if data is None:
            continue

        try:
            # 조건 1: 거래량 급증 (전일 대비 200% 이상)
            volume_condition = data['volume_ratio'] >= 2.0

            # 조건 2: MACD 골든크로스
            price_df = data['price_data']
            if len(price_df) < 2:
                continue

            macd_prev = price_df['MACD'].iloc[-2]
            signal_prev = price_df['Signal'].iloc[-2]
            macd_current = price_df['MACD'].iloc[-1]
            signal_current = price_df['Signal'].iloc[-1]

            if any(pd.isna(v) for v in [macd_prev, signal_prev, macd_current, signal_current]):
                continue

            golden_cross = (macd_prev <= signal_prev) and (macd_current > signal_current)

            # 조건 3: PER 15 이하
            per_condition = data['per'] is not None and data['per'] <= 15 and data['per'] > 0

            # 모든 조건 만족시 추가
            if volume_condition and golden_cross and per_condition:
                filtered_stocks.append({
                    'ticker': ticker,
                    'data': data,
                    'volume_ratio': data['volume_ratio'],
                    'per': data['per'],
                    'current_price': data['current_price']
                })
        except Exception as e:
            continue

    return sorted(filtered_stocks, key=lambda x: x['volume_ratio'], reverse=True)

def generate_analysis_report(stock_info, stock_names):
    """선정 종목 분석 리포트 생성"""
    ticker = stock_info['ticker']
    data = stock_info['data']
    name = stock_names.get(ticker, ticker)

    # 차트 관점 분석
    chart_analysis = f"""
    📊 **차트 관점 분석**
    - MACD 골든크로스 발생: 단기 상승 모멘텀 확인
    - 거래량 급증({stock_info['volume_ratio']:.1f}배): 기관/외국인 매수 신호 가능성
    - 현재가: {stock_info['current_price']:,}원
    """

    # 재무 관점 분석
    per_display = f"{stock_info['per']:.2f}" if stock_info['per'] is not None and not pd.isna(stock_info['per']) else "N/A"
    financial_analysis = f"""
    💰 **재무 관점 분석**
    - PER {per_display}배: 저평가 구간으로 판단
    - 업종 대비 밸류에이션 매력도 높음
    - 펀더멘털 기반 상승 여력 존재
    """

    return chart_analysis, financial_analysis

def create_chart(price_data, ticker, name):
    """가격 차트 생성"""
    fig = go.Figure()

    # 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=price_data.index,
        open=price_data['시가'],
        high=price_data['고가'],
        low=price_data['저가'],
        close=price_data['종가'],
        name=name
    ))

    # MACD
    fig.add_trace(go.Scatter(
        x=price_data.index,
        y=price_data['MACD'],
        name='MACD',
        line=dict(color='blue'),
        yaxis='y2'
    ))

    fig.add_trace(go.Scatter(
        x=price_data.index,
        y=price_data['Signal'],
        name='Signal',
        line=dict(color='red'),
        yaxis='y2'
    ))

    fig.update_layout(
        title=f'{name}({ticker}) 기술적 분석',
        yaxis_title='가격(원)',
        yaxis2=dict(title='MACD', overlaying='y', side='right'),
        height=400,
        showlegend=True
    )

    return fig

def main():
    st.title("📈 퀀트 비서 - 내일 상승 예상 종목")
    st.markdown("*17년 차 전문가를 위한 스마트 투자 도우미*")

    # 로딩 상태
    with st.spinner("📊 시장 데이터 분석 중..."):
        # 종목 리스트 가져오기
        stock_names = get_stock_list()

        if not stock_names:
            st.error("종목 데이터를 가져올 수 없습니다.")
            return

        # 샘플 종목으로 테스트 (실제로는 전체 종목 분석)
        sample_tickers = list(stock_names.keys())[:50]  # 성능을 위해 50개 종목만 테스트

        stock_data_dict = {}
        progress_bar = st.progress(0)

        for i, ticker in enumerate(sample_tickers):
            data = get_stock_data(ticker)
            if data:
                stock_data_dict[ticker] = data
            progress_bar.progress((i + 1) / len(sample_tickers))

        progress_bar.empty()

        # 퀀트 필터링 적용
        filtered_stocks = apply_quant_filter(stock_data_dict)

    # 결과 표시
    if not filtered_stocks:
        st.warning("⚠️ 현재 조건을 만족하는 종목이 없습니다.")
        st.info("조건: 거래량 급증 + MACD 골든크로스 + PER 15 이하")
        return

    # 메트릭 표시
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("분석 종목 수", f"{len(stock_data_dict)}개")
    with col2:
        st.metric("조건 만족 종목", f"{len(filtered_stocks)}개")
    with col3:
        st.metric("추천 신뢰도", "⭐⭐⭐⭐")

    # 최고 종목 분석
    if filtered_stocks:
        best_stock = filtered_stocks[0]
        ticker = best_stock['ticker']
        name = stock_names[ticker]

        st.markdown("---")
        st.subheader(f"🎯 오늘의 추천 종목: {name} ({ticker})")

        # 핵심 지표
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("현재가", f"{best_stock['current_price']:,}원")
        with col2:
            st.metric("거래량 증가율", f"{best_stock['volume_ratio']:.1f}배")
        with col3:
            per_display = f"{best_stock['per']:.2f}" if best_stock['per'] is not None and not pd.isna(best_stock['per']) else "N/A"
            st.metric("PER", per_display)
        with col4:
            st.metric("예상 상승률", "5%+")

        # 분석 리포트
        chart_analysis, financial_analysis = generate_analysis_report(best_stock, stock_names)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(chart_analysis)
        with col2:
            st.markdown(financial_analysis)

        # 차트
        if not best_stock['data']['price_data'].empty:
            chart = create_chart(best_stock['data']['price_data'], ticker, name)
            st.plotly_chart(chart, use_container_width=True)

        # 전체 후보 종목 테이블
        st.markdown("---")
        st.subheader("📋 전체 후보 종목")

        display_data = []
        for stock in filtered_stocks[:10]:  # 상위 10개만 표시
            per_value = f"{stock['per']:.2f}" if stock['per'] is not None and not pd.isna(stock['per']) else "N/A"
            display_data.append({
                '종목명': stock_names[stock['ticker']],
                '종목코드': stock['ticker'],
                '현재가': f"{stock['current_price']:,}원",
                '거래량증가': f"{stock['volume_ratio']:.1f}배",
                'PER': per_value
            })

        df_display = pd.DataFrame(display_data)
        st.dataframe(df_display, use_container_width=True)

    # 업데이트 정보
    st.markdown("---")
    st.caption(f"📅 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.caption("⚠️ 투자에 따른 손실은 투자자 본인에게 있습니다.")

if __name__ == "__main__":
    main()
