FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e . \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY data/products.db ./data/products.db
COPY data/chroma ./data/chroma

ENV PYTHONPATH=/app/src
EXPOSE 8501

CMD ["streamlit", "run", "src/copilot/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]