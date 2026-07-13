FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY src ./src

ENV PYTHONPATH=/app/src
EXPOSE 8080

CMD ["streamlit", "run", "src/copilot/ui/app.py", \
     "--server.port=8080", "--server.address=0.0.0.0", \
     "--server.headless=true"]