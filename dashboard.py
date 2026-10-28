#!/usr/bin/env python3
"""Qwen TTS Lab dashboard — one page to generate speech.

  cd ~/qwen-tts-lab && .venv/bin/python dashboard.py            # full TTS
  TTS_NO_MODEL=1 .venv/bin/python dashboard.py                  # UI preview, no GPU
  TTS_HOST=0.0.0.0 ...                                           # expose on LAN

Loads Qwen3-TTS-12Hz-1.7B-CustomVoice once (~5 GB), serves a UI with speaker
cards, style-instruction chips, sample prompts, player and history.
"""
import json
import os
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
    "Ryan": ("⚡", "dynamic male, rhythmic", "EN"),
    "Aiden": ("☀️", "sunny American male", "EN"),
    "Vivian": ("✨", "bright young female", "ZH"),
    "Serena": ("🌸", "warm gentle female", "ZH"),
    "Uncle_Fu": ("🎩", "low mellow seasoned male", "ZH"),
    "Dylan": ("🏙️", "Beijing male, clear", "ZH"),
    "Eric": ("🌶️", "Chengdu male, husky-bright", "ZH"),
    "Ono_Anna": ("🎀", "playful Japanese female", "JA"),
    "Sohee": ("🍀", "warm Korean female", "KO"),
}
LANGS = ["Auto", "Chinese", "English", "Japanese", "Korean", "German",
         "French", "Russian", "Portuguese", "Spanish", "Italian"]
CHIPS = ["Speak warmly", "Very excited", "Sad and slow", "Whisper quietly",
         "Angry and sharp", "Dramatic storytelling", "Professional news anchor", "Cheerful and fast"]
SAMPLES = [
    "Breaking news: local engineer builds a radio station out of a coffee machine. Experts are baffled.",
    "You are doing amazing. Seriously — take a breath, drink some water, keep going.",
    "The quick brown fox jumps over the lazy dog, twice, while nobody is watching.",
]

PREVIEW = os.environ.get("TTS_NO_MODEL", "0") == "1"
state = {"model": "preview" if PREVIEW else None, "error": None, "busy": False}
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


if not PREVIEW:
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
    if PREVIEW:
        out = {"model": "preview", "busy": False}
    else:
        out = {"model": "loading" if (state["model"] is None and state["error"] is None)
               else ("error" if state["error"] else "ready"), "busy": state["busy"]}
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
    if PREVIEW:
        return JSONResponse({"error": "preview mode — start without TTS_NO_MODEL=1 to generate"}, 425)
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
            text=text, language=body.get("language", "Auto"),
            speaker=body.get("speaker", "Ryan"), instruct=body.get("instruct") or None)
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


SPK_CARDS = "".join(
    f'<label class="spk"><input type="radio" name="spk" value="{k}"{" checked" if k=="Ryan" else ""}>'
    f'<span class="ic">{v[0]}</span><span class="nm">{k}</span>'
    f'<span class="ds">{v[1]}<br><i>{v[2]} native</i></span></label>'
    for k, v in SPEAKERS.items())

PAGE = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qwen TTS Lab</title><style>
:root{{--bg:#0b0d12;--card:#141824;--line:#232a3a;--tx:#e8eaf0;--mut:#8b93a8;--acc:#4f7cff;--ok:#22c55e;--warn:#eab308;--bad:#ef4444}}
*{{box-sizing:border-box}} body{{font-family:system-ui,-apple-system,sans-serif;background:linear-gradient(160deg,#0b0d12,#101527 60%,#0b0d12);color:var(--tx);margin:0;padding:28px 20px;max-width:920px;margin:auto}}
header{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
h1{{font-size:22px;margin:0}} .badge{{font-size:11px;color:#9fb4ff;background:#1a2340;border:1px solid #2c3a63;padding:2px 9px;border-radius:10px}}
.pill{{padding:2px 10px;border-radius:12px;font-size:12px;margin-left:6px}}
.ok{{background:#0f2e1a;color:#7ee2a0}}.bad{{background:#33161a;color:#ff9d9d}}.warn{{background:#33290f;color:#ffd97e}}.info{{background:#16213d;color:#9fb4ff}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:14px 0}}
textarea{{width:100%;height:110px;background:#0e1119;color:var(--tx);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:15px;resize:vertical}}
input[type=text]{{width:100%;background:#0e1119;color:var(--tx);border:1px solid var(--line);border-radius:10px;padding:10px;font-size:14px}}
.spkgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px}}
.spk{{display:flex;gap:8px;align-items:center;background:#0e1119;border:1px solid var(--line);border-radius:10px;padding:9px;cursor:pointer}}
.spk:has(input:checked){{border-color:var(--acc);background:#131b33;box-shadow:0 0 0 1px var(--acc)}}
.spk input{{display:none}} .spk .ic{{font-size:18px}} .spk .nm{{font-weight:600;font-size:13px}} .spk .ds{{font-size:11px;color:var(--mut)}}
.chip{{display:inline-block;background:#0e1119;border:1px solid var(--line);border-radius:14px;padding:4px 12px;margin:3px;cursor:pointer;font-size:12px;color:#c6cde0}}
.chip:hover{{border-color:var(--acc);color:#fff}}
.samp{{font-size:12px;color:#9fb4ff;cursor:pointer;margin-right:10px;text-decoration:underline dotted}}
button.go{{background:linear-gradient(135deg,#4f7cff,#7a5cff);color:#fff;border:0;border-radius:10px;padding:12px 30px;font-size:15px;cursor:pointer;font-weight:600}}
button.go:disabled{{opacity:.5;cursor:wait}}
select{{background:#0e1119;color:var(--tx);border:1px solid var(--line);border-radius:8px;padding:8px}}
.row{{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-top:12px}}
audio{{width:100%;height:36px}}
.item{{padding:10px 0;border-bottom:1px solid #1a2030}} .meta{{font-size:12px;color:var(--mut)}}
.speaker-badge{{font-size:11px;background:#1a2340;color:#9fb4ff;padding:1px 8px;border-radius:9px;margin-right:6px}}
.instruct-badge{{font-size:11px;background:#20261a;color:#b9e29f;padding:1px 8px;border-radius:9px;margin-right:6px}}
a.dl{{color:#7ab8ff;font-size:13px}}
footer{{margin-top:26px;padding-top:14px;border-top:1px solid var(--line);font-size:12px;color:var(--mut)}}
footer a{{color:#9fb4ff;text-decoration:none}}
h3{{font-size:13px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px;margin:0 0 10px}}
</style></head><body>
<header><h1>🎙️ Qwen TTS Lab</h1><span class="badge">Qwen3-TTS-12Hz-1.7B · Apache-2.0</span><span id="st"></span></header>

<div class="card">
 <h3>Script</h3>
 <textarea id="text" placeholder="Type anything — English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian..."></textarea>
 <div style="margin-top:6px">Try: {''.join(f'<span class="samp" onclick="setT({json.dumps(s)})">sample {i+1}</span>' for i,s in enumerate(SAMPLES))}</div>
 <div style="margin:10px 0 4px"><h3 style="margin-bottom:4px">Style chips</h3>
 {''.join(f'<span class="chip" onclick="setI({json.dumps(c)})">{c}</span>' for c in CHIPS)}</div>
 <input type="text" id="instruct" placeholder="...or write your own direction: 'whisper like you're telling a secret'">
</div>

<div class="card">
 <h3>Voice</h3><div class="spkgrid">{SPK_CARDS}</div>
 <div class="row">
  <label style="font-size:13px;color:var(--mut)">Language <select id="language">{''.join(f'<option>{l}</option>' for l in LANGS)}</select></label>
  <button class="go" id="go" onclick="gen()">✦ Generate</button><span id="msg" class="meta"></span>
 </div>
</div>

<div class="card" id="playercard" style="display:none"><h3>Output</h3><div id="player"></div></div>

<div class="card"><h3>History</h3><div id="hist"></div></div>

<footer>Model: <a href="https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice">Qwen3-TTS-12Hz-1.7B-CustomVoice</a> by the <b>Qwen Team, Alibaba Group</b> (Apache-2.0) · <a href="https://github.com/sohamwagh777/qwen-tts-local-lab">repo</a> · Built by Soham Wagh</footer>

<script>
function setT(t){{document.getElementById('text').value=t;}}
function setI(t){{document.getElementById('instruct').value=t;}}
async function refresh(){{
 try{{const s=await(await fetch('/api/status')).json();
  const cls={{ready:'ok',loading:'warn',error:'bad',preview:'info'}}[s.model]||'warn';
  document.getElementById('st').innerHTML=
   `<span class="pill ${{cls}}">model: ${{s.model}}</span>`+
   (s.mem_used_gb?`<span class="pill ${{s.mem_used_gb<100?'ok':'warn'}}">RAM ${{s.mem_used_gb}}/${{s.mem_total_gb}} GB</span>`:'');
  if(s.model==='preview')document.getElementById('msg').textContent='UI preview — generation disabled';
 }}catch(e){{document.getElementById('st').innerHTML='<span class="pill bad">offline</span>';}}
 try{{const h=await(await fetch('/api/history')).json();
  document.getElementById('hist').innerHTML=h.slice().reverse().map(x=>
   `<div class="item"><audio controls preload="none" src="/out/${{x.file}}"></audio><div class="meta"><span class="speaker-badge">${{x.speaker}}</span>${{x.instruct?`<span class="instruct-badge">${{x.instruct}}</span>`:''}}${{x.seconds}}s · ${{x.kb}} KB · ${{x.text.replaceAll('<','&lt;')}} · <a class="dl" href="/out/${{x.file}}" download>dl</a></div></div>`).join('')||'<span class="meta">nothing yet</span>';
 }}catch(e){{}}
}}
async function gen(){{
 const b=document.getElementById('go');b.disabled=true;document.getElementById('msg').textContent='generating…';
 const r=await fetch('/api/tts',{{method:'POST',headers:{{'content-type':'application/json'}},
  body:JSON.stringify({{text:document.getElementById('text').value,speaker:document.querySelector('input[name=spk]:checked').value,
   language:document.getElementById('language').value,instruct:document.getElementById('instruct').value}})}});
 const j=await r.json();b.disabled=false;
 if(j.error){{document.getElementById('msg').textContent=j.error;return;}}
 document.getElementById('msg').textContent=`${{j.seconds}}s · ${{j.kb}} KB`;
 document.getElementById('playercard').style.display='block';
 document.getElementById('player').innerHTML=`<audio controls autoplay src="${{j.url}}"></audio><br><a class="dl" href="${{j.url}}" download>⬇ download WAV</a>`;
 refresh();
}}
refresh();setInterval(refresh,4000);
</script></body></html>"""


@app.get("/api/history")
def hist():
    return history()


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


if __name__ == "__main__":
    import uvicorn
    # LAN-bind with TTS_HOST=0.0.0.0 (trusted home network only)
    uvicorn.run(app, host=os.environ.get("TTS_HOST", "127.0.0.1"),
                port=int(os.environ.get("TTS_PORT", "8642")), log_level="warning")
