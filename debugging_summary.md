# Resumo da Tentativa de Debug - Voice SDR WhatsApp

Este documento resume todas as etapas, logs e comandos utilizados na tentativa de resolver os problemas com a aplicação `voice_sdr_whatsapp`.

## Problema Inicial

A aplicação apresentava dois erros principais:
1.  Um `Internal Server Error (500)` ao receber um webhook de teste na sua própria API (`http://localhost:8000/webhook/evolution`).
2.  Um `Not Found (404)` ao tentar configurar a URL do webhook na Evolution API (`http://localhost:8080`).

---

## 1. Análise do "Internal Server Error" (500)

Este problema foi identificado como a **prioridade 1** e foi **resolvido**.

### Investigação e Solução

1.  **Análise do Código:** A análise do arquivo `voice_sdr_whatsapp/app/main.py` revelou que o endpoint do webhook (`/webhook/evolution`) recebia a requisição como um objeto `Request` genérico e lia o JSON manualmente (`data = await request.json()`).
2.  **Hipótese:** A ausência da validação automática do Pydantic do FastAPI estava causando uma exceção não tratada.
3.  **Aplicação da Correção:** O endpoint em `app/main.py` foi modificado para receber o payload diretamente como um modelo Pydantic (`payload: EvolutionWebhook`), ativando a validação automática do FastAPI.

### Status
✅ **Resolvido.** A aplicação agora está mais robusta e irá retornar um erro `422 Unprocessable Entity` com detalhes caso o formato do webhook esteja incorreto.

---

## 2. Análise do "Not Found" (404) na API da Evolution

Este problema foi **resolvido**. O objetivo era configurar o webhook da instância `voice_sdr_v4`.

### Investigação e Solução

Após múltiplas tentativas de configurar o webhook via endpoints da API (`/instance/setWebhook`, `/webhook/instance`, `/webhook/set`), todas resultando em erro `404 Not Found`, a investigação mudou de foco.

1.  **Análise do `docker-compose.yml`:** Uma análise mais detalhada do arquivo `docker-compose.yml` revelou a verdadeira forma de configurar o webhook para a versão da API em uso (`atendai/evolution-api:latest`).
2.  **Hipótese:** A configuração do webhook não é feita via API, mas sim através de **variáveis de ambiente** no `docker-compose.yml`.
3.  **Aplicação da Correção:**
    *   O `docker-compose.yml` foi modificado para incluir as seguintes variáveis de ambiente no serviço `evolution-api`:
        ```yaml
        # Webhook Configuration
        - WEBHOOK_GLOBAL_ENABLED=true
        - WEBHOOK_GLOBAL_URL=http://voice_sdr_bot:8000/webhook/evolution
        - WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=true
        - WEBHOOK_EVENTS=MESSAGES_UPSERT,CONNECTION_UPDATE,QRCODE_UPDATED
        ```
    *   O serviço `evolution-api` foi recriado com o comando `docker-compose up -d --force-recreate evolution-api` para aplicar as novas variáveis de ambiente.

### Status
✅ **Resolvido.** A configuração do webhook agora é feita de forma declarativa no `docker-compose.yml`, eliminando a necessidade de chamadas de API para este fim.

---

## 3. Análise do Loop de Conexão e Timeout

Após as correções anteriores, a aplicação entrou em um novo estado de erro, caracterizado por um loop de criação e falha da instância, resultando em timeouts.

### Investigação e Solução

1.  **Sintoma 1: Loop de Criação de Instância (403 Forbidden)**
    *   **Análise:** Os logs mostraram que a aplicação tentava criar uma instância, falhava com um erro `403 - Forbidden` (nome já em uso), deletava a instância e tentava recriar imediatamente.
    *   **Hipótese:** O tempo de espera de 2 segundos após a deleção era insuficiente para a API da Evolution processar a remoção completamente, causando uma condição de corrida (*race condition*).
    *   **Solução:** A lógica em `app/services/evolution.py` foi substituída por um mecanismo de retentativa mais robusto. Agora, a aplicação tenta recriar a instância até 3 vezes, com um tempo de espera crescente (5s, 10s, 15s), dando tempo suficiente para a API concluir a operação de exclusão.

2.  **Sintoma 2: Timeout na Conexão (408 Request Time-out)**
    *   **Análise:** Mesmo com a correção da condição de corrida, os logs da Evolution API mostraram um erro `Timed Out` vindo da biblioteca Baileys (`error in validating connection`). Isso indicava que a conexão com os servidores do WhatsApp estava falhando. Ao mesmo tempo, os logs da nossa aplicação mostravam múltiplas chamadas para `create instance`, sugerindo que o usuário estava recarregando a página `/qrcode` repetidamente.
    *   **Hipótese:** O problema tinha duas frentes: (A) um problema de conexão subjacente no ambiente Docker da Evolution API e (B) a ausência de um mecanismo para prevenir múltiplas solicitações de criação simultâneas na nossa aplicação.
    *   **Solução:**
        *   **Aumento do Timeout:** Para mitigar a lentidão da rede, o timeout para as chamadas de criação de instância em `app/services/evolution.py` foi aumentado para **120 segundos**. Isso dá mais tempo para a Baileys tentar estabelecer a conexão.
        *   **Bloqueio de Concorrência (*Concurrency Lock*):** Foi implementado um `asyncio.Lock` no endpoint `/qrcode` em `app/main.py`. Isso impede que novas solicitações de criação de instância sejam processadas enquanto uma já estiver em andamento, estabilizando o sistema e fornecendo um feedback claro ao usuário para que aguarde.

### Status
✅ **Resolvido.** A aplicação está agora mais resiliente a condições de rede lentas e protegida contra condições de corrida e solicitações simultâneas, tornando o processo de conexão muito mais estável.

---

## Estado Final dos Arquivos

Abaixo está o conteúdo dos principais arquivos do projeto no estado atual.

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  # ========================================
  # 1. Banco de Dados (CORRIGIDO PARA WINDOWS)
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
      - ./evolution_data/postgres:/var/lib/postgresql/data
    networks:
      - voice_sdr_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U evolution -d evolution"]
      interval: 15s        # Verifica a cada 15s
      timeout: 10s         # Espera 10s pela resposta
      retries: 10          # Tenta 10 vezes (Total ~150s + start_period)
      start_period: 60s    # DÁ 1 MINUTO DE FOLGA ANTES DE COMEÇAR A CHECAR

  # ========================================
  # 2. Redis (Cache de Sessão)
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
  # 3. Evolution API v2.2.2 (Configurada via Docs)
  # ========================================
  evolution-api:
    image: atendai/evolution-api:latest
    container_name: evolution_whatsapp
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    
    # ⚠️ CRÍTICO PARA WINDOWS: Memória compartilhada para o Chrome não crashar
    shm_size: '2gb' 
    
    ports:
            - "8080:8080"
          
          healthcheck:
            test: ["CMD", "curl", "-f", "http://localhost:8080/instance"]
            interval: 30s
            timeout: 10s
            retries: 5
            start_period: 60s
      
          environment:      # --- Servidor ---
      - SERVER_URL=http://localhost:8080
      - DOCKER_ENV=true
      - AUTHENTICATION_API_KEY=123456
      
      # --- Logs (Aumentados para DEBUG conforme sua doc) ---
      - LOG_LEVEL=DEBUG
      - LOG_BAILEYS=warn
      
      # --- Banco de Dados (Postgres) ---
      - DATABASE_ENABLED=true
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=postgresql://evolution:evolution@postgres:5432/evolution
      - DATABASE_SAVE_DATA_INSTANCE=true
      - DATABASE_SAVE_DATA_NEW_MESSAGE=true
      
      # --- Redis ---
      - CACHE_REDIS_ENABLED=true
      - CACHE_REDIS_URI=redis://:123456@redis:6379/0
      
      # Webhook Configuration
      - WEBHOOK_GLOBAL_ENABLED=true
      - WEBHOOK_GLOBAL_URL=http://voice_sdr_bot:8000/webhook/evolution
      - WEBHOOK_EVENTS=MESSAGES_UPSERT,CONNECTION_UPDATE,QRCODE_UPDATED
      
      # =====================================================
      # 🚨 A SOLUÇÃO DO PAREAMENTO (ENVs ESPECÍFICAS) 🚨
      # =====================================================
      
      # Força a habilitação da lógica de Pareamento por Código
      - CONFIG_SESSION_PHONE_PAIRING=true
      
      # Define o nome que aparece no celular
      - CONFIG_SESSION_PHONE_CLIENT=VoiceSDR
      - CONFIG_SESSION_PHONE_NAME=Chrome
      
      # Argumentos "Anti-Crash" para o Chrome no Windows
      - CHROME_ARGS=--no-sandbox --disable-dev-shm-usage
      
      # Impede que a instância morra se não conectar rápido
      - DEL_INSTANCE=false
      
    volumes:
      - ./evolution_data/instances:/evolution/instances
      - ./evolution_data/store:/evolution/store
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
      evolution-api:
        condition: service_healthy
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
    version="2.0.0",
    # FIX: Usa settings.environment em vez de settings.debug
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
    
    # Aguarda a Evolution API ficar pronta
    await asyncio.sleep(5)
    
    # Verifica se a instância já existe
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
    Exibe QR Code para conectar o WhatsApp
    Acesse este endpoint no navegador após iniciar o servidor
    """
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
                        <p>Uma conexão já está sendo estabelecida. Esta página será atualizada em 10 segundos.</p>
                    </div>
                </body>
            </html>
            """,
            status_code=202
        )

    async with creation_lock:
        # Primeiro, verifica se já está conectado
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
        
        # Se não estiver conectado, força a recriação da instância
        logger.info("ℹ️ Forçando a recriação da instância para obter um novo QR Code.")
        await evolution_service.delete_instance()
        await asyncio.sleep(2)  # Pausa para a API processar a exclusão
        result = await evolution_service.create_instance()
    
    # Extrai o QR Code de diferentes formatos possíveis
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
    
    # Se encontrou QR Code
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
                    .instructions ol {{
                        margin-left: 20px;
                    }}
                    .instructions li {{
                        margin: 12px 0;
                        font-size: 16px;
                    }}
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
    
    # Se tiver pairing code
    elif pairing_code:
        return f"""
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <div style="background: white; padding: 30px; border-radius: 10px; max-width: 500px; margin: 0 auto;">
                    <h1 style="color: #25D366;">🔢 Código de Pareamento</h1>
                    <p>Use este código no WhatsApp:</p>
                    <h2 style="font-size: 48px; letter-spacing: 10px; color: #667eea;">{pairing_code}</h2>
                    <p style="color: #666; margin-top: 30px;">
                        1. Abra WhatsApp > Aparelhos conectados<br>
                        2. Conectar aparelho > Conectar com número de telefone<br>
                        3. Digite o código acima
                    </p>
                </div>
            </body>
        </html>
        "
    
    # Se já está conectado (verificação dupla)
    elif result.get("status") == "connected":
        return """
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <div style="background: white; padding: 40px; border-radius: 10px; max-width: 500px; margin: 0 auto;">
                    <div style="font-size: 64px; margin: 20px 0;">✅</div>
                    <h1 style="color: #25D366;">WhatsApp Conectado!</h1>
                    <p>Envie um áudio para testar!</p>
                    <a href="/" style="display: inline-block; margin-top: 20px; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 25px;">← Dashboard</a>
                </div>
            </body>
        </html>
        "
    
    # Erro: QR Code não disponível ou Timeout
    else:
        # Caso específico de timeout
        if result.get("status") == "timeout":
            title = "⏳ Instância Iniciando Lentamente..."
            refresh_time = 10 # Mais tempo para instâncias lentas
        else:
            title = "⚠️ QR Code Indisponível"
            refresh_time = 5

        error_msg = result.get("message", "QR Code não disponível no momento.")
        error_details = result.get("error", "")
        
        return f"""
        <html>
            <head>
                <meta http-equiv="refresh" content="{refresh_time}">
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f2f5; }}
                    .container {{ background: white; padding: 40px; border-radius: 12px; max-width: 600px; margin: 0 auto; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
                    h1 {{ color: #ff9800; }}
                    .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #ff9800; border-radius: 50%; width: 40px; height: 40px; animation: spin 1.5s linear infinite; margin: 20px auto; }}
                    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>{title}</h1>
                    <div class="loader"></div>
                    <p style="font-size: 18px; color: #333;">{error_msg}</p>
                    {f'<pre style="text-align: left; background: #f5f5f5; padding: 15px; border-radius: 5px; overflow: auto; white-space: pre-wrap;">{error_details}</pre>' if error_details else ''}
                    <p style="color: #666; margin-top: 20px;">
                        A página será recarregada automaticamente em {refresh_time} segundos...
                    </p>
                    <p style="margin-top: 30px;">
                        <a href="/qrcode" style="padding: 12px 25px; background: #667eea; color: white; text-decoration: none; border-radius: 8px;">🔄 Tentar Novamente</a>
                    </p>
                </div>
            </body>
        </html>
        "


@app.get("/status")
async def check_status():
    """Verifica o status da conexão com o WhatsApp"""
    state = await evolution_service.get_connection_state()
    
    is_connected = state.get("state") == "open"
    connection_state["connected"] = is_connected
    connection_state["last_check"] = time.time()
    
    return {
        "connected": is_connected,
        "state": state.get("state"),
        "instance": settings.evolution_instance_name,
        "full_state": state
    }


@app.post("/webhook/evolution")
async def evolution_webhook(payload: EvolutionWebhook, background_tasks: BackgroundTasks):
    """
    Recebe eventos da Evolution API
    """
    logger.debug(f"📨 Webhook recebido: {payload.event}")
    
    # QR Code atualizado
    if payload.event == "qrcode.updated":
        # A API da Evolution pode não enviar 'data' neste evento
        # e o payload pode não ter essa estrutura.
        # Por segurança, melhor buscar o QR code via GET.
        # Mas por enquanto, vamos manter um log.
        logger.info("🔄 Evento de QR Code recebido (verificar payload).")
        return {"status": "qr_event_received"}
    
    # Conexão estabelecida
    if payload.event == "connection.update" and hasattr(payload, 'data'):
        state = payload.data.get("state")
        if state == "open":
            connection_state["connected"] = True
            logger.info("✅ WhatsApp conectado!")
        else:
            connection_state["connected"] = False
            logger.warning(f"⚠️ WhatsApp desconectado: {state}")
        return {"status": "connection_updated"}
    
    # Nova mensagem
    if payload.event == "messages.upsert":
        # Validação principal já feita pelo Pydantic
        if payload.is_from_me():
            return {"status": "own_message_ignored"}
        
        phone_number = payload.get_sender_number()
        message_type = payload.data.messageType
        
        metrics["total_messages"] += 1
        
        # Processa apenas áudios
        if message_type == "audioMessage":
            metrics["audio_messages"] += 1
            
            message_id = payload.data.key.id
            
            logger.info(f"🎤 Áudio recebido de {phone_number[-4:]}...")
            
            # Processa em background
            background_tasks.add_task(
                process_audio_pipeline,
                message_data=payload.data.dict(), # Passa como dicionário
                phone_number=phone_number,
                message_id=message_id
            )
        else:
            logger.info(f"ℹ️ Mensagem tipo {message_type} ignorada")
    
    return {"status": "received"}


async def process_audio_pipeline(message_data: Dict[str, Any], phone_number: str, message_id: str):
    """Pipeline completo de processamento de áudio"""
    input_audio = None
    output_audio = None
    
    start_time = time.time()
    
    try:
        logger.info(f"⚙️ Iniciando pipeline para {phone_number[-4:]}...")
        
        # 1. Download
        logger.info("📥 [1/4] Baixando áudio...")
        input_audio = await evolution_service.download_media(message_data)
        
        if not input_audio:
            logger.error("❌ Falha no download")
            metrics["errors"] += 1
            await evolution_service.send_text(
                phone_number,
                "Desculpe, não consegui processar seu áudio. Tente novamente!"
            )
            return
        
        # 2. IA
        logger.info("🧠 [2/4] Processando com Gemini...")
        response_text = await brain_service.process_audio_and_respond(input_audio)
        
        if not response_text:
            logger.error("❌ IA não respondeu")
            metrics["errors"] += 1
            return
        
        logger.info(f"💬 Resposta: '{response_text[:80]}...'")
        
        # 3. TTS
        logger.info("🎙️ [3/4] Gerando voz...")
        output_audio = await voice_service.generate_audio(response_text)
        
        if not output_audio:
            logger.error("❌ Falha no TTS, enviando texto")
            await evolution_service.send_text(phone_number, response_text)
            return
        
        # 4. Envio
        logger.info("📤 [4/4] Enviando resposta...")
        success = await evolution_service.send_audio(
            phone_number,
            output_audio,
            quoted_msg_id=message_id  # Responde à mensagem original
        )
        
        if success:
            elapsed = time.time() - start_time
            metrics["successful_responses"] += 1
            logger.info(f"✅ Pipeline concluído em {elapsed:.2f}s")
        else:
            metrics["errors"] += 1
    
    except Exception as e:
        logger.error(f"💥 Erro no pipeline: {e}", exc_info=True)
        metrics["errors"] += 1
    
    finally:
        safe_remove(input_audio)
        safe_remove(output_audio)


@app.get("/health")
async def health_check():
    """Health check para monitoramento"""
    # Tenta pegar estado com timeout curto para não travar healthcheck
    try:
        state = await evolution_service.get_connection_state()
        connected = state.get("state") == "open"
    except:
        connected = connection_state["connected"]

    return {
        "status": "healthy",
        "whatsapp_connected": connected,
        "uptime_seconds": int(time.time() - metrics["start_time"]),
        "metrics": metrics
    }


@app.post("/disconnect")
async def disconnect_whatsapp():
    """Desconecta do WhatsApp"""
    result = await evolution_service.delete_instance()
    
    if result:
        connection_state["connected"] = False
        return {"status": "disconnected"}
    
    return {"status": "error"}
```

### `app/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import Literal

class Settings(BaseSettings):
    """
    Configurações da aplicação adaptadas para Evolution API v2.
    """
    
    # Controle de Ambiente
    environment: Literal["development", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Evolution API
    evolution_api_url: str = Field(..., description="URL base da Evolution API")
    evolution_api_key: str = Field(..., description="Global API Key para autenticação")
    evolution_instance_name: str = Field(..., description="Nome da instância na Evolution")
    
    # Google Gemini
    gemini_api_key: str = Field(..., min_length=30)
    gemini_model_primary: str = Field(default="gemini-2.0-flash-exp")
    gemini_model_fallback: str = Field(default="gemini-1.5-flash")
    
    # Voice
    edge_tts_voice: str = Field(default="pt-BR-AntonioNeural")
    
    # Limites
    download_timeout: int = 30
    gemini_timeout: int = 30
    max_audio_size_mb: int = 16
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def evolution_headers(self) -> dict:
        return {
            "apikey": self.evolution_api_key,
            "Content-Type": "application/json"
        }
    
    # --- CORREÇÃO DE SEGURANÇA PARA WINDOWS ---
    @validator("*", pre=True)
    def strip_whitespace(cls, v):
        """Remove espaços invisíveis (\r, \n, spaces) de todas as strings"""
        if isinstance(v, str):
            return v.strip()
        return v

    @validator("evolution_api_url")
    def clean_url(cls, v):
        return v.rstrip("/")

settings = Settings()
```