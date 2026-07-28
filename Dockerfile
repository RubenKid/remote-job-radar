FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install ".[web,anthropic]"

# Web service (Railway/Render set $PORT). The daily worker runs the same image
# with a different command:  python -m job_radar.web.worker
EXPOSE 8000
CMD ["python", "-m", "job_radar.web"]
