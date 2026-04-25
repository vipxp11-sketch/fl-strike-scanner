import os
import math
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="FL Strike Scanner", page_icon="⚡", layout="wide")

# =============================
# إعدادات عامة
# =============================
RIYADH_TZ = ZoneInfo("Asia/Riyadh")
NY_TZ = ZoneInfo("America/New_York")

MARKET_SYMBOLS = {
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq 100 ETF",
    "DIA": "Dow Jones ETF",
    "IWM": "Small Caps ETF",
    "^VIX": "VIX"
}

SECTOR_SYMBOLS = {
    "XLK": "التقنية",
    "XLC": "الاتصالات",
    "XLF": "البنوك والمال",
    "XLE": "الطاقة",
    "XLV": "الصحة",
    "XLY": "الاستهلاكي الدوري",
    "XLI": "الصناعة",
    "XLU": "المرافق"
}

LEADER_STOCKS = ["NVDA", "AMD", "MSFT", "AAPL", "AMZN", "META", "TSLA", "GOOGL", "AVGO", "NFLX"]
SMALL_CAPS = ["SOUN", "BBAI", "PLTR", "RIOT", "MARA", "IONQ", "OPEN", "SOFI", "HOOD", "RIVN"]
TREND_PROXY = ["NVDA", "TSLA", "AMD", "PLTR", "AAPL", "AMZN", "META", "GOOGL", "SOFI", "RIVN", "MARA", "RIOT", "SOUN", "BBAI"]

# =============================
# CSS عربي
# =============================
st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; }
.block-container { padding-top: 1.2rem; }
.big-title {font-size: 34px; font-weight: 900; margin-bottom: 0px;}
.sub-title {font-size: 15px; color: #777; margin-bottom: 20px;}
.card {border: 1px solid #e5e7eb; border-radius: 18px; padding: 18px; background: #fff; box-shadow: 0 6px 20px rgba(0,0,0,0.04); margin-bottom: 12px;}
.good {color:#12823b;font-weight:800;}
.bad {color:#b42318;font-weight:800;}
.neutral {color:#946200;font-weight:800;}
.tag {display:inline-block; padding:6px 10px; border-radius:999px; background:#f3f4f6; margin:3px; font-size:13px;}
.verdict {font-size: 22px; font-weight: 900; line-height: 1.7;}
.small {font-size:13px; color:#666;}
</style>
""", unsafe_allow_html=True)

# =============================
# أدوات البيانات
# =============================
@st.cache_data(ttl=60)
def get_quotes(symbols):
    rows = []
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            info = t.fast_info
            hist_5d = t.history(period="7d", interval="1d", auto_adjust=False)
            hist_1d = t.history(period="1d", interval="1m", auto_adjust=False)
            if hist_5d.empty:
                continue

            last_price = float(info.get("last_price") or hist_5d["Close"].iloc[-1])
            prev_close = float(info.get("previous_close") or (hist_5d["Close"].iloc[-2] if len(hist_5d) > 1 else hist_5d["Open"].iloc[-1]))
            day_open = float(hist_1d["Open"].iloc[0]) if not hist_1d.empty else float(hist_5d["Open"].iloc[-1])
            volume = float(hist_5d["Volume"].iloc[-1]) if "Volume" in hist_5d else 0
            avg_vol = float(hist_5d["Volume"].tail(5).mean()) if "Volume" in hist_5d and hist_5d["Volume"].tail(5).mean() else 0
            rvol = volume / avg_vol if avg_vol > 0 else 0
            chg = ((last_price - prev_close) / prev_close) * 100 if prev_close else 0
            gap = ((day_open - prev_close) / prev_close) * 100 if prev_close else 0
            high = float(hist_5d["High"].iloc[-1])
            low = float(hist_5d["Low"].iloc[-1])
            momentum = ((last_price - day_open) / day_open) * 100 if day_open else 0

            rows.append({
                "الرمز": sym,
                "السعر": round(last_price, 2),
                "التغير %": round(chg, 2),
                "الفجوة %": round(gap, 2),
                "الحجم": int(volume),
                "RVOL": round(rvol, 2),
                "زخم اليوم %": round(momentum, 2),
                "أعلى اليوم": round(high, 2),
                "أدنى اليوم": round(low, 2),
            })
        except Exception as e:
            rows.append({"الرمز": sym, "خطأ": str(e)[:80]})
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def get_news(symbol="market"):
    # مصدر مجاني بدون مفتاح: Yahoo RSS عبر query1 صعب أحيانًا؛ نستخدم endpoint بحث Yahoo العام عبر query2 chart غير مضمون.
    # لذلك نخلي الأخبار اختيارية: Finnhub API إذا أضفت FINNHUB_API_KEY في Streamlit secrets أو env.
    key = os.getenv("FINNHUB_API_KEY") or st.secrets.get("FINNHUB_API_KEY", "") if hasattr(st, "secrets") else ""
    if not key:
        return []
    try:
        url = "https://finnhub.io/api/v1/news"
        params = {"category": "general", "token": key}
        data = requests.get(url, params=params, timeout=8).json()
        return data[:8] if isinstance(data, list) else []
    except Exception:
        return []

# =============================
# محركات التحليل
# =============================
def market_status():
    now_riyadh = datetime.now(RIYADH_TZ)
    now_ny = datetime.now(NY_TZ)
    weekday = now_ny.weekday()
    market_open = time(9, 30)
    market_close = time(16, 0)
    if weekday >= 5:
        status = "مغلق — عطلة نهاية الأسبوع"
    elif market_open <= now_ny.time() <= market_close:
        status = "مفتوح الآن"
    elif now_ny.time() < market_open:
        status = "قبل الافتتاح"
    else:
        status = "مغلق بعد الجلسة"
    return now_riyadh, now_ny, status

def classify_strength(change, rvol=0):
    if change >= 1.5 or rvol >= 2.5:
        return "قوي"
    if change >= 0.3 or rvol >= 1.3:
        return "متوسط"
    if change <= -1.0:
        return "سلبي"
    return "ضعيف/محايد"

def analyze_market(market_df, sector_df):
    if market_df.empty:
        return {"bias": "غير متاح", "risk": "غير متاح", "score": 0, "leader": "غير متاح", "summary": "لا توجد بيانات كافية."}

    def get_chg(sym):
        row = market_df[market_df["الرمز"] == sym]
        if row.empty or "التغير %" not in row:
            return 0
        return float(row["التغير %"].iloc[0])

    spy = get_chg("SPY")
    qqq = get_chg("QQQ")
    dia = get_chg("DIA")
    iwm = get_chg("IWM")
    vix = get_chg("^VIX")

    bullish = sum([spy > 0, qqq > 0, dia > 0, iwm > 0])
    score = 0
    score += 25 if spy > 0 else -15
    score += 25 if qqq > 0 else -15
    score += 15 if iwm > 0 else -5
    score += 20 if vix < 0 else -20
    score += 15 if bullish >= 3 else 0
    score = max(0, min(100, score + 30))

    if score >= 70:
        bias = "كول"
        risk = "Risk-On"
    elif score <= 35:
        bias = "بوت"
        risk = "Risk-Off"
    else:
        bias = "محايد"
        risk = "Neutral"

    leader = "غير واضح"
    if not sector_df.empty and "التغير %" in sector_df:
        top = sector_df.sort_values("التغير %", ascending=False).head(1)
        if not top.empty:
            leader = f"{top['الرمز'].iloc[0]} — {SECTOR_SYMBOLS.get(top['الرمز'].iloc[0], '')}"

    summary = f"السوق يميل إلى {bias}، الصورة العامة {risk}، القائد الحالي {leader}."
    if qqq > spy and qqq > 0:
        summary += " القيادة تميل للتقنية/النازداك."
    if vix > 1:
        summary += " انتبه: VIX صاعد وقد يضغط على الحركة."
    if iwm < 0 and bias == "كول":
        summary += " الاتساع ضعيف نسبيًا؛ الصعود انتقائي وليس شاملًا."

    return {"bias": bias, "risk": risk, "score": round(score), "leader": leader, "summary": summary}

def add_stock_scoring(df, small=False):
    if df.empty or "التغير %" not in df:
        return df
    out = df.copy()
    scores = []
    stages = []
    move_types = []
    flow_proxy = []
    statuses = []

    for _, r in out.iterrows():
        chg = float(r.get("التغير %", 0) or 0)
        rvol = float(r.get("RVOL", 0) or 0)
        gap = float(r.get("الفجوة %", 0) or 0)
        mom = float(r.get("زخم اليوم %", 0) or 0)

        score = 0
        score += min(25, max(0, chg * 5)) if chg > 0 else 0
        score += 25 if rvol >= 3 else 18 if rvol >= 2 else 10 if rvol >= 1.2 else 0
        score += 15 if gap >= 5 else 10 if gap >= 2 else 3 if gap > 0 else 0
        score += 20 if mom >= 2 else 12 if mom >= 0.8 else 5 if mom > 0 else 0
        if small:
            score += 10 if r.get("السعر", 999) <= 10 else 0
        score = int(max(0, min(100, score)))

        if chg > 25 and rvol > 3:
            stage = "بداية ساخنة" if mom > 0 else "نهاية/تصريف محتمل"
        elif chg > 8 and rvol > 1.5:
            stage = "منتصف الحركة"
        elif chg > 0 and mom > 0:
            stage = "نظيف"
        else:
            stage = "ضعيف"

        if rvol >= 2.5 and gap > 3:
            mtype = "Breakout"
        elif chg > 0 and mom > 0 and rvol >= 1.1:
            mtype = "Trend"
        elif chg > 20 and rvol < 1.5:
            mtype = "Pump مشبوه"
        else:
            mtype = "غير واضح"

        flow = "قوي" if (rvol >= 2 and chg > 2) else "متوسط" if (rvol >= 1.2 and chg > 0) else "ضعيف"
        status = "قوي" if score >= 75 else "مراقبة" if score >= 55 else "تجاهل"

        scores.append(score)
        stages.append(stage)
        move_types.append(mtype)
        flow_proxy.append(flow)
        statuses.append(status)

    out["Flow Proxy"] = flow_proxy
    out["المرحلة"] = stages
    out["نوع الحركة"] = move_types
    out["التقييم"] = scores
    out["الحالة"] = statuses
    return out.sort_values("التقييم", ascending=False)

def trending_proxy(df):
    if df.empty:
        return pd.DataFrame()
    base = df.copy()
    if "التغير %" not in base:
        return base
    base["درجة الترند"] = (base["RVOL"].fillna(0) * 25 + base["التغير %"].fillna(0).clip(lower=0) * 4 + base["الفجوة %"].fillna(0).clip(lower=0) * 3).round(1)
    base["جودة الترند"] = base.apply(lambda r: "مدعوم" if r["RVOL"] >= 1.5 and r["التغير %"] > 0 else "ضجيج" if r["درجة الترند"] > 30 else "ضعيف", axis=1)
    return base.sort_values("درجة الترند", ascending=False).head(8)

# =============================
# الواجهة
# =============================
st.markdown('<div class="big-title">⚡ FL Strike Scanner</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">نظام واحد لقراءة نية السوق + السيولة + المحفزات + الترند + أقوى الأسهم — بيانات حقيقية قدر الإمكان عبر مصادر مجانية.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ الإعدادات")
    refresh = st.button("🔄 تحديث البيانات")
    leader_input = st.text_area("قائمة الأسهم القيادية", ",".join(LEADER_STOCKS))
    small_input = st.text_area("قائمة الأسهم الصغيرة", ",".join(SMALL_CAPS))
    st.caption("الأخبار تحتاج FINNHUB_API_KEY اختياري. الأسعار تعمل عبر Yahoo Finance / yfinance.")

leader_symbols = [x.strip().upper() for x in leader_input.split(",") if x.strip()]
small_symbols = [x.strip().upper() for x in small_input.split(",") if x.strip()]

now_riyadh, now_ny, status = market_status()
col1, col2, col3, col4 = st.columns(4)
col1.metric("📅 التاريخ", now_riyadh.strftime("%Y-%m-%d"))
col2.metric("🕒 الرياض", now_riyadh.strftime("%I:%M %p"))
col3.metric("🗽 نيويورك", now_ny.strftime("%I:%M %p"))
col4.metric("حالة السوق", status)

with st.spinner("جاري سحب بيانات السوق الحقيقية..."):
    market_df = get_quotes(list(MARKET_SYMBOLS.keys()))
    sector_df = get_quotes(list(SECTOR_SYMBOLS.keys()))
    leaders_df = add_stock_scoring(get_quotes(leader_symbols), small=False)
    small_df = add_stock_scoring(get_quotes(small_symbols), small=True)
    trend_df = trending_proxy(get_quotes(TREND_PROXY))
    analysis = analyze_market(market_df, sector_df)

# لوحة الانطباع الأول
st.markdown("## 🧠 لوحة الانطباع الأول")
c1, c2, c3, c4 = st.columns(4)
c1.metric("نية السوق", analysis["bias"], f"ثقة {analysis['score']}%")
c2.metric("الصورة العامة", analysis["risk"])
c3.metric("القائد", analysis["leader"])
strong_count = 0 if leaders_df.empty else int((leaders_df["التقييم"] >= 75).sum())
c4.metric("أقوى الأسهم", strong_count)

st.markdown(f'<div class="card verdict">{analysis["summary"]}</div>', unsafe_allow_html=True)

cc1, cc2 = st.columns([1.2, 1])
with cc1:
    st.subheader("🔥 أقوى الأسهم المتفاعلة")
    if not leaders_df.empty:
        st.dataframe(leaders_df[["الرمز", "السعر", "التغير %", "RVOL", "Flow Proxy", "المرحلة", "نوع الحركة", "التقييم", "الحالة"]], use_container_width=True, hide_index=True)
    else:
        st.warning("لا توجد بيانات أسهم قيادية.")
with cc2:
    st.subheader("📣 الترند الاجتماعي — Proxy")
    if not trend_df.empty:
        st.dataframe(trend_df[["الرمز", "السعر", "التغير %", "RVOL", "درجة الترند", "جودة الترند"]], use_container_width=True, hide_index=True)
    else:
        st.warning("لا توجد بيانات ترند.")

st.markdown("## 🌍 سكانر نية السوق")
a, b = st.columns(2)
with a:
    st.subheader("المؤشرات")
    st.dataframe(market_df, use_container_width=True, hide_index=True)
with b:
    st.subheader("القطاعات والسيولة")
    if not sector_df.empty:
        sec = sector_df.copy()
        sec["اسم القطاع"] = sec["الرمز"].map(SECTOR_SYMBOLS)
        sec["القوة"] = sec.apply(lambda r: classify_strength(r.get("التغير %", 0), r.get("RVOL", 0)), axis=1)
        st.dataframe(sec[["الرمز", "اسم القطاع", "السعر", "التغير %", "RVOL", "القوة"]].sort_values("التغير %", ascending=False), use_container_width=True, hide_index=True)

st.markdown("## 🧾 الأخبار والمحفزات")
news = get_news()
if news:
    for item in news[:6]:
        headline = item.get("headline", "")
        source = item.get("source", "")
        url = item.get("url", "")
        st.markdown(f"- **{headline}** — {source}  [رابط]({url})")
else:
    st.info("الأخبار غير مفعلة حاليًا. أضف FINNHUB_API_KEY في Secrets لتفعيل الأخبار. مؤقتًا نعتمد على السعر + الحجم + الترند كـ Flow Proxy.")

st.markdown("## 🧨 سكانر الأسهم الصغيرة")
if not small_df.empty:
    st.dataframe(small_df[["الرمز", "السعر", "التغير %", "الفجوة %", "RVOL", "Flow Proxy", "المرحلة", "نوع الحركة", "التقييم", "الحالة"]], use_container_width=True, hide_index=True)
else:
    st.warning("لا توجد بيانات أسهم صغيرة.")

st.markdown("## ✅ الحكم النهائي")
leader_top = leaders_df.head(1)["الرمز"].iloc[0] if not leaders_df.empty else "غير متاح"
small_top = small_df.head(1)["الرمز"].iloc[0] if not small_df.empty else "غير متاح"
trend_top = trend_df.head(1)["الرمز"].iloc[0] if not trend_df.empty else "غير متاح"
verdict = f"الانطباع الحالي: {analysis['summary']} أقوى سهم قيادي: {leader_top}. أقوى سهم صغير: {small_top}. أكثر رمز عليه ترند Proxy: {trend_top}."
st.markdown(f'<div class="card verdict">{verdict}</div>', unsafe_allow_html=True)

st.caption("تنبيه: هذه أداة قراءة سوق وليست توصية شراء أو بيع. مصادر البيانات المجانية قد تتأخر أو تتوقف مؤقتًا.")
