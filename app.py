
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
from urllib.parse import quote

st.set_page_config(page_title="CAT + IREN Intelligence",layout="wide",page_icon="📈")
st.title("📈 CAT + IREN | Market Intelligence")
st.caption("Research dashboard • Market data may be delayed • Scenarios are not price guarantees")

with st.sidebar:
    ticker=st.selectbox("Company",["CAT","IREN"])
    period=st.selectbox("History",["1mo","3mo","6mo","1y","2y","5y"],index=3)
    interval=st.selectbox("Candle interval",["1d","1wk"],index=0)
    style=st.radio("Chart",["Candlesticks","Line"])
    horizon=st.slider("Scenario horizon (trading days)",20,252,63)
    st.info("CAT: industrials / construction / mining. IREN: AI infrastructure / data centers / bitcoin mining.")

@st.cache_data(ttl=900)
def get_data(symbol,period,interval):
    df=yf.download(symbol,period=period,interval=interval,auto_adjust=True,progress=False)
    if isinstance(df.columns,pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])

@st.cache_data(ttl=1800)
def get_news(symbol):
    try:
        items=yf.Ticker(symbol).news or []
        results=[]
        for x in items:
            c=x.get("content",x)
            title=c.get("title",x.get("title",""))
            link=(c.get("canonicalUrl") or c.get("clickThroughUrl") or {})
            if isinstance(link,dict): link=link.get("url","")
            link=link or x.get("link","")
            published=c.get("pubDate",x.get("providerPublishTime",""))
            if isinstance(published,(int,float)):
                published=datetime.fromtimestamp(published).strftime("%Y-%m-%d")
            provider=c.get("provider",{})
            provider=provider.get("displayName","") if isinstance(provider,dict) else str(provider)
            if title and link: results.append((title,link,str(published)[:10],provider))
        return results[:12]
    except Exception:
        return []

df=get_data(ticker,period,interval)
if df.empty:
    st.error("No market data returned. Try another period or interval.")
    st.stop()

close=df["Close"].astype(float)
df["MA20"]=close.rolling(20).mean()
df["MA50"]=close.rolling(50).mean()
df["MA200"]=close.rolling(200).mean()
delta=close.diff()
up=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
down=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
rs=up/down.replace(0,np.nan)
df["RSI"]=100-(100/(1+rs))
df["EMA12"]=close.ewm(span=12,adjust=False).mean()
df["EMA26"]=close.ewm(span=26,adjust=False).mean()
df["MACD"]=df["EMA12"]-df["EMA26"]
df["Signal"]=df["MACD"].ewm(span=9,adjust=False).mean()
df["Return"]=close.pct_change()
last=float(close.iloc[-1])
previous=float(close.iloc[-2]) if len(close)>1 else last
change=(last/previous-1)*100
rsi=float(df["RSI"].iloc[-1]) if pd.notna(df["RSI"].iloc[-1]) else np.nan
vol=float(df["Return"].std()*np.sqrt(252 if interval=="1d" else 52))
ma50=float(df["MA50"].iloc[-1]) if pd.notna(df["MA50"].iloc[-1]) else np.nan
ma200=float(df["MA200"].iloc[-1]) if pd.notna(df["MA200"].iloc[-1]) else np.nan

a,b,c,d=st.columns(4)
a.metric("Latest close",f"${last:,.2f}",f"{change:+.2f}%")
b.metric("RSI (14)",f"{rsi:.1f}" if np.isfinite(rsi) else "N/A")
c.metric("50-period MA",f"${ma50:,.2f}" if np.isfinite(ma50) else "N/A")
d.metric("Annualized historical volatility",f"{vol:.1%}" if np.isfinite(vol) else "N/A")
st.caption(f"Last available bar: {df.index[-1].strftime('%Y-%m-%d')} | Adjusted OHLC; not live quotes.")

fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.04,row_heights=[.78,.22])
if style=="Candlesticks":
    fig.add_trace(go.Candlestick(x=df.index,open=df["Open"],high=df["High"],low=df["Low"],close=df["Close"],name=ticker),row=1,col=1)
else:
    fig.add_trace(go.Scatter(x=df.index,y=close,name="Price",mode="lines"),row=1,col=1)
for label,color in [("MA20","#eab308"),("MA50","#38bdf8"),("MA200","#a78bfa")]:
    fig.add_trace(go.Scatter(x=df.index,y=df[label],name=label,line=dict(color=color,width=1.5)),row=1,col=1)
fig.add_trace(go.Bar(x=df.index,y=df["Volume"],name="Volume",marker_color="#64748b"),row=2,col=1)
fig.update_layout(height=600,xaxis_rangeslider_visible=False,template="plotly_dark",legend_orientation="h")
st.plotly_chart(fig,use_container_width=True)

left,right=st.columns(2)
with left:
    st.subheader("Momentum")
    rfig=go.Figure()
    rfig.add_trace(go.Scatter(x=df.index,y=df["RSI"],name="RSI"))
    rfig.add_hline(y=70,line_dash="dash",line_color="red")
    rfig.add_hline(y=30,line_dash="dash",line_color="green")
    rfig.update_layout(height=250,template="plotly_dark",yaxis_range=[0,100])
    st.plotly_chart(rfig,use_container_width=True)
with right:
    st.subheader("Technical interpretation")
    st.write("• RSI: "+("Overbought zone (>70)" if rsi>70 else "Oversold zone (<30)" if rsi<30 else "Neutral zone (30–70)") if np.isfinite(rsi) else "RSI unavailable")
    if np.isfinite(ma50): st.write("• Price vs MA50: "+("Above" if last>ma50 else "Below"))
    if np.isfinite(ma200): st.write("• Price vs MA200: "+("Above" if last>ma200 else "Below"))
    st.write("• MACD: "+("Above signal (positive momentum)" if df["MACD"].iloc[-1]>df["Signal"].iloc[-1] else "Below signal (negative momentum)"))
    st.caption("Signals can conflict; no indicator reliably predicts future returns.")

st.subheader("🔮 Forward-looking scenario model")
st.write("Customize assumptions below. These are **hypothetical scenarios**, not analyst price targets or statistically validated forecasts.")
annual_bear=st.number_input("Bear annual return assumption (%)",value=-25.0,step=5.0)
annual_base=st.number_input("Base annual return assumption (%)",value=10.0,step=5.0)
annual_bull=st.number_input("Bull annual return assumption (%)",value=35.0,step=5.0)
dates=pd.bdate_range(df.index[-1]+pd.Timedelta(days=1),periods=horizon)
forecast=pd.DataFrame({"Date":dates})
for name,r in [("Bear",annual_bear),("Base",annual_base),("Bull",annual_bull)]:
    forecast[name]=last*(1+r/100)**(np.arange(1,horizon+1)/252)
f=go.Figure()
for name in ["Bear","Base","Bull"]:
    f.add_trace(go.Scatter(x=[df.index[-1]]+list(dates),y=[last]+list(forecast[name]),name=name))
f.update_layout(template="plotly_dark",height=380,yaxis_title="Hypothetical price ($)")
st.plotly_chart(f,use_container_width=True)
st.dataframe(pd.DataFrame({"Scenario":["Bear","Base","Bull"],"Assumed annual return":[annual_bear,annual_base,annual_bull],"Price at horizon":[float(forecast[k].iloc[-1]) for k in ["Bear","Base","Bull"]]}),hide_index=True)

st.subheader("📰 Company news")
articles=get_news(ticker)
if articles:
    for title,url,date,provider in articles:
        st.markdown(f"**[{title}]({url})**  \n{provider} · {date}")
else:
    st.warning("The news feed is unavailable right now. Use the news search links below.")
q=quote("Caterpillar CAT stock earnings construction mining" if ticker=="CAT" else "IREN stock AI cloud data center bitcoin earnings")
st.link_button("Search recent company news",f"https://news.google.com/search?q={q}")

st.subheader("🎯 Catalysts and opportunities to research")
if ticker=="CAT":
    st.markdown("""
**Potential upside:** infrastructure spending, construction demand, mining equipment orders, services growth, pricing power, backlog conversion.

**Key downside risks:** slowing global growth, higher interest rates, dealer inventory buildup, weaker mining capex, tariffs and supply chain costs.

**Watch:** quarterly revenue and operating margin, orders/backlog, management guidance, free cash flow, China and North America demand.
""")
else:
    st.markdown("""
**Potential upside:** AI cloud/data-center contracts, capacity expansion, utilization, power availability, favorable financing and bitcoin economics.

**Key downside risks:** capital expenditure needs, dilution/debt, buildout delays, customer concentration, bitcoin volatility, power costs.

**Watch:** signed AI contracts vs announced capacity, GPU deployment, contracted revenue, capex and cash runway, debt/equity raises, bitcoin mining profitability.
""")
st.warning("Opportunity checklist is qualitative, not current verified company guidance. Read recent filings and earnings calls before investing.")
st.subheader("🔗 Primary research")
st.link_button("SEC filings",f"https://www.sec.gov/edgar/search/#/q={ticker}")
st.link_button("Yahoo Finance company page",f"https://finance.yahoo.com/quote/{ticker}/")
st.download_button("Download historical prices (CSV)",df.to_csv().encode(),f"{ticker}_history.csv","text/csv")
