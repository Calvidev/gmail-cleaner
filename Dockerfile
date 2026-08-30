# Fantasy Tool — imagen para publicar la herramienta en un servidor.
#
#   docker build -t fantasy-tool .
#   docker run -p 8000:8000 -v fantasy-cache:/app/.cache fantasy-tool

FROM python:3.12-slim

# Sin .pyc y con la salida sin buffer, para ver los logs en tiempo real.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Las dependencias van primero: así Docker reaprovecha la capa mientras solo
# cambie el código.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY web/ ./web/
COPY data/ ./data/
COPY .env.defaults ./
COPY docker-entrypoint.sh /usr/local/bin/

# La aplicación no corre como root. El contenedor sí arranca como root, solo lo
# justo para ceder el volumen de caché al usuario, y baja de privilegios antes
# de ejecutar nada: los discos persistentes se montan siempre como root.
RUN useradd --create-home --uid 10001 fantasy \
    && mkdir -p /app/.cache \
    && chown -R fantasy:fantasy /app \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

# El catálogo de jugadores pesa varios MB: el primer arranque tarda un poco más,
# así que el healthcheck da margen antes de empezar a comprobar.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8000)}/api/health').read()"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["sh", "-c", "python -m uvicorn app.main:app --host $HOST --port $PORT"]
