"""
Servidor FastAPI - Voice SDR com Evolution API
Versão 2.7.0 - Correção de JID e Proteção Anti-Flood
"""
import asyncio
import time
import json
from typing import Dict, Any

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings
from app.services.evolution import evolution_service
from app.services.brain import brain_service
from app.services.voice import voice_service
from app.services.notification import get_notification_service
from app.utils.files import safe_remove, cleanup_temp_files
from app.utils.logger import setup_logger

# Configura Logger
logger = setup_logger(__name__)
notification_service = get_notification_service()

# --- Middleware de Logs ---
class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Ignora logs da rota de saúde para não poluir
        if "/health" in request.url.path:
            return await call_next(request)

        # 1. Log da Entrada
        body = await request.body()
        logger.info(f"➡️ [REQ] {request.method} {request.url.path}")
        
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive

        # 2. Processamento
        response = await call_next(request)

        # 3. Log da Saída
        logger.info(f"⬅️ [RES] Status: {response.status_code}")
        return response

# Inicialização do FastAPI
app = FastAPI(
    title="Voice SDR WhatsApp",
    description="Atendente comercial autônomo via Voz",
    version="2.7.0"
)
app.add_middleware(LogMiddleware)

# Métricas em Memória
metrics = {
    "total_messages": 0,
    "audio_messages": 0,
    "text_messages": 0,
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
creation_lock = asyncio.Lock()


@app.on_event("startup")
async def startup_event():
    """Inicialização e Limpeza"""
    logger.info("=" * 70)
    logger.info("🚀 Voice SDR WhatsApp Iniciando (v2.7.0)...")
    logger.info("=" * 70)
    
    cleanup_temp_files(max_age_hours=1)
    
    # Delay para serviços externos
    await asyncio.sleep(2)
    
    try:
        # Tenta verificar estado inicial sem travar o boot
        state = await evolution_service.get_connection_state()
        if state.get("state") == "open":
            connection_state["connected"] = True
            logger.info("✅ WhatsApp detectado como CONECTADO.")
    except Exception:
        logger.warning("⚠️ Evolution API ainda não disponível no startup.")


@app.on_event("shutdown")
async def shutdown_event():
    """Executa ao encerrar o servidor"""
    logger.info("🛑 Encerrando Voice SDR WhatsApp")


@app.get("/", response_class=JSONResponse)
async def root():
    """Dashboard JSON"""
    uptime = int(time.time() - metrics["start_time"])
    return {
        "service": "Voice SDR Bot",
        "status": "online",
        "connected": connection_state["connected"],
        "uptime_seconds": uptime,
        "metrics": metrics,
        "actions": {
            "connect": "/qrcode",
            "reset_session": "/reset"
        }
    }

@app.get("/health")
async def health_check():
    """Health check para o Docker"""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/reset", response_class=HTMLResponse)
async def reset_session():
    """
    Força a exclusão da instância para limpar sessões bugadas.
    """
    logger.warning("🔥 RESET SOLICITADO: Deletando instância...")
    success = await evolution_service.delete_instance()
    
    if success:
        connection_state["connected"] = False
        return """
        <html>
            <body style='text-align:center; padding:50px; background:#ffebee; font-family:sans-serif;'>
                <h1 style='color:#c62828;'>🗑️ Sessão Deletada com Sucesso</h1>
                <p>A instância antiga foi removida.</p>
                <br>
                <a href='/qrcode' style='background:#2196F3; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-size:20px;'>
                    🔄 Gerar Novo QR Code
                </a>
            </body>
        </html>
        """
    else:
        return "<h1>❌ Falha ao deletar. Verifique os logs do Docker.</h1>"


@app.get("/qrcode", response_class=HTMLResponse)
async def get_qrcode_page():
    """Interface Visual para conexão."""
    if creation_lock.locked():
        return HTMLResponse("<h1>⏳ Aguarde...</h1>", status_code=429)

    async with creation_lock:
        try:
            state = await evolution_service.get_connection_state()
            if state.get("state") == "open":
                connection_state["connected"] = True
                return "<html><body style='text-align:center; padding:50px; background:#e0f7fa;'><h1>✅ Conectado!</h1><p>Bot Operacional.</p></body></html>"

            # Tenta criar (Se der erro 403, o service agora trata e reconecta)
            response = await evolution_service.create_instance()
            
            qr_data = None
            if isinstance(response, dict):
                if "qrcode" in response and isinstance(response["qrcode"], dict):
                    qr_data = response["qrcode"].get("base64")
                elif "base64" in response:
                    qr_data = response["base64"]
                elif "qrcode" in response and "base64" in response["qrcode"]:
                    qr_data = response["qrcode"]["base64"]
            
            if qr_data:
                return f"""
                <html>
                    <head><meta http-equiv="refresh" content="15"></head>
                    <body style="text-align:center; padding:20px; font-family:sans-serif;">
                        <h1>📱 Escaneie o QR Code</h1>
                        <img src="{qr_data}" style="border: 5px solid #333; width:300px; border-radius:10px;" />
                        <p>Atualizando em 15s...</p>
                        <br><br>
                        <hr>
                        <p style="color:red; font-size:12px;">Deu erro ao escanear? <a href="/reset">Clique aqui para Resetar</a></p>
                    </body>
                </html>
                """
            
            return f"""
            <html>
                <head><meta http-equiv="refresh" content="5"></head>
                <body style='text-align:center; padding:50px;'>
                    <h1>⏳ Carregando...</h1>
                    <p>Status: {response}</p>
                    <p>Tentando buscar QR Code...</p>
                </body>
            </html>
            """
        except Exception as e:
            return f"<h1>❌ Erro: {str(e)}</h1><p><a href='/reset'>Tentar Resetar Instância</a></p>"


@app.post("/webhook/evolution")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """Webhook Central."""
    try:
        body = await request.json()
        event_type = body.get("event")
        data = body.get("data", {})
        
        # 1. Atualização de Status
        if event_type == "connection.update":
            state = data.get("state")
            connection_state["connected"] = (state == "open")
            logger.info(f"📡 Status conexão: {state}")
            return {"ack": True}

        # 2. Filtro de Evento
        if event_type != "messages.upsert":
            return {"status": "ignored_event_type"}

        # 3. Filtro Anti-Histórico (CRÍTICO: 60s tolerancia)
        message_timestamp = data.get("messageTimestamp")
        if message_timestamp:
            msg_time = int(message_timestamp)
            current_time = int(time.time())
            # Reduzido para 60s para evitar loop de mensagens velhas
            if (current_time - msg_time) > 60:
                logger.info(f"⛔ Ignorado: Mensagem antiga ({current_time - msg_time}s atrás)")
                return {"status": "ignored_old_message"}

        key = data.get("key", {})
        sender = key.get("remoteJid", "")
        
        # 4. Filtros de Origem
        if key.get("fromMe"): return {"status": "ignored_from_me"}
        if "broadcast" in sender: return {"status": "ignored_broadcast"}

        # 5. Detecta Mensagem de Áudio ou Texto
        msg_type = data.get("messageType")
        is_audio = msg_type == "audioMessage"
        is_text = msg_type in ["conversation", "extendedTextMessage"]
        
        if msg_type == "ephemeralMessage":
            real_msg = data.get("message", {}).get("ephemeralMessage", {}).get("message", {})
            if "audioMessage" in real_msg:
                is_audio = True
                data["message"] = real_msg 
            elif "conversation" in real_msg or "extendedTextMessage" in real_msg:
                is_text = True
                data["message"] = real_msg

        # Incrementa contador de mensagens
        if is_audio:
            metrics["audio_messages"] += 1
        elif is_text:
            metrics["text_messages"] += 1
        else:
            return {"status": "ignored_not_supported"}

        # 6. Processamento
        metrics["total_messages"] += 1

        # CORREÇÃO: Usa o remoteJid completo para evitar Erro 400
        phone_jid = sender 
        msg_id = key.get("id")

        logger.info(f"{'🎤 Áudio' if is_audio else '💬 Texto'} VÁLIDO recebido de {phone_jid}. Iniciando pipeline...")

        background_tasks.add_task(
            pipeline_sales_response,
            message_data=data,
            phone_jid=phone_jid,
            message_id=msg_id,
            is_audio=is_audio
        )

        return {"status": "processing"}

    except Exception as e:
        logger.error(f"💥 Erro geral no webhook: {e}", exc_info=True)
        notification_service.notify_error(
            e,
            {"event": data.get("event"), "service": "webhook_handler"}
        )
        return {"status": "error_handled"}


async def pipeline_sales_response(message_data: Dict[str, Any], phone_jid: str, message_id: str, is_audio: bool = True):
    """Pipeline: Download -> IA -> Voz -> Envio (ou Texto -> IA -> Texto -> Envio)"""
    logger.info(f"🚀 [Pipeline] Iniciando para {phone_jid}...")
    input_path = None
    output_path = None
    
    try:
        # 1. Processamento de áudio ou texto
        if is_audio:
            # 1a. Download e transcrição de áudio
            input_path = await evolution_service.download_media(message_data)
            if not input_path:
                logger.error("❌ [Pipeline] Falha no download do áudio.")
                return

            logger.info(f"📥 [Pipeline] Áudio baixado em: {input_path}")

            # 2. Inteligência (Brain já transcreve e raciocina)
            response_text = await brain_service.process_audio_and_respond(
                input_path,
                remote_jid=phone_jid
            )
        else:
            # 1b. Processamento de mensagem de texto
            # Extrai o conteúdo da mensagem de texto
            message_content = message_data.get("message", {})
            text_content = message_content.get("conversation") or (
                message_content.get("extendedTextMessage", {}).get("text") if "extendedTextMessage" in message_content else None
            )
            
            if not text_content:
                logger.error("❌ [Pipeline] Conteúdo da mensagem de texto inválido.")
                return

            logger.info(f"📝 [Pipeline] Texto recebido: {text_content}")

            # 2. Inteligência (Processa o texto diretamente)
            response_text = await brain_service.process_text_and_respond(
                text_content,
                remote_jid=phone_jid
            )

        # Fallback de segurança se a IA falhar (ex: Rate Limit)
        if not response_text: 
            response_text = "Desculpe, tive um problema técnico momentâneo. Poderia repetir?"
            logger.warning("⚠️ [Pipeline] IA retornou vazio, usando resposta de fallback.")

        logger.info(f"🤖 [Pipeline] IA: {response_text[:50]}...")

        # 3. Decidir tipo de resposta baseado na configuração
        if settings.response_type == "audio":
            # Gera áudio
            output_path = await voice_service.generate_audio(response_text)

            # 4. Envio
            if output_path:
                logger.info("🎙️ [Pipeline] Enviando áudio de resposta...")
                await evolution_service.send_audio(phone_jid, str(output_path), quoted_id=message_id)
                metrics["successful_responses"] += 1
                logger.info("✅ [Pipeline] Sucesso!")
            else:
                # Fallback final (Texto)
                await evolution_service.send_text(phone_jid, response_text)
                logger.warning("⚠️ [Pipeline] Falha no áudio, enviado texto.")
        else:
            # Envia resposta como texto
            logger.info("💬 [Pipeline] Enviando texto de resposta...")
            await evolution_service.send_text(phone_jid, response_text)
            metrics["successful_responses"] += 1
            logger.info("✅ [Pipeline] Sucesso!")

    except Exception as e:
        logger.error(f"💥 [Pipeline] Erro crítico: {e}", exc_info=True)
        notification_service.notify_error(
            e,
            {"phone_jid": phone_jid, "message_id": message_id, "pipeline_stage": "processing"}
        )
        metrics["errors"] += 1
    finally:
        safe_remove(input_path)
        safe_remove(output_path)