"""
Servidor FastAPI - Voice SDR com Evolution API
Integrando Dashboard Visual + Lógica de Negócios Robusta
"""
import asyncio
import time
from typing import Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings
from app.services.evolution import evolution_service
from app.services.brain import brain_service
from app.services.voice import voice_service
from app.utils.files import safe_remove, cleanup_temp_files
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

# Inicialização do FastAPI
app = FastAPI(
    title="Voice SDR WhatsApp",
    description="Atendente comercial autônomo via Voz",
    version="2.2.0"
)

# Métricas em Memória
metrics = {
    "total_messages": 0,
    "audio_messages": 0,
    "successful_responses": 0,
    "errors": 0,
    "start_time": time.time()
}

# Estado da conexão (Cache local)
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
    logger.info("🚀 Voice SDR WhatsApp Iniciando...")
    logger.info("=" * 70)
    
    cleanup_temp_files(max_age_hours=1)
    
    # Pequeno delay para garantir que serviços externos subam
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
    uptime = time.time() - metrics["start_time"]
    logger.info("🛑 Encerrando Voice SDR WhatsApp")
    logger.info(f"📊 Métricas finais: {metrics}")


@app.get("/", response_class=JSONResponse)
async def root():
    """Dashboard JSON (Simples e Rápido)"""
    uptime = int(time.time() - metrics["start_time"])
    return {
        "service": "Voice SDR Bot",
        "status": "online",
        "connected": connection_state["connected"],
        "uptime_seconds": uptime,
        "metrics": metrics,
        "actions": {
            "connect": "/qrcode",
            "check_status": "/status"
        }
    }


@app.get("/qrcode", response_class=HTMLResponse)
async def get_qrcode_page():
    """
    Interface Visual para conexão.
    Gerencia a lógica de 'Instância já existe' vs 'Nova Instância' automaticamente.
    """
    if creation_lock.locked():
        return HTMLResponse("<h1>⏳ Aguarde, processando solicitação anterior...</h1>", status_code=429)

    async with creation_lock:
        # 1. Verifica status atual
        try:
            state = await evolution_service.get_connection_state()
            if state.get("state") == "open":
                connection_state["connected"] = True
                return """
                <html>
                    <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #e0f7fa;">
                        <h1 style="color: #00695c;">✅ WhatsApp Conectado!</h1>
                        <p>O robô já está operando.</p>
                        <a href="/">Voltar para Dashboard</a>
                    </body>
                </html>
                """

            # 2. Solicita criação/conexão
            response = await evolution_service.create_instance()
            
            # Lógica para extrair QR Code (Base64 ou String)
            qr_data = None
            if isinstance(response.get("qrcode"), dict):
                qr_data = response["qrcode"].get("base64")
            elif "base64" in response:
                qr_data = response["base64"]
            
            if qr_data:
                return f"""
                <html>
                    <head><meta http-equiv="refresh" content="15"></head>
                    <body style="font-family: sans-serif; text-align: center; padding: 20px;">
                        <h1>📱 Escaneie o QR Code</h1>
                        <img src="{qr_data}" style="border: 5px solid #333; border-radius: 10px; max-width: 300px;" />
                        <p>A página atualizará em 15 segundos...</p>
                        <p>Abra o WhatsApp > Aparelhos Conectados > Conectar</p>
                    </body>
                </html>
                """
            
            return f"<h1>⚠️ Estado: {response.get('instance', {}).get('state', 'Desconhecido')}</h1><p>Recarregue a página.</p>"

        except Exception as e:
            logger.error(f"Erro ao gerar QR: {e}")
            return f"<h1>❌ Erro: {str(e)}</h1>"


@app.get("/status")
async def check_status():
    """Verifica o status da conexão com o WhatsApp"""
    state = await evolution_service.get_connection_state()
    is_connected = state.get("state") == "open"
    connection_state["connected"] = is_connected
    return {
        "connected": is_connected,
        "state": state.get("state"),
        "metrics": metrics
    }


@app.post("/webhook/evolution")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook Central.
    Recebe TUDO da Evolution e filtra o que interessa.
    """
    try:
        # Lemos o JSON puro para flexibilidade (evita erros de validação Pydantic)
        body = await request.json()
        event_type = body.get("event")
        data = body.get("data", {})
        
        # --- Lógica de Atualização de Status ---
        if event_type == "connection.update":
            state = data.get("state")
            connection_state["connected"] = (state == "open")
            logger.info(f"📡 Status da conexão mudou para: {state}")
            return {"ack": True}

        # --- Filtro: Apenas Novas Mensagens ---
        if event_type != "messages.upsert":
            return {"status": "ignored_event_type"}

        key = data.get("key", {})
        
        # 1. Ignora mensagens enviadas por mim mesmo
        if key.get("fromMe"): 
            return {"status": "ignored_from_me"}
        
        # 2. Ignora Status/Stories (broadcast)
        remote_jid = key.get("remoteJid", "")
        if "broadcast" in remote_jid:
            return {"status": "ignored_broadcast"}

        # 3. Detecta Áudio (Normal ou Efêmero/Temporário)
        msg_type = data.get("messageType")
        is_audio = msg_type == "audioMessage"
        
        # Tratamento especial para mensagens temporárias (ephemeral)
        # O WhatsApp esconde o áudio dentro de ephemeralMessage -> message -> audioMessage
        if msg_type == "ephemeralMessage":
            real_msg = data.get("message", {}).get("ephemeralMessage", {}).get("message", {})
            if "audioMessage" in real_msg:
                is_audio = True
                # Ajusta os dados para o download funcionar corretamente
                # Substituímos a estrutura efêmera pela estrutura de áudio real para o resto do código
                data["message"] = real_msg 

        if not is_audio:
            metrics["total_messages"] += 1
            return {"status": "ignored_not_audio"}

        # --- Processamento ---
        metrics["total_messages"] += 1
        metrics["audio_messages"] += 1
        
        phone = remote_jid.split("@")[0]
        msg_id = key.get("id")

        logger.info(f"🎤 Áudio recebido de {phone}. Iniciando pipeline...")

        background_tasks.add_task(
            pipeline_sales_response,
            message_data=data,
            phone=phone,
            message_id=msg_id
        )

        return {"status": "processing"}

    except Exception as e:
        logger.error(f"Erro crítico no webhook: {e}")
        # Retornamos 200 mesmo com erro para o WhatsApp não ficar tentando reenviar infinitamente
        return {"status": "error_handled"}


async def pipeline_sales_response(message_data: Dict[str, Any], phone: str, message_id: str):
    """
    Coração do Robô: Download -> Cérebro -> Voz -> Envio
    """
    input_path = None
    output_path = None
    
    try:
        # 1. Download
        input_path = await evolution_service.download_media(message_data)
        if not input_path:
            logger.error("❌ Falha no download do áudio.")
            metrics["errors"] += 1
            return

        # 2. Inteligência (Gemini)
        # O brain_service já lida com o arquivo e retorna texto
        response_text = await brain_service.process_audio_and_respond(input_path)
        
        if not response_text:
            logger.warning("⚠️ IA retornou texto vazio ou falhou.")
            metrics["errors"] += 1
            return

        logger.info(f"🤖 IA sugere: {response_text[:50]}...")

        # 3. Voz (Edge-TTS + FFmpeg)
        output_path = await voice_service.generate_audio(response_text)

        # 4. Envio
        if output_path:
            await evolution_service.send_audio(phone, str(output_path), quoted_id=message_id)
            metrics["successful_responses"] += 1
            logger.info("✅ Ciclo completo com sucesso!")
        else:
            # Fallback: Se não conseguiu gerar áudio, manda texto
            await evolution_service.send_text(phone, response_text)
            logger.warning("⚠️ Áudio falhou, enviado fallback de texto.")
            metrics["errors"] += 1 # Conta como erro parcial

    except Exception as e:
        logger.error(f"💥 Erro no pipeline: {e}", exc_info=True)
        metrics["errors"] += 1
    finally:
        # Limpeza obrigatória para não encher o disco
        safe_remove(input_path)
        safe_remove(output_path)