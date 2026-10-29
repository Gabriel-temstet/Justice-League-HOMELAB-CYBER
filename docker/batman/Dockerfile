FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api.py normalizer.py ./
EXPOSE 8790
CMD ["uvicorn","api:app","--host","0.0.0.0","--port","8790"]
