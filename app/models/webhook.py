"""
Modelos Pydantic para validação estrita dos dados do webhook WhatsApp.
Compatível com Pydantic 2.x e API v21.0 da Meta.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple

class AudioMessage(BaseModel):
    """Dados específicos de mensagens de áudio/voz."""
    id: str = Field(..., description="ID único da mídia no WhatsApp")
    mime_type: str = Field(..., description="Tipo MIME (ex: audio/ogg; codecs=opus)")
    sha256: Optional[str] = Field(None, description="Hash para validação de integridade")
    voice: bool = Field(default=False, description="True se for nota de voz (PTT), False se for arquivo de áudio")

class TextMessage(BaseModel):
    """Dados de mensagens de texto."""
    body: str = Field(..., description="Conteúdo da mensagem")

class Message(BaseModel):
    """
    Estrutura unificada de mensagem.
    Trata o campo reservado 'from' usando alias.
    """
    from_: str = Field(..., alias="from", description="Número do remetente (WhatsApp ID)")
    id: str = Field(..., description="ID da mensagem")
    timestamp: str = Field(..., description="Unix timestamp da mensagem")
    type: str = Field(..., description="Tipo (audio, text, image, interaction, etc)")
    
    # Campos opcionais dependendo do tipo
    audio: Optional[AudioMessage] = None
    text: Optional[TextMessage] = None

class Contact(BaseModel):
    """Informações do contato enviadas pelo WhatsApp."""
    profile: dict = Field(default_factory=dict, description="Perfil do usuário (nome, etc)")
    wa_id: str = Field(..., description="WhatsApp ID do contato")

class Metadata(BaseModel):
    """Metadados técnicos do webhook."""
    display_phone_number: Optional[str] = None
    phone_number_id: Optional[str] = None

class Value(BaseModel):
    """Payload real do evento."""
    messaging_product: str = Field(default="whatsapp")
    metadata: Optional[Metadata] = None
    contacts: Optional[List[Contact]] = []
    messages: Optional[List[Message]] = []

class Change(BaseModel):
    """Objeto de mudança de estado."""
    value: Value
    field: str = Field(default="messages")

class Entry(BaseModel):
    """Entrada no array de eventos."""
    id: str
    changes: List[Change]

class WebhookPayload(BaseModel):
    """
    Root Model para o JSON recebido da Meta.
    Contém métodos auxiliares para extração segura de dados.
    """
    object: str
    entry: List[Entry]
    
    def get_messages(self) -> List[Message]:
        """Flatten: Extrai todas as mensagens de todas as entradas."""
        messages = []
        for entry in self.entry:
            for change in entry.changes:
                if change.value and change.value.messages:
                    messages.extend(change.value.messages)
        return messages
    
    def get_first_audio_message(self) -> Optional[Tuple[str, str]]:
        """
        Busca a primeira mensagem de áudio válida no payload.
        
        Returns:
            Tuple(audio_id, sender_phone) ou None
        """
        for msg in self.get_messages():
            if msg.type == "audio" and msg.audio:
                return (msg.audio.id, msg.from_)
        return None