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
    
    # Chave de API para proteger os endpoints
    api_key: str = Field(default="", description="Chave de API para proteger os endpoints da aplicação")
    
    # App Secret para validação de webhooks (Meta)
    app_secret: str = Field(default="", description="App secret para validação de webhooks da Meta")
    
    # LLM (Groq Compatible API)
    # URL Base da Groq
    openai_base_url: str = Field(default="https://api.groq.com/openai/v1/", description="URL Base do LLM")
    openai_api_key: str = Field(..., description="API Key da Groq")
    # Modelo llama-3.3-70b-versatile (Gratuito) via Groq
    openai_model: str = Field(default="llama-3.3-70b-versatile", description="Modelo a ser utilizado")
    
    # Voice (TTS)
    # Edge-TTS é o primário, gTTS entra como fallback se falhar
    edge_tts_voice: str = Field(default="pt-BR-AntonioNeural")
    
    # Azure TTS (opcional - usado como fallback após Edge-TTS)
    azure_tts_subscription_key: str = Field(default="", description="Chave de assinatura do Azure TTS")
    azure_tts_region: str = Field(default="brazilsouth", description="Região do Azure TTS")
    azure_tts_voice_name: str = Field(default="pt-BR-AntonioNeural", description="Nome da voz do Azure TTS")
    
    # Tipo de resposta (áudio ou texto)
    response_type: Literal["audio", "text"] = Field(default="audio", description="Tipo de resposta enviada ao usuário")

    # Link de agendamento
    calendar_link: str = Field(default="", description="Link para o sistema de agendamento (Calendly, Google Agenda, etc)")
    
    # Runtime Environment
    runtime_env: Literal["local", "docker", "production"] = Field(default="local", description="Ambiente de execução para ajustar configurações dinâmicas")

    # Database Connection (for metrics)
    database_host: str = Field(default="localhost", description="Host do banco de dados PostgreSQL (use 'host.docker.internal' se estiver rodando em Docker)")
    database_port: int = Field(default=5432, description="Porta do banco de dados PostgreSQL")
    database_user: str = Field(default="evolution", description="Usuário do banco de dados")
    database_password: str = Field(default="evolution", description="Senha do banco de dados")
    database_name: str = Field(default="evolution", description="Nome do banco de dados")
    
    # Limites
    download_timeout: int = 60
    max_audio_size_mb: int = 16

    # Configurações de notificação
    notification_type: Literal["console", "file", "webhook"] = Field(default="console", description="Tipo de notificação para erros críticos")
    notification_log_file_path: str = Field(default="notifications.log", description="Caminho do arquivo de log de notificação")
    notification_webhook_url: str = Field(default="", description="Webhook para notificação de erros críticos")

    # Rate limiting
    rate_limit_max_requests: int = Field(default=10, description="Número máximo de requisições por janela de tempo")
    rate_limit_window_seconds: int = Field(default=60, description="Janela de tempo para rate limiting em segundos")

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
    
    @property
    def database_connection_uri(self) -> str:
        """Retorna a URI de conexão com o banco de dados"""
        return f"postgresql://{self.database_user}:{self.database_password}@{self.database_host}:{self.database_port}/{self.database_name}"

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

# Instanciação do objeto settings
settings = Settings()