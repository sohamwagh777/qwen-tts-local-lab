# Qwen TTS — Local Lab 🎙️

One-command local text-to-speech on a single GPU box using
[Qwen3-TTS-12Hz-1.7B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice)
(Apache-2.0, 1.92B params): 9 studio voices, natural-language style instructions
(*"whisper like you're telling a secret"*), 10 languages, streaming-capable,
**fully offline after setup**.

Built and benchmarked on an NVIDIA GB10 (DGX Spark, 121 GB unified memory).
No API keys. No per-character billing. Your text never leaves the machine.

## Why this exists

Cloud TTS (ElevenLabs, OpenAI TTS, Fish Audio API) is great but: $/M chars,
data egress, rate limits. This lab runs a top-tier open TTS entirely on one
machine for ~5 GB RAM — small enough to coexist with an 80 GB LLM server on
the same GPU (yes, really: the setup script enforces the memory recipe that
took us one kernel-OOM-crash to learn).

## Quickstart (one command)

```bash
git clone https://github.com/sohamwagh777/qwen-tts-local-lab.git
cd qwen-tts-local-lab
./run.sh
```

`run.sh` bootstraps everything on first launch (uv venv → PyTorch cu129 → qwen-tts
→ ~5 GB model download) and then serves the dashboard:

```
http://127.0.0.1:8642          # machine itself
TTS_HOST=0.0.0.0 ./run.sh      # expose on LAN (e.g. laptop use)
```

CLI, if you prefer terminals:

```bash
.venv/bin/python say.py "Hello from a fully local TTS." -s Ryan -i "Cheerful and confident" -o hello.wav
```

## Requirements

- NVIDIA GPU (SM80+), ~8 GB free GPU/unified memory, ~6 GB disk
- `uv` ([install](https://docs.astral.sh/uv/)) — the script handles the rest
- Linux/WSL, Python 3.12 (uv fetches it)

## Benchmarks

**Measured on NVIDIA GB10 (DGX Spark), bf16, sdpa attention (no flash-attn), this repo's scripts:**

| Metric | Value |
|---|---|
| Model load (warm cache) | 42–47 s |
| 11.2 s speech generated in | 27.2 s (RTF ≈ 0.41) |
| 7.8 s speech generated in | 15.0 s (RTF ≈ 0.52) |
| Dashboard generation (resident model) | ~20 s for a paragraph |
| Resident memory footprint | ≈ 5 GB |
| Disk (weights + tokenizer) | 4.95 GB |
| Output | WAV 24 kHz |

*First-run CLI numbers include a ~45 s model load each — the dashboard exists
precisely to pay that once. With `flash-attn` installed and `attn_implementation="flash_attention_2"`,
expect meaningfully faster generation (not yet benchmarked here).*

**Official claims** (model card / tech report, arXiv:2601.15621):

| Metric | Value |
|---|---|
| End-to-end streaming latency | 97 ms (dual-track streaming) |
| Languages | Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian |
| SeedTTS-style WER (EN / CN), 1.7B CustomVoice | 2.356 / 2.812 |
| Tokenizer (12 Hz) PESQ_WB / STOI / SIM | 3.21 / 0.96 / 0.95 |

## How it works (architecture)

```
text + speaker + style-instruction
        │
        ▼
Qwen3-TTS-12Hz-1.7B (decoder LM, discrete multi-codebook)
        │  generates acoustic codes at 12 Hz
        ▼
Qwen3-TTS-Tokenizer-12Hz (non-DiT decoder)
        │
        ▼
24 kHz WAV  ──►  FastAPI dashboard (resident model, busy-lock, history)
```

Unlike LM+DiT pipelines, it's a full-information end-to-end discrete LM — the
style instruction is interpreted by the text model itself, so timbre/emotion/pace
follow the words' semantics.

## The one gotcha that matters on ARM+Blackwell (GB10/DGX Spark)

The generic `pip install torch` path gives you a **CPU-only** build on aarch64
(cu126/cu128 indices publish no ARM wheels). This repo's `setup.sh` pins the
working recipe:

```bash
uv pip install --python .venv/bin/python \
    --index-url https://download.pytorch.org/whl/cu129 torch==2.8.0 torchaudio==2.8.0
```

The `cuda capability 12.1 > max 12.0` UserWarning on GB10 is benign (verified GPU matmul).

## Files

| File | Purpose |
|---|---|
| `run.sh` | one command: bootstrap if needed + launch dashboard |
| `setup.sh` | idempotent env + weights installer |
| `say.py` | learn-by-hand CLI (documented flags, no hidden magic) |
| `dashboard.py` | FastAPI UI: speaker picker, style chips, player, history, RAM pill |
| `requirements.txt` | pinned deps (torch installed via setup.sh index) |

## Speakers

Ryan · Aiden (EN), Vivian · Serena · Uncle_Fu · Dylan · Eric (ZH, incl. Beijing/Chengdu dialects), Ono_Anna (JA), Sohee (KO). Every speaker can speak any of the 10 languages; native language sounds best.

## Roadmap

- [ ] flash-attn benchmark table
- [ ] VoiceDesign model variant (describe a voice from scratch, no preset)
- [ ] Base model: 3-second voice cloning endpoint in dashboard
- [ ] OpenAI-compatible `/v1/audio/speech` wrapper for drop-in app use

## License

MIT (scripts, dashboard, docs). Model weights: Apache-2.0 (Qwen).
Built by Soham Wagh — part of the daily-build portfolio series.
