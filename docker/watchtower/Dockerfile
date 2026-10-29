FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py start.sh ./
COPY veille-cyber/veille_cyber.py veille-cyber/
RUN mkdir -p /data/reports && chown -R 65532:65532 /data
USER 65532:65532
EXPOSE 8830
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8830/health')"
CMD ["sh","start.sh"]
