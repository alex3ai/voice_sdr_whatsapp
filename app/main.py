"""
Orquestrador Principal (FastAPI).
Integração via Evolution API v2.
"""
import time
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings
from app.services.evolution import evolution_service
from app.services.brain import brain_service
from app.services.voice import voice_service
from app.utils.files import safe_remove, cleanup_temp_files
from app.utils.logger import logger

# Inicialização da App
app = FastAPI(
    title="Voice SDR WhatsApp (Evolution API)",
    description="Agente de Vendas via Voz (Evolution API -> Gemini -> EdgeTTS)",
    version="2.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None
)

# Estado Global em Memória (Para UI do QR Code)
# Em produção com múltiplos workers, isso deveria ser Redis.
state_store = {
    "start_time": time.time(),
    "connected": False,
    "qr_code_base64": None,
    "metrics": {
        "total_received": 0,
        "audio_processed": 0,
        "errors": 0
    }
}

@app.on_event("startup")
async def startup_event():
    """Boot: Verifica conexão com Evolution."""
    logger.info(">>> Voice SDR (Evolution Edition) Iniciando 🚀")
    
    # Limpeza inicial
    cleanup_temp_files(max_age_hours=1)
    
    # Delay para garantir que o container da Evolution subiu
    await asyncio.sleep(5)
    
    # Checa estado atual
    conn = await evolution_service.get_connection_state()
    if conn.get("state") == "open":
        state_store["connected"] = True
        logger.info("✅ WhatsApp já está conectado!")
    else:
        logger.warning("⚠️ WhatsApp desconectado. Acesse /qrcode para conectar.")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Dashboard simples para status."""
    status_color = "#25D366" if state_store["connected"] else "#FF0000"
    status_text = "CONECTADO" if state_store["connected"] else "DESCONECTADO"
    
    return f"""
    <html>
        <body style="font-family: Arial; text-align: center; padding: 50px; background-color: #f4f4f9;">
            <div style="background: white; padding: 40px; border-radius: 10px; max-width: 600px; margin: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h1>🤖 Voice SDR Bot</h1>
                <p>Status: <b style="color: {status_color}">{status_text}</b></p>
                <p>Instância: <code>{settings.evolution_instance_name}</code></p>
                <hr>
                <h3>Métricas da Sessão</h3>
                <p>Mensagens Recebidas: {state_store['metrics']['total_received']}</p>
                <p>Áudios Processados: {state_store['metrics']['audio_processed']}</p>
                <br>
                <a href="/qrcode" style="background: #25D366; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    🔗 Conectar / Ver QR Code
                </a>
            </div>
        </body>
    </html>
    """

@app.get("/qrcode", response_class=HTMLResponse)
async def show_qrcode():
    """Gera/Exibe QR Code."""
    # Se já conectado
    if state_store["connected"]:
        return "<h1>✅ Já conectado!</h1><a href='/'>Voltar</a>"

    # Tenta criar/conectar para forçar geração do QR
    resp = await evolution_service.create_instance()
    
    # Atualiza store se vier QR novo
    if resp.get("qrcode", {}).get("base64"):
        state_store["qr_code_base64"] = resp["qrcode"]["base64"]

    qr_img = ""
    if state_store["qr_code_base64"]:
        qr_img = f'<img src="{state_store["qr_code_base64"]}" width="300" />'
    else:
        qr_img = "<p>⏳ Aguardando QR Code da API...</p>"

    return f"""
    <html>
        <head><meta http-equiv="refresh" content="5"></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Escaneie com seu WhatsApp</h1>
            {qr_img}
            <p>Atualizando a cada 5 segundos...</p>
            <p><small>Abra WhatsApp > Configurações > Aparelhos Conectados > Conectar</small></p>
            <a href="/">Voltar</a>
        </body>
    </html>
    """

@app.post("/webhook/evolution")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe eventos da Evolution API v2.
    """
    try:
        body = await request.json()
        event = body.get("event")
        data = body.get("data", {})
        
        # 1. Atualização de QR Code
        if event == "qrcode.updated":
            state_store["qr_code_base64"] = data.get("qrcode")
            state_store["connected"] = False
            return {"ack": True}

        # 2. Status de Conexão
        if event == "connection.update":
            state = data.get("state")
            state_store["connected"] = (state == "open")
            if state == "open":
                state_store["qr_code_base64"] = None
                logger.info("✅ Conexão estabelecida via Webhook!")
            return {"ack": True}

        # 3. Mensagens (Upsert)
        if event == "messages.upsert":
            # Ignora mensagens enviadas pelo próprio bot
            if data.get("key", {}).get("fromMe"):
                return {"ack": True}
            
            message_type = data.get("messageType")
            state_store["metrics"]["total_received"] += 1

            # Filtragem: Apenas Áudio
            if message_type == "audioMessage":
                state_store["metrics"]["audio_processed"] += 1
                
                remote_jid = data.get("key", {}).get("remoteJid", "")
                phone = remote_jid.split("@")[0]
                msg_id = data.get("key", {}).get("id")
                
                logger.info(f"🎤 Áudio recebido de {phone}")
                
                # Processamento em Background
                background_tasks.add_task(
                    pipeline_audio,
                    message_data=data, # Passa o objeto data inteiro (necessário p/ download)
                    phone=phone,
                    msg_id=msg_id
                )

        return {"ack": True}
        
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        return {"error": str(e)}

async def pipeline_audio(message_data: Dict, phone: str, msg_id: str):
    """
    Pipeline Lógica: Download -> Brain (IA) -> Voice (TTS) -> WhatsApp Send
    """
    input_file = None
    output_file = None
    
    try:
        # A. Download (Evolution V2)
        input_file = await evolution_service.download_media(message_data)
        if not input_file:
            logger.error("Abortando: Download falhou.")
            return

        # B. Inteligência (Async Gemini)
        # CORREÇÃO CRÍTICA: Adicionado 'await' aqui!
        response_text = await brain_service.process_audio_and_respond(input_file)
        
        if not response_text:
            logger.warning("Abortando: IA não gerou resposta.")
            return

        # C. Síntese de Voz
        output_file = await voice_service.generate_audio(response_text)
        if not output_file:
            # Fallback: Envia texto se o áudio falhar
            await evolution_service.send_text(phone, response_text)
            return

        # D. Envio
        await evolution_service.send_audio(phone, output_file)

    except Exception as e:
        logger.error(f"💥 Erro no pipeline: {e}", exc_info=True)
        state_store["metrics"]["errors"] += 1
    
    finally:
        safe_remove(input_file)
        safe_remove(output_file)

@app.get("/health")
async def health():
    return {"status": "ok", "connected": state_store["connected"]}