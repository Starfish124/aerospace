"""Live sky page: every scanned star lights up where it is on the sky. http://<mini>:7425
Positions come from the TIC catalog in bulk (cached in data/sky_positions.csv); one thread keeps
that cache filled, the HTTP server just serves JSON + one HTML page. No framework (ADR-006)."""
import csv
import json
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
html,body{margin:0;background:#02040a;color:#9fb3c8;font:13px/1.4 ui-monospace,Menlo,monospace;overflow:hidden}
canvas{display:block}
#hud{position:fixed;top:12px;left:16px;right:16px;display:flex;justify-content:space-between;pointer-events:none}
#hud b{color:#e8eef6;font-weight:600}
#ticker{position:fixed;left:16px;bottom:12px;right:16px;white-space:pre;color:#6f8399}
#ticker .n{color:#ff5b5b}#ticker .k{color:#f2c14e}
.legend span{margin-left:14px}.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:middle}
</style>
<div id=hud><div><b>aerospace</b> · TESS sector scan · <span id=stat>…</span></div>
<div class=legend><span><i style="background:#3a4a63"></i>rejected</span><span><i style="background:#f2c14e"></i>known planet</span><span><i style="background:#ff5b5b"></i>NEW</span></div></div>
<canvas id=c></canvas><div id=ticker></div>
<script>
const cv=document.getElementById('c'),cx=cv.getContext('2d');let rows=[],seen=new Set(),flash=[],first=true;
function size(){cv.width=innerWidth*devicePixelRatio;cv.height=innerHeight*devicePixelRatio;cv.style.width=innerWidth+'px';cv.style.height=innerHeight+'px';cx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0)}
addEventListener('resize',size);size();
// sky patch bounds: RA is shifted so the sector does not wrap at 0/360
const shift=r=>(r+60)%360;let bx0=1e9,bx1=-1e9,by0=1e9,by1=-1e9;
function place(r){if(r.ra==null)return null;const x=shift(r.ra),y=r.dec;bx0=Math.min(bx0,x);bx1=Math.max(bx1,x);by0=Math.min(by0,y);by1=Math.max(by1,y);return[x,y]}
function draw(){cx.fillStyle='#02040a';cx.fillRect(0,0,innerWidth,innerHeight);
 const W=innerWidth-80,H=innerHeight-120,sx=W/Math.max(bx1-bx0,1),sy=H/Math.max(by1-by0,1),s=Math.min(sx,sy);
 const ox=40+(W-(bx1-bx0)*s)/2,oy=60+(H-(by1-by0)*s)/2;
 for(const r of rows){if(r.ra==null)continue;const x=ox+(shift(r.ra)-bx0)*s,y=oy+(by1-r.dec)*s;
  const m=Math.max(0.6,3.2-(r.tmag-6)*0.22);
  cx.beginPath();cx.arc(x,y,r.label==='NEW'?m+2:m,0,7);
  cx.fillStyle=r.label==='NEW'?'#ff5b5b':r.label==='KNOWN'?'#f2c14e':'#3a4a63';cx.fill();
  if(r.label==='KNOWN'||r.label==='NEW'){cx.strokeStyle=cx.fillStyle;cx.globalAlpha=.35;cx.lineWidth=1;cx.beginPath();cx.arc(x,y,m+6,0,7);cx.stroke();cx.globalAlpha=1}}
 const now=Date.now();flash=flash.filter(f=>now-f.t<1500);
 for(const f of flash){const r=f.r,x=ox+(shift(r.ra)-bx0)*s,y=oy+(by1-r.dec)*s,a=1-(now-f.t)/1500;
  cx.strokeStyle='rgba(180,220,255,'+a+')';cx.lineWidth=1.5;cx.beginPath();cx.arc(x,y,4+(1-a)*18,0,7);cx.stroke()}
 requestAnimationFrame(draw)}
async function poll(){try{const d=await (await fetch('/data')).json();
 const fresh=d.rows.filter(r=>!seen.has(r.tic));for(const r of fresh){seen.add(r.tic);if(!first&&r.ra!=null)flash.push({r,t:Date.now()+Math.random()*2000})}first=false;
 rows=d.rows;for(const r of rows)place(r);
 document.getElementById('stat').innerHTML=`sector ${d.sector} · <b>${d.n}</b> / ${d.total} stars · rejected ${d.counts.REJECTED||0} · <span style="color:#f2c14e">known ${d.counts.KNOWN||0}</span> · <span style="color:#ff5b5b">NEW ${d.counts.NEW||0}</span> · ${d.rate} stars/min`;
 document.getElementById('ticker').innerHTML=d.last.map(r=>`<span class="${r.label==='NEW'?'n':r.label==='KNOWN'?'k':''}">TIC${String(r.tic).padEnd(12)} ${r.label.padEnd(9)} P=${(+r.period||0).toFixed(3).padStart(7)} d  depth ${String(r.depth||'').padStart(6)} ppm  snr ${String(r.snr||'').padStart(6)}  ${r.reasons||''}</span>`).join('\n');
 }catch(e){}setTimeout(poll,3000)}
poll();draw();
</script>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
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
