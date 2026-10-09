FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 DATABASE_PATH=/app/data/catchy.db
WORKDIR /app
RUN groupadd --gid 10001 catchy && useradd --uid 10001 --gid catchy --no-create-home catchy && mkdir /app/data && chown catchy:catchy /app/data
COPY --chown=catchy:catchy backend/ backend/
COPY --chown=catchy:catchy database/ database/
COPY --chown=catchy:catchy llms/ llms/
COPY --chown=catchy:catchy frontend/ frontend/
USER catchy
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python", "-m", "backend.server"]
