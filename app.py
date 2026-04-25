import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta, date

st.set_page_config(page_title="FL-STRIKE Decision Dashboard", page_icon="🔥", layout="wide")

DEFAULT_TICKERS = [
    "SPY", "QQQ", "IWM", "DIA",
    "NVDA", "TSLA", "AAPL", "MSFT", "AMD", "META",
    "AMZN", "GOOGL", "NFLX", "AVGO", "COIN", "MSTR",
    "PLTR", "SOFI", "RIVN", "ROKU", "SHOP", "UBER", "ARM",
    "SMCI", "HOOD", "BABA", "NIO", "INTC", "BA", "DIS"
]

st.title("🔥 FL-STRIKE Decision Dashboard")
st.caption("لوحة الانطباع الأول: نية السوق + أقوى الأسهم المتفاعلة + Flow Proxy + أخبار")

with st.sidebar:
    st.header("⚙️ الإعدادات")

    ticker_text = st.text_area("الرموز", value=", ".join(DEFAULT_TICKERS), height=160)

    st.subheader("فلاتر الأسهم")
    min_price = st.number_input("أقل سعر للسهم", value=5.0, step=1.0)
    min_atr = st.number_input("أقل ATR %", value=1.5, step=0.5)
    min_rel_vol = st.number_input("أقل Relative Volume", value=0.5, step=0.1)
    min_abs_gap = st.number_input("أقل Gap %", value=0.5, step=0.5)
    chase_limit = st.number_input("حد عدم المطاردة % من الافتتاح", value=3.0, step=0.5)

    st.subheader("فلاتر الأوبشن")
    min_option_volume = st.number_input("أقل Volume للعقد", value=500, step=100)
    min_volume_oi_ratio = st.number_input("أقل Volume/OI", value=0.50, step=0.10)
    max_spread_pct = st.number_input("أقصى Spread %", value=35.0, step=5.0)

    st.subheader("الأخبار")
    finnhub_key = st.text_input("Finnhub API Key اختياري", type="password")
    st.caption("بدون المفتاح: يستخدم أخبار Yahoo إن توفرت.")

def normalize_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

@st.cache_data(ttl=120)
def get_stock_data(ticker):
    t = yf.Ticker(ticker)
    daily = normalize_columns(t.history(period="35d", interval="1d"))
    intra = normalize_columns(t.history(period="1d", interval="5m"))
    return daily, intra

def atr_percent(df, period=14):
    if len(df) < period + 1:
        return None
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    close = df["Close"].iloc[-1]
    return float((atr / close) * 100) if close else None

def candle_rejection_status(intra):
    if intra.empty:
        return "Unknown"
    c = intra.iloc[-1]
    high, low, open_, close = float(c["High"]), float(c["Low"]), float(c["Open"]), float(c["Close"])
    rng = high - low
    if rng <= 0:
        return "No Range"

    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    if upper_wick / rng >= 0.45:
        return "Upper Rejection"
    if lower_wick / rng >= 0.45:
        return "Lower Rejection"
    return "Clean"

def stock_basic_metrics(ticker):
    daily, intra = get_stock_data(ticker)

    if daily.empty or intra.empty or len(daily) < 15:
        return None

    prev_close = float(daily["Close"].iloc[-2])
    prev_high = float(daily["High"].iloc[-2])
    prev_low = float(daily["Low"].iloc[-2])
    avg_volume = float(daily["Volume"].iloc[-15:-1].mean())

    current_price = float(intra["Close"].iloc[-1])
    day_open = float(intra["Open"].iloc[0])
    volume_today = float(intra["Volume"].sum())

    if prev_close == 0 or day_open == 0 or avg_volume == 0:
        return None

    gap = ((day_open - prev_close) / prev_close) * 100
    rel_volume = volume_today / avg_volume
    momentum = ((current_price - day_open) / day_open) * 100
    atr = atr_percent(daily)

    if atr is None:
        return None

    if current_price > prev_high:
        breakout = "Bullish Breakout"
        bias = "CALL"
    elif current_price < prev_low:
        breakout = "Bearish Breakdown"
        bias = "PUT"
    else:
        breakout = "Neutral"
        bias = "Watch"

    return {
        "Ticker": ticker,
        "Price": round(current_price, 2),
        "Prev High": round(prev_high, 2),
        "Prev Low": round(prev_low, 2),
        "Gap %": round(gap, 2),
        "Rel Volume": round(rel_volume, 2),
        "ATR %": round(atr, 2),
        "Momentum %": round(momentum, 2),
        "Volume": int(volume_today),
        "Breakout": breakout,
        "Bias": bias,
        "Rejection": candle_rejection_status(intra)
    }

def score_stock(row):
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

def market_intent(tickers):
    spy = stock_basic_metrics("SPY")
    qqq = stock_basic_metrics("QQQ")

    valid_rows = []
    for sym in tickers:
        row = stock_basic_metrics(sym)
        if row:
            valid_rows.append(row)

    if not valid_rows:
        return None, pd.DataFrame()

    breadth_up = sum(1 for r in valid_rows if r["Momentum %"] > 0)
    breadth_down = sum(1 for r in valid_rows if r["Momentum %"] < 0)
    total = len(valid_rows)

    up_pct = (breadth_up / total) * 100 if total else 0
    down_pct = (breadth_down / total) * 100 if total else 0

    bull_score = 0
    bear_score = 0
    reasons = []

    if spy:
        if spy["Breakout"] == "Bullish Breakout" or spy["Momentum %"] > 0.35:
            bull_score += 1
            reasons.append("SPY إيجابي")
        elif spy["Breakout"] == "Bearish Breakdown" or spy["Momentum %"] < -0.35:
            bear_score += 1
            reasons.append("SPY سلبي")

    if qqq:
        if qqq["Breakout"] == "Bullish Breakout" or qqq["Momentum %"] > 0.35:
            bull_score += 1
            reasons.append("QQQ إيجابي")
        elif qqq["Breakout"] == "Bearish Breakdown" or qqq["Momentum %"] < -0.35:
            bear_score += 1
            reasons.append("QQQ سلبي")

    if up_pct >= 60:
        bull_score += 1
        reasons.append("Breadth صاعد فوق 60%")
    elif down_pct >= 60:
        bear_score += 1
        reasons.append("Breadth هابط فوق 60%")

    avg_momentum = sum(r["Momentum %"] for r in valid_rows) / total
    if avg_momentum > 0.35:
        bull_score += 1
        reasons.append("متوسط الزخم إيجابي")
    elif avg_momentum < -0.35:
        bear_score += 1
        reasons.append("متوسط الزخم سلبي")

    if spy and spy["Rejection"] == "Upper Rejection":
        bear_score += 1
        reasons.append("رفض علوي على SPY")
    elif spy and spy["Rejection"] == "Lower Rejection":
        bull_score += 1
        reasons.append("رفض سفلي على SPY")

    net = bull_score - bear_score

    if net >= 2:
        intent = "🟢 Bullish / CALL Bias"
        action = "ركز على CALL فقط، ولا تطارد الأسهم الممتدة."
    elif net <= -2:
        intent = "🔴 Bearish / PUT Bias"
        action = "ركز على PUT فقط، وتجاهل الكولات الضعيفة."
    else:
        intent = "🟡 Neutral / Wait"
        action = "السوق غير واضح. لا تدخل إلا بعد كسر حقيقي."

    summary = {
        "Market Intent": intent,
        "Bull Score": bull_score,
        "Bear Score": bear_score,
        "Breadth Up %": round(up_pct, 1),
        "Breadth Down %": round(down_pct, 1),
        "Avg Momentum %": round(avg_momentum, 2),
        "Action": action,
        "Reasons": " | ".join(reasons) if reasons else "لا توجد إشارة سوق واضحة"
    }

    return summary, pd.DataFrame(valid_rows)

@st.cache_data(ttl=300)
def get_yahoo_news(ticker, limit=3):
    try:
        news = yf.Ticker(ticker).news or []
        rows = []
        for item in news[:limit]:
            title = item.get("title") or item.get("content", {}).get("title", "")
            publisher = item.get("publisher") or item.get("content", {}).get("provider", {}).get("displayName", "")
            link = item.get("link") or item.get("content", {}).get("canonicalUrl", {}).get("url", "")
            rows.append({"Ticker": ticker, "Title": title, "Source": publisher, "URL": link})
        return rows
    except Exception:
        return []

@st.cache_data(ttl=300)
def get_finnhub_news(ticker, api_key, limit=3):
    if not api_key:
        return []
    try:
        today = date.today()
        frm = today - timedelta(days=3)
        url = "https://finnhub.io/api/v1/company-news"
        params = {"symbol": ticker, "from": frm.isoformat(), "to": today.isoformat(), "token": api_key}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        rows = []
        for item in data[:limit]:
            rows.append({
                "Ticker": ticker,
                "Title": item.get("headline", ""),
                "Source": item.get("source", ""),
                "URL": item.get("url", "")
            })
        return rows
    except Exception:
        return []

def get_news(ticker, api_key):
    rows = get_finnhub_news(ticker, api_key)
    if rows:
        return rows
    return get_yahoo_news(ticker)

@st.cache_data(ttl=180)
def get_options_flow_proxy(ticker, price):
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return pd.DataFrame()

        expiry = expirations[0]
        chain = t.option_chain(expiry)

        frames = []
        for side_name, side_df in [("CALL", chain.calls), ("PUT", chain.puts)]:
            df = side_df.copy()
            if df.empty:
                continue

            df["Side"] = side_name
            df["Expiry"] = expiry
            df["Distance %"] = ((df["strike"] - price).abs() / price) * 100
            df["Mid"] = (df["bid"].fillna(0) + df["ask"].fillna(0)) / 2
            df["Spread %"] = ((df["ask"] - df["bid"]) / df["Mid"].replace(0, pd.NA)) * 100
            df["Volume/OI"] = df["volume"].fillna(0) / df["openInterest"].replace(0, pd.NA)

            df = df[
                [
                    "contractSymbol", "Side", "Expiry", "strike", "lastPrice",
                    "bid", "ask", "volume", "openInterest",
                    "Volume/OI", "Spread %", "Distance %", "impliedVolatility"
                ]
            ]
            frames.append(df)

        if not frames:
            return pd.DataFrame()

        out = pd.concat(frames, ignore_index=True)

        out = out[
            (out["volume"].fillna(0) >= min_option_volume)
            & (out["Volume/OI"].fillna(0) >= min_volume_oi_ratio)
            & (out["Spread %"].fillna(999) <= max_spread_pct)
            & (out["Distance %"] <= 8)
        ]

        if out.empty:
            return out

        return out.sort_values(["volume", "Volume/OI"], ascending=[False, False]).head(8)

    except Exception:
        return pd.DataFrame()

def scan_stocks(tickers):
    rows, errors = [], []

    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue

        try:
            row = stock_basic_metrics(ticker)
            if not row:
                errors.append(f"{ticker}: بيانات غير كافية")
                continue

            row["Stock Score"] = score_stock(row)
            row["Chase Risk"] = "High" if abs(row["Momentum %"]) > chase_limit else "OK"

            if (
                row["Price"] >= min_price
                and row["ATR %"] >= min_atr
                and row["Rel Volume"] >= min_rel_vol
                and abs(row["Gap %"]) >= min_abs_gap
            ):
                rows.append(row)

        except Exception as e:
            errors.append(f"{ticker}: {e}")

    df = pd.DataFrame(rows)
    if not df.empty:
        df["Abs Momentum %"] = df["Momentum %"].abs()
        df = df.sort_values(
            ["Stock Score", "Rel Volume", "Abs Momentum %", "Volume"],
            ascending=[False, False, False, False]
        )
        df = df.drop(columns=["Abs Momentum %"])

    return df, errors

def best_candidate(stocks_df, market_summary):
    if stocks_df.empty:
        return None, "لا توجد أسهم مرشحة."

    df = stocks_df.copy()
    intent = market_summary["Market Intent"] if market_summary else "Neutral"

    if "Bullish" in intent:
        preferred = df[df["Bias"].isin(["CALL", "Watch"])].copy()
    elif "Bearish" in intent:
        preferred = df[df["Bias"].isin(["PUT", "Watch"])].copy()
    else:
        preferred = df.copy()

    if preferred.empty:
        preferred = df.copy()

    preferred["Decision Score"] = preferred["Stock Score"]
    preferred.loc[preferred["Chase Risk"] == "High", "Decision Score"] -= 2
    preferred.loc[preferred["Breakout"] != "Neutral", "Decision Score"] += 1

    preferred = preferred.sort_values(
        ["Decision Score", "Rel Volume", "Volume"],
        ascending=[False, False, False]
    )

    top = preferred.iloc[0]

    reasons = []
    reasons.append(f"Score {top['Stock Score']}/10")
    reasons.append(f"RVOL {top['Rel Volume']}")
    reasons.append(f"Momentum {top['Momentum %']}%")
    reasons.append(top["Breakout"])
    if top["Chase Risk"] == "High":
        reasons.append("تحذير: السهم ممتد، لا تطارد")

    text = " | ".join(reasons)
    return top, text

tickers = [x.strip().upper() for x in ticker_text.replace("\n", ",").split(",") if x.strip()]

c1, c2, c3, c4 = st.columns(4)
c1.metric("عدد الرموز", len(tickers))
c2.metric("آخر تحديث", datetime.now().strftime("%H:%M:%S"))
c3.metric("ATR Filter", min_atr)
c4.metric("RelVol Filter", min_rel_vol)

if st.button("🚀 تشغيل لوحة القرار", type="primary", use_container_width=True):
    with st.spinner("جاري قراءة نية السوق وفحص الأسهم..."):
        market_summary, market_rows = market_intent(tickers)
        stocks_df, errors = scan_stocks(tickers)

    st.subheader("🧭 Market Intent — الانطباع الأول عن السوق")

    if market_summary:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Market Intent", market_summary["Market Intent"])
        m2.metric("Bull Score", market_summary["Bull Score"])
        m3.metric("Bear Score", market_summary["Bear Score"])
        m4.metric("Avg Momentum", f"{market_summary['Avg Momentum %']}%")

        st.info(market_summary["Action"])
        st.caption(market_summary["Reasons"])

        with st.expander("تفاصيل Breadth للرموز"):
            st.dataframe(market_rows, use_container_width=True, hide_index=True)
    else:
        st.warning("تعذر حساب نية السوق.")

    st.divider()

    if stocks_df.empty:
        st.warning("ما فيه مرشحين مطابقين الآن. خفف الشروط أو شغله وقت الحركة.")
    else:
        st.subheader("⭐ أفضل سهم الآن — First Impression Candidate")
        top, reason = best_candidate(stocks_df, market_summary)

        if top is not None:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Ticker", top["Ticker"])
            b2.metric("Bias", top["Bias"])
            b3.metric("Score", f"{top['Stock Score']}/10")
            b4.metric("Chase Risk", top["Chase Risk"])

            st.success(reason)

            if top["Chase Risk"] == "High":
                st.warning("لا تدخل مطاردة. انتظر Pullback أو كسر جديد.")

        st.subheader("🔥 الأسهم المتفاعلة — Smart Ranking")
        st.dataframe(stocks_df, use_container_width=True, hide_index=True)

        st.subheader("💰 Options Flow Proxy")
        flow_frames = []

        for _, row in stocks_df.head(8).iterrows():
            flow = get_options_flow_proxy(row["Ticker"], row["Price"])
            if not flow.empty:
                flow.insert(0, "Ticker", row["Ticker"])
                flow_frames.append(flow)

        if flow_frames:
            flow_df = pd.concat(flow_frames, ignore_index=True)
            flow_df = flow_df.round({
                "Volume/OI": 2,
                "Spread %": 2,
                "Distance %": 2,
                "impliedVolatility": 2
            })
            st.dataframe(flow_df, use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد Flow Proxy مطابق للفلاتر الحالية.")

        st.subheader("📰 الأخبار / المحفزات")
        top_symbols = stocks_df.head(5)["Ticker"].tolist()
        all_news = []
        for sym in top_symbols:
            all_news.extend(get_news(sym, finnhub_key))

        if all_news:
            news_df = pd.DataFrame(all_news)
            st.dataframe(news_df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد أخبار متاحة من المصادر الحالية.")

        csv = stocks_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "تحميل نتائج الأسهم CSV",
            csv,
            f"fl_strike_decision_dashboard_{datetime.now().strftime('%Y-%m-%d')}.csv",
            "text/csv",
            use_container_width=True
        )

    if errors:
        with st.expander("ملاحظات / أخطاء"):
            for e in errors:
                st.write(e)
else:
    st.info("اضغط تشغيل بعد الافتتاح أو وقت الحركة. هذه لوحة انطباع أول، وليست زر دخول مباشر.")