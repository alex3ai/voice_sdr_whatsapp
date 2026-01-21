from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import Literal

class Settings(BaseSettings):
    """
    Configurações da aplicação adaptadas para Evolution API v2.
    """
    
    # Controle de Ambiente (Usado pelo Logger)
    environment: Literal["development", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Evolution API (Gateway WhatsApp)
    evolution_api_url: str = Field(..., description="URL base da Evolution API")
    evolution_api_key: str = Field(..., description="Global API Key para autenticação")
    evolution_instance_name: str = Field(..., description="Nome da instância na Evolution")
    
    # Google Gemini (IA)
    gemini_api_key: str = Field(..., min_length=30)
    gemini_model_primary: str = Field(default="gemini-2.0-flash-exp")
    gemini_model_fallback: str = Field(default="gemini-1.5-flash")
    
    # Voice (TTS)
    edge_tts_voice: str = Field(default="pt-BR-AntonioNeural")
    
    # Limites e Timeouts (SRE)
    download_timeout: int = 30
    gemini_timeout: int = 30
    max_audio_size_mb: int = 16
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def evolution_headers(self) -> dict:
        """
        Headers para autenticação na Evolution.
        Usa a Global API Key.
        """
        return {
            "apikey": self.evolution_api_key,
            "Content-Type": "application/json"
        }
    
    @validator("gemini_api_key")
    def validate_gemini_key(cls, v):
        if "your" in v.lower() or "sua" in v.lower() or "XXX" in v:
            raise ValueError("Erro: Configure uma GEMINI_API_KEY válida!")
        return v

    @validator("evolution_api_url")
    def clean_url(cls, v):
        """Remove barra no final para evitar URL malformada (ex: url//message)"""
        return v.rstrip("/")

settings = Settings()