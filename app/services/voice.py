import os
import aiohttp
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from app.config import settings
from app.utils.files import get_temp_filename, safe_remove
from app.utils.logger import setup_logger
from app.utils.retry_handler import retry_with_backoff, get_retryable_exceptions

logger = setup_logger(__name__)

class VoiceService:
    """
    Gerenciador de síntese de voz usando Azure TTS via API REST (HTTP).
    Vantagem: Não requer drivers de áudio (GStreamer/ALSA) no Docker,
    eliminando o erro "Failed to initialize platform".
    """

    def __init__(self):
        self.speech_key = os.getenv("AZURE_SPEECH_KEY")
        self.service_region = os.getenv("AZURE_SPEECH_REGION")
        
        if not self.speech_key or not self.service_region:
            logger.critical("🚨 Credenciais AZURE_SPEECH não encontradas!")

        # Endpoint oficial da API REST da Azure
        self.endpoint = f"https://{self.service_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        
        # Voz Neural Masculina (Padrão)
        self.voice_name = "pt-BR-AntonioNeural"
        
        # Formato nativo aceito pelo WhatsApp (Opus dentro de Ogg)
        # Isso garante que o áudio seja enviado como "Nota de Voz" e não arquivo de música
        self.output_format = "ogg-48khz-16bit-mono-opus"

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        exceptions=get_retryable_exceptions()
    )
    async def generate_audio(self, text: str) -> Optional[Path]:
        """
        Gera áudio enviando SSML para a API REST da Azure.
        """
        if not text:
            return None
        
        if not self.speech_key:
            logger.error("❌ Chave da Azure não configurada.")
            return None

        ogg_path = get_temp_filename(".ogg", prefix="voice_note")

        # 1. Construção do SSML (XML que diz à Azure como falar)
        # Usamos escape(text) para evitar que símbolos como < ou > quebrem o XML
        ssml = f"""
        <speak version='1.0' xml:lang='pt-BR'>
            <voice xml:lang='pt-BR' xml:gender='Male' name='{self.voice_name}'>
                {escape(text)}
            </voice>
        </speak>
        """

        # 2. Cabeçalhos Obrigatórios da API
        headers = {
            "Ocp-Apim-Subscription-Key": self.speech_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": self.output_format,
            "User-Agent": "VoiceSDRBot"
        }

        try:
            # 3. Requisição HTTP Assíncrona (Não trava o Bot)
            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint, headers=headers, data=ssml) as response:
                    
                    if response.status == 200:
                        # Sucesso: Grava os bytes diretamente no arquivo
                        with open(ogg_path, "wb") as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                f.write(chunk)
                        
                        # Verifica se o arquivo foi realmente criado e tem conteúdo
                        if ogg_path.exists() and ogg_path.stat().st_size > 0:
                            return ogg_path
                        else:
                            logger.error("❌ Arquivo de áudio criado vazio.")
                            return None
                    else:
                        # Tratamento de Erro da API
                        error_text = await response.text()
                        logger.error(f"❌ Erro Azure API REST ({response.status}): {error_text}")
                        safe_remove(ogg_path)
                        return None

        except Exception as e:
            logger.error(f"💥 Falha de conexão com Azure REST: {e}")
            safe_remove(ogg_path)
            return None

# Singleton
voice_service = VoiceService()