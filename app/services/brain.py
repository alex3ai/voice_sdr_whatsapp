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

    # from app.services.evolution import evolution_service

    async def process_audio_and_respond(self, audio_path: str | pathlib.Path, remote_jid: str) -> str:
        """
        Pipeline: Ouvir (Groq) -> Lembrar (Evolution) -> Pensar (DeepSeek)
        """
        try:
            # 1. Ouvir (Transcrição)
            user_text = await self.transcribe_audio(str(audio_path))
            
            if not user_text or len(user_text) < 2: 
                return "Oi, não consegui te ouvir direito. Pode mandar de novo?"

            # 2. Lembrar (Busca histórico na Evolution)
            # Importação local para evitar ciclo de importação circular, se necessário
            from app.services.evolution import evolution_service 
            
            history_data = await evolution_service.get_history(remote_jid, limit=5)
            
            # Formata histórico para o padrão OpenAI
            messages_context = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            
            for msg in history_data:
                # Filtra apenas texto/conversas válidas
                content = msg.get("message", {}).get("conversation") or \
                          msg.get("message", {}).get("extendedTextMessage", {}).get("text")
                
                if content:
                    role = "assistant" if msg["key"]["fromMe"] else "user"
                    messages_context.append({"role": role, "content": content})

            # Adiciona a mensagem atual do usuário
            messages_context.append({"role": "user", "content": user_text})

            # 3. Pensar (Envia tudo para a IA)
            response = await self.client_brain.chat.completions.create(
                model=self.model_brain,
                messages=messages_context, # Agora com histórico!
                temperature=0.6,
                max_tokens=150
            )

            reply = response.choices[0].message.content
            clean_reply = reply.strip().replace('"', '').replace("*", "")
            
            logger.info(f"🧠 Cérebro Respondeu (com contexto): {clean_reply}")
            return clean_reply

        except Exception as e:
            logger.error(f"❌ Erro no cérebro: {e}", exc_info=True)
            return "Oi! Tive um problema técnico. Pode repetir o áudio?"

# Singleton
brain_service = BrainService()