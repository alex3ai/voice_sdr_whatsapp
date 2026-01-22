"""
Servidor FastAPI - Voice SDR com Evolution API
"""
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

logger = setup_logger(__name__)

# Inicialização do FastAPI
app = FastAPI(
    title="Voice SDR WhatsApp (Evolution API)",
    description="Atendente de vendas com IA que responde áudios no WhatsApp",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
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
    "last_check": None
}


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
    import asyncio
    await asyncio.sleep(5)
    
    # Verifica se a instância já existe
    state = await evolution_service.get_connection_state()
    
    if state.get("state") == "open":
        logger.info("✅ WhatsApp já conectado!")
        connection_state["connected"] = True
    else:
        logger.info("⏳ WhatsApp não conectado. Acesse /qrcode para conectar.")


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
    
    state = await evolution_service.get_connection_state()
    is_connected = state.get("state") == "open"
    
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
        """
    
    # Se não estiver conectado, busca/cria a instância
    result = await evolution_service.create_instance()
    
    # Extrai o QR Code de diferentes formatos possíveis
    qr_code = None
    
    # Formato 1: {qrcode: {base64: "..."}}
    if isinstance(result.get("qrcode"), dict):
        qr_code = result["qrcode"].get("base64")
    
    # Formato 2: {base64: "..."}
    elif "base64" in result:
        qr_code = result["base64"]
    
    # Formato 3: {pairingCode: "..."}  (algumas versões usam pairing code)
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
                        <img src="data:image/png;base64,{qr_code}" alt="QR Code">
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
        """
    
    # Se tiver pairing code (método alternativo)
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
        """
    
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
        """
    
    # Erro: QR Code não disponível
    else:
        error_msg = result.get("message", "QR Code não disponível")
        error_details = result.get("error", "")
        
        return f"""
        <html>
            <head>
                <meta http-equiv="refresh" content="3">
            </head>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <div style="background: white; padding: 30px; border-radius: 10px; max-width: 500px; margin: 0 auto;">
                    <h1 style="color: #ff6b6b;">⚠️ QR Code Indisponível</h1>
                    <p>{error_msg}</p>
                    {f'<pre style="text-align: left; background: #f5f5f5; padding: 15px; border-radius: 5px; overflow: auto;">{error_details}</pre>' if error_details else ''}
                    <p style="color: #666; margin-top: 20px;">
                        Recarregando automaticamente em 3 segundos...
                    </p>
                    <p style="margin-top: 30px;">
                        <a href="/qrcode" style="padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">🔄 Tentar Novamente</a>
                    </p>
                </div>
            </body>
        </html>
        """


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
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe eventos da Evolution API
    
    Tipos de eventos:
    - messages.upsert: Nova mensagem recebida
    - qrcode.updated: QR Code atualizado
    - connection.update: Status da conexão mudou
    """
    data = await request.json()
    
    event_type = data.get("event")
    
    logger.debug(f"📨 Webhook recebido: {event_type}")
    
    # QR Code atualizado
    if event_type == "qrcode.updated":
        qr_data = data.get("data", {})
        connection_state["qr_code"] = qr_data.get("qrcode")
        logger.info("🔄 QR Code atualizado")
        return {"status": "qr_updated"}
    
    # Conexão estabelecida
    if event_type == "connection.update":
        state = data.get("data", {}).get("state")
        if state == "open":
            connection_state["connected"] = True
            logger.info("✅ WhatsApp conectado!")
        else:
            connection_state["connected"] = False
            logger.warning(f"⚠️ WhatsApp desconectado: {state}")
        return {"status": "connection_updated"}
    
    # Nova mensagem
    if event_type == "messages.upsert":
        message_data = data.get("data", {})
        
        # Verifica se é uma mensagem recebida (não enviada por nós)
        if message_data.get("key", {}).get("fromMe"):
            return {"status": "own_message_ignored"}
        
        # Pega informações da mensagem
        remote_jid = message_data.get("key", {}).get("remoteJid", "")
        message_type = message_data.get("messageType")
        
        # Extrai número do telefone
        phone_number = remote_jid.replace("@s.whatsapp.net", "")
        
        metrics["total_messages"] += 1
        
        # Processa apenas áudios
        if message_type == "audioMessage":
            metrics["audio_messages"] += 1
            
            message_id = message_data.get("key", {}).get("id")
            
            logger.info(f"🎤 Áudio recebido de {phone_number[-4:]}...")
            
            # Processa em background
            background_tasks.add_task(
                process_audio_pipeline,
                message_data=message_data,
                phone_number=phone_number,
                message_id=message_id
            )
        else:
            logger.debug(f"ℹ️ Mensagem tipo {message_type} ignorada")
    
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
        response_text = brain_service.process_audio_and_respond(input_audio)
        
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
    state = await evolution_service.get_connection_state()
    
    return {
        "status": "healthy",
        "whatsapp_connected": state.get("state") == "open",
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