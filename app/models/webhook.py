"""
Modelos Pydantic para validação do webhook da Evolution API v2.
Evento: MESSAGES_UPSERT
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, Any

# --- Sub-modelos para o conteúdo da mensagem ---

class Key(BaseModel):
    """Identificadores da mensagem."""
    remoteJid: str = Field(..., description="ID do remetente (ex: 5511999999999@s.whatsapp.net)")
    fromMe: bool = Field(..., description="Se fui eu que enviei")
    id: str = Field(..., description="ID único da mensagem")

class AudioMessage(BaseModel):
    """Conteúdo de áudio."""
    url: Optional[str] = None  # URL para download direto (se configurado)
    mimetype: str = Field(..., description="Tipo do arquivo (audio/ogg, etc)")
    ptt: bool = Field(default=False, description="True se for nota de voz (Push To Talk)")
    seconds: Optional[int] = None

class ExtendedTextMessage(BaseModel):
    """Texto quando é uma resposta ou tem formatação."""
    text: str

class MessageContent(BaseModel):
    """
    O conteúdo real da mensagem.
    A chave muda dependendo do tipo (conversation, audioMessage, etc).
    """
    conversation: Optional[str] = None  # Texto simples
    extendedTextMessage: Optional[ExtendedTextMessage] = None  # Texto complexo
    audioMessage: Optional[AudioMessage] = None  # Áudio

    def get_text(self) -> Optional[str]:
        """Helper para extrair texto de qualquer formato."""
        if self.conversation:
            return self.conversation
        if self.extendedTextMessage:
            return self.extendedTextMessage.text
        return None

# --- Modelos Principais ---

class Data(BaseModel):
    """O payload principal de dados."""
    key: Key
    pushName: Optional[str] = Field(None, description="Nome de exibição do usuário")
    message: MessageContent
    messageType: str = Field(..., description="conversation, audioMessage, extendedTextMessage, etc")

class EvolutionWebhook(BaseModel):
    """
    Root Model para o Webhook da Evolution API v2.
    """
    event: str  # Ex: "MESSAGES_UPSERT"
    instance: str
    data: Data
    destination: Optional[str] = None
    date_time: str = Field(..., alias="date_time")
    sender: Optional[str] = None

    # --- Helpers para facilitar sua vida ---

    def is_from_me(self) -> bool:
        """Ignora mensagens enviadas pelo próprio bot."""
        return self.data.key.fromMe

    def get_sender_number(self) -> str:
        """
        Retorna apenas o número (sem @s.whatsapp.net).
        Ex: 5511999999999
        """
        jid = self.data.key.remoteJid
        return jid.split('@')[0] if '@' in jid else jid

    def get_audio_url(self) -> Optional[str]:
        """Retorna a URL do áudio se existir."""
        if self.data.message.audioMessage:
            return self.data.message.audioMessage.url
        return None

    def get_text_content(self) -> Optional[str]:
        return self.data.message.get_text()