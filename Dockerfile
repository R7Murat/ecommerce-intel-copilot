FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gradio \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
COPY src ./src
COPY app.py ./
ENV PYTHONPATH=/app/src
EXPOSE 8080
CMD ["python", "app.py"]