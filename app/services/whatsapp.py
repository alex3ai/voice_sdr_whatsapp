"""
Serviço de integração com WhatsApp Cloud API.
Otimizado para I/O não-bloqueante e resiliência de rede.
"""
import httpx
import aiofiles
import asyncio
from pathlib import Path
from typing import Optional
from app.config import settings
from app.utils.files import get_temp_filename, get_file_size_mb
from app.utils.logger import logger

class WhatsAppService:
    """Gerenciador de comunicação com a WhatsApp Cloud API"""
    
    def __init__(self):
        # Timeouts configuráveis para evitar hangs
        self.timeout = httpx.Timeout(settings.download_timeout, connect=5.0)
        self.max_retries = 3
    
    async def download_media(self, media_id: str) -> Optional[Path]:
        """
        Baixa mídia do WhatsApp de forma 100% assíncrona.
        """
        temp_file_path = None
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 1. Obtém URL de download
                media_info_url = f"{settings.media_url_base}/{media_id}"
                
                logger.debug(f"Buscando metadados da mídia: {media_id}")
                response = await client.get(
                    media_info_url,
                    headers=settings.whatsapp_headers
                )
                response.raise_for_status()
                
                media_data = response.json()
                download_url = media_data.get('url')
                mime_type = media_data.get('mime_type', 'audio/ogg')
                
                if not download_url:
                    logger.error("URL de download não encontrada")
                    return None
                
                # 2. Baixa o binário (Stream)
                # Usamos stream para não carregar arquivos gigantes na RAM de uma vez
                async with client.stream('GET', download_url, headers=settings.whatsapp_headers) as resp:
                    resp.raise_for_status()
                    
                    extension = self._get_extension_from_mime(mime_type)
                    temp_file_path = get_temp_filename(extension, prefix="in_wa")
                    
                    # 3. Escrita não-bloqueante no disco
                    async with aiofiles.open(temp_file_path, "wb") as f:
                        async for chunk in resp.aiter_bytes():
                            await f.write(chunk)
                
                # Validação
                size_mb = get_file_size_mb(temp_file_path)
                logger.info(f"Mídia baixada: {size_mb:.2f} MB")
                
                if size_mb > settings.max_audio_size_mb:
                    logger.warning(f"Áudio ignorado (muito grande): {size_mb:.2f}MB")
                    return None # O controller vai tratar limpeza
                
                return temp_file_path
        
        except Exception as e:
            logger.error(f"Erro no download da mídia: {e}")
            return None

    async def send_voice_note(self, to_number: str, audio_path: Path) -> bool:
        """
        Envia nota de voz com Retry e Backoff Exponencial.
        """
        if not audio_path or not audio_path.exists():
            logger.error("Tentativa de envio de arquivo inexistente")
            return False

        upload_url = f"{settings.media_url_base}/{settings.phone_number_id}/media"
        
        # Lê o arquivo para memória (para upload) de forma async
        # Como limitamos o tamanho no config, é seguro ler em memória
        try:
            async with aiofiles.open(audio_path, "rb") as f:
                file_content = await f.read()
        except Exception as e:
            logger.error(f"Erro ao ler arquivo para envio: {e}")
            return False

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    # 1. Upload da Mídia
                    files = {
                        "file": ("voice.ogg", file_content, "audio/ogg; codecs=opus")
                    }
                    data = {
                        "messaging_product": "whatsapp",
                        "type": "audio/ogg"
                    }
                    
                    # Header específico para upload (sem Content-Type json)
                    upload_headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
                    
                    logger.info(f"Enviando áudio (Tentativa {attempt})...")
                    up_resp = await client.post(
                        upload_url, headers=upload_headers, files=files, data=data
                    )
                    up_resp.raise_for_status()
                    
                    media_id = up_resp.json().get("id")
                    if not media_id:
                        raise ValueError("API não retornou Media ID")

                    # 2. Disparo da Mensagem
                    msg_payload = {
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": to_number,
                        "type": "audio",
                        "audio": {"id": media_id}
                    }
                    
                    send_resp = await client.post(
                        settings.whatsapp_api_url,
                        headers=settings.whatsapp_headers,
                        json=msg_payload
                    )
                    send_resp.raise_for_status()
                    
                    logger.info(f"✅ Áudio enviado com sucesso para {to_number}")
                    return True

            except httpx.HTTPStatusError as e:
                # Tratamento específico para Rate Limit (429)
                if e.response.status_code == 429:
                    wait_time = (2 ** attempt) * 2 # Backoff mais agressivo
                    logger.warning(f"Rate Limit do WhatsApp atingido! Esperando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif attempt < self.max_retries:
                    logger.warning(f"Erro HTTP {e.response.status_code}. Retentando...")
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Falha final após {self.max_retries} tentativas: {e}")
            
            except Exception as e:
                logger.error(f"Erro inesperado no envio: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)
                else:
                    return False
        
        return False

    @staticmethod
    def _get_extension_from_mime(mime_type: str) -> str:
        mime_map = {
            "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a", "audio/aac": ".aac",
            "audio/amr": ".amr"
        }
        return mime_map.get(mime_type, ".ogg")

# Singleton
whatsapp_service = WhatsAppService()