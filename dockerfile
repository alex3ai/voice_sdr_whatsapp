# ========================================
# Stage 1: Builder (Compilação e Dependências)
# ========================================
FROM python:3.10-slim as builder

WORKDIR /app

# Instala ferramentas de compilação necessárias (GCC para bibliotecas C)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências no diretório do usuário (.local)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ========================================
# Stage 2: Runtime (Imagem Final)
# ========================================
FROM python:3.10-slim

# Metadados do projeto
LABEL maintainer="Voice SDR Team"
LABEL service="voice-sdr-whatsapp"

# Otimizações do Python para Container:
# - PYTHONUNBUFFERED: Garante que os logs saiam imediatamente (não trava no buffer)
# - PYTHONDONTWRITEBYTECODE: Não gera arquivos .pyc (economiza espaço e I/O)
# - PATH: Adiciona os binários instalados pelo pip ao sistema
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/sdruser/.local/bin:$PATH

# Instala FFmpeg (obrigatório para conversão de áudio OGG/MP3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Cria usuário não-root (Segurança)
RUN useradd -m -u 1000 sdruser

# Configura diretório de trabalho
WORKDIR /app

# Copia as bibliotecas Python instaladas no Stage 1
COPY --from=builder /root/.local /home/sdruser/.local

# Copia o código da aplicação com as permissões corretas
COPY --chown=sdruser:sdruser ./app ./app

# Muda para o usuário seguro
USER sdruser

# Expõe a porta da aplicação
EXPOSE 8000

# Health Check: O Docker vai "pingar" sua API a cada 30s
# Se falhar 3 vezes, marca o container como "unhealthy"
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Comando de execução
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]