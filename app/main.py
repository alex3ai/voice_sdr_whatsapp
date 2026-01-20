"""
Orquestrador Principal (FastAPI).
Integra Webhook, IA, Voz e WhatsApp com monitoramento e processamento em background.
"""
import time
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from app.config import settings
from app.models.webhook import WebhookPayload
from app.services.whatsapp import whatsapp_service
from app.services.brain import brain_service
from app.services.voice import voice_service
from app.utils.files import safe_remove, cleanup_temp_files
from app.utils.security import validate_webhook_signature
from app.utils.logger import logger

# Inicialização da App
app = FastAPI(
    title="Voice SDR WhatsApp",
    description="Agente de Vendas via Voz (WhatsApp -> Gemini -> EdgeTTS)",
    version="1.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url=None
)

# Métricas em Memória (Básico para Health Check)
# Em produção real, exportaríamos para Prometheus
metrics = {
    "start_time": time.time(),
    "total_received": 0,
    "audio_processed": 0,
    "responses_sent": 0,
    "errors": 0
}

@app.on_event("startup")
async def startup_event():
    """Boot do sistema: Logs e Limpeza inicial."""
    logger.info(">>> Voice SDR Iniciando 🚀")
    logger.info(f"Ambiente: {settings.environment}")
    logger.info(f"Modelo IA: {settings.gemini_model_primary}")
    
    # Limpa lixo de execuções anteriores
    cleanup_temp_files(max_age_hours=1)

@app.on_event("shutdown")
async def shutdown_event():
    """Graceful Shutdown."""
    uptime = (time.time() - metrics["start_time"]) / 60
    logger.info(f"🛑 Encerrando. Uptime: {uptime:.1f} min")
    logger.info(f"📊 Resumo: {metrics}")

@app.get("/", tags=["Health"])
async def root():
    """Health Check simples para Load Balancers."""
    return {
        "status": "online",
        "service": "Voice SDR",
        "uptime_seconds": int(time.time() - metrics["start_time"]),
        "metrics": metrics
    }

@app.get("/webhook", tags=["Webhook"])
async def verify_webhook(request: Request):
    """
    Challenge de verificação da Meta.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.verify_token:
        logger.info("✅ Webhook verificado com sucesso.")
        return PlainTextResponse(content=challenge)
    
    logger.warning("❌ Falha na verificação do webhook (Token inválido).")
    raise HTTPException(status_code=403, detail="Forbidden")

@app.post("/webhook", tags=["Webhook"])
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe eventos do WhatsApp.
    Valida assinatura e processa áudio em background.
    """
    # 1. Validação de Segurança (HMAC)
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    if not validate_webhook_signature(body_bytes, signature):
        # Retorna 403 para a Meta saber que rejeitamos, ou 200 para enganar atacante (opção de segurança)
        # Aqui vamos de 403 explícito
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    metrics["total_received"] += 1

    # 2. Parse do Payload
    try:
        json_data = await request.json()
        payload = WebhookPayload(**json_data)
    except ValidationError:
        logger.warning("Payload malformado recebido.")
        return {"status": "ignored"} # 200 OK para a Meta não retentar
    except Exception as e:
        logger.error(f"Erro no parse: {e}")
        return {"status": "error"}

    # 3. Filtragem de Áudio
    audio_info = payload.get_first_audio_message()
    
    if audio_info:
        audio_id, sender_phone = audio_info
        logger.info(f"🎤 Áudio detectado de {sender_phone} (ID: {audio_id})")
        
        # Agenda processamento em background (Non-blocking)
        background_tasks.add_task(
            pipeline_audio, 
            audio_id=audio_id, 
            sender_phone=sender_phone
        )
        metrics["audio_processed"] += 1
    else:
        logger.debug("Evento ignorado (não é áudio).")

    return {"status": "processed"}

async def pipeline_audio(audio_id: str, sender_phone: str):
    """
    Pipeline de Negócio:
    Download -> Brain (IA) -> Voice (TTS) -> WhatsApp Send
    """
    input_audio_path = None
    output_audio_path = None
    
    try:
        # A. Download
        input_audio_path = await whatsapp_service.download_media(audio_id)
        if not input_audio_path:
            return # Erro já logado no serviço

        # B. Inteligência (Agora com AWAIT correto!)
        response_text = await brain_service.process_audio_and_respond(input_audio_path)
        
        if not response_text:
            logger.warning("Brain não gerou resposta. Abortando.")
            return

        # C. Voz
        output_audio_path = await voice_service.generate_audio(response_text)
        if not output_audio_path:
            return

        # D. Envio
        sent = await whatsapp_service.send_voice_note(sender_phone, output_audio_path)
        if sent:
            metrics["responses_sent"] += 1
        else:
            metrics["errors"] += 1

    except Exception as e:
        logger.error(f"💥 Erro não tratado no pipeline: {e}", exc_info=True)
        metrics["errors"] += 1
    
    finally:
        # Limpeza robusta
        safe_remove(input_audio_path)
        safe_remove(output_audio_path)

@app.post("/admin/cleanup", tags=["Admin"])
async def trigger_cleanup(background_tasks: BackgroundTasks):
    """Limpeza manual via API."""
    background_tasks.add_task(cleanup_temp_files, max_age_hours=0)
    return {"status": "cleanup_started"}