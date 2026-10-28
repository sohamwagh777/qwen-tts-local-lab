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
    f'<option value="{k}"{" selected" if k=="Ryan" else ""}>{k}</option>'
    for k in SPEAKERS)

PAGE = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Qwen TTS Lab</title><style>
:root{{--bg:#0d0f14;--surface:#151922;--border:#242b38;--text:#e6e9f0;--muted:#7d8698;--accent:#4f7cff}}
*{{box-sizing:border-box}} body{{font-family:system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:32px 20px;max-width:680px;margin:auto}}
header{{display:flex;align-items:center;gap:10px;margin-bottom:22px}} h1{{font-size:21px;font-weight:600;margin:0}}
.status{{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:7px}} .dot{{width:7px;height:7px;border-radius:50%;background:#4f7cff}} .ready{{background:#22c55e}} .loading{{background:#eab308}} .error{{background:#ef4444}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px}}
label{{display:block;font-size:13px;color:var(--muted);margin:14px 0 6px}} textarea,select{{display:block;width:100%;min-height:42px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font:inherit}}
textarea{{height:112px;resize:vertical}} button.go{{width:100%;min-height:46px;margin-top:18px;background:#4f7cff;color:#fff;border:0;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}} button.go:disabled{{opacity:.65;cursor:wait}}
:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}} audio{{width:100%;height:36px;margin-top:12px}} .meta{{font-size:12px;color:var(--muted)}} .output-link,a.dl{{color:#9db4ff;font-size:12px}} details{{margin-top:18px;color:var(--muted);font-size:13px}} summary{{cursor:pointer}} .item{{padding:10px 0;border-bottom:1px solid var(--border)}} .history-row{{display:flex;align-items:center;gap:8px;min-width:0}} .history-text{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;color:var(--muted)}} .history-row a{{color:#9db4ff}} footer{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-top:22px;padding-top:14px;border-top:1px solid var(--border);font-size:12px;color:var(--muted)}} footer a{{color:#9db4ff;text-decoration:none}}
</style></head><body>
<header><h1>Qwen TTS Lab</h1><span id="st" class="status"><span class="dot" aria-label="Loading"></span><span>loading</span></span></header>
<main class="card">
 <label for="text">Text</label><textarea id="text" rows="4" placeholder="Enter text to turn into speech"></textarea>
 <label for="speaker">Voice</label><select id="speaker">{SPK_CARDS}</select>
 <label for="instruct">Style instruction</label><select id="instruct"><option value="">Neutral (none)</option>{''.join(f'<option value="{c}">{c}</option>' for c in CHIPS)}</select>
 <label for="language">Language</label><select id="language">{''.join(f'<option>{l}</option>' for l in LANGS)}</select>
 <button class="go" id="go" onclick="gen()">Generate</button><div id="msg" class="meta" style="margin-top:8px"></div><div id="player"></div>
</main>
<details><summary>History</summary><div id="hist"></div></details>
<footer><span>Qwen3-TTS by the <b>Qwen Team, Alibaba Group</b> (Apache-2.0) — <a href="https://github.com/sohamwagh777/qwen-tts-local-lab">repo</a> — Built by Soham Wagh</span><span id="ram"></span></footer>

<script>
async function refresh(){{
 try{{const s=await(await fetch('/api/status')).json();
  const st=document.getElementById('st'), cls={{ready:'ready',loading:'loading',error:'error',preview:'preview'}}[s.model]||'loading';
  st.innerHTML=`<span class="dot ${{cls}}" aria-label="${{s.model}}"></span><span>${{s.model}}</span>`;
  document.getElementById('ram').textContent=s.mem_used_gb?`RAM ${{s.mem_used_gb}}/${{s.mem_total_gb}} GB`:'';
  if(s.model==='preview')document.getElementById('msg').textContent='UI preview — generation disabled';
 }}catch(e){{document.getElementById('st').innerHTML='<span class="dot error" aria-label="Error"></span><span>offline</span>';}}
 try{{const h=await(await fetch('/api/history')).json();
  document.getElementById('hist').innerHTML=h.slice().reverse().map(x=>
   `<div class="item"><div class="history-row"><span>${{x.speaker}}</span><span class="meta">${{x.seconds}}s</span><span class="history-text">${{x.text.replaceAll('<','&lt;')}}</span><audio controls preload="none" src="/out/${{x.file}}" aria-label="Play ${{x.speaker}} audio"></audio><a class="dl" href="/out/${{x.file}}" download>dl</a></div></div>`).join('')||'<span class="meta">nothing yet</span>';
 }}catch(e){{}}
}}
async function gen(){{
 const b=document.getElementById('go');b.disabled=true;b.textContent='Generating…';document.getElementById('msg').textContent='';
 const r=await fetch('/api/tts',{{method:'POST',headers:{{'content-type':'application/json'}},
  body:JSON.stringify({{text:document.getElementById('text').value,speaker:document.getElementById('speaker').value,
   language:document.getElementById('language').value,instruct:document.getElementById('instruct').value}})}});
 const j=await r.json();b.disabled=false;b.textContent='Generate';
 if(j.error){{document.getElementById('msg').textContent=j.error;return;}}
 document.getElementById('msg').textContent=`${{j.seconds}}s · ${{j.kb}} KB`;
 document.getElementById('player').innerHTML=`<audio controls autoplay src="${{j.url}}"></audio><br><a class="output-link" href="${{j.url}}" download>download WAV</a>`;
 refresh();
}}
document.getElementById('text').focus();document.getElementById('text').addEventListener('keydown',e=>{{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')gen();}});
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
