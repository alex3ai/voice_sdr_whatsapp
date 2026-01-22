"""
Serviço de integração com Evolution API V2
Documentação: https://doc.evolution-api.com/
"""
import httpx
import asyncio
import base64
from typing import Optional, Dict, Any
from pathlib import Path
from app.config import settings
from app.utils.files import get_temp_filename, get_file_size_mb
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class EvolutionService:
    """Gerenciador de comunicação com a Evolution API"""
    
    def __init__(self):
        self.base_url = settings.evolution_api_url
        self.instance_name = settings.evolution_instance_name
        self.headers = settings.evolution_headers
        self.timeout = httpx.Timeout(settings.download_timeout, connect=10.0)
    
    async def create_instance(self) -> Dict[str, Any]:
        """
        Cria uma nova instância do WhatsApp OU busca QR Code se já existir
        
        Returns:
            Dict com status e QR code em base64
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Primeiro, tenta criar a instância
                url = f"{self.base_url}/instance/create"
                
                payload = {
                    "instanceName": self.instance_name,
                    "qrcode": True,
                    "integration": "WHATSAPP-BAILEYS"
                }
                
                response = await client.post(url, json=payload, headers=self.headers)
                
                # Se criar com sucesso
                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.info(f"✓ Instância criada: {self.instance_name}")
                    return data
                
                # Se já existe (409), busca o QR Code
                elif response.status_code == 409:
                    logger.info(f"ℹ️ Instância '{self.instance_name}' já existe. Buscando QR Code de conexão...")
                    return await self._fetch_qrcode()
                
                else:
                    response.raise_for_status()
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP ao criar instância: {e.response.status_code} - {e.response.text}")
            
            # Se for 409 (já existe), tenta buscar QR Code
            if e.response.status_code == 409:
                return await self._fetch_qrcode()
            
            return {"error": str(e), "status_code": e.response.status_code}
        
        except Exception as e:
            logger.error(f"Erro ao criar instância: {e}")
            return {"error": str(e)}
    
    async def _fetch_qrcode(self) -> Dict[str, Any]:
        """
        Busca o QR Code de uma instância existente
        
        Returns:
            Dict com QR Code base64
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Endpoint para conectar e obter QR Code
                url = f"{self.base_url}/instance/connect/{self.instance_name}"
                
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                data = response.json()
                
                # Se tiver QR Code na resposta
                if "qrcode" in data or "base64" in data:
                    logger.info("✓ QR Code obtido com sucesso!")
                    return data
                
                # Se já estiver conectado
                if data.get("state") == "open":
                    logger.info("✅ WhatsApp já está conectado!")
                    return {"status": "connected", "state": "open"}
                
                # Tenta outro endpoint (algumas versões da Evolution usam diferente)
                logger.debug("Tentando endpoint alternativo para QR Code...")
                url_alt = f"{self.base_url}/instance/qrcode/{self.instance_name}"
                
                response_alt = await client.get(url_alt, headers=self.headers)
                
                if response_alt.status_code == 200:
                    data_alt = response_alt.json()
                    if "qrcode" in data_alt or "base64" in data_alt:
                        logger.info("✓ QR Code obtido (endpoint alternativo)!")
                        return data_alt
                
                logger.warning("QR Code não disponível no momento")
                return {"status": "qr_not_available", "message": "Tente novamente em alguns segundos"}
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro ao buscar QR Code: {e.response.status_code} - {e.response.text}")
            return {"error": "qr_fetch_failed", "details": e.response.text}
        
        except Exception as e:
            logger.error(f"Erro ao buscar QR Code: {e}")
            return {"error": str(e)}
    
    async def get_connection_state(self) -> Dict[str, Any]:
        """
        Verifica o status da conexão
        
        Returns:
            Dict com estado da conexão
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/instance/connectionState/{self.instance_name}"
                
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                
                return response.json()
        
        except Exception as e:
            logger.error(f"Erro ao obter estado: {e}")
            return {"state": "error", "error": str(e)}
    
    async def download_media(self, message_data: Dict[str, Any]) -> Optional[str]:
        """
        Baixa mídia de uma mensagem
        
        Args:
            message_data: Dados da mensagem do webhook
        
        Returns:
            Caminho do arquivo baixado ou None
        """
        try:
            # A Evolution API já envia o base64 do áudio direto no webhook
            # em message.message.audioMessage.ptt (para áudio PTT)
            
            audio_msg = message_data.get("message", {}).get("audioMessage")
            
            if not audio_msg:
                logger.error("Mensagem não contém áudio")
                return None
            
            # Pega a URL de download da mídia
            media_url = audio_msg.get("url")
            mime_type = audio_msg.get("mimetype", "audio/ogg")
            
            if not media_url:
                logger.error("URL de mídia não encontrada")
                return None
            
            # Baixa o arquivo
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("Baixando arquivo de mídia...")
                
                # A Evolution expõe endpoint para download
                download_url = f"{self.base_url}/instance/downloadMedia/{self.instance_name}"
                
                payload = {
                    "message": message_data
                }
                
                response = await client.post(
                    download_url,
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                
                # Salva localmente
                extension = self._get_extension_from_mime(mime_type)
                temp_file = get_temp_filename(extension, prefix="evolution_download")
                
                # A resposta pode vir em base64 ou bytes
                content = response.content
                
                with open(temp_file, "wb") as f:
                    f.write(content)
                
                file_size = get_file_size_mb(temp_file)
                logger.info(f"✓ Mídia baixada: {file_size:.2f} MB")
                
                return temp_file
        
        except Exception as e:
            logger.error(f"Erro ao baixar mídia: {e}", exc_info=True)
            return None
    
    async def send_audio(self, phone_number: str, audio_path: str, quoted_msg_id: Optional[str] = None) -> bool:
        """
        Envia áudio (nota de voz) via WhatsApp
        
        Args:
            phone_number: Número no formato 5511999999999
            audio_path: Caminho do arquivo de áudio local
            quoted_msg_id: ID da mensagem para responder (opcional)
        
        Returns:
            True se enviado com sucesso
        """
        try:
            # Converte áudio para base64
            with open(audio_path, "rb") as audio_file:
                audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/message/sendWhatsAppAudio/{self.instance_name}"
                
                payload = {
                    "number": phone_number,
                    "audioBase64": audio_base64,
                    "delay": 1200  # Delay para parecer mais humano (milissegundos)
                }
                
                # Se for resposta a uma mensagem
                if quoted_msg_id:
                    payload["quoted"] = {
                        "key": {
                            "id": quoted_msg_id
                        }
                    }
                
                logger.info(f"Enviando áudio para {phone_number[-4:]}...")
                
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                
                logger.info("✓ Áudio enviado com sucesso!")
                return True
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP ao enviar áudio: {e.response.status_code} - {e.response.text}")
            return False
        
        except Exception as e:
            logger.error(f"Erro ao enviar áudio: {e}", exc_info=True)
            return False
    
    async def send_text(self, phone_number: str, text: str) -> bool:
        """
        Envia mensagem de texto
        
        Args:
            phone_number: Número no formato 5511999999999
            text: Texto da mensagem
        
        Returns:
            True se enviado com sucesso
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/message/sendText/{self.instance_name}"
                
                payload = {
                    "number": phone_number,
                    "text": text,
                    "delay": 1200
                }
                
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                
                logger.info("✓ Texto enviado!")
                return True
        
        except Exception as e:
            logger.error(f"Erro ao enviar texto: {e}")
            return False
    
    async def delete_instance(self) -> bool:
        """Deleta a instância (desconecta do WhatsApp)"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/instance/delete/{self.instance_name}"
                
                response = await client.delete(url, headers=self.headers)
                response.raise_for_status()
                
                logger.info("✓ Instância deletada")
                return True
        
        except Exception as e:
            logger.error(f"Erro ao deletar instância: {e}")
            return False
    
    @staticmethod
    def _get_extension_from_mime(mime_type: str) -> str:
        """Mapeia MIME type para extensão de arquivo"""
        mime_map = {
            "audio/ogg": ".ogg",
            "audio/ogg; codecs=opus": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".m4a",
            "audio/aac": ".aac"
        }
        return mime_map.get(mime_type, ".ogg")


# Singleton do serviço
evolution_service = EvolutionService()