# ========================================
# Stage 1: Builder (Compilação e Dependências)
# ========================================
FROM python:3.10-slim as builder

WORKDIR /app

# Instala ferramentas básicas de compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python no diretório do usuário
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ========================================
# Stage 2: Runtime (Imagem Final Leve)
# ========================================
FROM python:3.10-slim

# Metadados
LABEL maintainer="Voice SDR Team"
LABEL service="voice-sdr-whatsapp"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/sdruser/.local/bin:$PATH"

# Instala apenas o essencial
# - ffmpeg: Para garantir compatibilidade de áudio se necessário
# - curl: Para o Healthcheck
# NÃO precisamos mais de GStreamer/ALSA (pois usaremos API REST)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Cria usuário não-root
RUN useradd -m -u 1000 sdruser
WORKDIR /app

# Copia as bibliotecas do estágio builder
COPY --from=builder /root/.local /home/sdruser/.local

# Copia o código da aplicação
COPY --chown=sdruser:sdruser ./app ./app

# Muda para o usuário seguro
USER sdruser

# Expõe a porta
EXPOSE 8000

# Health Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando de execução
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]