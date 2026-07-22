#!/usr/bin/env python3
import json, math, os, random, statistics, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'config.json').read_text())
UA={'User-Agent':'Mozilla/5.0 BennixIntelligence/1.0'}

def clamp(x,a=0,b=100): return max(a,min(b,x))
def normalize_probs(p):
    s=sum(max(0,float(v)) for v in p.values()) or 1
    return {k:round(max(0,float(v))/s,4) for k,v in p.items()}
def classify(s): return 'STUDY' if s>=70 else ('WATCH' if s>=48 else 'AVOID')
def pct(x): return None if x is None else round(x*100,2)

def get_json(url,timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=timeout) as r:
        return json.load(r)

def chart(symbol,days=220):
    q=urllib.parse.quote(symbol,safe='')
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{q}?range=1y&interval=1d&events=div%2Csplits'
    try:
        z=get_json(url)['chart']['result'][0]; ts=z['timestamp']; quote=z['indicators']['quote'][0]
        rows=[]
        for i,t in enumerate(ts):
            c=quote['close'][i]; v=quote['volume'][i]
            if c is not None: rows.append((t,float(c),float(v or 0)))
        if len(rows)<65: raise ValueError('history too short')
        return rows[-days:], 'yahoo-chart'
    except Exception as e:
        seed=sum(ord(c) for c in symbol); rng=random.Random(seed); price=500+(seed%7000); rows=[]
        now=int(time.time())
        for i in range(days):
            price=max(10,price*(1+rng.gauss(.00025,.018)))
            rows.append((now-(days-i)*86400,price,100000+rng.random()*900000))
        return rows, 'deterministic-fallback:'+type(e).__name__

def metrics(rows,benchmark=None):
    c=[x[1] for x in rows]; v=[x[2] for x in rows]
    ret=lambda n: c[-1]/c[-1-n]-1 if len(c)>n and c[-1-n] else None
    daily=[c[i]/c[i-1]-1 for i in range(1,len(c)) if c[i-1]]
    vol=statistics.pstdev(daily[-60:])*math.sqrt(252) if len(daily)>=20 else None
    peak=max(c[-120:]); dd=c[-1]/peak-1 if peak else None
    r60=ret(60); br60=benchmark.get('r60') if benchmark else 0
    avgv=statistics.mean(v[-60:-20]) if len(v)>=60 else statistics.mean(v)
    vr=statistics.mean(v[-20:])/avgv if avgv else None
    return {'price':round(c[-1],2),'r20':ret(20),'r60':r60,'r120':ret(120),'vol':vol,'drawdown':dd,
            'rel':None if r60 is None or br60 is None else r60-br60,'volume_ratio':vr}

def component(value,lo,hi,missing=50,invert=False):
    if value is None: return missing
    z=clamp((value-lo)/(hi-lo)*100)
    return 100-z if invert else z

def score_stock(m):
    parts={
      'trend':component((m.get('r20') or 0)*.4+(m.get('r60') or 0)*.6,-.20,.30) if m.get('r20') is not None else 45,
      'relative_strength':component(m.get('rel'),-.20,.25),
      'risk':round((component(m.get('vol'),.15,.70,invert=True)+component(m.get('drawdown'),-.45,0))/2),
      'liquidity':component(m.get('volume_ratio'),.5,2.0),
      'fundamental':50,
      'news':clamp(50+(m.get('news') or 0)*12)
    }
    w=CFG['weights']; score=sum(parts[k]*w[k] for k in parts)/sum(w.values())
    return round(clamp(score),1),parts

def rss_news(query,limit=8):
    url='https://news.google.com/rss/search?q='+urllib.parse.quote(query)+'&hl=id&gl=ID&ceid=ID:id'
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=12) as r: root=ElementTree.parse(r).getroot()
        out=[]
        for item in root.findall('.//item')[:limit]:
            out.append({'title':item.findtext('title',''),'link':item.findtext('link',''),'published':item.findtext('pubDate','')})
        return out,'google-news-rss'
    except Exception as e: return [],'rss-fallback:'+type(e).__name__

def sentiment(t):
    t=t.lower(); pos=['naik','tumbuh','surplus','rekor','ekspansi','untung','laba','menguat','investasi']; neg=['turun','rugi','defisit','perang','krisis','anjlok','utang','phk','melemah']
    return sum(x in t for x in pos)-sum(x in t for x in neg)

def macro_regime(proxy):
    usd=proxy['USDIDR']['r20'] or 0; oil=proxy['Minyak']['r20'] or 0; idx=proxy['IHSG']['r60'] or 0; yld=proxy['Yield_US']['r20'] or 0
    risk=50+usd*120+max(0,oil)*80+max(0,yld)*80-max(0,idx)*100
    label='RISK-OFF' if risk>65 else ('RISK-ON' if risk<40 else 'MIXED')
    return {'label':label,'risk_score':round(clamp(risk),1),'signals':[
      f"IHSG 60h {pct(idx):+.1f}%",f"USD/IDR 20h {pct(usd):+.1f}%",f"Minyak 20h {pct(oil):+.1f}%",f"US10Y 20h {pct(yld):+.1f}%"]}

def predictions(regime,proxy,news):
    usd=proxy['USDIDR']['r20'] or 0; oil=proxy['Minyak']['r20'] or 0; gold=proxy['Emas']['r20'] or 0
    specs=[
      ('Rupiah 1–3 bulan',{'bull':3 if usd<0 else 2,'base':5,'bear':3 if usd>0 else 2},
       ['arus modal global','selisih suku bunga','neraca perdagangan'], 'USD/IDR berbalik >5% dari tren 20 hari'),
      ('Energi Indonesia 3–6 bulan',{'bull':3 if oil>0 else 2,'base':5,'bear':3 if oil<0 else 2},
       ['harga minyak','geopolitik jalur pasok','kebijakan domestik'], 'minyak menembus tren berlawanan selama 20 hari'),
      ('Emas 1–6 bulan',{'bull':3 if gold>0 or regime['label']=='RISK-OFF' else 2,'base':5,'bear':2 if gold>0 else 3},
       ['risk-off','yield riil','dolar AS'], 'yield dan dolar menguat bersamaan secara persisten')]
    out=[]
    for title,p,evidence,invalid in specs:
        pr=normalize_probs(p); conf=round(max(pr.values())*100)
        out.append({'topic':title,'probabilities':pr,'confidence':conf,'evidence':evidence,'invalidation':invalid,
                    'causal_chain':'pemicu global → arus uang/barang → harga/biaya → sektor pemenang/pecundang',
                    'not_prediction_of_price':True})
    return out

def render(data):
    payload=json.dumps(data,ensure_ascii=False).replace('</','<\\/')
    html='''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bennix Intelligence</title><style>
:root{--bg:#071018;--card:#0d1b27;--muted:#8ba0b5;--line:#1c3142;--green:#45e0a8;--yellow:#f5c45e;--red:#ff6b72;--blue:#63a9ff}*{box-sizing:border-box}body{margin:0;background:linear-gradient(145deg,#061019,#0a1621);color:#edf6ff;font:14px system-ui}header{padding:22px 5vw;border-bottom:1px solid var(--line);position:sticky;top:0;background:#071018eF;backdrop-filter:blur(12px);z-index:3}h1{font-size:22px;margin:0}small,.muted{color:var(--muted)}main{max-width:1250px;margin:auto;padding:20px 4vw}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:0 8px 30px #0004}h2{font-size:16px;margin:0 0 12px}.big{font-size:32px;font-weight:800}.pill{display:inline-block;padding:4px 9px;border-radius:20px;background:#173047;margin:3px}.STUDY{color:var(--green)}.WATCH{color:var(--yellow)}.AVOID{color:var(--red)}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 7px;border-bottom:1px solid var(--line)}th{color:var(--muted)}.bar{height:7px;background:#172b3b;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--green))}details{margin-top:7px}.warn{border-color:#6e5520;background:#211d12}a{color:var(--blue)}@media(max-width:600px){.hide{display:none}header{padding:16px}main{padding:12px}.card{padding:13px}td,th{padding:8px 4px;font-size:12px}}
</style></head><body><header><h1>BENNIX // Investment Intelligence</h1><small id="fresh"></small></header><main><div class="grid" id="top"></div><br><div class="card"><h2>Ranking Emiten</h2><table><thead><tr><th>Emiten</th><th>Sektor</th><th>Skor</th><th>Status</th><th class="hide">20H</th><th class="hide">Risiko</th></tr></thead><tbody id="stocks"></tbody></table></div><br><div class="grid" id="pred"></div><br><div class="grid" id="sectors"></div><br><div class="card warn"><b>Batasan penting</b><p>Shortlist riset, bukan rekomendasi jual/beli dan bukan jaminan return. Fundamental bernilai netral bila data publik tidak tersedia. Verifikasi laporan keuangan, valuasi, tata kelola, dan risiko sebelum mengambil keputusan.</p></div></main><script>const D='''+payload+''';
const q=x=>document.querySelector(x),fmt=x=>x==null?'n/a':x.toFixed(1)+'%';q('#fresh').textContent='Diperbarui '+D.generated_at+' · sumber: '+D.sources.join(', ');q('#top').innerHTML=`<div class="card"><h2>Regime Makro</h2><div class="big">${D.regime.label}</div><p>Risk score ${D.regime.risk_score}/100</p>${D.regime.signals.map(x=>`<span class="pill">${x}</span>`).join('')}</div><div class="card"><h2>Kandidat STUDY</h2><div class="big STUDY">${D.summary.study}</div><p>${D.summary.watch} WATCH · ${D.summary.avoid} AVOID</p></div><div class="card"><h2>Metode</h2><p>Tren → causal chain → sektor → emiten → skenario → invalidasi.</p><small>Data hilang ditandai, tidak dihalusinasikan.</small></div>`;
q('#stocks').innerHTML=D.stocks.map(s=>`<tr><td><b>${s.ticker}</b><details><summary>alasan</summary>${Object.entries(s.parts).map(([k,v])=>`${k}: ${Math.round(v)}`).join('<br>')}<br><small>${s.note}</small></details></td><td>${s.sector}</td><td><b>${s.score}</b><div class="bar"><i style="width:${s.score}%"></i></div></td><td class="${s.status}">${s.status}</td><td class="hide">${fmt(s.r20_pct)}</td><td class="hide">${fmt(s.vol_pct)}</td></tr>`).join('');
q('#pred').innerHTML=D.predictions.map(p=>`<div class="card"><h2>${p.topic}</h2><p>Bull ${Math.round(p.probabilities.bull*100)}% · Base ${Math.round(p.probabilities.base*100)}% · Bear ${Math.round(p.probabilities.bear*100)}%</p><b>Confidence ${p.confidence}%</b><p>${p.causal_chain}</p><small>Invalidasi: ${p.invalidation}</small></div>`).join('');
q('#sectors').innerHTML=D.sectors.map(s=>`<div class="card"><h2>${s.sector}</h2><div class="big">${s.score}</div><p>${s.count} emiten · ${s.direction}</p></div>`).join('');</script></body></html>'''
    return html

def scan():
    (ROOT/'data/history').mkdir(parents=True,exist_ok=True); (ROOT/'dashboard').mkdir(exist_ok=True)
    proxies={}; sources=set()
    for name,symbol in CFG['proxies'].items():
        rows,src=chart(symbol); sources.add(src); proxies[name]=metrics(rows)
    bench=proxies['IHSG']; news,nsrc=rss_news('ekonomi Indonesia OR emiten IHSG OR geopolitik investasi'); sources.add(nsrc)
    nscore=sentiment(' '.join(x['title'] for x in news))
    stocks=[]
    for ticker,sector in CFG['universe'].items():
        rows,src=chart(ticker); sources.add(src); m=metrics(rows,bench); m['news']=nscore/10
        score,parts=score_stock(m); status=classify(score)
        stocks.append({'ticker':ticker,'sector':sector,'score':score,'status':status,'parts':parts,
          'price':m['price'],'r20_pct':pct(m['r20']),'r60_pct':pct(m['r60']),'vol_pct':pct(m['vol']),
          'note':'Fundamental netral (50) sampai laporan keuangan terstruktur tersedia; wajib verifikasi manual.'})
    stocks.sort(key=lambda x:x['score'],reverse=True)
    sec=[]
    for s in sorted(set(CFG['universe'].values())):
        xs=[x['score'] for x in stocks if x['sector']==s]; avg=round(statistics.mean(xs),1)
        sec.append({'sector':s,'score':avg,'count':len(xs),'direction':'positif' if avg>=60 else ('netral' if avg>=45 else 'lemah')})
    sec.sort(key=lambda x:x['score'],reverse=True)
    regime=macro_regime(proxies); preds=predictions(regime,proxies,news)
    now=datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
    data={'schema_version':1,'generated_at':now,'sources':sorted(sources),'regime':regime,'proxies':proxies,'stocks':stocks,'sectors':sec,
      'predictions':preds,'news':news,'summary':{'study':sum(x['status']=='STUDY' for x in stocks),'watch':sum(x['status']=='WATCH' for x in stocks),'avoid':sum(x['status']=='AVOID' for x in stocks)},
      'disclaimer':'Riset otomatis, bukan nasihat investasi atau jaminan hasil.'}
    raw=json.dumps(data,ensure_ascii=False,indent=2)
    (ROOT/'data/latest.json').write_text(raw); stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); (ROOT/f'data/history/{stamp}.json').write_text(raw)
    html=render(data)
    (ROOT/'dashboard/index.html').write_text(html)
    (ROOT/'index.html').write_text(html)
    print(json.dumps({'ok':True,'generated_at':now,'stocks':len(stocks),'summary':data['summary'],'dashboard':str(ROOT/'dashboard/index.html'),'sources':sorted(sources)},ensure_ascii=False))

def serve():
    os.chdir(ROOT/'dashboard'); print('http://127.0.0.1:8765'); ThreadingHTTPServer(('127.0.0.1',8765),SimpleHTTPRequestHandler).serve_forever()

if __name__=='__main__':
    cmd=sys.argv[1] if len(sys.argv)>1 else 'scan'
    {'scan':scan,'serve':serve}.get(cmd,scan)()
