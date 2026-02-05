"""
Serviço de Inteligência Artificial Híbrido.
Ouvido: Groq (Whisper) - Rápido e Gratuito.
Cérebro: OpenRouter (DeepSeek/Llama) - Inteligente.
"""
import pathlib
import os
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

class BrainService:
    """
    Gerenciador de raciocínio e audição.
    """

    # Prompt de Vendas
    SYSTEM_PROMPT = """
    Você é o Alex, um SDR sênior e consultor da 'TechSolutions'.
    
    Objetivo: 
    Conversar naturalmente com o lead para entender suas necessidades e, se fizer sentido, agendar uma reunião.
    
    Diretrizes de Personalidade:
    1. Responda de forma fluida e humana (varie o vocabulário, evite repetir vícios de linguagem como 'tá bom' em toda frase).
    2. Seja conciso, mas entregue valor (respostas ideais entre 1 a 3 frases).
    3. Use tom profissional mas acolhedor.
    4. NUNCA use emojis.
    5. Sempre mantenha a conversa viva com uma pergunta relevante no final.
    """

    def __init__(self):
        # 1. Configura o CÉREBRO (Texto -> Texto)
        # Usa as configurações do config.py (OpenRouter/DeepSeek)
        try:
            self.client_brain = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            self.model_brain = settings.openai_model
            logger.info(f"🧠 Cérebro conectado: {self.model_brain}")
        except Exception as e:
            logger.critical(f"Falha ao iniciar Cérebro: {e}")
            raise

        # 2. Configura o OUVIDO (Áudio -> Texto)
        # Usa a Groq Cloud (Whisper-large-v3) que é extremamente rápida
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        if self.groq_api_key:
            self.client_ear = AsyncOpenAI(
                api_key=self.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            logger.info("👂 Ouvido ativado: Whisper via Groq.")
        else:
            self.client_ear = None
            logger.warning("⚠️ Chave GROQ_API_KEY não encontrada no .env. O bot continuará 'fingindo' que ouviu.")

    async def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcreve o áudio usando Groq Whisper (Real) ou Fallback (Simulado).
        """
        # Modo Simulação (se não tiver chave)
        if not self.client_ear:
            logger.warning("Simulando audição (Adicione GROQ_API_KEY no .env para corrigir)")
            return "Olá, vi seu anúncio no Instagram e quero saber mais."

        # Modo Real (Groq)
        try:
            path_obj = pathlib.Path(audio_path)
            if not path_obj.exists():
                logger.error(f"Arquivo de áudio não existe: {audio_path}")
                return ""

            # Abre o arquivo e envia para a Groq
            with open(path_obj, "rb") as audio_file:
                transcription = await self.client_ear.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3", # Melhor modelo open-source atual
                    response_format="text",
                    language="pt" # Força português para evitar alucinações
                )
            
            text_result = str(transcription).strip()
            logger.info(f"🗣️ Transcrição Real: {text_result}")
            return text_result

        except Exception as e:
            logger.error(f"❌ Erro na transcrição (Groq): {e}")
            return ""

    async def process_audio_and_respond(self, audio_path: str | pathlib.Path) -> str:
        """
        Pipeline: Ouvir (Groq) -> Pensar (DeepSeek)
        """
        try:
            # 1. Ouvir
            user_text = await self.transcribe_audio(str(audio_path))
            
            # Se o áudio estava vazio ou inaudível
            if not user_text or len(user_text) < 2: 
                return "Oi, não consegui te ouvir direito. Pode mandar de novo?"

            # 2. Pensar
            response = await self.client_brain.chat.completions.create(
                model=self.model_brain,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_text}
                ],
                temperature=0.6,
                max_tokens=150
            )

            reply = response.choices[0].message.content
            
            # Limpeza
            clean_reply = reply.strip().replace('"', '').replace("*", "")
            
            logger.info(f"🧠 Cérebro Respondeu: {clean_reply}")
            return clean_reply

        except Exception as e:
            logger.error(f"❌ Erro no cérebro: {e}", exc_info=True)
            return "Oi! Tive um problema técnico. Pode repetir o áudio?"

# Singleton
brain_service = BrainService()