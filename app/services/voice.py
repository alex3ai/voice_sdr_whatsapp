import asyncio
import shutil
from pathlib import Path

import edge_tts
from app.config import settings
from app.utils.exceptions import VoiceServiceException
from app.utils.files import get_temp_filename, safe_remove
from app.utils.logger import logger


class VoiceService:
    """
    Gerenciador de síntese de voz (TTS) e conversão de áudio.
    Otimizado para alta concorrência com controle de recursos via Semáforo.
    """

    def __init__(self):
        self.voice = settings.edge_tts_voice
        self._verify_dependency()

        # SRE: Limita a 3 conversões simultâneas para evitar CPU Throttling
        self._semaphore = asyncio.Semaphore(3)

    def _verify_dependency(self):
        """Fail Fast: Verifica se o FFmpeg está instalado."""
        if not shutil.which("ffmpeg"):
            error_msg = "FFmpeg não encontrado no PATH do sistema."
            logger.critical(f"🚨 {error_msg}")
            logger.critical("No Dockerfile, adicione: RUN apt-get install -y ffmpeg")
            raise VoiceServiceException(error_msg)
        else:
            logger.info("✅ FFmpeg detectado e pronto para uso.")

    async def generate_audio(self, text: str) -> Path:
        """
        Pipeline: Texto -> Edge-TTS (MP3) -> FFmpeg (OGG/Opus).
        Lança VoiceServiceException em caso de falha.
        """
        if not text:
            raise VoiceServiceException("O texto para geração de áudio não pode ser vazio.")

        # Garante que get_temp_filename retorne Path, se retornar str, converte
        mp3_path = Path(get_temp_filename(".mp3"))
        ogg_path = Path(get_temp_filename(".ogg"))

        try:
            # 1. Gera o áudio bruto (MP3) com Edge-TTS
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(mp3_path))
            
            # 2. Converte para o formato OGG/Opus para WhatsApp
            await self._convert_to_whatsapp_format(mp3_path, ogg_path)
            
            logger.info(f"🔊 Áudio gerado com sucesso: {ogg_path.name}")
            return ogg_path

        except Exception as e:
            # Limpa o arquivo OGG se a conversão falhou
            safe_remove(ogg_path)
            error_msg = f"Falha no pipeline de geração de voz: {e}"
            logger.error(error_msg)
            # Se for uma exceção nossa, relança. Se for genérica, encapsula.
            if isinstance(e, VoiceServiceException):
                raise
            raise VoiceServiceException(error_msg, original_exception=e)

        finally:
            # Garante a limpeza do arquivo MP3 intermediário (lixo)
            safe_remove(mp3_path)

    async def _convert_to_whatsapp_format(self, input_path: Path, output_path: Path):
        """
        Converte um arquivo de áudio para o formato OGG Opus usando FFmpeg.
        Executa em subprocesso para não bloquear o Event Loop do FastAPI.
        """
        # Parâmetros otimizados para Nota de Voz do WhatsApp
        cmd = [
            "ffmpeg",
            "-v", "quiet",          # Remove logs verbosos do ffmpeg
            "-y",                   # Sobrescreve se existir
            "-i", str(input_path),
            "-c:a", "libopus",      # Codec Opus (Nativo do WhatsApp)
            "-b:a", "32k",          # Bitrate (32k-64k é ideal para voz, economiza dados)
            "-ar", "24000",         # Sample rate (24khz dá mais brilho à voz que 16khz)
            "-ac", "1",             # Mono (WhatsApp voice notes são mono)
            "-application", "voip", # Otimização para voz
            str(output_path),
        ]

        process = None
        # Entra na fila do semáforo (máx 3 simultâneos)
        async with self._semaphore:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )

                # Timeout para evitar processos "zumbis"
                _, stderr = await asyncio.wait_for(process.communicate(), timeout=15)

                if process.returncode != 0:
                    err_msg = stderr.decode().strip() if stderr else "Erro desconhecido"
                    raise VoiceServiceException(f"FFmpeg falhou (Código {process.returncode}): {err_msg}")

            except asyncio.TimeoutError as e:
                if process:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                raise VoiceServiceException("Timeout de 15s excedido na conversão de áudio.", original_exception=e)

            except Exception as e:
                if isinstance(e, VoiceServiceException):
                    raise
                raise VoiceServiceException(f"Erro inesperado no FFmpeg: {e}", original_exception=e)


# Singleton
voice_service = VoiceService()