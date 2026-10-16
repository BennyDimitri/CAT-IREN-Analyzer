import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
import html
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title='CAT + IREN Live Research', page_icon='📈', layout='wide', initial_sidebar_state='collapsed')
st.markdown("""<style>.block-container {max-width: 100% !important; padding-left: 1.2rem; padding-right: 1.2rem; padding-top: 1rem;} iframe {width:100%;}</style>""", unsafe_allow_html=True)
st.title('CAT + IREN | Investor Terminal Pro')
st.caption('Two TradingView charts • external analyst targets • company news • refreshed research')

with st.sidebar:
    st.header('Dashboard controls')
    timeframe = st.selectbox('TradingView interval', ['1D','1W','1M','60','15','5'], index=0, format_func=lambda x: {'1D':'Daily','1W':'Weekly','1M':'Monthly','60':'1 hour','15':'15 minutes','5':'5 minutes'}[x])
    chart_style = st.selectbox('Chart type', ['Candles','Line'], index=0)
    chart_height = st.slider('Chart height (pixels)', 700, 1500, 1050, step=50)
    st.caption('Click Refresh to reload research. TradingView updates its chart independently.')
    st.caption('Exchange feeds may be delayed; Yahoo data and TradingView are separate.')
    if st.button('🔄 Refresh research', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

@st.cache_data(ttl=120, show_spinner=False)
def info_for(symbol):
    try:
        t=yf.Ticker(symbol)
        info=t.info or {}
        return {k:info.get(k) for k in ['currentPrice','regularMarketPrice','previousClose','targetLowPrice','targetMeanPrice','targetHighPrice','targetMedianPrice','numberOfAnalystOpinions','recommendationKey','recommendationMean','currency','shortName','earningsTimestamp','marketCap','fiftyTwoWeekLow','fiftyTwoWeekHigh','totalRevenue','revenueGrowth','earningsGrowth','profitMargins','operatingMargins','freeCashflow','totalDebt','totalCash','forwardPE','trailingPE']}
    except Exception as e:
        return {'error':str(e)}

@st.cache_data(ttl=300, show_spinner=False)
def news_for(symbol):
    try:
        raw=yf.Ticker(symbol).news or []
        out=[]
        for item in raw:
            c=item.get('content',item)
            title=c.get('title') or item.get('title')
            url=c.get('canonicalUrl') or c.get('clickThroughUrl') or item.get('link')
            if isinstance(url,dict):url=url.get('url')
            provider=c.get('provider') or {}
            if isinstance(provider,dict):provider=provider.get('displayName','')
            date=c.get('pubDate') or item.get('providerPublishTime') or ''
            if isinstance(date,(int,float)):date=datetime.fromtimestamp(date,timezone.utc).strftime('%b %d, %Y')
            if title and isinstance(url,str) and url.startswith('https://'):
                out.append((title,url,str(date)[:16],provider))
        return out[:8]
    except Exception:return []

def chart(symbol):
    # Explicit dimensions are essential: TradingView autosize can collapse
    # the internal chart to ~100px even when Streamlit allocates 1000px.
    import json
    config = {
        'autosize': False,
        'width': '100%',
        'height': chart_height,
        'symbol': 'NASDAQ:IREN' if symbol == 'IREN' else 'NYSE:CAT',
        'interval': timeframe,
        'timezone': 'America/New_York',
        'theme': 'dark',
        'style': '1' if chart_style == 'Candles' else '2',
        'locale': 'en',
        'allow_symbol_change': False,
        'hide_side_toolbar': False,
        'withdateranges': True,
        'save_image': False,
        'calendar': False,
        'studies': ['STD;SMA'],
        'support_host': 'https://www.tradingview.com'
    }
    markup = f'''<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"/>
    <style>html,body{{margin:0;padding:0;width:100%;height:{chart_height}px;overflow:hidden;background:#101216}}
    .tradingview-widget-container{{width:100%;height:{chart_height}px}}
    .tradingview-widget-container__widget{{width:100%;height:{chart_height}px}}</style></head><body>
    <div class="tradingview-widget-container">
    <div class="tradingview-widget-container__widget"></div>
    <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{json.dumps(config)}</script>
    </div></body></html>'''
    components.html(markup, height=chart_height + 8, scrolling=False)


def dollar(x):
    return f'${x:,.2f}' if isinstance(x,(float,int)) else 'Unavailable'

@st.cache_data(ttl=180, show_spinner=False)
def history_for(symbol):
    try:
        df=yf.download(symbol,period='1y',interval='1d',auto_adjust=True,progress=False)
        if isinstance(df.columns,pd.MultiIndex):df.columns=df.columns.get_level_values(0)
        return df.dropna(subset=['Close'])
    except Exception:return pd.DataFrame()

def fmt_pct(v):
    return f'{100*v:+.1f}%' if isinstance(v,(float,int)) and np.isfinite(v) else 'N/A'

def fmt_large(v):
    if not isinstance(v,(float,int)) or not np.isfinite(v):return 'N/A'
    if abs(v)>1e12:return f'${v/1e12:.2f}T'
    if abs(v)>1e9:return f'${v/1e9:.2f}B'
    if abs(v)>1e6:return f'${v/1e6:.1f}M'
    return dollar(v)

def section(symbol,company):
    st.header(f'{company} ({symbol})')
    data=info_for(symbol)
    price=data.get('currentPrice') or data.get('regularMarketPrice')
    prev=data.get('previousClose')
    a,b,c,d=st.columns(4)
    a.metric('Latest provider quote',dollar(price),fmt_pct(price/prev-1) if isinstance(price,(float,int)) and isinstance(prev,(float,int)) and prev else None)
    b.metric('52-week low',dollar(data.get('fiftyTwoWeekLow')))
    c.metric('52-week high',dollar(data.get('fiftyTwoWeekHigh')))
    d.metric('Market capitalization',fmt_large(data.get('marketCap')))
    chart(symbol)
    st.caption('Embedded TradingView chart. Intraday updates depend on exchange permissions; Yahoo Finance quote may differ.')
    tabs=st.tabs(['🎯 Analyst expectations','📉 Technical analysis','📰 News','🏢 Fundamentals','🔍 Opportunities & risks'])
    with tabs[0]:
        low,mean,high=(data.get('targetLowPrice'),data.get('targetMeanPrice'),data.get('targetHighPrice'))
        a,b,c,d=st.columns(4)
        a.metric('Low analyst target',dollar(low))
        b.metric('Mean analyst target',dollar(mean))
        c.metric('High analyst target',dollar(high))
        d.metric('Analyst count',str(data.get('numberOfAnalystOpinions') or 'N/A'))
        st.write('**Consensus rating:** '+str(data.get('recommendationKey') or 'Unavailable'))
        if isinstance(price,(int,float)) and price>0:
            estimates=[(name,target) for name,target in [('Bear / low',low),('Consensus / mean',mean),('Bull / high',high)] if isinstance(target,(int,float))]
            if estimates:
                frame=pd.DataFrame({'Analyst target':[n for n,v in estimates],'Target price':[v for n,v in estimates],'Implied change (%)':[(v/price-1)*100 for n,v in estimates]})
                fig=go.Figure(go.Bar(x=frame['Analyst target'],y=frame['Implied change (%)'],text=[f'{x:+.1f}%' for x in frame['Implied change (%)']],textposition='outside'))
                fig.update_layout(template='plotly_dark',height=310,yaxis_title='Implied change (%)')
                st.plotly_chart(fig,use_container_width=True,key=f'target_{symbol}')
                st.dataframe(frame,hide_index=True,use_container_width=True)
        st.caption('Published aggregated Yahoo Finance targets. These are not probabilities, verified recent revisions, or forecasts generated by this app.')
        st.link_button('See analyst estimates',f'https://finance.yahoo.com/quote/{symbol}/analysis/')
        st.link_button('TradingView community analysis',f'https://www.tradingview.com/symbols/{"NYSE-CAT" if symbol=="CAT" else "NASDAQ-IREN"}/ideas/')
    with tabs[1]:
        df=history_for(symbol)
        if len(df)<30:st.warning('Daily historical data unavailable for technical calculations.')
        else:
            close=df['Close'].astype(float)
            ma20=close.rolling(20).mean().iloc[-1]
            ma50=close.rolling(50).mean().iloc[-1]
            ma200=close.rolling(200).mean().iloc[-1]
            delta=close.diff()
            gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
            loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
            rsi=(100-100/(1+gain/loss.replace(0,np.nan))).iloc[-1]
            macd=close.ewm(span=12,adjust=False).mean()-close.ewm(span=26,adjust=False).mean()
            signal=macd.ewm(span=9,adjust=False).mean()
            a,b,c,d=st.columns(4)
            a.metric('RSI (14)',f'{rsi:.1f}' if np.isfinite(rsi) else 'N/A')
            b.metric('MA20',dollar(ma20))
            c.metric('MA50',dollar(ma50))
            d.metric('MA200',dollar(ma200))
            for name,level in [('20-day',ma20),('50-day',ma50),('200-day',ma200)]:
                if np.isfinite(level):st.write(f'• Price is **{"above" if close.iloc[-1]>level else "below"}** the {name} moving average.')
            if np.isfinite(rsi):st.write('• RSI: '+('Overbought zone (>70)' if rsi>70 else 'Oversold zone (<30)' if rsi<30 else 'Neutral (30–70)'))
            st.write('• MACD: '+('Above signal line' if macd.iloc[-1]>signal.iloc[-1] else 'Below signal line'))
            st.write(f'• Recent 20-session price range: {dollar(df["Low"].tail(20).min())} – {dollar(df["High"].tail(20).max())}')
            st.download_button('Download daily prices (CSV)',df.to_csv().encode(),f'{symbol}_prices.csv',key=f'csv_{symbol}')
            st.caption('Indicators use daily historical Yahoo Finance bars, not a live TradingView indicator feed. Signals are not trading instructions.')
    with tabs[2]:
        news=news_for(symbol)
        if news:
            for title,url,date,provider in news:st.markdown(f'- [{html.escape(title)}]({url}) — {html.escape(str(provider))} · {html.escape(date)}')
        else:st.warning('News feed unavailable. Use the links below for the latest coverage.')
        st.link_button('Search recent headlines',f'https://news.google.com/search?q={symbol}%20stock')
        st.link_button('TradingView news',f'https://www.tradingview.com/symbols/{"NYSE-CAT" if symbol=="CAT" else "NASDAQ-IREN"}/news/')
        st.caption('Headlines are third-party reports; a headline alone does not establish why a stock moved.')
    with tabs[3]:
        values=[('Revenue',fmt_large(data.get('totalRevenue'))),('Revenue growth',fmt_pct(data.get('revenueGrowth'))),('Earnings growth',fmt_pct(data.get('earningsGrowth'))),('Operating margin',fmt_pct(data.get('operatingMargins'))),('Profit margin',fmt_pct(data.get('profitMargins'))),('Trailing P/E',str(data.get('trailingPE') or 'N/A')),('Forward P/E',str(data.get('forwardPE') or 'N/A')),('Free cash flow',fmt_large(data.get('freeCashflow'))),('Debt',fmt_large(data.get('totalDebt'))),('Cash',fmt_large(data.get('totalCash')))]
        st.dataframe(pd.DataFrame(values,columns=['Metric','Provider value']),hide_index=True,use_container_width=True)
        st.link_button('Verify SEC filings',f'https://www.sec.gov/edgar/search/#/q={symbol}')
        st.caption('Financial fields may be stale or absent; check reporting periods in original company filings.')
    with tabs[4]:
        if symbol=='CAT':
            st.markdown("""**Potential upside:** construction and mining orders, infrastructure investment, services growth, margin expansion.

**Risks:** slower industrial demand, tariffs, dealer inventories, financing costs.

**Verify next:** orders, backlog, management guidance, margins and free cash flow.""")
        else:
            st.markdown("""**Potential upside:** signed AI cloud contracts, data center capacity, GPU deployment and utilization.

**Risks:** dilution, debt, buildout delays, power costs, bitcoin exposure and customer concentration.

**Verify next:** contracted revenue, deployment milestones, cash runway, capex and financing.""")
        st.caption('Qualitative research checklist; not a real-time prediction.')

st.info('TradingView charts and Yahoo Finance analyst/news data are separate services. This dashboard does not have a paid TradingView API or guaranteed tick-by-tick prices.')
section('CAT','Caterpillar')
st.divider()
section('IREN','IREN')
st.caption('Research only, not financial advice. Targets may be stale; always verify original analyst reports and company filings.')

st.divider()
st.subheader('CAT vs IREN: what matters most')
st.markdown('**CAT:** cyclical industrial earnings, construction/mining demand, margins and backlog.  **IREN:** AI infrastructure contracts, financing, deployment, cash runway and bitcoin exposure. Compare each against its own business model, not just price momentum.')
st.caption('For research only. Not financial advice. No paid TradingView API or guaranteed second-by-second quote/news feed.')
