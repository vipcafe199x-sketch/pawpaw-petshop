FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --create-home pawpaw \
    && mkdir -p /app/data \
    && chown -R pawpaw:pawpaw /app
COPY --chown=pawpaw:pawpaw backend ./backend
COPY --chown=pawpaw:pawpaw frontend ./frontend
COPY --chown=pawpaw:pawpaw db ./db
COPY --chown=pawpaw:pawpaw main.py ./main.py
USER pawpaw
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
