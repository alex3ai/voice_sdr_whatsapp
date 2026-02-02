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

        mp3_path = get_temp_filename("mp3", prefix="tts_raw")
        ogg_path = get_temp_filename("ogg", prefix="voice_final")

        try:
            # 1. Gera o áudio bruto (MP3) com Edge-TTS
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(mp3_path))
            logger.info("Etapa 1/2: Áudio MP3 gerado via Edge-TTS.")

            # 2. Converte para o formato OGG/Opus para WhatsApp
            await self._convert_to_whatsapp_format(mp3_path, ogg_path)
            logger.info("Etapa 2/2: Áudio convertido para OGG Opus com sucesso.")

            return ogg_path

        except Exception as e:
            # Limpa o arquivo OGG se a conversão falhou
            safe_remove(ogg_path)
            # Encapsula a exceção original para fornecer mais contexto
            error_msg = f"Falha no pipeline de geração de voz: {e}"
            logger.error(error_msg, exc_info=True)
            raise VoiceServiceException(error_msg, original_exception=e)

        finally:
            # Garante a limpeza do arquivo MP3 intermediário
            safe_remove(mp3_path)

    async def _convert_to_whatsapp_format(self, input_path: Path, output_path: Path):
        """
        Converte um arquivo de áudio para o formato OGG Opus usando FFmpeg.
        Lança VoiceServiceException em caso de erro.
        """
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-c:a", "libopus",
            "-b:a", "64k",
            "-ar", "16000",
            "-ac", "1",
            "-application", "voip",
            "-y",
            str(output_path),
        ]

        process = None
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
                    err_msg = stderr.decode().strip() if stderr else "Erro desconhecido no FFmpeg"
                    raise VoiceServiceException(f"FFmpeg falhou com código {process.returncode}: {err_msg}")

            except asyncio.TimeoutError as e:
                if process:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass  # O processo pode já ter terminado
                raise VoiceServiceException("Timeout de 15s excedido durante a conversão de áudio com FFmpeg.", original_exception=e)

            except Exception as e:
                # Captura outras exceções (ex: FileNotFoundError se ffmpeg não estiver no PATH)
                # e as encapsula.
                if isinstance(e, VoiceServiceException):
                    raise  # Re-lança a exceção já tratada
                raise VoiceServiceException(f"Erro inesperado durante a execução do FFmpeg.", original_exception=e)


# Singleton
voice_service = VoiceService()