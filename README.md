# EchoVault

**Some memories refuse to disappear.**

EchoVault is a local-first AI memory vault that turns family voice recordings into searchable stories. It transcribes audio, extracts people, places, traditions and moments, and answers questions using evidence from the original transcript.

## Try EchoVault on your computer

> **Current availability:** EchoVault is a local application, not a hosted website yet. The frontend, API, Whisper transcription and Ollama model run on your own computer. This keeps the AI processing local, but it means you need to complete the setup below before opening the app.

### 1. Install the prerequisites

Install:

- [Python](https://www.python.org/downloads/)
- [Node.js](https://nodejs.org/) (includes npm)
- [Ollama](https://ollama.com/download)

### 2. Download the project

Open PowerShell or a terminal:

```powershell
git clone https://github.com/R-iddhi/Echovault.git
cd Echovault
```

### 3. Set up the Python backend

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

### 4. Download the local language model

Make sure Ollama is running, then run:

```bash
ollama pull qwen2.5:3b
```

EchoVault uses Qwen 2.5 through Ollama for memory extraction and grounded questions. The first transcription may also download the faster-whisper `base.en` model, so an internet connection is needed during initial setup.

### 5. Start the backend

From the project root, open a terminal and run:

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**macOS or Linux** (with the virtual environment activated)

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Keep this terminal open.

### 6. Start the website

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite, usually:

**http://localhost:5173**

Keep both the backend and frontend terminals running while using EchoVault.

## How to use it

1. Open EchoVault in your browser.
2. Upload a family voice recording.
3. Review and edit the generated transcript.
4. Preserve the memory to extract people, places, traditions and moments.
5. Open the evidence attached to an extracted detail with Ghostlight.
6. Ask a question in **Ask this Memory**. EchoVault should answer from the transcript and say when a detail is not present.

## Local-first design

- **faster-whisper** transcribes audio on the same computer.
- **Qwen 2.5** runs locally through **Ollama**.
- **Ghostlight** links extracted details back to supporting transcript sentences.
- **Ask this Memory** is designed to stay grounded in the original transcript instead of inventing missing details.

Because this version runs locally, there is no public click-and-use URL at present. A hosted version would need a separately deployed AI backend and a different privacy setup. The demo video shows the current application in action.

## Project links

- **Demo video:** Add the public YouTube link here after publishing.
- **Source code:** https://github.com/R-iddhi/Echovault

## Technology

React · Vite · FastAPI · faster-whisper · Qwen 2.5 · Ollama

## License

MIT
