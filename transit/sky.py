"""Live sky page: every scanned star lights up where it is on the sky. http://<mini>:7425
Positions come from the TIC catalog in bulk (cached in data/sky_positions.csv); one thread keeps
that cache filled, the HTTP server just serves JSON + one HTML page. No framework (ADR-006)."""
import csv
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from transit.fetch import DATA

POS = DATA / "sky_positions.csv"
PORT = 7425
_lock = threading.Lock()
_positions: dict[str, tuple[float, float, float]] = {}


def _load_positions():
    if POS.exists():
        for r in csv.DictReader(POS.open()):
            _positions[r["tic"]] = (float(r["ra"]), float(r["dec"]), float(r["tmag"]))


def _scan_rows():
    rows = []
    for f in sorted(DATA.glob("scan_*.csv")):
        try:
            rows += list(csv.DictReader(f.open()))
        except Exception:
            pass
    looks = DATA / "looks.csv"
    if looks.exists():  # a full multi-sector look outranks the single-sector scan verdict
        over = {r["tic"]: r for r in csv.DictReader(looks.open())}
        for r in rows:
            o = over.get(r["tic"])
            if o:
                r["label"] = o["label"]; r["reasons"] = f"look {o['recovered']} sectors: " + o["reasons"]
    return rows


def _fill_positions_forever():
    """Every 20 s: fetch positions for scanned stars we have not placed yet, 500 at a time."""
    from astroquery.mast import Catalogs
    while True:
        try:
            missing = [r["tic"] for r in _scan_rows() if r["tic"] not in _positions]
            for i in range(0, len(missing), 500):
                chunk = missing[i:i + 500]
                t = Catalogs.query_criteria(catalog="TIC", ID=chunk)
                new = {str(row["ID"]): (float(row["ra"]), float(row["dec"]), float(row["Tmag"])) for row in t}
                with _lock, POS.open("a", newline="") as f:
                    w = csv.writer(f)
                    if POS.stat().st_size == 0:
                        w.writerow(["tic", "ra", "dec", "tmag"])
                    for tic, (ra, dec, tmag) in new.items():
                        w.writerow([tic, ra, dec, tmag])
                    _positions.update(new)
        except Exception as e:  # MAST hiccup: try again next round
            print("positions:", e, flush=True)
        time.sleep(20)


HTML = r"""<!doctype html><meta charset=utf-8><title>aerospace sky</title>
<style>
html,body{margin:0;height:100%;background:#02040a;color:#9fb3c8;font:13px/1.4 ui-monospace,Menlo,monospace;overflow:hidden}
#wrap{display:grid;grid-template-columns:1fr 420px;grid-template-rows:44px 1fr 150px;height:100vh}
#hud{grid-column:1/3;display:flex;align-items:center;justify-content:space-between;padding:0 16px;border-bottom:1px solid #0e1626}
#hud b{color:#e8eef6;font-weight:600}
.legend span{margin-left:14px}.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}
#map{grid-column:1;grid-row:2;position:relative;overflow:hidden}#c{display:block;width:100%;height:100%;cursor:grab}
#hint{position:absolute;left:12px;bottom:8px;color:#3e4f66;font-size:11px}
#panel{grid-column:2;grid-row:2/4;display:flex;flex-direction:column;gap:6px;padding:10px 14px;border-left:1px solid #0e1626;min-height:0}
#panel h3{margin:0;font:600 13px ui-monospace,Menlo,monospace;color:#e8eef6}
#panel .sub{color:#6f8399;white-space:pre-wrap;font-size:12px}
#panel .plotbox{flex:1 1 0;min-height:0;display:flex;flex-direction:column}
#panel canvas{flex:1 1 0;min-height:0;width:100%;background:#050912;border:1px solid #101828;border-radius:4px}
#panel .lab{color:#6f8399;font-size:11px;margin:2px 0}
#bottom{grid-column:1;grid-row:3;display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:8px 16px;border-top:1px solid #0e1626;overflow:hidden}
#ticker{white-space:pre;color:#6f8399;font-size:12px;overflow:hidden}#ticker .n{color:#ff5b5b}#ticker .k{color:#f2c14e}
#stats{color:#6f8399;font-size:12px;white-space:pre-wrap;overflow:hidden}#stats b{color:#9fb3c8;font-weight:600}
#tip{position:fixed;pointer-events:none;background:#0b1220;border:1px solid #223;padding:4px 7px;border-radius:4px;color:#e8eef6;display:none;white-space:pre;z-index:9}
</style>
<div id=wrap>
<div id=hud><div><b>aerospace</b> · TESS sector scan · <span id=stat>…</span></div>
<div class=legend><span><i style="background:#3a4a63"></i>rejected</span><span><i style="background:#f2c14e"></i>known planet</span><span><i style="background:#ff5b5b"></i>NEW</span><span><i style="background:#fff;opacity:.5"></i>bright star (naked eye)</span></div></div>
<div id=map><canvas id=c></canvas><div id=hint>scroll = zoom · drag = pan · hover = numbers · click gold/red = pin evidence · double-click = reset</div></div>
<div id=panel><h3 id=ptitle>looking at …</h3><div class=sub id=psub></div>
<div class=plotbox><div class=lab>light curve (flattened), flux vs days</div><canvas id=p1></canvas></div>
<div class=plotbox><div class=lab>periodogram: BLS power per trial period; red line = the peak it picked</div><canvas id=p2></canvas></div>
<div class=plotbox><div class=lab>folded on that period; a transit is one dip inside the shaded band</div><canvas id=p3></canvas></div></div>
<div id=bottom><div id=ticker></div><div id=stats></div></div>
</div><div id=tip></div>
<script>
const $=id=>document.getElementById(id);const cv=$('c'),cx=cv.getContext('2d');
let rows=[],bright=[],seen=new Set(),flash=[],first=true,pinned=null,current=null,geo={},view={z:1,px:0,py:0},drag=null;
const shift=r=>(r+60)%360;let bx0=1e9,bx1=-1e9,by0=1e9,by1=-1e9;
function bounds(r){const x=shift(r.ra),y=r.dec;bx0=Math.min(bx0,x);bx1=Math.max(bx1,x);by0=Math.min(by0,y);by1=Math.max(by1,y)}
function size(){const W=cv.clientWidth,H=cv.clientHeight;cv.width=W*devicePixelRatio;cv.height=H*devicePixelRatio;cx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
addEventListener('resize',size);size();
function base(){const W=cv.clientWidth-60,H=cv.clientHeight-60,s=Math.min(W/Math.max(bx1-bx0,1),H/Math.max(by1-by0,1));return{ox:30+(W-(bx1-bx0)*s)/2,oy:30+(H-(by1-by0)*s)/2,s}}
function xy(ra,dec){const b=geo;return[b.ox+(shift(ra)-bx0)*b.s,b.oy+(by1-dec)*b.s]}
function draw(){const W=cv.clientWidth,H=cv.clientHeight;cx.fillStyle='#02040a';cx.fillRect(0,0,W,H);
 const b=base();geo={ox:(b.ox-W/2)*view.z+W/2+view.px,oy:(b.oy-H/2)*view.z+H/2+view.py,s:b.s*view.z};
 // graticule: RA every 15° (1 hour), Dec every 10°
 cx.strokeStyle='#0c1524';cx.fillStyle='#2a3a52';cx.lineWidth=1;cx.font='10px ui-monospace';
 for(let ra=0;ra<360;ra+=15){const [x]=xy(ra,0);if(x<0||x>W)continue;cx.beginPath();cx.moveTo(x,0);cx.lineTo(x,H);cx.stroke();cx.fillText((ra/15)+'h',x+3,H-6)}
 for(let dec=-90;dec<=0;dec+=10){const [,y]=xy(0,dec);if(y<0||y>H)continue;cx.beginPath();cx.moveTo(0,y);cx.lineTo(W,y);cx.stroke();cx.fillText(dec+'°',4,y-3)}
 // real bright stars behind everything
 for(const [ra,dec,m] of bright){const [x,y]=xy(ra,dec);if(x<-5||x>W+5||y<-5||y>H+5)continue;const r=Math.max(0.4,(6.8-m)*0.32)*Math.sqrt(view.z);cx.fillStyle='rgba(255,255,255,'+Math.min(.55,(7-m)*.09)+')';cx.beginPath();cx.arc(x,y,r,0,7);cx.fill()}
 const z=Math.sqrt(view.z);
 for(const r of rows){if(r.ra==null)continue;const [x,y]=xy(r.ra,r.dec);if(x<-5||x>W+5||y<-5||y>H+5)continue;
  const m=Math.max(0.6,3.2-(r.tmag-6)*0.22)*z;cx.beginPath();cx.arc(x,y,r.label==='NEW'?m+2:m,0,7);
  cx.fillStyle=r.label==='NEW'?'#ff5b5b':r.label==='KNOWN'?'#f2c14e':'#3a4a63';cx.fill();
  if(r.label==='KNOWN'||r.label==='NEW'){cx.strokeStyle=cx.fillStyle;cx.globalAlpha=.35;cx.beginPath();cx.arc(x,y,m+6,0,7);cx.stroke();cx.globalAlpha=1}}
 const now=Date.now();flash=flash.filter(f=>now-f.t<1500);
 for(const f of flash){const [x,y]=xy(f.r.ra,f.r.dec),a=1-(now-f.t)/1500;cx.strokeStyle='rgba(180,220,255,'+a+')';cx.lineWidth=1.5;cx.beginPath();cx.arc(x,y,4+(1-a)*18,0,7);cx.stroke()}
 if(current&&current.ra!=null){const [x,y]=xy(current.ra,current.dec);cx.strokeStyle='#7fb3ff';cx.lineWidth=1;cx.setLineDash([3,3]);
  cx.beginPath();cx.moveTo(x-18,y);cx.lineTo(x-6,y);cx.moveTo(x+6,y);cx.lineTo(x+18,y);cx.moveTo(x,y-18);cx.lineTo(x,y-6);cx.moveTo(x,y+6);cx.lineTo(x,y+18);cx.stroke();cx.setLineDash([]);
  cx.fillStyle='#7fb3ff';cx.font='11px ui-monospace';cx.fillText('looking at TIC'+current.tic,x+22,y+4)}
 requestAnimationFrame(draw)}
function plot(id,xs,ys,o={}){const c=$(id),g=c.getContext('2d');const W=c.clientWidth,H=c.clientHeight;if(!W||!H)return;c.width=W*devicePixelRatio;c.height=H*devicePixelRatio;g.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
 g.fillStyle='#050912';g.fillRect(0,0,W,H);const pts=xs.map((x,i)=>[x,ys[i]]).filter(p=>p[1]!=null&&isFinite(p[1]));if(!pts.length)return;
 let x0=Math.min(...xs),x1=Math.max(...xs),srt=pts.map(p=>p[1]).sort((a,b)=>a-b),y0=srt[Math.floor(srt.length*.005)],y1=srt[Math.floor(srt.length*.995)];if(y1<=y0)y1=y0+1e-6;
 const X=x=>8+(x-x0)/(x1-x0)*(W-16),Y=y=>H-8-(y-y0)/(y1-y0)*(H-16);
 if(o.band){g.fillStyle='rgba(255,91,91,.12)';g.fillRect(X(-o.band/2),0,X(o.band/2)-X(-o.band/2),H)}
 g.strokeStyle=g.fillStyle=o.color||'#9fb3c8';
 if(o.line){g.beginPath();pts.forEach((p,i)=>i?g.lineTo(X(p[0]),Y(p[1])):g.moveTo(X(p[0]),Y(p[1])));g.lineWidth=1;g.stroke()}else pts.forEach(p=>g.fillRect(X(p[0]),Y(p[1]),1.2,1.2));
 if(o.mark!=null){g.strokeStyle='#ff5b5b';g.beginPath();g.moveTo(X(o.mark),0);g.lineTo(X(o.mark),H);g.stroke()}
 g.fillStyle='#4b5d75';g.font='10px ui-monospace';g.fillText(o.xl||'',W-8-g.measureText(o.xl||'').width,H-2);g.fillText(y0.toFixed(o.dp||3),2,H-9);g.fillText(y1.toFixed(o.dp||3),2,10)}
function showStar(d,tag){if(!d||!d.lc)return;const r=d.row||{};$('ptitle').textContent=`${tag} TIC${d.tic} · sector ${d.sector} · ${r.label||''}`;
 $('psub').textContent=`P = ${(+r.period).toFixed(4)} d   depth ${r.depth} ppm   duration ${(r.duration*24).toFixed(1)} h   snr ${r.snr}   sde ${d.sde}   transits ${d.n_transits}\n${r.reasons||''}`;
 plot('p1',d.lc.t,d.lc.f,{xl:'days'});plot('p2',d.pgram.p.map(Math.log10),d.pgram.w,{line:true,mark:Math.log10(+r.period),xl:'log10 period (d)',dp:1,color:'#7fb3ff'});
 plot('p3',d.fold.phase,d.fold.f,{line:true,band:d.fold.duration_phase,xl:'phase',color:'#f2c14e'})}
function hit(mx,my){let best=null,bd=64;for(const r of rows){if(r.ra==null)continue;const [x,y]=xy(r.ra,r.dec);const d=(x-mx)**2+(y-my)**2;if(d<bd){bd=d;best=r}}return best}
cv.addEventListener('mousemove',e=>{if(drag){view.px=drag.px+e.clientX-drag.x;view.py=drag.py+e.clientY-drag.y;return}
 const h=hit(e.offsetX,e.offsetY),t=$('tip');if(!h){t.style.display='none';cv.style.cursor='grab';return}cv.style.cursor='pointer';t.style.display='block';t.style.left=(e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px';
 t.textContent=`TIC${h.tic}  ${h.label}\nP ${(+h.period||0).toFixed(3)} d  depth ${h.depth} ppm  snr ${h.snr}\nTmag ${(+h.tmag).toFixed(1)}  RA ${(h.ra/15).toFixed(2)}h  Dec ${(+h.dec).toFixed(2)}°`});
cv.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY,px:view.px,py:view.py,moved:false}});
addEventListener('mouseup',async e=>{if(!drag)return;const moved=Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>3;drag=null;if(moved)return;
 const h=hit(e.clientX-cv.getBoundingClientRect().left,e.clientY-cv.getBoundingClientRect().top);if(!h){pinned=null;return}if(h.label!=='KNOWN'&&h.label!=='NEW')return;
 const d=await (await fetch('/star/'+h.tic)).json();if(d.lc){pinned=h.tic;showStar(d,'pinned ·')}});
cv.addEventListener('wheel',e=>{e.preventDefault();const f=Math.exp(-e.deltaY*0.0015),W=cv.clientWidth,H=cv.clientHeight,mx=e.offsetX-W/2,my=e.offsetY-H/2;
 const nz=Math.min(40,Math.max(0.5,view.z*f)),k=nz/view.z;view.px=mx-(mx-view.px)*k;view.py=my-(my-view.py)*k;view.z=nz},{passive:false});
cv.addEventListener('dblclick',()=>{view={z:1,px:0,py:0}});
fetch('/bright').then(r=>r.json()).then(b=>bright=b);
async function poll(){try{const d=await (await fetch('/data')).json();
 const fresh=d.rows.filter(r=>!seen.has(r.tic));for(const r of fresh){seen.add(r.tic);if(!first&&r.ra!=null)flash.push({r,t:Date.now()+Math.random()*2000})}first=false;
 rows=d.rows;for(const r of rows)bounds(r);
 const c=await (await fetch('/current')).json();current=rows.find(r=>r.tic==c.tic)||null;if(!pinned)showStar(c,'looking at');
 const st=await (await fetch('/stats')).json();
 $('stat').innerHTML=`sector ${d.sector} · <b>${d.n}</b> / ${d.total} stars · rejected ${d.counts.REJECTED||0} · <span style="color:#f2c14e">known ${d.counts.KNOWN||0}</span> · <span style="color:#ff5b5b">NEW ${d.counts.NEW||0}</span> · ${d.rate} stars/min`;
 $('stats').innerHTML='<b>why stars get rejected</b>\n'+st.why.map(([k,v])=>`${String(v).padStart(5)}  ${k}`).join('\n')+`\n<b>${st.left}</b> stars left · ${st.rate}/min · ETA ${st.eta_min?Math.floor(st.eta_min/60)+'h '+st.eta_min%60+'m':'…'}`;
 $('ticker').innerHTML=d.last.map(r=>`<span class="${r.label==='NEW'?'n':r.label==='KNOWN'?'k':''}">TIC${String(r.tic).padEnd(11)} ${r.label.padEnd(9)} P=${(+r.period||0).toFixed(3).padStart(7)} d  ${String(r.depth||'').padStart(6)} ppm  snr ${String(r.snr||'').padStart(6)}</span>`).join('\n');
 }catch(e){console.error(e)}setTimeout(poll,3000)}
poll();draw();
</script>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/bright":
            f = DATA / "bright.csv"
            return self._json([[float(r["ra"]), float(r["dec"]), float(r["tmag"])] for r in csv.DictReader(f.open())] if f.exists() else [])
        if self.path == "/current":
            f = DATA / "current.json"
            return self._json(json.loads(f.read_text()) if f.exists() else {})
        if self.path.startswith("/star/"):
            f = DATA / "stars" / (self.path[6:].replace("TIC", "").strip("/") + ".json")
            return self._json(json.loads(f.read_text()) if f.exists() else {}, 200 if f.exists() else 404)
        if self.path == "/stats":
            rows = _scan_rows()
            why = {}
            for r in rows:
                if r["label"] == "REJECTED":
                    first = (r.get("reasons") or "").split(";")
                    key = next((x.strip() for x in first if "<" in x or "only" in x or "sine" in x or "binary" in x or "companion" in x), "other")
                    key = re.sub(r"[-\d.]+", "#", key)[:60]
                    why[key] = why.get(key, 0) + 1
            rate = _rate()
            left = 15889 - len(rows)
            return self._json({"why": sorted(why.items(), key=lambda kv: -kv[1])[:8], "rate": rate,
                               "eta_min": round(left / rate) if rate else None, "left": left})
        if self.path == "/data":
            rows = _scan_rows()
            n = len(rows)
            tail = rows[-60:]
            counts = {}
            for r in rows:
                counts[r["label"]] = counts.get(r["label"], 0) + 1
            csvs = sorted(DATA.glob("scan_*.csv"))
            sector = csvs[-1].stem.split("_")[1] if csvs else "?"
            total = 15889 if sector == "1" else "?"
            mt = csvs[-1].stat().st_mtime if csvs else time.time()
            rate = round(len(rows[-100:]) / max((mt - _first_time(csvs[-1])) / 60, 1e-6)) if csvs and n > 100 else 0
            out = []
            with _lock:
                for r in rows:
                    p = _positions.get(r["tic"])
                    out.append({"tic": r["tic"], "label": r["label"], "period": r.get("period"), "depth": r.get("depth"), "snr": r.get("snr"),
                                "ra": p[0] if p else None, "dec": p[1] if p else None, "tmag": p[2] if p else 12,
                                "reasons": (r.get("reasons") or "")[:90] if r["label"] in ("NEW", "KNOWN") else ""})
            body = json.dumps({"rows": out, "n": n, "total": total, "counts": counts, "sector": sector, "rate": _rate(),
                               "last": out[-8:][::-1]}).encode()
            ctype = "application/json"
        else:
            body, ctype = HTML.encode(), "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


_hist = []


def _rate():
    """stars per minute over the last ~2 minutes, from row counts sampled at each /data call."""
    _hist.append((time.time(), len(_scan_rows())))
    while _hist and time.time() - _hist[0][0] > 120:
        _hist.pop(0)
    if len(_hist) < 2:
        return 0
    (t0, n0), (t1, n1) = _hist[0], _hist[-1]
    return round((n1 - n0) / max((t1 - t0) / 60, 1e-6))


def _first_time(f):
    return f.stat().st_ctime


def main():
    _load_positions()
    threading.Thread(target=_fill_positions_forever, daemon=True).start()
    print(f"sky page on http://0.0.0.0:{PORT}  (tailnet: http://mac-mini:{PORT})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
