"""
Serviço de integração com Evolution API V2.
Gerencia instâncias, envio e recebimento de mensagens.
"""
import httpx
import base64
import aiofiles
from typing import Optional, Dict, Any
from app.config import settings
from app.utils.files import get_temp_filename, get_file_size_mb
from app.utils.logger import logger

class EvolutionService:
    """
    Gerenciador de comunicação com a Evolution API.
    """
    
    def __init__(self):
        self.base_url = settings.evolution_api_url
        self.instance_name = settings.evolution_instance_name
        self.headers = settings.evolution_headers
        # Timeout maior para operações de mídia
        self.timeout = httpx.Timeout(settings.download_timeout, connect=10.0)

    async def create_instance(self) -> Dict[str, Any]:
        """
        Cria/Conecta a instância na Evolution API.
        Retorna o QR Code (base64) se necessário.
        """
        url = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(f"Criando instância '{self.instance_name}'...")
                resp = await client.post(url, json=payload, headers=self.headers)
                
                # Se já existe (409), tenta reconectar para pegar status
                if resp.status_code == 409:
                    logger.info("Instância já existe. Verificando conexão...")
                    return await self.get_connection_state()
                
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Erro ao criar instância: {e}")
            return {"error": str(e)}

    async def get_connection_state(self) -> Dict[str, Any]:
        """Checa se o WhatsApp está conectado."""
        url = f"{self.base_url}/instance/connectionState/{self.instance_name}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=self.headers)
                return resp.json()
        except Exception as e:
            logger.warning(f"Não foi possível checar estado: {e}")
            return {"state": "down"}

    async def download_media(self, message_data: Dict[str, Any]) -> Optional[str]:
        """
        Baixa o áudio de uma mensagem recebida.
        A Evolution v2 precisa do objeto 'message' completo para achar a mídia.
        """
        download_url = f"{self.base_url}/instance/downloadMedia/{self.instance_name}"
        
        # Payload específico da Evolution V2
        payload = {
            "message": message_data,
            "convertToMp4": False
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("Baixando mídia da Evolution API...")
                resp = await client.post(download_url, json=payload, headers=self.headers)
                resp.raise_for_status()
                
                # Detecta extensão (Evolution geralmente retorna o binário direto)
                # Assumimos OGG se não vier header explícito, pois é o padrão de voz
                content_type = resp.headers.get("content-type", "")
                ext = ".mp3" if "mpeg" in content_type else ".ogg"
                
                filename = get_temp_filename(ext, prefix="evo_in")
                
                # Salva usando I/O não-bloqueante
                async with aiofiles.open(filename, "wb") as f:
                    await f.write(resp.content)
                
                size = get_file_size_mb(filename)
                logger.info(f"Mídia baixada: {size:.2f} MB")
                return str(filename)

        except Exception as e:
            logger.error(f"Falha no download da mídia: {e}")
            return None

    async def send_audio(self, number: str, audio_path: str) -> bool:
        """
        Envia áudio (PTT) lendo o arquivo local e convertendo para Base64.
        """
        url = f"{self.base_url}/message/sendWhatsAppAudio/{self.instance_name}"
        
        try:
            # 1. Leitura Async do Arquivo
            async with aiofiles.open(audio_path, "rb") as f:
                file_content = await f.read()
                audio_b64 = base64.b64encode(file_content).decode("utf-8")

            # 2. Envio
            payload = {
                "number": number,
                "audioBase64": audio_b64,
                "delay": 1200 # Delay humano (1.2s)
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
                resp.raise_for_status()
                logger.info(f"✅ Áudio enviado para {number}")
                return True

        except Exception as e:
            logger.error(f"❌ Erro ao enviar áudio: {e}")
            return False

    async def send_text(self, number: str, text: str) -> bool:
        """Helper para enviar texto (útil para mensagens de erro/fallback)."""
        url = f"{self.base_url}/message/sendText/{self.instance_name}"
        payload = {"number": number, "text": text, "delay": 2000}
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, headers=self.headers)
                return True
        except:
            return False

# Singleton
evolution_service = EvolutionService()