FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY reportes/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 appuser

COPY reportes/ ./reportes/

WORKDIR /app/reportes
EXPOSE 8501

USER appuser

ENTRYPOINT ["python", "-m", "streamlit", "run", "app2.py"]
CMD ["--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
