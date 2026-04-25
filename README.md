# FL Strike Scanner — Streamlit

لوحة عربية واحدة لقراءة السوق:
- الوقت وحالة السوق
- نية السوق
- السيولة والقطاعات
- Flow Proxy
- أقوى الأسهم القيادية
- الأسهم الصغيرة
- الترند الاجتماعي Proxy
- أخبار Finnhub اختيارية

## التشغيل المحلي
```bash
pip install -r requirements.txt
streamlit run app.py
```

## التشغيل على Render
Build Command:
```bash
pip install -r requirements.txt
```
Start Command:
```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

## Streamlit Cloud
ارفع الملفات إلى GitHub ثم اختر `app.py`.

## الأخبار
لإضافة الأخبار ضع مفتاح Finnhub باسم:
```txt
FINNHUB_API_KEY
```
في Secrets أو Environment Variables.
