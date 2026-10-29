FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir feedparser==6.0.11 httpx==0.28.1
COPY app.py start.sh tool_cli.py ./
COPY osint/osint_veille.py osint/
CMD ["sh","start.sh"]
