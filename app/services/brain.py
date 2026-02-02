"""
Serviço de Inteligência Artificial usando Google Gemini.
Implementação 100% Assíncrona com Fallback e Leitura não-bloqueante.
"""
import aiofiles
import pathlib
from typing import Optional

from google import genai
from google.api_core import exceptions as google_exceptions
from google.genai import types

from app.config import settings
from app.utils.exceptions import GeminiApiException
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
            # Retornar uma mensagem padrão para o usuário final
            return "Ops, não encontrei o arquivo de áudio que você enviou."

        try:
            # 1. Leitura não-bloqueante do disco (usando aiofiles)
            async with aiofiles.open(path_obj, "rb") as f:
                audio_bytes = await f.read()

            file_size_kb = len(audio_bytes) / 1024

            # Validação simples para economizar API
            if len(audio_bytes) < 100:
                logger.warning("Áudio vazio ou muito curto ignorado.")
                return "Não consegui te ouvir, o áudio ficou mudo. Pode repetir?"

            logger.info(f"Enviando {file_size_kb:.1f}KB para o Gemini...")

            # 2. Tenta modelo primário com lógica de fallback interna
            response = await self._try_models_with_fallback(audio_bytes)

            return response

        except GeminiApiException as e:
            # Erro já logado na camada da API, aqui apenas tratamos o fluxo
            logger.error(f"Falha na comunicação com a API do Gemini: {e}")
            return self._get_fallback_message()
        except Exception as e:
            logger.error(f"Erro inesperado no pipeline do Brain: {e}", exc_info=True)
            return self._get_fallback_message()

    async def _try_models_with_fallback(self, audio_bytes: bytes) -> str:
        """Tenta o modelo primário e, em caso de falha, aciona o fallback."""
        try:
            # Tenta o modelo atual (que pode ser primário ou fallback)
            return await self._call_gemini_api(audio_bytes, self._current_model)
        except GeminiApiException as e:
            logger.warning(
                f"Modelo {self._current_model} falhou. Tentando fallback para {self.fallback_model}..."
            )
            # Se o modelo atual (primário) falhou, tenta o fallback
            if self._current_model == self.primary_model:
                try:
                    response = await self._call_gemini_api(
                        audio_bytes, self.fallback_model
                    )
                    # Se o fallback funcionar, define-o como o modelo atual
                    self._current_model = self.fallback_model
                    logger.info(
                        f"Sucesso com o fallback. Novo modelo padrão: {self.fallback_model}"
                    )
                    return response
                except GeminiApiException as fallback_e:
                    logger.critical(
                        f"Modelo de fallback ({self.fallback_model}) também falhou. {fallback_e}"
                    )
                    raise fallback_e  # Relança a exceção do fallback
            # Se o modelo que falhou já era o fallback, apenas relança a exceção
            raise e

    async def _call_gemini_api(
        self, audio_bytes: bytes, model: str
    ) -> str:
        """
        Realiza a chamada à API do Google e encapsula os erros.
        Lança GeminiApiException em caso de falha.
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text="Responda a este áudio como Alex."),
                            types.Part.from_bytes(
                                data=audio_bytes, mime_type="audio/ogg"
                            ),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=200,  # Mantém resposta curta
                ),
            )

            if response and response.text:
                clean_text = response.text.strip()
                logger.info(f"🤖 Resposta gerada ({len(clean_text)} chars)")
                return clean_text

            # Se a resposta for vazia mas não houve exceção
            raise GeminiApiException("A API do Gemini retornou uma resposta vazia.")

        except (
            google_exceptions.GoogleAPICallError,
            google_exceptions.RetryError,
            Exception,
        ) as e:
            error_message = f"Erro na chamada à API Gemini ({model})"
            logger.error(f"{error_message}: {e}")
            raise GeminiApiException(error_message, original_exception=e)

    @staticmethod
    def _get_fallback_message() -> str:
        """Mensagem segura quando a IA está indisponível."""
        return "Tive um problema técnico para processar seu áudio. Você poderia, por favor, tentar novamente ou escrever sua mensagem?"


# Singleton
brain_service = BrainService()