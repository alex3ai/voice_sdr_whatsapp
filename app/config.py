from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator
from typing import Literal

class Settings(BaseSettings):
    """
    Configurações da aplicação com validação rigorosa.
    Une a estrutura do Claude com a segurança do Gemini.
    """
    
    # Controle de Ambiente
    environment: Literal["development", "production"] = Field(default="development")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # Meta WhatsApp (Segurança Crítica)
    whatsapp_token: str = Field(..., min_length=50, description="Token de acesso da WhatsApp API")
    phone_number_id: str = Field(..., min_length=10, description="ID do número de telefone")
    verify_token: str = Field(..., min_length=8, description="Token de verificação do webhook")
    # AQUI ESTA A CORREÇÃO: app_secret é OBRIGATÓRIO (Removido Optional)
    app_secret: str = Field(..., min_length=10, description="Secret do app Meta para validação HMAC")
    
    # Google Gemini
    gemini_api_key: str = Field(..., min_length=30, description="Chave da API do Gemini")
    gemini_model_primary: str = Field(default="gemini-2.0-flash-exp", description="Modelo IA Primário")
    gemini_model_fallback: str = Field(default="gemini-1.5-flash", description="Modelo IA Fallback")
    
    # Servidor
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1024, le=65535)
    
    # Configurações de Voice
    edge_tts_voice: str = Field(default="pt-BR-AntonioNeural")
    
    # Timeouts e Limites (SRE/Performance)
    download_timeout: int = Field(default=30, description="Timeout download mídia (s)")
    gemini_timeout: int = Field(default=30, description="Timeout IA (s)")
    max_audio_size_mb: int = Field(default=16, description="Limite tamanho áudio")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False, # Permite escrever maiúsculo ou minúsculo no .env
        extra="ignore"
    )
    
    # --- Helpers (Do Claude, muito úteis) ---
    @property
    def whatsapp_api_url(self) -> str:
        return f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"
    
    @property
    def media_url_base(self) -> str:
        return "https://graph.facebook.com/v21.0"
    
    @property
    def whatsapp_headers(self) -> dict:
        """Retorna headers prontos para uso no httpx"""
        return {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json"
        }
    
    # --- Validadores ---
    @validator("gemini_api_key")
    def validate_gemini_key(cls, v):
        if "your" in v.lower() or "sua" in v.lower():
            raise ValueError("Erro: Você esqueceu de configurar a GEMINI_API_KEY real!")
        return v

# Singleton
settings = Settings()