FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && groupadd --gid 10001 catchy && useradd --uid 10001 --gid catchy --no-create-home catchy && mkdir /app/data && chown catchy:catchy /app/data
COPY --chown=catchy:catchy backend/ backend/
COPY --chown=catchy:catchy llms/ llms/
COPY --chown=catchy:catchy database/ database/
COPY --chown=catchy:catchy frontend/ frontend/
COPY --chown=catchy:catchy evaluation/ evaluation/
COPY --chown=catchy:catchy data/as/cases.json data/as/cases.json
COPY --chown=catchy:catchy data/bn/cases.json data/bn/cases.json
COPY --chown=catchy:catchy data/en/cases.json data/en/cases.json
COPY --chown=catchy:catchy data/gu/cases.json data/gu/cases.json
COPY --chown=catchy:catchy data/hi/cases.json data/hi/cases.json
COPY --chown=catchy:catchy data/kn/cases.json data/kn/cases.json
COPY --chown=catchy:catchy data/ml/cases.json data/ml/cases.json
COPY --chown=catchy:catchy data/mr/cases.json data/mr/cases.json
COPY --chown=catchy:catchy data/or/cases.json data/or/cases.json
COPY --chown=catchy:catchy data/pa/cases.json data/pa/cases.json
COPY --chown=catchy:catchy data/ta/cases.json data/ta/cases.json
COPY --chown=catchy:catchy data/te/cases.json data/te/cases.json
COPY --chown=catchy:catchy data/ur/cases.json data/ur/cases.json
USER catchy
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python","-m","uvicorn","backend.product:app","--host","0.0.0.0","--port","8000","--no-access-log"]
