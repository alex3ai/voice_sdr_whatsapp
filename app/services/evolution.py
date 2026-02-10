"""
Serviço de integração com Evolution API V2 (Corrigido Fluxo de Reconexão, PTT e Histórico)
"""
import asyncio
import base64
import aiofiles
from pathlib import Path
from typing import Any, Dict, Optional, Union

import httpx
from app.config import settings
from app.utils.exceptions import EvolutionApiException
from app.utils.files import get_temp_filename
from app.utils.logger import setup_logger
from app.utils.retry_handler import retry_with_backoff, get_retryable_exceptions

logger = setup_logger(__name__)


class EvolutionService:
    """Gerenciador de comunicação com a Evolution API"""

    def __init__(self):
        self.base_url = settings.evolution_api_url
        self.instance_name = settings.evolution_instance_name
        self.headers = settings.evolution_headers
        self.timeout = httpx.Timeout(settings.download_timeout, connect=10.0)
        self._instance_lock = asyncio.Lock()

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        exceptions=get_retryable_exceptions() + (EvolutionApiException,)
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        log_success: str = "",
        log_error: str = "",
        json_data: dict = None,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Union[Dict[str, Any], bytes]:
        """
        Wrapper central para realizar chamadas HTTP à Evolution API.
        """
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"
        
        request_timeout = httpx.Timeout(timeout, connect=10.0) if timeout else self.timeout

        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                if json_data:
                    kwargs['json'] = json_data

                response = await client.request(
                    method, url, headers=self.headers, **kwargs
                )
                
                # Tratamos o 403 como erro para o create_instance capturar
                response.raise_for_status()

                if log_success:
                    logger.info(log_success)

                content_type = response.headers.get("content-type", "")
                if "download" in endpoint or "audio" in content_type or "image" in content_type:
                    return response.content
                
                if response.status_code == 204:
                    return {}

                return response.json()

        except httpx.HTTPStatusError as e:
            # Se for 403 (Instance already exists), lançamos erro específico
            if e.response.status_code == 403:
                raise EvolutionApiException("InstanceConflict", original_exception=e)

            err_msg = f"{log_error}: API Status {e.response.status_code}" if log_error else f"Erro API {e.response.status_code}"
            try:
                err_msg += f" - {e.response.json()}"
            except:
                err_msg += f" - {e.response.text}"
            
            logger.error(err_msg)
            raise EvolutionApiException(err_msg, original_exception=e)
            
        except Exception as e:
            if isinstance(e, EvolutionApiException):
                raise e
                
            err_msg = f"{log_error}: Erro inesperado." if log_error else "Erro inesperado na API"
            logger.error(f"{err_msg} Detalhes: {e}")
            raise EvolutionApiException(err_msg, original_exception=e)

    async def create_instance(self) -> Dict[str, Any]:
        """Tenta criar. Se falhar com 403, tenta conectar."""
        payload = {
            "instanceName": self.instance_name,
            "token": "", 
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        try:
            logger.info(f"🔨 Configurando instância '{self.instance_name}'...")
            return await self._request("POST", "instance/create", json_data=payload)
        
        except EvolutionApiException as e:
            if "InstanceConflict" in str(e):
                logger.warning(f"⚠️ Instância já existe. Buscando QR Code...")
                return await self.connect_instance()
            return {"error": str(e)}

    async def connect_instance(self) -> Dict[str, Any]:
        """Busca o QR Code da instância."""
        try:
            return await self._request(
                "GET", 
                f"instance/connect/{self.instance_name}",
                log_success="📡 Solicitação de conexão enviada."
            )
        except Exception as e:
            logger.error(f"Erro ao buscar QR Code: {e}")
            return {"error": str(e)}

    async def delete_instance(self) -> bool:
        try:
            await self._request("DELETE", f"instance/delete/{self.instance_name}")
            return True
        except:
            return False

    async def get_connection_state(self) -> Dict[str, Any]:
        try:
            return await self._request("GET", f"instance/connectionState/{self.instance_name}")
        except:
            return {"state": "disconnected"}

    async def send_text(self, phone: str, text: str) -> bool:
        try:
            payload = {"number": phone, "delay": 1200, "text": text}
            await self._request("POST", f"message/sendText/{self.instance_name}", json_data=payload, log_success=f"💬 Texto enviado para {phone}")
            return True
        except:
            return False

    async def download_media(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Baixa a mídia de uma mensagem usando Base64."""
        msg_content = message_data.get("message", {}) or message_data.get("data", {}).get("message", {})
        audio_msg = msg_content.get("audioMessage")
        if not audio_msg and "ephemeralMessage" in msg_content:
             audio_msg = msg_content.get("ephemeralMessage", {}).get("message", {}).get("audioMessage")

        if not audio_msg:
            if message_data.get("messageType") == "audioMessage":
                audio_msg = msg_content
            else:
                return None

        mime_type = audio_msg.get("mimetype", "audio/ogg")
        extension = ".mp3" if "mp3" in mime_type else ".ogg"

        try:
            payload = {"message": message_data, "convertToBase64": True}
            
            response_data = await self._request(
                "POST",
                f"chat/getBase64FromMediaMessage/{self.instance_name}",
                json_data=payload,
                log_success="✓ Mídia baixada (Base64).",
            )

            if isinstance(response_data, dict) and "base64" in response_data:
                 base64_str = response_data["base64"]
                 if "," in base64_str:
                     base64_str = base64_str.split(",")[1]
                     
                 media_bytes = base64.b64decode(base64_str)
            else:
                 return None

            temp_file = get_temp_filename(extension, prefix="evo_down")
            with open(temp_file, "wb") as f:
                f.write(media_bytes)

            return temp_file
        except Exception as e:
            logger.error(f"Erro no download da mídia: {e}")
            return None

    async def send_audio(self, phone: str, audio_path: str, quoted_id: str = None):
        """
        Envia áudio como NOTA DE VOZ (PTT) usando endpoint específico.
        """
        url_endpoint = f"message/sendWhatsAppAudio/{self.instance_name}"
        
        try:
            path_obj = Path(audio_path)
            if not path_obj.exists():
                logger.error(f"Arquivo de áudio não encontrado: {audio_path}")
                return

            async with aiofiles.open(path_obj, "rb") as f:
                file_content = await f.read()
                base64_audio = base64.b64encode(file_content).decode('utf-8')

        except Exception as e:
            logger.error(f"Erro ao ler arquivo de áudio: {e}")
            return

        payload = {
            "number": phone,
            "audio": base64_audio,
            "delay": 1200,
            "encoding": True
        }

        if quoted_id:
            payload["quoted"] = {"key": {"id": quoted_id}}

        try:
            await self._request("POST", url_endpoint, json_data=payload, log_success="📤 Nota de voz enviada!")
        except EvolutionApiException as e:
            logger.warning(f"sendWhatsAppAudio falhou ({e}), tentando fallback sendMedia...")
            await self._send_audio_fallback(phone, base64_audio, quoted_id)

    async def _send_audio_fallback(self, phone: str, base64_audio: str, quoted_id: str):
        """Fallback usando sendMedia genérico se o PTT falhar."""
        payload = {
            "number": phone,
            "media": base64_audio,
            "mediatype": "audio",
            "mimetype": "audio/ogg",
            "fileName": "audio.ogg"
        }
        if quoted_id:
            payload["quoted"] = {"key": {"id": quoted_id}}
        
        await self._request(
            "POST", 
            f"message/sendMedia/{self.instance_name}", 
            json_data=payload, 
            log_success="📤 Áudio enviado (Fallback sendMedia)."
        )

    async def get_history(self, remote_jid: str, limit: int = 10) -> list:
        """
        Busca as últimas mensagens do chat para contexto.
        Endpoint: POST /chat/findMessages/{instance}
        """
        # CORREÇÃO: Usar _request em vez de httpx direto para consistência
        endpoint = f"chat/findMessages/{self.instance_name}"
        
        payload = {
            "where": {
                "key": {
                    "remoteJid": remote_jid
                }
            },
            "options": {
                "limit": limit,
                "sort": "DESC" # Pega as mais recentes
            }
        }

        try:
            response_data = await self._request("POST", endpoint, json_data=payload)
            
            # Verifica se retornou dados válidos
            if isinstance(response_data, dict):
                messages = response_data.get("messages", {}).get("records", [])
                
                # CORREÇÃO CRÍTICA DO ERRO DE TIMESTAMP:
                # A API já retorna ordenado DESC (Mais novo -> Mais antigo).
                # A IA precisa ler cronologicamente (Antigo -> Novo).
                # Simplesmente invertemos a lista. Isso evita erros de chave 'timestamp'.
                return messages[::-1] if messages else []
            
            return []

        except Exception as e:
            logger.error(f"❌ Erro de conexão (Histórico): {e}")
            return []

# Singleton
evolution_service = EvolutionService()