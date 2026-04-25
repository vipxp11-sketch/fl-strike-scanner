import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="FL Strike Scanner", layout="wide")

st.title("📊 FL Strike Scanner")

st.write("### 🧠 نية السوق (Market Bias)")

symbols = {
    "SPY": "S&P500",
    "QQQ": "NASDAQ",
    "DIA": "DOW",
    "VIX": "VIX"
}

data = {}

for sym in symbols:
    df = yf.download(sym, period="1d", interval="5m")
    if not df.empty:
        change = ((df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]) * 100
        data[sym] = round(change, 2)

# عرض البيانات
for sym, change in data.items():
    st.metric(symbols[sym], f"{change}%")

# تحديد النية
if data.get("SPY", 0) > 0 and data.get("QQQ", 0) > 0:
    st.success("🚀 السوق صاعد (Call Bias)")
elif data.get("SPY", 0) < 0 and data.get("QQQ", 0) < 0:
    st.error("📉 السوق هابط (Put Bias)")
else:
    st.warning("⚖️ السوق متذبذب")

st.write("---")

st.write("### 📈 أقوى الأسهم")

watchlist = ["NVDA", "AMD", "AMZN", "TSLA"]

rows = []

for stock in watchlist:
    df = yf.download(stock, period="1d", interval="5m")
    if not df.empty:
        change = ((df["Close"].iloc[-1] - df["Open"].iloc[0]) / df["Open"].iloc[0]) * 100
        rows.append([stock, round(change, 2)])

df_table = pd.DataFrame(rows, columns=["Ticker", "Change %"])
st.dataframe(df_table)
