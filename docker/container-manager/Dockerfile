FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py tools.py ./
COPY static static
EXPOSE 8801
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8801/health')"
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8801"]
