from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import Literal

class Settings(BaseSettings):
    """
    Configurações Universais (Groq LLM + Evolution API v2).
    """
    
    # Controle de Ambiente
    environment: Literal["development", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Evolution API
    evolution_api_url: str = Field(..., description="URL base da Evolution API")
    evolution_api_key: str = Field(..., description="Global API Key para autenticação")
    evolution_instance_name: str = Field(..., description="Nome da instância na Evolution")
    
    # LLM (Groq Compatible API)
    # URL Base da Groq
    openai_base_url: str = Field(default="https://api.groq.com/openai/v1/", description="URL Base do LLM")
    openai_api_key: str = Field(..., description="API Key da Groq")
    # Modelo llama-3.3-70b-versatile (Gratuito) via Groq
    openai_model: str = Field(default="llama-3.3-70b-versatile", description="Modelo a ser utilizado")
    
    # Voice (TTS)
    # Edge-TTS é o primário, gTTS entra como fallback se falhar
    edge_tts_voice: str = Field(default="pt-BR-AntonioNeural")
    
    # Tipo de resposta (áudio ou texto)
    response_type: Literal["audio", "text"] = Field(default="audio", description="Tipo de resposta enviada ao usuário")
    
    # Limites
    download_timeout: int = 60
    max_audio_size_mb: int = 16
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def evolution_headers(self) -> dict:
        return {
            "apikey": self.evolution_api_key,
            "Content-Type": "application/json"
        }
    
    # --- CORREÇÃO DE SEGURANÇA PARA WINDOWS ---
    @validator("*", pre=True)
    def strip_whitespace(cls, v):
        """Remove espaços invisíveis (\r, \n, spaces) de todas as strings"""
        if isinstance(v, str):
            return v.strip()
        return v

    @validator("evolution_api_url", "openai_base_url")
    def clean_url(cls, v):
        """Garante que URLs não terminem com barra /"""
        return v.rstrip("/") if isinstance(v, str) else v

settings = Settings()