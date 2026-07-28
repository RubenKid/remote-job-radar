# 🛰️ Remote Job Radar

Find **100% remote jobs** that match your CV — automatically. Upload your resume
once; the app understands your experience with AI, searches remote job boards
every day, ranks the results intelligently, and emails you only the best
opportunities. No manual keyword configuration.

## How it works

```
CV.pdf ──▶ Profile Engine ──▶ candidate_profile.json ──▶ Search Engine ──▶ Daily email
```

- **Profile Engine** (runs only when your CV changes): extracts text locally
  (PyMuPDF), then asks an LLM to produce an anonymized professional profile.
  No personal data (name, email, phone, age, …) is ever stored.
- **Search Engine** (runs daily): collects remote jobs → fast local pre-filter →
  AI evaluation of only the top candidates → daily email digest. History
  prevents duplicate emails, and only the shortlist ever reaches the (paid) LLM.

Sources: **Remotive**, **We Work Remotely**, **Jobicy** (more planned).

## Requirements

- Python 3.11+
- An **OpenAI** or **Anthropic** API key
- SMTP credentials for sending email (e.g. a Gmail App Password)

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # add '.[anthropic]' to use Claude instead of OpenAI

cp .env.example .env             # then fill in your keys + SMTP creds
```

Edit `.env`:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini

SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-app-password   # https://myaccount.google.com/apppasswords
EMAIL_TO=you@gmail.com
```

`config.yaml` controls behavior (sources, how many jobs get AI-ranked, the
minimum score, region preferences). Secrets never go there.

## Usage

```bash
# 1. Build your profile from a CV (only needed when the CV changes)
job-radar profile --cv path/to/your_cv.pdf

# 2. Run the daily search (add --dry-run to preview without sending email)
job-radar search --dry-run
job-radar search
```

## Automated daily digest (single user)

`.github/workflows/daily.yml` runs `job-radar search` on a cron schedule.
Add your `.env` values as repository **Actions secrets** (same names). Commit
your `data/candidate_profile.json` (it contains no personal data) so CI can use
it.

## Web app (multi-user)

Beyond the CLI, there's a multi-user web app: users sign in with Google, connect
their own OpenAI/Anthropic key, upload a CV, and receive a daily digest at their
Google email. A scheduled worker runs the search for every user once a day.

```bash
pip install -e '.[web]'
cp .env.example .env          # set APP_SECRET_KEY, SMTP_*, (optionally) GOOGLE_*
python -m job_radar.web       # http://localhost:8000
```

Without `GOOGLE_CLIENT_ID/SECRET`, the app uses a built-in **dev login** so you
can try the full flow offline. To run the daily digest for all users:

```bash
python -m job_radar.web.worker      # or the installed 'job-radar-worker'
```

### Google OAuth setup

1. [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
   → *Create OAuth client ID* → *Web application*.
2. Authorized redirect URI: `<BASE_URL>/auth/callback`
   (e.g. `http://localhost:8000/auth/callback` locally).
3. Put the client ID/secret in `.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

### Deploy (Render / Railway)

A `Dockerfile` and `render.yaml` blueprint are included. On **Render**, push to
GitHub and create a *Blueprint* — it provisions Postgres, the web service, and a
daily cron worker. Fill in the secret env vars (`GOOGLE_*`, `SMTP_*`, `BASE_URL`)
in the dashboard. On **Railway**, deploy the Dockerfile as a service, add a
Postgres plugin (`DATABASE_URL` is injected), and add a cron service running
`python -m job_radar.web.worker`.

Security notes: each user's API key is encrypted at rest (Fernet, keyed by
`APP_SECRET_KEY`); dedup history is per-user in Postgres; personal data is never
stored in the profile (only professional info).

> **LinkedIn login** (planned): the official *Sign In with LinkedIn* / OIDC only
> exposes name, email, and picture — not work history — so CV upload remains the
> way to build the profile until LinkedIn partner access is granted.

## Using Claude instead of OpenAI

```bash
pip install -e '.[anthropic]'
# in .env:
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-8
```

## Project layout

```
src/job_radar/
  common/          config, logging, shared models
  providers/       LLM abstraction (openai, anthropic)
  profile_engine/  pdf_parser, profile_generator, models
  search_engine/
    collectors/    remotive, weworkremotely, jobicy
    ranking/       local_filter (free) + ai_ranker (LLM)
    email/         renderer + SMTP sender
    history/       dedup store (namespaced, multi-user ready)
    pipeline.py    orchestrates the daily run
  cli.py
```

## Development

```bash
pip install -e '.[dev]'
pytest        # offline logic tests (no network / API keys needed)
ruff check .
```

## License

MIT
