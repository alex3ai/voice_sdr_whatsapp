# Resumo Abrangente do Projeto - Voice SDR WhatsApp

Este documento fornece um resumo completo do estado atual e da arquitetura da aplicação `voice-sdr-whatsapp`, além de preservar o histórico de depuração.

---

## 1. Visão Geral da Arquitetura

A aplicação é um sistema `dockerizado` composto por 3 serviços principais que se comunicam em uma rede privada:

1.  **`sdr-bot` (Esta Aplicação):**
    *   **Tecnologia:** FastAPI (Python) com `uvicorn`.
    *   **Responsabilidade:** Orquestrar todo o fluxo. Recebe webhooks da Evolution API, gerencia a lógica de negócios e se comunica com os serviços de IA e TTS.
    *   **Interface:** Expõe endpoints para conexão (`/qrcode`), status (`/status`) e recebimento de eventos (`/webhook/evolution`).

2.  **`evolution-api`:**
    *   **Tecnologia:** Imagem Docker `atendai/evolution-api:latest`.
    *   **Responsabilidade:** Atuar como um gateway para o WhatsApp. Gerencia a conexão (via QR Code), envio e recebimento de mensagens.
    *   **Comunicação:** Notifica o `sdr-bot` sobre novos eventos (mensagens, status de conexão) através de webhooks.

3.  **`postgres` e `redis`:**
    *   **Tecnologia:** Imagens oficiais do PostgreSQL e Redis.
    *   **Responsabilidade:** Fornecer persistência e cache para a `evolution-api`, armazenando sessões, mensagens e outros dados.

## 2. Fluxo de Processamento de Áudio (Pipeline)

Quando um usuário envia uma mensagem de áudio para o número conectado:

1.  **Recepção (Evolution API):** A `evolution-api` recebe o áudio e dispara um webhook do tipo `messages.upsert` para o `sdr-bot`.

2.  **Validação e Delegação (FastAPI):**
    *   O endpoint `/webhook/evolution` em `app/main.py` recebe a notificação.
    *   O payload é validado pelo modelo Pydantic `EvolutionWebhook`.
    *   Para evitar bloqueios, o processamento é delegado para uma tarefa em background (`process_audio_pipeline`).

3.  **Download do Áudio (Serviço Evolution):**
    *   O `evolution_service` baixa o áudio (que vem no formato `.ogg`) da `evolution-api` e o salva em um arquivo temporário.

4.  **Processamento de IA (Serviço Brain):**
    *   O `brain_service` envia o arquivo de áudio para a **API do Google Gemini**.
    *   A IA transcreve o áudio, analisa a pergunta e gera uma resposta em texto, seguindo as diretrizes do `SYSTEM_PROMPT`.
    *   O serviço possui uma lógica de **fallback**: se o modelo principal falhar, ele tenta um modelo secundário.

5.  **Síntese de Voz (Serviço Voice):**
    *   O `voice_service` recebe o texto gerado pela IA.
    *   Ele utiliza a biblioteca `edge-tts` para converter o texto em um áudio `.mp3` com a voz neural configurada.
    *   Em seguida, usa o **FFmpeg** para converter o `.mp3` para o formato `.ogg` com codec Opus, otimizado para o WhatsApp.

6.  **Envio da Resposta (Serviço Evolution):**
    *   O `evolution_service` envia o áudio `.ogg` finalizado de volta para o usuário, respondendo à mensagem original.

7.  **Limpeza:** Todos os arquivos de áudio temporários (`.ogg`, `.mp3`) são automaticamente removidos do sistema.

---

## 3. Histórico de Depuração (Resolvido)

Esta seção detalha os problemas encontrados e resolvidos durante o desenvolvimento inicial.

### 3.1. Análise do "Internal Server Error" (500)
✅ **Resolvido.** A causa era a falta de um modelo Pydantic para validar o payload do webhook. A correção foi aplicar o modelo `EvolutionWebhook` no endpoint, permitindo que o FastAPI gerencie a validação automaticamente.

### 3.2. Análise do "Not Found" (404) na API da Evolution
✅ **Resolvido.** O problema era tentar configurar o webhook via API. A solução foi definir o webhook através de **variáveis de ambiente** no `docker-compose.yml`, que é a abordagem correta para a versão da API em uso.

### 3.3. Análise do Loop de Conexão e Timeout
✅ **Resolvido.** A aplicação entrava em um loop de `criar -> falhar -> deletar -> recriar` instância. A solução teve duas partes:
1.  **Remoção da Lógica Agressiva:** Em vez de deletar e recriar, a lógica em `app/main.py` foi simplificada. O método `create_instance` em `app/services/evolution.py` foi ajustado para primeiro tentar criar e, ao receber um erro `403 (Forbidden)`, interpretar que a instância já existe e apenas solicitar a conexão.
2.  **Implementação de um `asyncio.Lock`:** No endpoint `/qrcode`, foi adicionado um lock para impedir que múltiplas solicitações de criação de QR Code ocorram simultaneamente, estabilizando o processo.

---

## 4. Estado Atual dos Arquivos

Abaixo está o conteúdo dos principais arquivos do projeto no estado atual.

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  # ========================================
  # 1. Banco de Dados (Agora com Volume Interno)
  # ========================================
  postgres:
    image: postgres:15
    container_name: evolution_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=evolution
      - POSTGRES_PASSWORD=evolution
      - POSTGRES_DB=evolution
    volumes:
      # MUDANÇA CRÍTICA: Usando volume interno (rápido e seguro no Windows)
      - evolution_postgres_data:/var/lib/postgresql/data
    networks:
      - voice_sdr_network
    # Healthcheck mais tolerante para a primeira inicialização
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U evolution -d evolution"]
      interval: 10s
      timeout: 10s
      retries: 20
      start_period: 60s

  # ========================================
  # 2. Redis
  # ========================================
  redis:
    image: redis:alpine
    container_name: evolution_redis
    command: redis-server --appendonly yes --requirepass 123456
    volumes:
      - ./evolution_data/redis:/data
    networks:
      - voice_sdr_network
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "123456", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ========================================
  # 3. Evolution API (Configuração BLINDADA)
  # ========================================
  evolution-api:
    image: evoapicloud/evolution-api:v2.3.0
    container_name: evolution_whatsapp
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    dns:
      - 8.8.8.8
      - 8.8.4.4
      - 1.1.1.1
    shm_size: '2gb' 
    ports:
      - "8080:8080"
    environment:
      - SERVER_URL=http://localhost:8080
      - DOCKER_ENV=true
      - AUTHENTICATION_API_KEY=123456
      - LOG_LEVEL=ERROR
      - LOG_BAILEYS=error
      
      # Banco e Cache
      - DATABASE_ENABLED=true
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=postgresql://evolution:evolution@postgres:5432/evolution?schema=public&connection_limit=5
      - DATABASE_SAVE_DATA_INSTANCE=true
      - DATABASE_SAVE_DATA_NEW_MESSAGE=true
      - CACHE_REDIS_ENABLED=true
      - CACHE_REDIS_URI=redis://:123456@redis:6379/0
      
      # WebSocket 
      - WEBSOCKET_MAX_PAYLOAD=104857600
      - WEBSOCKET_PING_INTERVAL=20000
      - WEBSOCKET_PONG_TIMEOUT=60000
      
      # Webhook
      - WEBHOOK_GLOBAL_ENABLED=true
      - WEBHOOK_GLOBAL_URL=http://voice_sdr_bot:8000/webhook/evolution
      - WEBHOOK_EVENTS=MESSAGES_UPSERT,CONNECTION_UPDATE,QRCODE_UPDATED
      
      # Chrome
      - CONFIG_SESSION_PHONE_CLIENT=VoiceSDR
      - CONFIG_SESSION_PHONE_NAME=Chrome
      - CHROME_ARGS=--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-setuid-sandbox
      - DEL_INSTANCE=false
      - QRCODE_LIMIT=30
      
    volumes:
      - evolution_instances:/evolution/instances
      - evolution_store:/evolution/store
    networks:
      - voice_sdr_network

  # ========================================
  # 4. Bot (Sua Aplicação)
  # ========================================
  sdr-bot:
    build: 
      context: .
      dockerfile: Dockerfile
    container_name: voice_sdr_bot
    restart: unless-stopped
    depends_on:
      - evolution-api 
    ports:
      - "${PORT:-8000}:8000"
    env_file:
      - .env
    environment:
      - EVOLUTION_API_URL=http://evolution-api:8080
      - EVOLUTION_API_KEY=123456
    networks:
      - voice_sdr_network

networks:
  voice_sdr_network:
    driver: bridge

# ========================================
# Definição dos Volumes Internos
# ========================================
volumes:
  evolution_instances:
  evolution_store:
  evolution_postgres_data: # Volume novo para o Banco
```

### `Dockerfile`

```dockerfile
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
```

### `app/main.py`

```python
"""
Servidor FastAPI - Voice SDR com Evolution API
"""
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import time
from typing import Dict, Any

from app.config import settings
from app.services.evolution import evolution_service
from app.services.brain import brain_service
from app.services.voice import voice_service
from app.utils.files import safe_remove, cleanup_temp_files
from app.utils.logger import setup_logger
from app.models.webhook import EvolutionWebhook

logger = setup_logger(__name__)

# Inicialização do FastAPI
app = FastAPI(
    title="Voice SDR WhatsApp (Evolution API)",
    description="Atendente de vendas com IA que responde áudios no WhatsApp",
    version="2.1.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None
)

# Métricas
metrics = {
    "total_messages": 0,
    "audio_messages": 0,
    "successful_responses": 0,
    "errors": 0,
    "start_time": time.time()
}

# Estado da conexão
connection_state = {
    "connected": False,
    "qr_code": None,
    "last_check": None,
    "is_creating": False
}
# Lock para evitar múltiplas solicitações simultâneas de QR Code
creation_lock = asyncio.Lock()


@app.on_event("startup")
async def startup_event():
    """Executa ao iniciar o servidor"""
    logger.info("=" * 70)
    logger.info("🚀 Voice SDR WhatsApp (Evolution API) iniciando...")
    logger.info(f"📱 Instância: {settings.evolution_instance_name}")
    logger.info(f"🤖 Modelo Gemini: {settings.gemini_model_primary}")
    logger.info(f"🎙️ Voz TTS: {settings.edge_tts_voice}")
    logger.info(f"🔗 Evolution API: {settings.evolution_api_url}")
    logger.info("=" * 70)
    
    # Limpeza inicial
    cleanup_temp_files(max_age_hours=1)
    
    # Aguarda a Evolution API ficar pronta (tempo para o Docker subir)
    await asyncio.sleep(5)
    
    # Verifica se a instância já existe e está conectada
    try:
        state = await evolution_service.get_connection_state()
        if state.get("state") == "open":
            logger.info("✅ WhatsApp já conectado!")
            connection_state["connected"] = True
        else:
            logger.info("⏳ WhatsApp não conectado. Acesse /qrcode para conectar.")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível verificar status inicial: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Executa ao encerrar o servidor"""
    uptime = time.time() - metrics["start_time"]
    logger.info("=" * 70)
    logger.info("🛑 Encerrando Voice SDR WhatsApp")
    logger.info(f"📊 Métricas da sessão:")
    logger.info(f"   - Tempo ativo: {uptime/3600:.1f}h")
    logger.info(f"   - Mensagens processadas: {metrics['total_messages']}")
    logger.info(f"   - Áudios recebidos: {metrics['audio_messages']}")
    logger.info(f"   - Respostas enviadas: {metrics['successful_responses']}")
    logger.info(f"   - Erros: {metrics['errors']}")
    logger.info("=" * 70)


@app.get("/")
async def root():
    """Endpoint raiz - Dashboard"""
    uptime_hours = (time.time() - metrics["start_time"]) / 3600
    
    # Tenta obter estado atualizado, fallback para cache local se falhar
    try:
        state = await evolution_service.get_connection_state()
        is_connected = state.get("state") == "open"
    except:
        is_connected = connection_state["connected"]
    
    return {
        "status": "online",
        "service": "Voice SDR WhatsApp (Evolution API)",
        "whatsapp_connected": is_connected,
        "uptime_hours": round(uptime_hours, 2),
        "metrics": metrics,
        "endpoints": {
            "qrcode": "/qrcode",
            "status": "/status",
            "webhook": "/webhook/evolution",
            "health": "/health"
        }
    }


@app.get("/qrcode", response_class=HTMLResponse)
async def get_qrcode():
    """
    Exibe QR Code para conectar o WhatsApp.
    Gerencia a criação ou reconexão da instância de forma segura.
    """
    # Se já existe um processo de criação rodando, pede para aguardar
    if creation_lock.locked():
        return HTMLResponse(
            """
            <html>
                <head>
                    <title>Aguarde...</title>
                    <meta http-equiv="refresh" content="10">
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f2f5; }
                        .container { background: white; padding: 40px; border-radius: 12px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                        h1 { color: #667eea; }
                        .loader { border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; width: 40px; height: 40px; animation: spin 1.5s linear infinite; margin: 20px auto; }
                        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🔄 Processando Solicitação...</h1>
                        <div class="loader"></div>
                        <p>Estamos comunicando com a API do WhatsApp. A página atualizará em 10 segundos.</p>
                    </div>
                </body>
            </html>
            """,
            status_code=202
        )

    async with creation_lock:
        # 1. Verifica se já está conectado antes de qualquer coisa
        state = await evolution_service.get_connection_state()
        
        if state.get("state") == "open":
            return """
            <html>
                <head>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            text-align: center;
                            padding: 50px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                        }
                        .container {
                            background: white;
                            color: #333;
                            padding: 40px;
                            border-radius: 15px;
                            max-width: 500px;
                            margin: 0 auto;
                            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                        }
                        h1 { color: #25D366; margin-top: 0; }
                        .icon { font-size: 64px; margin: 20px 0; }
                        a {
                            display: inline-block;
                            margin-top: 20px;
                            padding: 12px 30px;
                            background: #667eea;
                            color: white;
                            text-decoration: none;
                            border-radius: 25px;
                            transition: all 0.3s;
                        }
                        a:hover { background: #764ba2; transform: translateY(-2px); }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="icon">✅</div>
                        <h1>WhatsApp Conectado!</h1>
                        <p style="font-size: 18px;">Seu bot está online e pronto para receber mensagens.</p>
                        <p style="color: #666; margin-top: 20px;">
                            📱 Envie um áudio para o número conectado e veja a mágica acontecer!
                        </p>
                        <a href="/">← Dashboard</a>
                        <a href="/status">📊 Ver Status</a>
                    </div>
                </body>
            </html>
            "
        
        # 2. Se não estiver conectado, solicita QR Code (Criar ou Conectar)
        # MODIFICAÇÃO: Não deletamos mais a instância. O método create_instance
        # agora lida internamente com "Instância já existe" fazendo apenas a conexão.
        logger.info("ℹ️ Solicitando QR Code (Criar ou Conectar)...")
        result = await evolution_service.create_instance()
    
    # 3. Processa o resultado para extrair o QR Code
    qr_code = None
    
    # Formato 1: {qrcode: {base64: "..."}}
    if isinstance(result.get("qrcode"), dict):
        qr_code = result["qrcode"].get("base64")
    
    # Formato 2: {base64: "..."}
    elif "base64" in result:
        qr_code = result["base64"]
    
    # Formato 3: {qrcode: "string_base64"}
    elif isinstance(result.get("qrcode"), str) and len(result.get("qrcode")) > 100:
        qr_code = result["qrcode"]

    # Formato 4: Pairing Code
    pairing_code = result.get("pairingCode") or result.get("code")
    
    # Cenario A: Temos QR Code
    if qr_code:
        connection_state["qr_code"] = qr_code
        
        return f"""
        <html>
            <head>
                <meta http-equiv="refresh" content="5">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        text-align: center;
                        padding: 20px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                    }}
                    .container {{
                        background: white;
                        padding: 30px;
                        border-radius: 15px;
                        max-width: 600px;
                        margin: 20px auto;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    }}
                    h1 {{ color: #25D366; margin-top: 0; }}
                    .qr-code {{
                        margin: 20px 0;
                        padding: 20px;
                        background: white;
                        border-radius: 10px;
                    }}
                    .qr-code img {{
                        max-width: 300px;
                        border: 3px solid #25D366;
                        border-radius: 10px;
                    }}
                    .instructions {{
                        text-align: left;
                        margin: 20px 0;
                        background: #f5f5f5;
                        padding: 20px;
                        border-radius: 10px;
                    }}
                    .instructions ol {{ margin-left: 20px; }}
                    .instructions li {{ margin: 12px 0; font-size: 16px; }}
                    .status {{
                        background: #fff3cd;
                        color: #856404;
                        padding: 15px;
                        border-radius: 8px;
                        margin: 15px 0;
                        border: 1px solid #ffc107;
                    }}
                    .loader {{
                        border: 4px solid #f3f3f3;
                        border-top: 4px solid #25D366;
                        border-radius: 50%;
                        width: 40px;
                        height: 40px;
                        animation: spin 1s linear infinite;
                        margin: 10px auto;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>📱 Conectar WhatsApp</h1>
                    <p style="color: #666;">Esta página atualiza automaticamente a cada 5 segundos</p>
                    
                    <div class="qr-code">
                        <img src="{qr_code}" alt="QR Code">
                    </div>
                    
                    <div class="instructions">
                        <h3 style="margin-top: 0;">📋 Como conectar:</h3>
                        <ol>
                            <li>Abra o <strong>WhatsApp</strong> no celular</li>
                            <li>Toque em <strong>Mais opções</strong> (⋮) ou <strong>Configurações</strong></li>
                            <li>Toque em <strong>Aparelhos conectados</strong></li>
                            <li>Toque em <strong>Conectar um aparelho</strong></li>
                            <li>Aponte a câmera para este QR Code ☝️</li>
                        </ol>
                    </div>
                    
                    <div class="status">
                        <div class="loader"></div>
                        <p style="margin: 10px 0 0 0;">
                            <strong>Aguardando conexão...</strong>
                        </p>
                    </div>
                </div>
            </body>
        </html>
        "