# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is a Streamlit app that gives a face-reading (관상) interpretation of an uploaded photo using an OpenAI vision model. Key documents:
- `PRD.md`: the source of truth for requirements (features F1–F9, prompt rules, output format, env handling, deployment).
- `PROMPTS.md`: the staged build plan the user follows (skeleton → features → UI → review). All four stages have been completed once.
- `.env`: a local secret file. Don't print its contents.

User-facing text, prompts, and docs are written in Korean.

## Commands

```bash
pip install -r requirements.txt
python -m streamlit run app.py                                              # local dev (streamlit.exe is not on PATH on this machine)
python -m streamlit run app.py --server.headless true --server.port 8501    # for Playwright / automated checks
python .playwright-mcp/check_fixes.py                                       # local-only unit checks (validation, refusal parsing, quota, temperature fallback)
```

There is no formal test suite in the repo. `.playwright-mcp/` is git-ignored, so its scripts exist only on this machine and not in a fresh clone. It holds ad-hoc test scripts, test images (including an AI-generated fictional face, `test_face_ai.png`), and screenshots. The Playwright MCP can only write inside the project, so its output goes there too. `.streamlit/config.toml` changes need a server restart. Env vars set on the command line (e.g. `MAX_ANALYSES_PER_SESSION=2`) override `.env`, which is handy for testing limits.

Playwright tips: Streamlit's page scrolls inside its own container, so use a tall viewport instead of `fullPage` screenshots. Upload with `page.setInputFiles('input[type=file]', ...)`. After an upload, wait for the rerun to finish before clicking "관상 보기". If you click too early, the new image's `load_image` clears the pending analysis.

## Architecture (`app.py`, single file)

- **Settings**: `_setting()` reads `st.secrets` first, then `.env`/`os.environ`. `st.secrets` access is wrapped in try/except because it raises without a secrets file. `get_config()` returns the API key, the model (`OPENAI_MODEL`, default `gpt-4o-mini`), `MAX_ANALYSES_PER_SESSION` (5) and `DAILY_ANALYSIS_LIMIT` (100).
- **Input pipeline**: the file uploader has no `type=` filter on purpose. Streamlit's own format and size errors are English, so `validate_upload()` (extension, 10MB) and `preprocess_image()` (Pillow decode, format whitelist incl. MPO, EXIF rotate, RGB, ≤1024px, JPEG bytes) produce Korean `ImageError`s instead. `config.toml` sets `maxUploadSize = 50` so files up to 50MB reach the app's check. `load_image()` runs this once per image digest and stores `prepared_jpeg` / `input_error` in session state. The preview shows `prepared_jpeg`, never the raw upload, because `st.image` on corrupt bytes crashes the script. Images are never written to disk.
- **Analysis**: `run_analysis()` checks the per-session count and the process-wide daily quota (`@st.cache_resource` counter, which resets on restart), then calls `analyze_face()`. It uses Chat Completions with a base64 data URL and `detail: "high"`. If the model rejects `temperature`, it retries once without it. Every OpenAI exception type maps to a Korean `AnalysisError`.
- **Prompt**: `SYSTEM_PROMPT` enforces PRD §6.2: positive tone, no stereotypes, no identity guessing, address the user as "당신". It refuses only when there is no face or more than one face (never for blur). The PRD §6.3 sections are fixed `## ` headings. The part labels embed traditional terms (천정, 인당, 전택, 준두, 인중, 수주, 삼정), because `gpt-4o-mini` ignored a plain instruction to use them.
- **Refusal**: the model starts its reply with `REFUSAL_TAG` (`[분석 불가]`). `parse_refusal()` tolerates markdown decoration around it, and the app shows it as `st.warning`.
- **Rendering**: `split_sections()` splits on `## `. With fewer than 3 sections, the raw markdown is shown in `card_raw`. Cards are `st.container(key=...)`, styled via the `.st-key-<key>` classes (`input_card`, `preview`, `card_<n>`, `card_final`) in the `APP_CSS` constant. Only the first "종합" section gets `card_final`, because duplicate keys crash Streamlit. Model output only ever goes through plain `st.markdown`, and `unsafe_allow_html` is used only for static CSS/HTML.

## Deployment

The app is pushed to GitHub and deployed on Streamlit Community Cloud with `app.py` as the entry point and Python 3.12 (local is 3.15). Secrets go into the Cloud app settings in TOML format. The README tells the user to also set an OpenAI budget limit, because the in-app daily limit resets when the app restarts.
