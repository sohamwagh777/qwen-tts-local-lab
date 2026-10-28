# TASK.md — Dashboard UI: minimal redesign (frontend only)

Role: you are a minimalist product designer implementing, not brainstorming.

## Problem
The dashboard in `dashboard.py` (single-file FastAPI app, HTML page embedded in
the `PAGE` f-string + the `SPK_CARDS` builder) is TOO NOISY: emoji everywhere,
9 big voice cards, sample-prompt links, chips + free-text style field both,
badges/pills competing for attention, gradient button. The owner wants:
**minimal, calm, optimal to use.**

## Hard rule: backend contract frozen
Do NOT change anything under `app = FastAPI()` except the two page-building
pieces (`SPK_CARDS`, `PAGE`). These must stay byte-identical in behavior:
`/api/status` (JSON keys model/busy/mem_used_gb/mem_total_gb), `/api/tts`
(POST body: text, speaker, language, instruct), `/api/history`, `/out` mount,
`TTS_NO_MODEL` preview mode, `TTS_HOST`/`TTS_PORT` env vars.
Frontend redesign only. You may only edit `dashboard.py`. No new files, no
git commands, no JS frameworks/CDN — everything stays one file, inline CSS/JS.

## Design mandate (art director decisions — encode exactly)
- ONE accent color: `#4f7cff`. No gradients. Neutral base: bg `#0d0f14`,
  surface `#151922`, border `#242b38`, text `#e6e9f0`, muted `#7d8698`.
- NO emoji anywhere in the UI (header, buttons, voice names, badges).
- Header: plain "Qwen TTS Lab" + one muted status dot (green=ready, amber=loading,
  blue=preview, red=error) with tiny text. Remove the model badge pill and RAM
  pill from the header — put RAM (if present) as muted text bottom-right in the footer.
- ONE card containing the whole form, top-to-bottom:
  1. textarea (4 rows) — main focus on load
  2. voice: a single native `<select>` (drop the 9-card grid). Option text: name only.
  3. style instruction: single native `<select>` with options: "Neutral (none)",
     then the 8 existing chips as options. Keep the value sent as `instruct`.
  4. language: native `<select>` (keep all langs)
  5. Generate button: solid `#4f7cff`, no gradient, full width, text "Generate"
- DELETE: sample-prompt links, style chip pills (folded into select), speaker
  cards, separate Script/Voice/Output cards, instruct free-text field
  (select is enough), instruct-badge on history items.
- Output: when audio ready, show `<audio controls>` inline directly under the
  Generate button (no separate card, no autoplay attribute change — keep autoplay).
  Small muted "download WAV" text link under it.
- History: collapsed by default under a muted `<details>` labeled "History".
  Each row: speaker · time · text (one line, ellipsis) + play + dl. No badges.
- Footer (muted, 12px): `Qwen3-TTS by the Qwen Team, Alibaba Group (Apache-2.0) — repo link — Built by Soham Wagh` and RAM pill here.
- Keyboard: Ctrl+Enter (and Cmd+Enter) in textarea triggers generate.
- Keep `busy` behavior: disable button, label becomes "Generating…".

## Accessibility floor (non-negotiable)
- Generate button min 44px tall; select/textarea min 40px; focus-visible outlines
  using the accent. Text contrast >= 4.5:1 against its background (muted text
  #7d8698 on #0d0f14 is 5.4:1 — verify anything you add).
- Every control has a `<label>` (or aria-label). Status dot has aria-label with the state text.

## Verification gates — RUN ALL YOURSELF before finishing, paste raw outputs
1. `~/qwen-tts-lab/.venv/bin/python -m py_compile dashboard.py` → exit 0
2. Boot preview and probe (must not touch GPU):
   `TTS_NO_MODEL=1 TTS_HOST=127.0.0.1 TTS_PORT=8699 ~/qwen-tts-lab/.venv/bin/python dashboard.py &`
   then `curl -s localhost:8699/api/status` → contains `"model":"preview"`;
   `curl -s localhost:8699/ | grep -c '<emoji>'` → 0 (no emoji chars in served HTML);
   kill the server after (bracket-pattern pkill so you don't kill your shell).
3. Count gates on served HTML (`curl -s localhost:8699/`):
   `<label` <= 4, `<select` == 3, `<button` == 1, `<textarea` == 1,
   no `class="spk"` remaining, no `class="samp"` remaining, no `gradient` in CSS.
4. Served HTML contains the footer credit string "Qwen Team" and "TTS_NO_MODEL"
   hint path is NOT required in UI (preview message may stay as muted text under button).
5. Final answer format: raw outputs of gates 1-3 + a list of what you removed.

## Definition of done
Page reads as one calm column: textarea → 3 selects → Generate. Everything
else muted and out of the way. No behavior regressions on the API side.
