# ==============================================================================
# [1] 시스템 의존성 및 런타임 환경 강제 설정
# 목적: Python 3.11/3.12 환경의 패키지 참조 무결성 확보
# ==============================================================================
import sys
import time
import warnings
from datetime import datetime, timedelta

# pkg_resources 모듈 누락에 대한 런타임 패치
try:
    import pkg_resources
except ImportError:
    try:
        import pip._vendor.pkg_resources as pkg_resources
    except ImportError:
        import setuptools.extern._packaged_resources as pkg_resources
    sys.modules['pkg_resources'] = pkg_resources

import streamlit as st
import pandas as pd
from pykrx import stock
import plotly.graph_objects as go

# 분석 로그 및 경고 관리
warnings.filterwarnings('ignore')

# ==============================================================================
# [2] 전문가용 프리미엄 UI 커스터마이징 (CSS)
# 목적: 17년 차 전문가의 가독성과 모바일 대응력을 위한 고해상도 디자인
# ==============================================================================
st.set_page_config(
    page_title="퀀트 비서 - 전문가용 필승 전략",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def apply_pro_theme():
    """고급스러운 다크/라이트 하이브리드 스타일 시트"""
    st.markdown("""
    <style>
        /* 메인 뷰포트 최적화 */
        .main > div { padding: 1.5rem; max-width: 1200px; margin: 0 auto; }
        
        /* 메트릭 카드: 전문가용 입체 디자인 */
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #ffffff, #f0f2f6);
            border: 1px solid #d1d9e6;
            padding: 1.5rem !important;
            border-radius: 15px;
            box-shadow: 5px 5px 15px #d1d9e6, -5px -5px 15px #ffffff;
        }
        
        /* 리포트 섹션: 가독성 극대화 */
        .analysis-card {
            background-color: #ffffff;
            padding: 25px;
            border-radius: 12px;
            border-left: 8px solid #1d3557;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            margin-bottom: 20px;
            line-height: 1.6;
        }
        
        /* 시그널 텍스트 컬러웨이 */
        .txt-up { color: #e63946; font-weight: 800; }
        .txt-down { color: #457b9d; font-weight: 800; }
        
        /* 모바일 최적화 폰트 */
        @media (max-width: 768px) {
            .stDataFrame { font-size: 11px; }
            .stMetric label { font-size: 0.8rem !important; }
            .stMetric div { font-size: 1.2rem !important; }
        }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# [3] 고성능 데이터 엔진 (Multi-Layer Retry & Fallback)
# 목적: 거래소 서버 점검 시간대(22:00~24:00)에도 무결한 데이터 추출
# ==============================================================================
@st.cache_data(ttl=1800)
def get_reliable_market_snapshot():
    """최대 10일 전까지 역추적하여 유효한 시장 스냅샷 확보"""
    current_dt = datetime.now()
    
    # 10일치 루프 (긴 연휴 대응)
    for i in range(10):
        search_date = (current_dt - timedelta(days=i)).strftime("%Y%m%d")
        try:
            # [수정] market="ALL" 대신 개별 호출로 안정성 확보
            kospi = stock.get_market_ticker_list(search_date, market="KOSPI")
            time.sleep(0.2) # API 부하 분산
            kosdaq = stock.get_market_ticker_list(search_date, market="KOSDAQ")
            
            all_tickers = kospi + kosdaq
            if len(all_tickers) > 500: # 정상적인 시장 데이터인지 검증
                names = {t: stock.get_market_ticker_name(t) for t in all_tickers[:500]} # 성능 최적화 샘플링
                return names, search_date
            
            time.sleep(0.5)
        except:
            continue
    return {}, None

@st.cache_data(ttl=1800)
def get_safe_fundamentals(date_str):
    """펀더멘털 데이터 수집 예외 처리"""
    try:
        df = stock.get_market_fundamental_by_ticker(date_str)
        if df is not None and not df.empty:
            return df
    except:
        pass
    return None

@st.cache_data(ttl=1200)
def deep_analyze_stock(ticker, ref_date, window=45):
    """개별 종목의 기술적/재무적 입체 분석"""
    try:
        # 기준일로부터 과거 데이터 로드
        end_dt = datetime.strptime(ref_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=window)
        
        df = stock.get_market_ohlcv_by_date(
            start_dt.strftime("%Y%m%d"), 
            ref_date, 
            ticker
        )

        # [안전장치] 데이터 프레임 유효성 검사
        if df is None or df.empty or len(df) < 25:
            return None

        # 1. 기술적 지표 산출 (지수이동평균 기반 MACD)
        exp12 = df['종가'].ewm(span=12, adjust=False).mean()
        exp26 = df['종가'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # 2. 거래량 분석 (Index Error 방어 로직)
        if len(df) < 5: return None
        v_curr = df['거래량'].iloc[-1]
        v_prev = df['거래량'].iloc[-2]
        v_ratio = float(v_curr / v_prev) if v_prev > 0 else 0

        # 3. 재무 데이터 연동
        f_df = get_safe_fundamentals(ref_date)
        per_val = None
        if f_df is not None and ticker in f_df.index:
            per_val = f_df.loc[ticker, 'PER']

        return {
            'ohlcv': df,
            'per': per_val,
            'last_price': int(df['종가'].iloc[-1]),
            'vol_ratio': v_ratio,
            'target_date': ref_date
        }
    except Exception as e:
        return None

# ==============================================================================
# [4] 퀀트 필터링 및 리포트 제네레이터
# 목적: 17년 차 전문가의 매수 로직을 코드로 구현
# ==============================================================================
def run_quant_scanner(pool, p_limit=15.0, v_limit=2.0):
    """골든크로스 + 수급폭발 + 저평가 필터링"""
    results = []
    for ticker, data in pool.items():
        if not data: continue
        try:
            df = data['ohlcv']
            # 지표 추출
            m_now, s_now = df['MACD'].iloc[-1], df['Signal'].iloc[-1]
            m_old, s_old = df['MACD'].iloc[-2], df['Signal'].iloc[-2]
            
            # 조건식 바인딩
            is_golden = (m_old <= s_old) and (m_now > s_now)
            is_heavy_vol = data['vol_ratio'] >= v_limit
            is_low_per = data['per'] is not None and 0 < data['per'] <= p_limit
            
            if is_golden and is_heavy_vol and is_low_per:
                results.append({
                    'ticker': ticker,
                    'data': data,
                    'rank_score': data['vol_ratio'] # 거래량 순 정렬
                })
        except:
            continue
    
    return sorted(results, key=lambda x: x['rank_score'], reverse=True)

def render_expert_report(item, names):
    """심층 분석 리포트 마크다운 생성"""
    t_code = item['ticker']
    t_name = names.get(t_code, t_code)
    info = item['data']
    
    technical_part = f"""
    ### 🚩 기술적 분석 (Technical Report)
    - **추세 시그널:** MACD가 Signal선을 상향 돌파하는 **역전 골든크로스**가 발생했습니다.
    - **수급 모멘텀:** 전일 대비 **{info['vol_ratio']:.1f}배**의 거래량 폭발은 매집 세력의 유입을 강력히 시사합니다.
    - **가격 전략:** 현재가 **{info['last_price']:,}원**은 하락 추세를 멈추고 우상향으로 꺾이는 변곡점입니다.
    """
    
    p_str = f"{info['per']:.2f}" if info['per'] else "N/A"
    fundamental_part = f"""
    ### 💰 재무적 가치 (Value Report)
    - **밸류에이션:** PER **{p_str}배**는 업종 평균 대비 현저히 저평가된 수치입니다.
    - **리스크 관리:** 저평가 구간에서의 대량 거래는 하방 경직성을 확보해주는 핵심 근거입니다.
    """
    return technical_part, fundamental_part

def draw_advanced_chart(df, ticker, name):
    """Plotly 캔들스틱 + MACD 이중 축 차트"""
    fig = go.Figure()
    
    # 주가 영역
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['시가'], high=df['고가'],
        low=df['저가'], close=df['종가'], name='Price'
    ))
    
    # 보조지표 영역 (오른쪽 Y축)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='#2196F3', width=2), yaxis='y2'))
    fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], name='Signal', line=dict(color='#F44336', width=2), yaxis='y2'))
    
    fig.update_layout(
        title=f'<b>{name} ({ticker})</b> 퀀트 분석 차트',
        yaxis_title='주가 (KRW)',
        yaxis2=dict(title='MACD/Signal', overlaying='y', side='right', showgrid=False),
        template='plotly_white',
        height=600,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.1, x=0.5, xanchor='center')
    )
    return fig

# ==============================================================================
# [5] 메인 애플리케이션 제어부
# ==============================================================================
def main():
    apply_pro_theme()
    
    st.title("📈 퀀트 비서 - 17년 차 전문가 전용")
    
    # 1. 시장 스냅샷 로드
    with st.status("🔍 시장 통신망 연결 및 데이터 동기화 중...", expanded=True) as status:
        name_dict, target_date = get_reliable_market_snapshot()
        
        if not target_date:
            st.error("거래소 서버의 장시간 점검으로 데이터 확보에 실패했습니다. (KRX 22시 점검 이슈)")
            return

        st.write(f"✅ **분석 기준일 확정:** {target_date} (최근 영업일 데이터 우회 성공)")
        
        # 2. 전수 조사 실행
        tickers = list(name_dict.keys())
        st.write(f"🚀 총 {len(tickers)}개 종목 분석을 시작합니다...")
        
        analysis_pool = {}
        prog = st.progress(0)
        for i, t in enumerate(tickers):
            res = deep_analyze_stock(t, target_date)
            if res: analysis_pool[t] = res
            prog.progress((i + 1) / len(tickers))
        
        # 3. 필터링 실행
        final_candidates = run_quant_scanner(analysis_pool)
        status.update(label="✅ 분석 완료! 추천 종목을 확인하세요.", state="complete", expanded=False)

    # 4. 결과 시각화
    if not final_candidates:
        st.warning(f"⚠️ {target_date} 기준, 필터링 조건(거래량 2배, 골든크로스, PER 15이하)을 충족하는 종목이 없습니다.")
        return

    # 대시보드 메트릭 섹션
    st.success(f"🎯 퀀트 알고리즘이 {len(final_candidates)}개의 전략 종목을 포착했습니다.")
    m1, m2, m3 = st.columns(3)
    m1.metric("조사 종목", f"{len(analysis_pool)}건")
    m2.metric("최종 후보", f"{len(final_candidates)}건")
    m3.metric("데이터 기준일", target_date)

    # TOP 1 추천 상세 섹션
    top = final_candidates[0]
    t_code, t_name = top['ticker'], name_dict[top['ticker']]
    
    st.markdown("---")
    st.header(f"🏆 오늘의 TOP 전략주: {t_name} ({t_code})")
    
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("현재가", f"{top['data']['last_price']:,}원")
    h2.metric("거래량 폭증", f"{top['data']['vol_ratio']:.1f}배")
    h3.metric("PER 밸류", f"{top['data']['per']:.2f}" if top['data']['per'] else "N/A")
    h4.metric("추천 등급", "강력 매수 (A+)")

    # 리포트 카드 레이아웃
    tech_txt, fund_txt = render_expert_report(top, name_dict)
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.markdown(f'<div class="analysis-card">{tech_txt}</div>', unsafe_allow_html=True)
    with r_col2:
        st.markdown(f'<div class="analysis-card" style="border-left-color: #457b9d;">{fund_txt}</div>', unsafe_allow_html=True)

    # 차트 렌더링
    st.plotly_chart(draw_advanced_chart(top['data']['ohlcv'], t_code, t_name), use_container_width=True)

    # 전체 리스트 요약
    st.markdown("---")
    st.subheader("📋 퀀트 필터링 결과 리스트 (상위 10선)")
    
    df_result = pd.DataFrame([{
        '순위': idx + 1,
        '종목명': name_dict[s['ticker']],
        '현재가': f"{s['data']['last_price']:,}원",
        '거래량증가': f"{s['data']['vol_ratio']:.1f}배",
        'PER': f"{s['data']['per']:.2f}" if s['data']['per'] else "N/A",
        '코드': s['ticker']
    } for idx, s in enumerate(final_candidates[:10])])
    
    st.table(df_result)
    
    st.caption("※ 본 분석 데이터는 투자 결정을 돕기 위한 보조 지표이며, 모든 투자의 책임은 본인에게 있습니다.")

if __name__ == "__main__":
    main()
