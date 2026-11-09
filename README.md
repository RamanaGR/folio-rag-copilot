# Folio RAG Copilot

A privacy-first Chrome Manifest V3 side-panel assistant for reading visible job context, staging known form answers, attaching a local resume, generating a grounded cover letter, and learning answers only after the user supplies them.

## Architecture

- `backend/`: FastAPI service, local SQLite memory, NumPy cosine similarity, and Ollama integration.
- `data/`: verified profile, generated local resume PDF, and runtime `memory.db`.
- `extension/`: MV3 background service worker, persistent side panel, and active-tab content script.

No cloud database or Docker service is required. Form submission always remains a human action.

## Run the backend

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Install and start Ollama separately, then make the configured models available:

```bash
ollama pull nomic-embed-text:latest
ollama pull qwen2.5-coder:7b
```

The extension expects `http://localhost:8000` and `http://localhost:11434` on the local machine. The backend serves `data/Ramana_Gangarao_CV.pdf` at `/api/files/resume`.

## Load the extension

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Choose **Load unpacked** and select this repository's `extension/` folder.
4. Open a role page, click the toolbar icon, and use the side panel.

The panel has three views: **Overview** for the current role and two-step workflow, **Form Assistant** for staging controls and human-review fields, and **Profile** for the verified data categories available locally. It stores role context in `chrome.storage.local` by hostname while a navigation moves from the role page to the form. Unknown answers stay empty and receive an Amber outline. Manual answers submitted on `blur` or `change` are sent to `/api/learn`; learned answers are only reused at cosine similarity `>= 0.86`.

Narrative application answers are written in first person as the applicant. Previously learned narrative answers are checked for third-person wording before reuse; invalid answers fall back to a grounded response or require human review.

## Verification

```bash
python3 -m compileall backend
node --check extension/background.js
node --check extension/sidepanel.js
node --check extension/content.js
```
