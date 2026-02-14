"""
Serviço de Inteligência Artificial Híbrido.
Ouvido: Groq (Whisper)
Cérebro: Groq (llama-3.3-70b-versatile)
Memória: Persistência em Arquivo JSON (Resistente a reinicializações do Docker)
"""
import pathlib
import os
import json
from openai import AsyncOpenAI
from app.config import settings
from app.utils.logger import setup_logger
from app.utils.retry_handler import retry_with_backoff, get_retryable_exceptions
from .appointment import AppointmentService

logger = setup_logger(__name__)

class BrainService:
    """
    Gerenciador de raciocínio, audição e memória persistente.
    """

    # Prompt de Vendas
    SYSTEM_PROMPT = """
    Você é o Alex, um SDR sênior e consultor da 'TechSolutions'.
    
    OBJETIVO PRINCIPAL:
    Conversar naturalmente com o lead para entender suas necessidades e, se fizer sentido, agendar uma reunião.
    
    SERVIÇOS DA EMPRESA:
    - Desenvolvimento de software personalizado
    - Consultoria em tecnologia da informação
    - Segurança cibernética
    - Análise de dados e inteligência de negócios
    - Automação de processos
    - Gestão de projetos e inovação digital
    
    DIRETRIZES IMPORTANTES:
    1. Responda SOMENTE perguntas relacionadas aos serviços da TechSolutions.
    2. Se o usuário perguntar sobre algo fora do escopo da TechSolutions, informe educadamente que você só pode ajudar com assuntos relacionados à empresa.
    3. Responda de forma fluida e humana (varie o vocabulário, evite repetir vícios de linguagem como 'tá bom' em toda frase).
    4. Seja conciso, mas entregue valor (respostas ideais entre 1 a 3 frases).
    5. Use tom profissional mas acolhedor.
    6. NUNCA use emojis.
    7. Sempre mantenha a conversa viva com uma pergunta relevante no final.
    8. Jamais responda perguntas sobre outros assuntos (história, geografia, ciência, etc.)
    """

    def __init__(self):
        # 1. Configura o CÉREBRO (Texto -> Texto)
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
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        
        if self.groq_api_key:
            self.client_ear = AsyncOpenAI(
                api_key=self.groq_api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            logger.info("👂 Ouvido ativado: Whisper via Groq.")
        else:
            self.client_ear = None
            logger.warning("⚠️ Chave GROQ_API_KEY não encontrada. Modo surdo.")

        # 3. Configura o SERVIÇO DE AGENDAMENTO
        self.appointment_service = AppointmentService()
        
        # --- MEMÓRIA PERSISTENTE (JSON) ---
        # Carrega o histórico do arquivo ao iniciar
        self.history_file = pathlib.Path("chat_history.json")
        self.sessions = self._load_memory()

    def _load_memory(self) -> dict:
        """Carrega histórico do disco se existir"""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"📂 Memória carregada: {len(data)} conversas recuperadas.")
                    return data
            except Exception as e:
                logger.error(f"⚠️ Erro ao carregar memória (iniciando vazia): {e}")
        return {}

    def _save_memory(self):
        """Salva histórico no disco"""
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Erro ao salvar memória: {e}")

    def _update_memory(self, remote_jid: str, role: str, content: str):
        """Atualiza memória e salva no disco imediatamente"""
        if remote_jid not in self.sessions:
            self.sessions[remote_jid] = []
        
        # Adiciona nova mensagem ao histórico
        self.sessions[remote_jid].append({"role": role, "content": content})
        
        # Mantém apenas as últimas 20 interações (Janela de Contexto)
        if len(self.sessions[remote_jid]) > 20:
            self.sessions[remote_jid] = self.sessions[remote_jid][-20:]
            
        # Persiste a alteração no arquivo
        self._save_memory()

    def _is_off_topic_request(self, user_text: str) -> bool:
        """
        Detecta se a mensagem do usuário é sobre um assunto fora do escopo da TechSolutions
        """
        user_text_lower = user_text.lower()
        
        # Palavras-chave comuns em perguntas fora do escopo
        off_topic_keywords = [
            # Perguntas gerais
            "quem foi", "quem descobriu", "por que o brasil", "história do brasil", 
            "quando foi", "o que foi", "como surgiu", "qual a origem",
            
            # Assuntos acadêmicos
            "matéria de", "estudar ", "escola", "professor", "prova", "trabalho de ",
            
            # Assuntos pessoais não relacionados ao negócio
            "namorar", "casar", "casamento", "filhos", "família", "relacionamento",
            
            # Assuntos não empresariais
            "política", "eleição", "governador", "prefeito", "presidente",
            
            # Assuntos não relacionados à tecnologia/negócios
            "culinária", "receita", "comida", "filme", "música", "esporte",
            
            # Perguntas sobre a própria IA (se o usuário mencionar que está sendo atendido por um bot)
            "você é um bot", "você é humano", "quem criou você", "inteligência artificial",
        ]
        
        # Verifica se alguma palavra-chave está presente no texto
        for keyword in off_topic_keywords:
            if keyword in user_text_lower:
                return True
        
        # Verifica padrões de perguntas comuns fora do escopo
        question_patterns = [
            "quem foi ", "quem descobriu ", "quem inventou ", "quem criou ",
            "quando foi ", "como surgiu ", "qual a origem ", "de onde veio ",
            "o que é ", "o que foi ", "historia de ", "história de "
        ]
        
        for pattern in question_patterns:
            if pattern in user_text_lower:
                return True
                
        return False

    def _generate_off_topic_response(self) -> str:
        """
        Gera uma resposta educada para quando o usuário faz perguntas fora do escopo
        """
        responses = [
            "Desculpe, mas só posso ajudar com informações sobre os serviços da TechSolutions. Posso te ajudar com algo relacionado à tecnologia da informação, desenvolvimento de software, consultoria ou automação de processos?",
            "Essa pergunta está fora do meu campo de atuação. Sou assistente da TechSolutions e posso te ajudar com nossos serviços de tecnologia. Gostaria de saber mais sobre como podemos ajudar o seu negócio?",
            "Infelizmente não posso responder sobre esse assunto. Estou aqui para apresentar os serviços da TechSolutions. Tem interesse em soluções de TI, consultoria ou automação?",
            "Só posso fornecer informações sobre os serviços da TechSolutions. Somos especializados em desenvolvimento de software, consultoria em TI, segurança cibernética e automação de processos. Gostaria de saber mais sobre algum desses serviços?"
        ]
        
        # Retorna uma resposta aleatória para variar
        import random
        return random.choice(responses)

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        exceptions=get_retryable_exceptions() + (Exception,)
    )
    async def transcribe_audio(self, audio_path: str) -> str:
        """
        Transcreve o áudio usando Groq Whisper.
        """
        if not self.client_ear:
            logger.warning("Simulando audição (Sem chave Groq)")
            return "Olá, gostaria de saber mais."

        try:
            path_obj = pathlib.Path(audio_path)
            if not path_obj.exists():
                logger.error(f"Arquivo de áudio não existe: {audio_path}")
                return ""

            with open(path_obj, "rb") as audio_file:
                transcription = await self.client_ear.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3", 
                    response_format="text",
                    language="pt" 
                )
            
            text_result = str(transcription).strip()
            logger.info(f"🗣️ Transcrição Real: {text_result}")
            return text_result

        except Exception as e:
            logger.error(f"❌ Erro na transcrição (Groq): {e}")
            return ""

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        exceptions=get_retryable_exceptions() + (Exception,)
    )
    async def process_audio_and_respond(self, audio_path: str | pathlib.Path, remote_jid: str) -> str:
        """
        Pipeline: Ouvir -> Carregar Contexto -> Pensar -> Salvar Contexto
        """
        try:
            # 1. Ouvir (Transcrição)
            user_text = await self.transcribe_audio(str(audio_path))
            
            if not user_text or len(user_text) < 2: 
                return "Oi, não consegui te ouvir direito. Pode mandar de novo?"

            # 2. Verificar se a solicitação está fora do escopo antes de processar pela IA
            if self._is_off_topic_request(user_text):
                off_topic_response = self._generate_off_topic_response()
                self._update_memory(remote_jid, "assistant", off_topic_response)
                logger.info(f"🎯 Resposta fora do escopo para {remote_jid}: {off_topic_response}")
                return off_topic_response

            # 3. Verificar intenção de agendamento antes de processar pela IA
            scheduling_response = await self.appointment_service.handle_appointment_request(type('obj', (object,), {'body': user_text})())
            if scheduling_response:
                # Adiciona resposta de agendamento ao histórico e retorna
                self._update_memory(remote_jid, "assistant", scheduling_response)
                logger.info(f"📅 Resposta de agendamento enviada: {scheduling_response}")
                # Retorna a resposta com um prefixo especial para indicar que é uma resposta de agendamento
                return f"[SCHEDULING_RESPONSE]{scheduling_response}"

            # 4. Atualizar Memória com a fala do usuário
            self._update_memory(remote_jid, "user", user_text)

            # 5. Construir Contexto para a IA
            messages_payload = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            
            if remote_jid in self.sessions:
                messages_payload.extend(self.sessions[remote_jid])

            # 6. Pensar (Envia histórico completo)
            response = await self.client_brain.chat.completions.create(
                model=self.model_brain,
                messages=messages_payload,
                temperature=0.6,
                max_tokens=150
            )

            reply = response.choices[0].message.content
            
            # Limpeza da resposta
            clean_reply = reply.strip().replace('"', '').replace("*", "")
            
            # 7. Atualizar Memória com a resposta do Bot
            self._update_memory(remote_jid, "assistant", clean_reply)
            
            logger.info(f"🧠 Cérebro Respondeu: {clean_reply}")
            return clean_reply

        except Exception as e:
            logger.error(f"❌ Erro no cérebro: {e}", exc_info=True)
            return "Oi! Tive um problema técnico. Pode repetir o áudio?"

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        exceptions=get_retryable_exceptions() + (Exception,)
    )
    async def process_text_and_respond(self, user_text: str, remote_jid: str) -> str:
        """
        Processa mensagem de texto diretamente, sem necessidade de transcrição.
        """
        try:
            if not user_text or len(user_text) < 2: 
                return "Oi, não consegui entender direito. Pode repetir?"

            # 1. Verificar se a solicitação está fora do escopo antes de processar pela IA
            if self._is_off_topic_request(user_text):
                off_topic_response = self._generate_off_topic_response()
                self._update_memory(remote_jid, "assistant", off_topic_response)
                logger.info(f"🎯 Resposta fora do escopo para {remote_jid}: {off_topic_response}")
                return off_topic_response

            # 2. Verificar intenção de agendamento antes de processar pela IA
            scheduling_response = await self.appointment_service.handle_appointment_request(type('obj', (object,), {'body': user_text})())
            if scheduling_response:
                # Adiciona resposta de agendamento ao histórico e retorna
                self._update_memory(remote_jid, "assistant", scheduling_response)
                logger.info(f"📅 Resposta de agendamento enviada: {scheduling_response}")
                # Retorna a resposta com um prefixo especial para indicar que é uma resposta de agendamento
                return f"[SCHEDULING_RESPONSE]{scheduling_response}"

            # 3. Atualizar Memória com a mensagem do usuário
            self._update_memory(remote_jid, "user", user_text)

            # 4. Construir Contexto para a IA
            messages_payload = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            
            if remote_jid in self.sessions:
                messages_payload.extend(self.sessions[remote_jid])

            # 5. Pensar (Envia histórico completo)
            response = await self.client_brain.chat.completions.create(
                model=self.model_brain,
                messages=messages_payload,
                temperature=0.6,
                max_tokens=150
            )

            reply = response.choices[0].message.content
            
            # Limpeza da resposta
            clean_reply = reply.strip().replace('"', '').replace("*", "")
            
            # 6. Atualizar Memória com a resposta do Bot
            self._update_memory(remote_jid, "assistant", clean_reply)
            
            logger.info(f"🧠 Cérebro Respondeu (texto): {clean_reply}")
            return clean_reply

        except Exception as e:
            logger.error(f"❌ Erro no cérebro (texto): {e}", exc_info=True)
            return "Oi! Tive um problema técnico. Pode repetir a mensagem?"

# Singleton
brain_service = BrainService()