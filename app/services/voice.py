import asyncio
import shutil
import edge_tts
from gtts import gTTS  # Biblioteca de fallback
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.exceptions import VoiceServiceException
from app.utils.files import get_temp_filename, safe_remove
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class VoiceService:
    """
    Gerenciador de síntese de voz (TTS) e conversão de áudio.
    Otimizado para alta concorrência com controle de recursos via Semáforo.
    """

    def __init__(self):
        self.voice = settings.edge_tts_voice
        # SRE: Limita a 3 conversões simultâneas para evitar CPU Throttling
        self._semaphore = asyncio.Semaphore(3)
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Fail Fast: Verifica se o FFmpeg está instalado de forma assíncrona."""
        if not shutil.which("ffmpeg"):
            logger.critical("🚨 FFmpeg não encontrado no PATH! O áudio não será gerado.")
        else:
            logger.info("✅ FFmpeg detectado e pronto para uso.")

    async def generate_audio(self, text: str) -> Optional[Path]:
        """
        Orquestra o processo: Texto -> Áudio Bruto -> OGG (FFmpeg).
        Retorna None se falhar, para ativar o fallback de texto.
        """
        if not text:
            return None

        # Limpa caracteres que quebram o TTS
        clean_text = text.replace("*", "").replace("_", "").strip()
        
        mp3_path = get_temp_filename(".mp3", prefix="tts_raw")
        ogg_path = get_temp_filename(".ogg", prefix="voice_note")

        try:
            # --- TENTATIVA 1: Edge-TTS (Alta Qualidade) ---
            try:
                communicate = edge_tts.Communicate(clean_text, self.voice)
                await communicate.save(str(mp3_path))
                
                # Se salvou com sucesso, converte
                await self._convert_to_whatsapp_format(mp3_path, ogg_path)
                return ogg_path

            except Exception as e_edge:
                logger.warning(f"⚠️ Edge-TTS falhou (Provável bloqueio 403). Tentando gTTS... Erro: {e_edge}")
                # Limpa o ogg se ele foi criado parcialmente
                safe_remove(ogg_path) 
                # Não retorna, deixa cair para o bloco de baixo (gTTS)

            # --- TENTATIVA 2: gTTS (Fallback garantido) ---
            try:
                # gTTS é síncrono/bloqueante, rodamos em uma thread separada para não travar o bot
                await asyncio.to_thread(self._run_gtts, clean_text, mp3_path)
                
                logger.info("ℹ️ Usando gTTS (Fallback).")
                await self._convert_to_whatsapp_format(mp3_path, ogg_path)
                return ogg_path

            except Exception as e_gtts:
                logger.error(f"❌ gTTS também falhou: {e_gtts}")
                safe_remove(ogg_path) # Limpa lixo
                return None

        finally:
            # Sempre limpa o arquivo intermediário (MP3) para economizar espaço
            safe_remove(mp3_path)

    def _run_gtts(self, text: str, path: Path):
        """Executa a geração do Google Translate TTS (Síncrono)"""
        tts = gTTS(text=text, lang='pt', slow=False)
        tts.save(str(path))

    async def _convert_to_whatsapp_format(self, input_path: Path, output_path: Path):
        """
        Converte MP3 para OGG Opus (Formato nativo do WhatsApp).
        """
        cmd = [
            "ffmpeg",
            "-v", "quiet",          # Silencioso
            "-y",                   # Sobrescreve
            "-i", str(input_path),
            "-c:a", "libopus",      # Codec Opus
            "-b:a", "32k",          # Leve (economia de dados)
            "-ar", "24000",         # Sample rate bom para voz
            "-ac", "1",             # Mono
            "-application", "voip", # Otimização VOIP
            str(output_path),
        ]

        async with self._semaphore:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )

                _, stderr = await asyncio.wait_for(process.communicate(), timeout=15)

                if process.returncode != 0:
                    err_msg = stderr.decode().strip() if stderr else "Erro desconhecido"
                    raise VoiceServiceException(f"FFmpeg falhou: {err_msg}")

            except asyncio.TimeoutError:
                if process:
                    try: process.kill()
                    except: pass
                raise VoiceServiceException("Timeout na conversão de áudio.")

# Singleton
voice_service = VoiceService()