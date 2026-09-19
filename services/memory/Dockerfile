FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home memory
COPY kakam_memory ./kakam_memory
COPY migrations ./migrations
USER memory
EXPOSE 8081
CMD ["uvicorn", "kakam_memory.app:app", "--host", "0.0.0.0", "--port", "8081", "--no-access-log"]
