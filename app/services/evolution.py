"""
Serviço de integração com Evolution API V2 (Atualizado v2.3+)
Documentação: https://doc.evolution-api.com/
"""
import asyncio
import base64
from typing import Any, Dict, Optional, Union

import httpx
from app.config import settings
from app.utils.exceptions import EvolutionApiException
from app.utils.files import get_temp_filename
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class EvolutionService:
    """Gerenciador de comunicação com a Evolution API"""

    def __init__(self):
        self.base_url = settings.evolution_api_url
        self.instance_name = settings.evolution_instance_name
        self.headers = settings.evolution_headers
        self.timeout = httpx.Timeout(settings.download_timeout, connect=10.0)
        self._instance_lock = asyncio.Lock()

    async def _request(
        self,
        method: str,
        endpoint: str,
        log_success: str = "",
        log_error: str = "",
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Union[Dict[str, Any], bytes]:
        """
        Wrapper central para realizar chamadas HTTP à Evolution API.
        """
        # Garante que não haja barras duplas na URL
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"
        
        request_timeout = httpx.Timeout(timeout, connect=10.0) if timeout else self.timeout

        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                response = await client.request(
                    method, url, headers=self.headers, **kwargs
                )
                
                # Tratamento específico para 403 (Instância já existe ou erro de Auth)
                if response.status_code == 403:
                    raise httpx.HTTPStatusError(
                        f"403 Forbidden: {response.text}", 
                        request=response.request, 
                        response=response
                    )

                response.raise_for_status()

                if log_success:
                    logger.info(log_success)

                # Para downloads, retornar o conteúdo binário
                content_type = response.headers.get("content-type", "")
                if "download" in endpoint or "audio" in content_type or "image" in content_type:
                    return response.content
                
                # Para respostas vazias (ex: DELETE 204)
                if response.status_code == 204:
                    return {}

                return response.json()

        except httpx.HTTPStatusError as e:
            # Erro de status (4xx, 5xx)
            err_msg = f"{log_error}: A API retornou o status {e.response.status_code}." if log_error else f"Erro API {e.response.status_code}"
            
            if e.response.status_code != 403:
                # Tenta pegar mensagem de erro detalhada do JSON se existir
                try:
                    error_detail = e.response.json()
                    err_msg += f" - {error_detail}"
                except:
                    err_msg += f" - {e.response.text}"
                logger.error(err_msg)
            
            raise EvolutionApiException(err_msg, original_exception=e)
            
        except httpx.RequestError as e:
            err_msg = f"{log_error}: Falha de conexão com a API." if log_error else "Falha de conexão com a API"
            logger.error(f"{err_msg} Detalhes: {e}")
            raise EvolutionApiException(err_msg, original_exception=e)
            
        except Exception as e:
            err_msg = f"{log_error}: Ocorreu um erro inesperado." if log_error else "Erro inesperado na API"
            logger.error(f"{err_msg} Detalhes: {e}", exc_info=True)
            raise EvolutionApiException(err_msg, original_exception=e)

    async def create_instance(self) -> Dict[str, Any]:
        """Cria a instância OU conecta se ela já existir."""
        payload = {
            "instanceName": self.instance_name,
            "token": "", 
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }

        try:
            logger.info(f"🔨 Tentando criar instância '{self.instance_name}'...")
            return await self._request("POST", "instance/create", json=payload)

        except EvolutionApiException as e:
            if isinstance(e.original_exception, httpx.HTTPStatusError) and e.original_exception.response.status_code == 403:
                logger.warning(f"⚠️ Instância '{self.instance_name}' já existe. Solicitando conexão...")
                return await self.connect_instance()
            
            logger.error(f"Falha crítica ao criar instância: {e}")
            return {"error": str(e), "status": "error"}

    async def connect_instance(self) -> Dict[str, Any]:
        """Força a conexão da instância existente."""
        try:
            return await self._request(
                "GET", 
                f"instance/connect/{self.instance_name}",
                log_success="📡 Solicitação de conexão enviada."
            )
        except Exception as e:
            logger.error(f"Erro ao tentar conectar: {e}")
            return {"error": str(e), "status": "error"}

    async def delete_instance(self) -> bool:
        """Deleta a instância."""
        try:
            await self._request(
                "DELETE",
                f"instance/delete/{self.instance_name}",
                log_success=f"✓ Instância '{self.instance_name}' deletada com sucesso.",
            )
            return True
        except EvolutionApiException as e:
            if isinstance(e.original_exception, httpx.HTTPStatusError) and e.original_exception.response.status_code == 404:
                return True
            return False

    async def get_connection_state(self) -> Dict[str, Any]:
        """Verifica o estado da conexão."""
        try:
            return await self._request(
                "GET",
                f"instance/connectionState/{self.instance_name}",
            )
        except EvolutionApiException:
            return {"state": "disconnected"}

    async def download_media(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Baixa a mídia de uma mensagem."""
        
        # Lógica de extração de mídia compatível com v2
        msg_content = message_data.get("message", {}) or message_data.get("data", {}).get("message", {})
        audio_msg = msg_content.get("audioMessage")
        
        if not audio_msg:
            if message_data.get("messageType") == "audioMessage":
                audio_msg = msg_content
            else:
                return None

        mime_type = audio_msg.get("mimetype", "audio/ogg")

        try:
            # Na v2.3+, enviamos o objeto da mensagem para download
            payload = {"message": message_data}
            
            media_bytes = await self._request(
                "POST",
                f"message/downloadMedia/{self.instance_name}", # Endpoint ajustado
                json=payload,
                log_success="✓ Mídia baixada com sucesso.",
            )

            if not media_bytes:
                return None

            extension = ".ogg"
            if "mp4" in mime_type or "aac" in mime_type:
                extension = ".aac"
            if "mpeg" in mime_type or "mp3" in mime_type:
                extension = ".mp3"

            temp_file = get_temp_filename(extension, prefix="evo_down")
            with open(temp_file, "wb") as f:
                f.write(media_bytes)

            return temp_file
        except Exception as e:
            logger.error(f"Erro no download da mídia: {e}")
            return None

    async def send_audio(self, phone: str, path: str, quoted_id: Optional[str] = None) -> bool:
        """Envia uma mensagem de áudio (PTT/Gravação de voz)."""
        try:
            with open(path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "number": phone,
                "options": {
                    "delay": 1200, 
                    "presence": "recording",
                    "encoding": True 
                },
                "audioMessage": {
                    "audio": audio_b64
                }
            }
            
            if quoted_id:
                payload["options"]["quoted"] = {"key": {"id": quoted_id}}

            # Endpoint atualizado para garantir envio como WhatsApp Audio
            await self._request(
                "POST",
                f"message/sendWhatsAppAudio/{self.instance_name}",
                json=payload,
                log_success=f"🎙️ Áudio enviado para {phone}",
            )
            return True
        except Exception as e:
            logger.error(f"Não foi possível enviar o áudio: {e}")
            return False

    async def send_text(self, phone: str, text: str) -> bool:
        """Envia uma mensagem de texto (Rota V2.3 Simplificada)."""
        try:
            # CORREÇÃO CRÍTICA: Payload plano, sem 'textMessage' aninhado
            payload = {
                "number": phone, 
                "delay": 1200,
                "text": text
            }
            
            # CORREÇÃO CRÍTICA: Endpoint específico para texto
            await self._request(
                "POST",
                f"message/sendText/{self.instance_name}",
                json=payload,
                log_success=f"💬 Texto enviado para {phone}",
            )
            return True
        except EvolutionApiException:
            return False


# Singleton
evolution_service = EvolutionService()