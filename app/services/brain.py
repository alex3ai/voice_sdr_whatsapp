"""
Serviço de Inteligência Artificial usando Google Gemini.
Implementação 100% Assíncrona com Fallback e Leitura não-bloqueante.
"""
from google import genai
from google.genai import types
import aiofiles
import pathlib
from typing import Optional
from app.config import settings
from app.utils.logger import logger

class BrainService:
    """
    Gerenciador de raciocínio (IA) com estratégia de redundância.
    """
    
    # Prompt do sistema: Define a personalidade do SDR
    SYSTEM_PROMPT = """
Você é o 'Alex', um consultor de vendas experiente da 'TechSolutions Brasil'.

**Sua missão:**
- Ouvir a dúvida do cliente no áudio.
- Responder de forma clara, curta (máx 3 frases) e persuasiva.
- Focar em qualificar o lead para uma demonstração.

**Regras:**
1. Linguagem natural de WhatsApp (coloquial, educada, sem gírias pesadas).
2. NUNCA use formatação markdown (negrito, itálico) - isso quebra o TTS.
3. Se o áudio for inaudível, peça educadamente para repetir.
4. Se o cliente perguntar preço, diga que depende do perfil e sugira uma call rápida.
"""

    def __init__(self):
        try:
            # Inicializa o cliente do Google GenAI
            self.client = genai.Client(api_key=settings.gemini_api_key)
            
            # Estratégia de Modelos (Primary -> Fallback)
            self.primary_model = settings.gemini_model_primary
            self.fallback_model = settings.gemini_model_fallback
            self._current_model = self.primary_model
            
            logger.info(f"🧠 Brain inicializado. Modelo Principal: {self._current_model}")
        except Exception as e:
            logger.critical(f"Falha crítica ao iniciar BrainService: {e}")
            raise

    async def process_audio_and_respond(self, audio_path: pathlib.Path | str) -> Optional[str]:
        """
        Lê o arquivo de áudio e solicita resposta à IA.
        """
        path_obj = pathlib.Path(audio_path)
        
        if not path_obj.exists():
            logger.error(f"Arquivo de áudio não encontrado: {audio_path}")
            return None

        try:
            # 1. Leitura não-bloqueante do disco (usando aiofiles)
            async with aiofiles.open(path_obj, 'rb') as f:
                audio_bytes = await f.read()

            file_size_kb = len(audio_bytes) / 1024
            
            # Validação simples para economizar API
            if len(audio_bytes) < 100:
                logger.warning("Áudio vazio ou muito curto ignorado.")
                return "Não consegui te ouvir, o áudio ficou mudo. Pode repetir?"

            logger.info(f"Enviando {file_size_kb:.1f}KB para o Gemini...")

            # 2. Tenta modelo primário
            response = await self._call_gemini_async(audio_bytes, self._current_model)

            # 3. Lógica de Retry/Fallback
            if not response and self._current_model == self.primary_model:
                logger.warning(f"Modelo {self.primary_model} falhou. Tentando fallback para {self.fallback_model}...")
                response = await self._call_gemini_async(audio_bytes, self.fallback_model)
                
                # Se funcionar no fallback, mantemos ele como atual por um tempo (Circuit Breaker simples)
                if response:
                    self._current_model = self.fallback_model

            if response:
                return response
            
            return self._get_fallback_message()

        except Exception as e:
            logger.error(f"Erro no pipeline do Brain: {e}", exc_info=True)
            return self._get_fallback_message()

    async def _call_gemini_async(self, audio_bytes: bytes, model: str) -> Optional[str]:
        """Chamada assíncrona à API do Google."""
        try:
            # NOTA: O SDK v0.8+ usa client.aio para chamadas async
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text="Responda a este áudio como Alex."),
                            types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg")
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=200, # Mantém resposta curta
                )
            )

            if response and response.text:
                clean_text = response.text.strip()
                logger.info(f"🤖 Resposta gerada ({len(clean_text)} chars)")
                return clean_text
            
            return None

        except Exception as e:
            logger.error(f"Erro na API Gemini ({model}): {e}")
            return None

    @staticmethod
    def _get_fallback_message() -> str:
        """Mensagem segura quando a IA está indisponível."""
        return "Tive um problema técnico para ouvir seu áudio. Pode escrever por texto rapidinho?"

# Singleton
brain_service = BrainService()