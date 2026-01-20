import asyncio
import shutil
import edge_tts
from pathlib import Path
from typing import Optional
from app.config import settings
from app.utils.logger import logger
from app.utils.files import get_temp_filename, safe_remove

class VoiceService:
    """
    Gerenciador de síntese de voz (TTS) e conversão de áudio.
    Otimizado para alta concorrência com controle de recursos via Semáforo.
    """
    
    def __init__(self):
        self.voice = settings.edge_tts_voice
        self._verify_dependency()
        
        # SRE: Limita a 3 conversões simultâneas para evitar CPU Throttling no Docker
        # FFmpeg é CPU-intensive. Não queremos bloquear o Event Loop.
        self._semaphore = asyncio.Semaphore(3)

    def _verify_dependency(self):
        """Fail Fast: Verifica se o FFmpeg está instalado no PATH do sistema."""
        if not shutil.which("ffmpeg"):
            logger.critical("🚨 FFmpeg não encontrado! O serviço de voz não funcionará.")
            logger.critical("No Dockerfile, adicione: RUN apt-get install -y ffmpeg")
            # Não damos raise aqui para não crashar o app todo, mas o log avisa
        else:
            logger.info("✅ FFmpeg detectado e pronto para uso.")

    async def generate_audio(self, text: str) -> Optional[Path]:
        """
        Pipeline: Texto -> Edge-TTS (MP3) -> FFmpeg (OGG/Opus)
        """
        if not text:
            return None

        mp3_path = get_temp_filename("mp3", prefix="tts_raw")
        ogg_path = get_temp_filename("ogg", prefix="voice_final")

        try:
            # 1. Gera o áudio bruto (MP3)
            # Edge-TTS não bloqueia CPU significativamente, então ok sem semáforo
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(mp3_path))
            
            # 2. Converte para formato WhatsApp (Pesado)
            success = await self._convert_to_whatsapp_format(mp3_path, ogg_path)
            
            if success:
                return ogg_path
            else:
                safe_remove(ogg_path)
                return None

        except Exception as e:
            logger.error(f"Erro na geração de voz: {e}")
            safe_remove(ogg_path)
            return None
            
        finally:
            # Limpeza imediata do arquivo intermediário
            safe_remove(mp3_path)

    async def _convert_to_whatsapp_format(self, input_path: Path, output_path: Path) -> bool:
        """
        Converte MP3 para OGG Opus (padrão WhatsApp Voice Note).
        Protegido por Semáforo e Timeout.
        """
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-c:a", "libopus",           # Codec Opcus
            "-b:a", "64k",               # Bitrate otimizado
            "-ar", "16000",              # 16kHz (Voz)
            "-ac", "1",                  # Mono
            "-application", "voip",      # Preset VOIP
            "-y",                        # Overwrite
            str(output_path)
        ]

        # SRE: Proteção de Concorrência
        async with self._semaphore:
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE
                )

                # SRE: Proteção de Timeout (evita processos zumbis)
                _, stderr = await asyncio.wait_for(process.communicate(), timeout=15)

                if process.returncode != 0:
                    err_msg = stderr.decode() if stderr else "Erro desconhecido"
                    logger.error(f"Falha no FFmpeg: {err_msg}")
                    return False
                
                return True

            except asyncio.TimeoutError:
                logger.error("Timeout na conversão de áudio (FFmpeg demorou >15s)")
                if process:
                    try:
                        process.kill() # Mata o processo travado
                    except ProcessLookupError:
                        pass
                return False
            except Exception as e:
                logger.error(f"Erro inesperado no FFmpeg: {e}")
                return False

# Singleton
voice_service = VoiceService()