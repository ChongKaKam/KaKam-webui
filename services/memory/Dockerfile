FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home memory
COPY kakam_memory ./kakam_memory
COPY migrations ./migrations
# Git checkout may use umask 077; keep code root-owned but readable by runtime UID.
RUN chmod -R a+rX /app/kakam_memory /app/migrations
USER memory
RUN python -c "import kakam_memory.admin, kakam_memory.manager; from pathlib import Path; paths = list(Path('/app/migrations').glob('*.sql')); assert paths; [p.read_bytes() for p in paths]"
EXPOSE 8081
CMD ["uvicorn", "kakam_memory.app:app", "--host", "0.0.0.0", "--port", "8081", "--no-access-log"]
