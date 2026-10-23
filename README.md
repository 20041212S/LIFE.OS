# LIFE.OS — Personal Command Center

A personal life-tracking project with a responsive dashboard prototype and a FastAPI backend.

## Current status

- `index.html`: interactive browser-only dashboard for adding, editing, searching, filtering, deleting, and exporting records. Prototype data is saved in the browser's local storage.
- `api/`: FastAPI + SQLAlchemy API for storing life entries in SQLite by default. The dashboard is **not yet connected** to this API.

## Run the dashboard

Open `index.html` in a modern browser. No build step is needed. Use **Export JSON** periodically to back up browser-local records.

## Run the API (Linux/macOS)

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Generate a strong secret:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(40))'
```

Put the generated value in `api/.env` as `PERSONAL_API_KEY=...`. Then load the environment and run the server:

```bash
set -a
source .env
set +a
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs
Health check: http://127.0.0.1:8000/health

The API defaults to a local SQLite database (`personal_life.db`) in the API working directory. Do not expose this development server to the public internet as-is. Before deployment, add proper user authentication, HTTPS, secure secret management, backups, and production server configuration.

## Push to GitHub

Create an empty repository on GitHub (for example, `life-os`) without initializing it with a README, then run from this folder:

```bash
git init
git add .
git commit -m "Initial LIFE.OS dashboard and API"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/life-os.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username. Never commit `.env`, API keys, or real personal records.
# LIFE.OS
# LIFE.OS
# LIFE.OS
