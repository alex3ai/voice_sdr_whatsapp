"""
Exceções customizadas para o aplicativo.
"""

class ApiException(Exception):
    """Classe base para exceções de API."""
    def __init__(self, message: str, original_exception: Exception = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(f"{message}: {original_exception}" if original_exception else message)

class GeminiApiException(ApiException):
    """Exceções relacionadas à API do Gemini."""
    pass

class EvolutionApiException(ApiException):
    """Exceções relacionadas à API da Evolution."""
    pass

class VoiceServiceException(Exception):
    """Exceções relacionadas ao serviço de voz (TTS/FFmpeg)."""
    pass
