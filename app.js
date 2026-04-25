const WATCHLIST = {
  market: [
    {symbol:'SPY', type:'مؤشر/ETF', change:1.05, strength:'قوي', catalyst:'شراء واسع', key:'فوق VWAP', status:'صاعد'},
    {symbol:'QQQ', type:'تقنية', change:1.95, strength:'قائد', catalyst:'زخم تقني / AI', key:'أعلى من SPY', status:'قائد'},
    {symbol:'DIA', type:'داو', change:-0.12, strength:'ضعيف', catalyst:'ضغط قطاعي', key:'تحت الأداء', status:'معرقل'},
    {symbol:'IWM', type:'اتساع السوق', change:0.60, strength:'متوسط', catalyst:'مشاركة جزئية', key:'فوق دعم', status:'محايد'},
    {symbol:'VIX', type:'الخوف', change:-2.97, strength:'داعم', catalyst:'انخفاض الخوف', key:'تحت 20', status:'يدعم الكول'},
    {symbol:'XLK', type:'قطاع التقنية', change:2.10, strength:'قوي جدًا', catalyst:'شرائح / AI', key:'قائد القطاعات', status:'قائد'},
    {symbol:'XLC', type:'اتصالات', change:1.15, strength:'جيد', catalyst:'ميغا كاب', key:'داعم', status:'داعم'},
    {symbol:'XLF', type:'بنوك', change:0.20, strength:'ضعيف', catalyst:'انتظار بيانات', key:'محايد', status:'هادئ'}
  ],
  social: [
    {symbol:'NVDA', mentions:'مرتفع جدًا', sentiment:'إيجابي', quality:'مدعوم'},
    {symbol:'AMD', mentions:'مرتفع', sentiment:'إيجابي', quality:'مدعوم'},
    {symbol:'TSLA', mentions:'مرتفع', sentiment:'منقسم', quality:'ضجيج'},
    {symbol:'ARM', mentions:'متوسط', sentiment:'إيجابي', quality:'قابل للمتابعة'}
  ],
  news: [
    {symbol:'NVDA', title:'اهتمام قوي بقطاع الذكاء الاصطناعي والشرائح', impact:'إيجابي'},
    {symbol:'AMD', title:'زخم قطاع الشرائح يرفع اهتمام المتداولين', impact:'إيجابي'},
    {symbol:'AMZN', title:'أخبار سحابية / AWS تدعم السهم', impact:'إيجابي'},
    {symbol:'TSLA', title:'تفاعل اجتماعي مرتفع لكن الرأي منقسم', impact:'مختلط'}
  ]
};

let stockRows = [];
let manualNews = '';

function fmtPct(n){ return `${n>0?'+':''}${Number(n).toFixed(2)}%`; }
function pctNum(v){ return Number(String(v).replace('%','')) || 0; }
function num(v){ return Number(String(v).replace(/,/g,'')) || 0; }
function pill(text, cls){ return `<span class="pill ${cls}">${text}</span>`; }

function getRiyadhClock(){
  const now = new Date();
  const parts = new Intl.DateTimeFormat('ar-SA-u-ca-gregory', {timeZone:'Asia/Riyadh', weekday:'long', year:'numeric', month:'long', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).formatToParts(now);
  const obj = Object.fromEntries(parts.map(p=>[p.type,p.value]));
  const time = `${obj.hour}:${obj.minute}:${obj.second}`;
  const date = `${obj.weekday}، ${obj.day} ${obj.month} ${obj.year}`;
  const ny = new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',weekday:'short',hour12:false}).formatToParts(now);
  const nyObj = Object.fromEntries(ny.map(p=>[p.type,p.value]));
  const h = Number(nyObj.hour), m = Number(nyObj.minute);
  const day = nyObj.weekday;
  const weekday = !['Sat','Sun'].includes(day);
  const minutes = h*60+m;
  let state='مغلق', cls='closed';
  if(weekday && minutes>=570 && minutes<960){ state='مفتوح'; cls='open'; }
  else if(weekday && minutes>=240 && minutes<570){ state='قبل الافتتاح'; cls='pre'; }
  return {time,date,state,cls};
}

function parseCSV(text){
  const lines = text.trim().split(/\r?\n/);
  const headers = lines.shift().split(',').map(h=>h.trim());
  return lines.map(line=>{
    const vals = line.split(',');
    const o = {}; headers.forEach((h,i)=>o[h]=vals[i]);
    return o;
  });
}

function stage(row){
  const gap = pctNum(row['Gap %']); const rvol = num(row['Rel Volume']); const mom = pctNum(row['Momentum %']);
  if(gap >= 5 && rvol >= 2 && mom >= 3) return 'بداية';
  if(mom > 6 || gap > 12) return 'نهاية';
  if(rvol >= 1.5 && mom >= 2) return 'منتصف';
  return 'نظيف';
}
function moveType(row){
  const b = String(row.Breakout||''); const rvol = num(row['Rel Volume']); const gap = pctNum(row['Gap %']);
  if(b.includes('Breakout') && rvol >= 1.8) return 'Breakout';
  if(gap > 8 && rvol < 1.5) return 'Pump';
  return 'Trend';
}
function reEntry(row){
  const st = stage(row); const rejection = String(row.Rejection||'');
  if(st === 'نظيف') return 'نعم';
  if(st === 'منتصف' && rejection.includes('Clean')) return 'نعم';
  return 'لا';
}
function risk(row){
  const atr = pctNum(row['ATR %']); const gap = pctNum(row['Gap %']); const mv = moveType(row);
  if(atr > 5 || gap > 8 || mv==='Pump') return 'عالية';
  if(atr > 3) return 'متوسطة';
  return 'منخفضة';
}
function sector(row){
  const map = {NVDA:'تقنية/شرائح', AMD:'تقنية/شرائح', ARM:'تقنية/شرائح', SMCI:'تقنية/AI Servers', AMZN:'استهلاكي/سحابة', META:'اتصالات', AAPL:'تقنية', MSFT:'تقنية/سحابة', TSLA:'سيارات كهربائية'};
  return map[row.Ticker] || 'غير محدد';
}
function catalyst(row){
  const s = row.Ticker;
  const n = WATCHLIST.news.find(x=>x.symbol===s);
  if(n) return n.title;
  const mv = moveType(row);
  if(mv==='Breakout') return 'زخم سعري + حجم';
  return 'لا يوجد محفز مؤكد';
}
function flowProxy(row){
  const rvol = num(row['Rel Volume']); const gap = pctNum(row['Gap %']); const mom = pctNum(row['Momentum %']);
  let score = 0; if(rvol>=2) score+=35; else if(rvol>=1.2) score+=18;
  if(gap>=5) score+=25; else if(gap>=2) score+=12;
  if(mom>=4) score+=25; else if(mom>=2) score+=12;
  if(String(row.Breakout||'').includes('Bullish')) score+=15;
  return Math.min(score,100);
}
function score(row){
  const st = stage(row), mt = moveType(row), rv = num(row['Rel Volume']), gap = pctNum(row['Gap %']), fp = flowProxy(row);
  let s = 0;
  s += st==='بداية'?25:st==='نظيف'?20:st==='منتصف'?12:0;
  s += mt==='Breakout'?20:mt==='Trend'?15:5;
  s += rv>5?15:rv>=3?10:rv>=2?7:rv>=1?3:0;
  s += gap>10?5:gap>=5?3:gap>=2?2:0;
  s += catalyst(row).includes('لا يوجد')?0:15;
  s += reEntry(row)==='نعم'?10:0;
  s += fp>=70?10:fp>=45?5:0;
  return Math.min(s,100);
}
function statusByScore(s){
  if(s>=90) return ['فرصة نادرة','p-green'];
  if(s>=75) return ['قوية','p-blue'];
  if(s>=60) return ['متوسطة','p-yellow'];
  return ['تجاهل','p-red'];
}

function marketIntent(){
  const m = WATCHLIST.market;
  const spy = m.find(x=>x.symbol==='SPY').change, qqq=m.find(x=>x.symbol==='QQQ').change, vix=m.find(x=>x.symbol==='VIX').change, iwm=m.find(x=>x.symbol==='IWM').change;
  let pts = 0; if(spy>0) pts+=25; if(qqq>spy) pts+=25; if(vix<0) pts+=25; if(iwm>0) pts+=15; if(m.find(x=>x.symbol==='XLK').change>1) pts+=10;
  const intent = pts>=75?'كول قوي':pts>=55?'كول انتقائي':pts<=35?'حذر / بوت':'محايد';
  const picture = pts>=65?'Risk-On':pts<=35?'Risk-Off':'Neutral';
  const leader = qqq>spy?'تقنية / QQQ / XLK':'سوق عام / SPY';
  return {pts,intent,picture,leader};
}

function firstImpression(){
  const mi = marketIntent();
  const ranked = [...stockRows].sort((a,b)=>score(b)-score(a)).slice(0,4);
  const topTickers = ranked.map(r=>r.Ticker).join(' | ') || 'لا توجد بيانات';
  const avgFlow = ranked.length ? Math.round(ranked.reduce((a,r)=>a+flowProxy(r),0)/ranked.length) : 0;
  const socialHot = WATCHLIST.social.slice(0,3).map(x=>x.symbol).join(' | ');
  const socialSent = WATCHLIST.social.filter(x=>x.sentiment==='إيجابي').length >= 2 ? 'إيجابي' : 'منقسم';
  const text = `السوق ${mi.picture}، النية ${mi.intent}، القيادة ${mi.leader}. أقوى الأسهم المتفاعلة: ${topTickers}. الترند الاجتماعي: ${socialHot}. رأي السوق ${socialSent}. Flow Proxy ${avgFlow}%. ${manualNews ? 'ملاحظة أخبار يدوية: '+manualNews : ''}`;
  return {mi, ranked, avgFlow, socialHot, socialSent, text};
}

function render(){
  const c = getRiyadhClock(); const fi = firstImpression();
  document.getElementById('app').innerHTML = `
  <div class="container">
    <div class="topbar">
      <div class="brand"><h1>لوحة FL Strike Decision</h1><p>نسخة عربية مجانية: قراءة السوق + الأسهم + الترند + الأخبار + Flow Proxy</p></div>
      <div class="clock"><div class="time">${c.time}</div><div class="date">${c.date}</div><div style="margin-top:10px">${pill('حالة السوق: '+c.state,c.cls)}</div><div class="sub">الافتتاح الأمريكي: 09:30 نيويورك — الإغلاق: 16:00 نيويورك</div></div>
    </div>

    <section class="card">
      <h2>لوحة الانطباع الأول</h2>
      <div class="grid grid-4">
        <div class="metric"><div class="label">نية السوق</div><div class="value ${fi.mi.pts>=65?'green':fi.mi.pts<=35?'red':'yellow'}">${fi.mi.intent}</div><div class="sub">الثقة: ${fi.mi.pts}%</div></div>
        <div class="metric"><div class="label">الصورة العامة</div><div class="value blue">${fi.mi.picture}</div><div class="sub">القائد: ${fi.mi.leader}</div></div>
        <div class="metric"><div class="label">Flow Proxy</div><div class="value purple">${fi.avgFlow}%</div><div class="sub">RVOL + فجوة + زخم + كسر</div></div>
        <div class="metric"><div class="label">رأي السوق / السوشال</div><div class="value ${fi.socialSent==='إيجابي'?'green':'yellow'}">${fi.socialSent}</div><div class="sub">الأكثر تداولًا: ${fi.socialHot}</div></div>
      </div>
      <div class="grid grid-2" style="margin-top:14px">
        <div class="metric"><div class="label">أقوى الأسهم المتفاعلة</div><div class="value">${fi.ranked.map(r=>r.Ticker).join(' | ') || '—'}</div><div class="sub">مرتبة حسب التقييم + Flow Proxy</div></div>
        <div class="metric"><div class="label">الحكم السريع</div><div class="sub" style="font-size:15px;color:#e5e7eb">${fi.text}</div></div>
      </div>
      <div style="margin-top:14px"><textarea class="textarea" placeholder="أضف خبر/محفز يدوي هنا: مثال: نتائج NVDA أو رفع تصنيف AMD" oninput="manualNews=this.value; render();">${manualNews}</textarea></div>
    </section>

    <section class="card" style="margin-top:14px"><h2>سكانر نية السوق</h2>${marketTable()}</section>
    <section class="card" style="margin-top:14px"><h2>سكانر الأسهم القيادية</h2>${stocksTable(false)}</section>
    <section class="card" style="margin-top:14px"><h2>سكانر الأسهم الصغيرة</h2>${stocksTable(true)}</section>
    <section class="card" style="margin-top:14px"><h2>الترند الاجتماعي + آراء السوق</h2>${socialTable()}</section>
    <section class="card" style="margin-top:14px"><h2>الأخبار والمحفزات</h2>${newsTable()}</section>
    <div class="footer">هذه نسخة مجانية تعليمية/تشغيلية أولى. البيانات الحالية من CSV وعينات قابلة للتعديل. لا تعتبر توصية شراء أو بيع.</div>
  </div>`;
}
function marketTable(){return `<div class="table-wrap"><table><thead><tr><th>العنصر</th><th>النوع</th><th>التغير</th><th>القوة</th><th>المحفز/التفسير</th><th>المستوى المهم</th><th>الحالة</th></tr></thead><tbody>${WATCHLIST.market.map(x=>`<tr><td><b>${x.symbol}</b></td><td>${x.type}</td><td class="${x.change>=0?'green':'red'}">${fmtPct(x.change)}</td><td>${x.strength}</td><td>${x.catalyst}</td><td>${x.key}</td><td>${statusPill(x.status)}</td></tr>`).join('')}</tbody></table></div>`}
function statusPill(s){ const cls = /قائد|صاعد|يدعم|داعم|قوية|ساخن|نادرة/.test(s)?'p-green':/معرقل|تجاهل|فخ|ضعيف/.test(s)?'p-red':/محايد|متوسطة|مراقبة|منقسم/.test(s)?'p-yellow':'p-blue'; return pill(s,cls); }
function stocksTable(small){
  const rows = stockRows.filter(r=> small ? num(r.Price)<50 : num(r.Price)>=50).sort((a,b)=>score(b)-score(a));
  return `<div class="table-wrap"><table><thead><tr><th>الرمز</th><th>القطاع</th><th>السعر</th><th>الفجوة</th><th>الحجم النسبي</th><th>الزخم</th><th>المحفز</th><th>Flow Proxy</th><th>المرحلة</th><th>إعادة دخول</th><th>نوع الحركة</th><th>المخاطرة</th><th>التقييم</th><th>الحالة</th></tr></thead><tbody>${rows.map(r=>{const s=score(r), st=statusByScore(s);return `<tr><td><b>${r.Ticker}</b></td><td>${sector(r)}</td><td>${num(r.Price).toFixed(2)}</td><td class="${pctNum(r['Gap %'])>=0?'green':'red'}">${fmtPct(pctNum(r['Gap %']))}</td><td>${num(r['Rel Volume']).toFixed(2)}x</td><td>${fmtPct(pctNum(r['Momentum %']))}</td><td>${catalyst(r)}</td><td class="score">${flowProxy(r)}%</td><td>${stage(r)}</td><td>${reEntry(r)}</td><td>${moveType(r)}</td><td>${risk(r)}</td><td class="score">${s}</td><td>${pill(st[0],st[1])}</td></tr>`}).join('')}</tbody></table></div>`;
}
function socialTable(){return `<div class="table-wrap"><table><thead><tr><th>الرمز</th><th>حجم الحديث آخر 24 ساعة</th><th>رأي الناس</th><th>جودة الترند</th></tr></thead><tbody>${WATCHLIST.social.map(x=>`<tr><td><b>${x.symbol}</b></td><td>${x.mentions}</td><td>${statusPill(x.sentiment)}</td><td>${statusPill(x.quality)}</td></tr>`).join('')}</tbody></table></div>`}
function newsTable(){return `<div class="table-wrap"><table><thead><tr><th>الرمز</th><th>الخبر/المحفز</th><th>الأثر</th></tr></thead><tbody>${WATCHLIST.news.map(x=>`<tr><td><b>${x.symbol}</b></td><td>${x.title}</td><td>${statusPill(x.impact)}</td></tr>`).join('')}</tbody></table></div>`}

async function init(){
  try{ const res = await fetch('data/stocks.csv'); stockRows = parseCSV(await res.text()); }
  catch(e){ stockRows = []; console.warn(e); }
  render(); setInterval(render,1000);
}
init();
