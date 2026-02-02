"""
Serviço de Inteligência Artificial usando Google Gemini.
Implementação 100% Assíncrona com Fallback e Leitura não-bloqueante.
"""
import aiofiles
import pathlib
from typing import Optional

# Certifique-se de ter instalado: pip install google-genai
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from app.config import settings
from app.utils.exceptions import GeminiApiException
from app.utils.logger import logger


class BrainService:
    """
    Gerenciador de raciocínio (IA) com estratégia de redundância.
    """

    # Prompt do sistema atualizado com a personalidade de vendas
    SYSTEM_PROMPT = """
Você é o 'Alex', um consultor de vendas sênior da 'TechSolutions Brasil'.
Seu objetivo é qualificar leads e agendar demonstrações.

**Regras de Comportamento:**
1. Responda de forma curta, natural e persuasiva (máximo 2 frases).
2. Use linguagem falada (pode usar "tá bom", "né", "olha só").
3. Jamais invente preços, diga que depende do projeto.
4. Se o cliente perguntar preço, tente agendar uma reunião.
5. IMPORTANTE: Sua saída será convertida em áudio. Não use emojis, listas, markdown (*negrito*) ou caracteres especiais. Apenas texto puro.
"""

    def __init__(self):
        try:
            # Inicializa o cliente do Google GenAI (SDK v1.0+)
            self.client = genai.Client(api_key=settings.gemini_api_key)

            # Estratégia de Modelos (Primary -> Fallback)
            # Ex: Primary = "gemini-2.0-flash-exp", Fallback = "gemini-1.5-flash"
            self.primary_model = settings.gemini_model_primary
            self.fallback_model = settings.gemini_model_fallback
            self._current_model = self.primary_model

            logger.info(
                f"🧠 Brain inicializado. Modelo Principal: {self._current_model}"
            )
        except Exception as e:
            logger.critical(f"Falha crítica ao iniciar BrainService: {e}")
            raise

    async def process_audio_and_respond(
        self, audio_path: pathlib.Path | str
    ) -> str:
        """
        Lê o arquivo de áudio e solicita resposta à IA.
        """
        path_obj = pathlib.Path(audio_path)

        if not path_obj.exists():
            logger.error(f"Arquivo de áudio não encontrado: {audio_path}")
            return "Ops, tive um erro técnico e não encontrei seu áudio."

        try:
            # 1. Leitura não-bloqueante do disco (Vital para FastAPI)
            async with aiofiles.open(path_obj, "rb") as f:
                audio_bytes = await f.read()

            file_size_kb = len(audio_bytes) / 1024

            # Validação simples
            if len(audio_bytes) < 100:
                logger.warning("Áudio vazio ou muito curto ignorado.")
                return "Não consegui te ouvir, o áudio ficou mudo. Pode repetir?"

            logger.info(f"Enviando {file_size_kb:.1f}KB para o Gemini...")

            # 2. Tenta processar com fallback automático
            response = await self._try_models_with_fallback(audio_bytes)

            return response

        except GeminiApiException as e:
            logger.error(f"Falha na comunicação com a API do Gemini: {e}")
            return self._get_fallback_message()
        except Exception as e:
            logger.error(f"Erro inesperado no pipeline do Brain: {e}", exc_info=True)
            return self._get_fallback_message()

    async def _try_models_with_fallback(self, audio_bytes: bytes) -> str:
        """Tenta o modelo primário e, em caso de falha, aciona o fallback."""
        try:
            return await self._call_gemini_api(audio_bytes, self._current_model)
        except GeminiApiException as e:
            logger.warning(
                f"Modelo {self._current_model} falhou. Tentando fallback para {self.fallback_model}..."
            )
            
            # Se já estávamos no fallback e falhou, não tem o que fazer
            if self._current_model == self.fallback_model:
                raise e

            # Tenta mudar para o fallback
            try:
                response = await self._call_gemini_api(
                    audio_bytes, self.fallback_model
                )
                # Se funcionar, mantemos o fallback como padrão temporariamente ou apenas retornamos
                # Aqui opto por apenas retornar para tentar o primário na próxima (failback strategy)
                logger.info(f"Sucesso com o fallback ({self.fallback_model}).")
                return response
            except GeminiApiException as fallback_e:
                logger.critical(f"Modelo de fallback também falhou: {fallback_e}")
                raise fallback_e

    async def _call_gemini_api(
        self, audio_bytes: bytes, model: str
    ) -> str:
        """
        Realiza a chamada à API usando envio de bytes (Inline Data).
        """
        try:
            # SDK v1.0+ structure
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text="O cliente enviou este áudio. Responda seguindo suas instruções."),
                            types.Part.from_bytes(
                                data=audio_bytes, 
                                mime_type="audio/ogg" # OGG é o padrão do WhatsApp
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.6, # Levemente mais criativo, mas controlado
                    max_output_tokens=150, # Respostas curtas para áudio
                ),
            )

            if response and response.text:
                clean_text = response.text.strip()
                logger.info(f"🤖 Resposta gerada ({len(clean_text)} chars)")
                return clean_text

            raise GeminiApiException("A API do Gemini retornou uma resposta vazia.")

        except Exception as e:
            # Captura erros genéricos do Google e encapsula
            error_message = f"Erro na chamada à API Gemini ({model})"
            logger.error(f"{error_message}: {e}")
            raise GeminiApiException(error_message, original_exception=e)

    @staticmethod
    def _get_fallback_message() -> str:
        return "Tive um problema técnico para processar seu áudio. Pode escrever, por favor?"

# Singleton
brain_service = BrainService()