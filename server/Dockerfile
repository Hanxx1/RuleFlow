FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server/app ./server/app
COPY shared ./shared
RUN useradd --create-home --uid 10001 ruleflow && mkdir -p /data && chown -R ruleflow:ruleflow /data /workspace
USER ruleflow
ENV DATABASE_PATH=/data/ruleflow.db VAULT_UPLOAD_ROOT=/data/vault_uploads APP_ENV=production
EXPOSE 8000
WORKDIR /workspace/server
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--proxy-headers"]
