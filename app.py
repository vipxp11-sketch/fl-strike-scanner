import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="FL-STRIKE Scanner",
    page_icon="🔥",
    layout="wide"
)

DEFAULT_TICKERS = [
    "SPY", "QQQ", "IWM", "DIA",
    "NVDA", "TSLA", "AAPL", "MSFT", "AMD", "META",
    "AMZN", "GOOGL", "NFLX", "AVGO", "COIN", "MSTR",
    "PLTR", "SOFI", "RIVN", "ROKU", "SHOP", "UBER", "ARM",
    "SMCI", "HOOD", "BABA", "NIO", "INTC", "BA", "DIS"
]

st.title("🔥 FL-STRIKE Daily Scanner")
st.caption("فلتر يومي لاستخراج الأسهم المتفاعلة للجلسة — مناسب للمراقبة قبل اختيار عقد الأوبشن.")

with st.sidebar:
    st.header("إعدادات الفلتر")

    ticker_text = st.text_area(
        "الرموز",
        value=", ".join(DEFAULT_TICKERS),
        height=160
    )

    min_price = st.number_input("أقل سعر للسهم", value=5.0, step=1.0)
    min_atr = st.number_input("أقل ATR %", value=1.5, step=0.5)
    min_rel_vol = st.number_input("أقل Relative Volume", value=0.5, step=0.1)
    min_abs_gap = st.number_input("أقل Gap %", value=0.5, step=0.5)

    st.divider()
    st.caption("ملاحظة: بيانات Yahoo المجانية قد تتأخر أو تتوقف مؤقتًا أحيانًا.")

def normalize_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def atr_percent(df, period=14):
    if len(df) < period + 1:
        return None

    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    close = df["Close"].iloc[-1]

    if close == 0:
        return None

    return float((atr / close) * 100)

@st.cache_data(ttl=120)
def get_stock_data(ticker):
    t = yf.Ticker(ticker)
    daily = t.history(period="35d", interval="1d")
    intra = t.history(period="1d", interval="5m")

    daily = normalize_columns(daily)
    intra = normalize_columns(intra)

    return daily, intra

def score_row(row):
    score = 0

    if abs(row["Gap %"]) >= 1:
        score += 1
    if row["Rel Volume"] >= 0.5:
        score += 2
    if row["ATR %"] >= 1.5:
        score += 2
    if abs(row["Momentum %"]) >= 1:
        score += 2
    if row["Breakout"] != "Neutral":
        score += 2
    if row["Volume"] >= 3_000_000:
        score += 1

    return score

def scan(tickers):
    rows = []
    errors = []

    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue

        try:
            daily, intra = get_stock_data(ticker)

            if daily.empty or intra.empty or len(daily) < 15:
                errors.append(f"{ticker}: بيانات غير كافية")
                continue

            prev_close = float(daily["Close"].iloc[-2])
            prev_high = float(daily["High"].iloc[-2])
            prev_low = float(daily["Low"].iloc[-2])
            avg_volume = float(daily["Volume"].iloc[-15:-1].mean())

            current_price = float(intra["Close"].iloc[-1])
            day_open = float(intra["Open"].iloc[0])
            volume_today = float(intra["Volume"].sum())

            if prev_close == 0 or day_open == 0 or avg_volume == 0:
                errors.append(f"{ticker}: قيم صفرية غير صالحة")
                continue

            gap = ((day_open - prev_close) / prev_close) * 100
            rel_volume = volume_today / avg_volume
            momentum = ((current_price - day_open) / day_open) * 100
            atr = atr_percent(daily)

            if atr is None:
                errors.append(f"{ticker}: ATR غير متاح")
                continue

            if current_price > prev_high:
                breakout = "Bullish Breakout"
                bias = "CALL"
            elif current_price < prev_low:
                breakout = "Bearish Breakdown"
                bias = "PUT"
            else:
                breakout = "Neutral"
                bias = "Watch"

            row = {
                "Ticker": ticker,
                "Price": round(current_price, 2),
                "Gap %": round(gap, 2),
                "Rel Volume": round(rel_volume, 2),
                "ATR %": round(atr, 2),
                "Momentum %": round(momentum, 2),
                "Volume": int(volume_today),
                "Breakout": breakout,
                "Bias": bias
            }

            row["Score"] = score_row(row)

            if (
                current_price >= min_price
                and atr >= min_atr
                and rel_volume >= min_rel_vol
                and abs(gap) >= min_abs_gap
            ):
                rows.append(row)

        except Exception as e:
            errors.append(f"{ticker}: {e}")

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(["Score", "Rel Volume", "Momentum %"], ascending=[False, False, False])

    return df, errors

tickers = [x.strip().upper() for x in ticker_text.replace("\n", ",").split(",") if x.strip()]

col1, col2, col3, col4 = st.columns(4)
col1.metric("عدد الرموز", len(tickers))
col2.metric("آخر تحديث", datetime.now().strftime("%H:%M:%S"))
col3.metric("فلتر ATR %", min_atr)
col4.metric("فلتر Rel Vol", min_rel_vol)

run = st.button("🚀 تشغيل السكان", type="primary", use_container_width=True)

if run:
    with st.spinner("جاري فحص الأسهم..."):
        df, errors = scan(tickers)

    if df.empty:
        st.warning("ما طلع مرشح مطابق. خفف الشروط أو جرّب وقت افتتاح السوق.")
    else:
        st.subheader("🔥 أفضل الأسهم المتفاعلة")
        st.dataframe(df, use_container_width=True, hide_index=True)

        top = df.iloc[0]
        st.success(
            f"أفضل مرشح حاليًا: {top['Ticker']} | Bias: {top['Bias']} | Score: {top['Score']}/10"
        )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "تحميل النتائج CSV",
            csv,
            f"fl_strike_scanner_{datetime.now().strftime('%Y-%m-%d')}.csv",
            "text/csv",
            use_container_width=True
        )

    if errors:
        with st.expander("ملاحظات / أخطاء بعض الرموز"):
            for err in errors:
                st.write(err)
else:
    st.info("اضغط زر تشغيل السكان بعد افتتاح السوق أو قبل الافتتاح للمراقبة.")