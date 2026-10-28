#!/usr/bin/env python3
"""Qwen TTS Lab dashboard — one page to generate speech.

  cd ~/qwen-tts-lab && .venv/bin/python dashboard.py
Open: http://127.0.0.1:8642

Loads Qwen3-TTS-12Hz-1.7B-CustomVoice once (~4-6 GB GPU), serves a simple UI:
speaker picker, language, natural-language style instruction, text, player, history.
"""
import json
import threading
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
HISTORY = HERE / ".history.json"
MODEL = str(HERE / "Qwen3-TTS-12Hz-1.7B-CustomVoice")

SPEAKERS = {
    "Ryan": "dynamic male, rhythmic (EN native)",
    "Aiden": "sunny American male",
    "Vivian": "bright young female (ZH native)",
    "Serena": "warm gentle female (ZH native)",
    "Uncle_Fu": "low mellow seasoned male",
    "Dylan": "Beijing male, clear",
    "Eric": "Chengdu male, slightly husky",
    "Ono_Anna": "playful Japanese female",
    "Sohee": "warm Korean female",
}
LANGS = ["Auto", "Chinese", "English", "Japanese", "Korean", "German",
         "French", "Russian", "Portuguese", "Spanish", "Italian"]
CHIPS = ["Speak warmly", "Very excited", "Sad and slow", "Whisper quietly",
         "Angry and sharp", "Dramatic storytelling", "Professional news anchor",
         " Cheerful and fast"]

state = {"model": None, "error": None, "busy": False}
lock = threading.Lock()


def load_model():
    try:
        import torch
        from qwen_tts import Qwen3TTSModel
        t0 = time.time()
        state["model"] = Qwen3TTSModel.from_pretrained(
            MODEL, device_map="cuda:0", dtype=torch.bfloat16,
            attn_implementation="sdpa")
        print(f"model ready in {time.time()-t0:.1f}s", flush=True)
    except Exception as e:
        state["error"] = str(e)[:400]
        print("model load FAILED:", state["error"], flush=True)


threading.Thread(target=load_model, daemon=True).start()

app = FastAPI()
app.mount("/out", StaticFiles(directory=str(OUT)), name="out")


def history():
    try:
        return json.loads(HISTORY.read_text())
    except Exception:
        return []


@app.get("/api/status")
def status():
    out = {"model": "loading" if (state["model"] is None and state["error"] is None)
           else ("error" if state["error"] else "ready"),
           "busy": state["busy"]}
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":")
            mem[k] = int(v.split()[0])
        out["mem_used_gb"] = round((mem["MemTotal"] - mem["MemAvailable"]) / 1048576, 1)
        out["mem_total_gb"] = round(mem["MemTotal"] / 1048576, 1)
    except Exception:
        pass
    return out


@app.post("/api/tts")
async def tts(req: Request):
    body = await req.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)
    if state["model"] is None:
        return JSONResponse({"error": f"model {state['model'] or state['error']}"}, status_code=503)
    if not lock.acquire(blocking=False):
        return JSONResponse({"error": "busy — one generation at a time"}, status_code=429)
    try:
        t0 = time.time()
        wavs, sr = state["model"].generate_custom_voice(
            text=text,
            language=body.get("language", "Auto"),
            speaker=body.get("speaker", "Ryan"),
            instruct=body.get("instruct") or None,
        )
        import soundfile as sf
        name = f"{int(time.time()*1000)}.wav"
        sf.write(str(OUT / name), wavs[0], sr)
        entry = {"file": name, "text": text[:120], "speaker": body.get("speaker", "Ryan"),
                 "instruct": body.get("instruct") or "", "seconds": round(time.time()-t0, 1),
                 "kb": (OUT / name).stat().st_size // 1024}
        HISTORY.write_text(json.dumps((history() + [entry])[-50:]))
        return {"url": f"/out/{name}", **entry}
    except Exception as e:
        return JSONResponse({"error": str(e)[:400]}, status_code=500)
    finally:
        lock.release()


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qwen TTS Lab</title><style>
body{font-family:system-ui,sans-serif;background:#0f1117;color:#e6e6e6;margin:0;padding:24px;max-width:880px;margin:auto}
h1{font-size:20px}.pill{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;margin-left:6px}
.ok{background:#123d1e;color:#7ee2a0}.bad{background:#451a1a;color:#ff9d9d}.warn{background:#3d3413;color:#ffd97e}
textarea{width:100%;height:120px;background:#171a22;color:#eee;border:1px solid #2a2f3a;border-radius:8px;padding:12px;font-size:15px;box-sizing:border-box}
input[type=text]{width:100%;background:#171a22;color:#eee;border:1px solid #2a2f3a;border-radius:8px;padding:9px;font-size:14px;box-sizing:border-box}
.chip{display:inline-block;background:#1d2330;border:1px solid #2f3850;border-radius:14px;padding:3px 11px;margin:3px;cursor:pointer;font-size:12px}
.chip:hover,.chip.on{background:#273052;border-color:#4b6bb0}
select{background:#171a22;color:#eee;border:1px solid #2a2f3a;border-radius:6px;padding:7px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:11px 26px;font-size:15px;cursor:pointer}
button:disabled{background:#333}
.row{margin:12px 0;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.item{padding:8px 0;border-bottom:1px solid #1c2029}audio{width:100%;height:32px}
.meta{font-size:12px;color:#8b93a5}</style></head><body>
<h1>🎙️ Qwen TTS Lab <span id="st"></span></h1>
<textarea id="text" placeholder="Type anything — English, Chinese, Japanese, Korean, European languages..."></textarea>
<div style="margin:6px 0">""" + "".join(f'<span class="chip" onclick="setI(\'{c.strip()}\')">{c.strip()}</span>' for c in CHIPS) + """</div>
<input type="text" id="instruct" placeholder="Style instruction (natural language, optional)... e.g. 'whisper like you're telling a secret'">
<div class="row">
 <label>Speaker <select id="speaker">""" + "".join(f'<option value="{k}">{k} — {v}</option>' for k, v in SPEAKERS.items()) + """</select></label>
 <label>Language <select id="language">""" + "".join(f'<option>{l}</option>' for l in LANGS) + """</select></label>
 <button id="go" onclick="gen()">Generate</button><span id="msg" class="meta"></span>
</div>
<div id="player"></div>
<div style="border-top:1px solid #262b36;margin-top:20px;padding-top:10px"><b>History</b><div id="hist"></div></div>
<script>
function setI(t){document.getElementById('instruct').value=t;}
async function refresh(){
 try{const s=await(await fetch('/api/status')).json();
  document.getElementById('st').innerHTML=
   `<span class="pill ${s.model==='ready'?'ok':s.model==='error'?'bad':'warn'}">model ${s.model}</span>`+
   (s.mem_used_gb?`<span class="pill ${s.mem_used_gb<95?'ok':'warn'}">RAM ${s.mem_used_gb}/${s.mem_total_gb} GB</span>`:'');
 }catch(e){document.getElementById('st').innerHTML='<span class="pill bad">offline</span>';}
 try{const h=await(await fetch('/api/history')).json();
  document.getElementById('hist').innerHTML=h.slice().reverse().map(x=>
   `<div class="item"><audio controls preload="none" src="/out/${x.file}"></audio><div class="meta">${x.speaker}${x.instruct?' · '+x.instruct:''} · ${x.seconds}s · ${x.kb} KB · ${x.text.replaceAll('<','&lt;')}</div></div>`).join('');
 }catch(e){}
}
async function gen(){
 const b=document.getElementById('go');b.disabled=true;document.getElementById('msg').textContent='generating…';
 const r=await fetch('/api/tts',{method:'POST',headers:{'content-type':'application/json'},
  body:JSON.stringify({text:document.getElementById('text').value,speaker:document.getElementById('speaker').value,
   language:document.getElementById('language').value,instruct:document.getElementById('instruct').value})});
 const j=await r.json();b.disabled=false;
 if(j.error){document.getElementById('msg').textContent='ERROR: '+j.error;return;}
 document.getElementById('msg').textContent=`${j.seconds}s · ${j.kb} KB`;
 document.getElementById('player').innerHTML=`<audio controls autoplay src="${j.url}"></audio> <a href="${j.url}" download style="color:#7ab8ff">download</a>`;
 refresh();
}
refresh();setInterval(refresh,4000);
</script></body></html>"""


@app.get("/api/history")
def hist():
    return history()


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


if __name__ == "__main__":
    import os
    import uvicorn
    # LAN-bound so Soham's laptop can reach it (trusted home network only)
    uvicorn.run(app, host=os.environ.get("TTS_HOST", "127.0.0.1"), port=int(os.environ.get('TTS_PORT', '8642')), log_level="warning")
