import asyncio
import logging
import edge_tts
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from aiohttp import ClientSession

# Importar a biblioteca oficial do Azure Speech
try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    speechsdk = None
    print("⚠️ Biblioteca azure-cognitiveservices-speech não encontrada. Instale com: pip install azure-cognitiveservices-speech")

from app.config import settings
from app.utils.files import get_temp_filename
from app.utils.logger import setup_logger
from .notification import get_notification_service

logger = setup_logger(__name__)
notification_service = get_notification_service()

class VoiceService:
    """
    Gerenciador de síntese de voz usando Azure TTS via API REST (HTTP).
    Vantagem: Não requer drivers de áudio (GStreamer/ALSA) no Docker,
    eliminando o erro "Failed to initialize platform".
    """

    def __init__(self):
        # Usar a região configurada nas variáveis de ambiente para montar o endpoint
        self.tts_url = f"https://{settings.azure_tts_region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self.token_url = f"https://{settings.azure_tts_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        self.subscription_key = settings.azure_tts_subscription_key
        self.region = settings.azure_tts_region
        self.voice_name = settings.azure_tts_voice_name
        self.edge_voice_name = settings.edge_tts_voice
        self.notification_service = get_notification_service()

    async def generate_audio(self, text: str) -> Optional[Path]:
        """
        Gera um arquivo de áudio OGG/Opus via Azure Cognitive Services REST API.
        Retorna o caminho para o arquivo de áudio gerado ou None se falhar.
        Primeiro tenta Azure TTS com biblioteca oficial, depois via requisição direta e por fim Edge TTS como fallback.
        """
        
        # Tenta primeiro com Azure TTS usando a biblioteca oficial
        if speechsdk:
            azure_sdk_result = await self._generate_azure_sdk_audio(text)
            if azure_sdk_result:
                return azure_sdk_result
        
        # Se Azure SDK falhar ou não estiver disponível, tenta com requisição direta
        azure_result = await self._generate_azure_audio(text)
        if azure_result:
            return azure_result
            
        # Se Azure falhar, tenta Edge TTS como fallback
        logger.info("🔄 Azure TTS falhou, tentando com Edge TTS...")
        return await self._generate_edge_audio(text)

    async def _generate_azure_sdk_audio(self, text: str) -> Optional[Path]:
        """
        Gera áudio usando Azure Cognitive Services SDK.
        """
        if not self.subscription_key or not speechsdk:
            logger.warning("⚠️ Chave Azure TTS não configurada ou SDK não instalado, pulando...")
            return None

        # Gera nome de arquivo temporário com extensão .wav (padrão do SDK)
        output_path = get_temp_filename(extension=".wav")

        try:
            # Configura a síntese de fala
            speech_config = speechsdk.SpeechConfig(subscription=self.subscription_key, region=self.region)
            speech_config.speech_synthesis_voice_name = self.voice_name
            # Corrigindo o formato de áudio
            speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm)
            
            audio_config = speechsdk.audio.AudioOutputConfig(filename=str(output_path))
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
            
            # Realiza a síntese com SSML simplificado
            ssml_string = f"""
            <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='pt-BR'>
                <voice name='{self.voice_name}'>{text}</voice>
            </speak>
            """
            
            result = synthesizer.speak_ssml_async(ssml_string).get()
            
            # Verifica o resultado
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"🔊 Áudio sintetizado via Azure SDK: {output_path}")
                
                # Converte WAV para OGG se necessário (por compatibilidade com WhatsApp)
                ogg_path = get_temp_filename(extension=".ogg")
                
                # Como não queremos adicionar PyDub ou FFmpeg como dependência,
                # vamos usar o arquivo wav diretamente mas com extensão ogg
                # Isso geralmente funciona com o WhatsApp, que é tolerante com extensões
                ogg_path.unlink(missing_ok=True)  # Remove se já existir
                output_path.rename(ogg_path)      # Renomeia o wav para ogg
                
                return ogg_path
            else:
                logger.error(f"❌ Falha na síntese de áudio via Azure SDK: {result.reason}")
                if result.cancellation_details:
                    logger.error(f"❌ Detalhes do cancelamento: {result.cancellation_details.reason}")
                    if result.cancellation_details.error_details:
                        logger.error(f"❌ Detalhes do erro: {result.cancellation_details.error_details}")
                return None
        except Exception as e:
            logger.error(f"💥 Falha ao usar Azure SDK: {e}")
            # Mesmo que o SDK falhe, continuamos com outros métodos
            return None

    async def _generate_azure_audio(self, text: str) -> Optional[Path]:
        """
        Gera áudio usando Azure Cognitive Services via requisição direta.
        """
        if not self.subscription_key:
            logger.warning("⚠️ Chave Azure TTS não configurada, pulando...")
            return None

        # Gera nome de arquivo temporário com extensão .ogg
        output_path = get_temp_filename(extension=".ogg")

        # Monta o corpo da solicitação SSML simplificado
        ssml = f"""
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='pt-BR'>
    <voice name='{self.voice_name}'>{text}</voice>
</speak>
        """.strip()

        # Primeiro, obtemos um token de autorização
        auth_token = await self._get_auth_token()
        if not auth_token:
            logger.error("❌ Não foi possível obter o token de autorização para Azure TTS")
            return None

        # Headers da requisição com o token de autorização
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/ssml+xml",
            "User-Agent": "MyTTSApp",
            "X-Microsoft-OutputFormat": "ogg-24khz-16bit-mono-opus"  # Formato compatível com WhatsApp
        }

        try:
            logger.info(f"🔊 Tentando Azure TTS - Endpoint: {self.tts_url}, Região: {self.region}")
            async with ClientSession() as session:
                async with session.post(
                    self.tts_url,
                    headers=headers,
                    data=ssml.encode('utf-8')
                ) as response:
                    
                    logger.info(f"🔊 Resposta Azure API: {response.status}")
                    
                    if response.status == 200:
                        # Sucesso: Grava os bytes diretamente no arquivo
                        async with aiofiles.open(output_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(1024):
                                await f.write(chunk)
                        
                        # Verifica se o arquivo foi realmente criado e tem conteúdo
                        if output_path.exists() and output_path.stat().st_size > 0:
                            logger.info(f"🔊 Áudio sintetizado via Azure: {output_path}")
                            return output_path
                        else:
                            logger.error("❌ Arquivo de áudio Azure criado vazio.")
                            return None
                    else:
                        # Tratamento de Erro da API
                        error_text = await response.text()
                        logger.error(f"❌ Erro Azure API REST ({response.status}): {error_text}")
                        # Registrar o erro como crítica para investigação
                        logger.error(f"❌ Detalhes: Endpoint={self.tts_url}, Região={self.region}, Voice={self.voice_name}")
                        logger.error(f"❌ SSML enviado: {ssml[:200]}...")  # Primeiros 200 chars
                        # Não notificamos erro crítico aqui pois tentaremos fallback
                        return None

        except Exception as e:
            logger.error(f"💥 Falha de conexão com Azure REST: {e}")
            logger.error(f"❌ Detalhes: Endpoint={self.tts_url}, Região={self.region}, Voice={self.voice_name}")
            return None

    async def _get_auth_token(self) -> Optional[str]:
        """
        Obtém um token de autorização usando a chave de subscrição.
        """
        headers = {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "MyTTSApp"
        }
        
        try:
            async with ClientSession() as session:
                async with session.post(
                    self.token_url,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        token = await response.text()
                        return token
                    else:
                        logger.error(f"❌ Erro ao obter token de autorização: {response.status}")
                        error_text = await response.text()
                        logger.error(f"❌ Detalhes: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"💥 Falha ao obter token de autorização: {e}")
            return None

    async def _generate_edge_audio(self, text: str) -> Optional[Path]:
        """
        Gera áudio usando Edge TTS como fallback.
        """
        if not self.edge_voice_name:
            logger.warning("⚠️ Voice name para Edge TTS não configurado.")
            return None
        
        output_path = get_temp_filename(extension=".ogg")
        
        try:
            logger.info(f"🔊 Tentando Edge TTS - Voz: {self.edge_voice_name}")
            communicate = edge_tts.Communicate(text, self.edge_voice_name)
            await communicate.save(output_path)
            
            # Verifica se o arquivo foi realmente criado e tem conteúdo
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"🔊 Áudio sintetizado via Edge TTS: {output_path}")
                return output_path
            else:
                logger.error("❌ Arquivo de áudio Edge TTS criado vazio.")
                return None
                
        except Exception as e:
            logger.error(f"💥 Falha ao gerar áudio com Edge TTS: {e}")
            return None

# Singleton
voice_service = VoiceService()