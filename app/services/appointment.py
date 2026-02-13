import re
from typing import Optional
from ..config import settings
from ..utils.logger import setup_logger
from ..models.webhook import EvolutionWebhook

logger = setup_logger(__name__)


class AppointmentService:
    """Serviço responsável por gerenciar a lógica de agendamento de reuniões."""
    
    def __init__(self):
        self.calendar_link = settings.calendar_link
        self.scheduling_keywords = [
            r'agendar',
            r'marcar.*reunião',
            r'marcar.*consulta',
            r'marcar.*meet',
            r'marcar.*encontro',
            r'horário.*disponível',
            r'disponibilidade.*horário',
            r'pode.*marcar',
            r'gostaria.*agendar',
            r'quero.*agendar',
            r'preciso.*reunião',
            r'meeting.*disponível',
            r'agendamento',
            r'calendário',
            r'horário.*livre'
        ]
    
    def detect_scheduling_intent(self, message_text: str) -> bool:
        """
        Detecta se a mensagem contém intenção de agendamento de reunião.
        
        Args:
            message_text (str): Texto da mensagem recebida
            
        Returns:
            bool: True se detectar intenção de agendamento, False caso contrário
        """
        message_lower = message_text.lower()
        
        for keyword in self.scheduling_keywords:
            if re.search(keyword, message_lower, re.IGNORECASE):
                logger.info(f"Detectada intenção de agendamento na mensagem: '{message_text[:50]}...'")
                return True
                
        return False
    
    def generate_scheduling_response(self) -> str:
        """
        Gera a resposta com o link de agendamento.
        
        Returns:
            str: Mensagem contendo o link de agendamento
        """
        if not self.calendar_link:
            logger.warning("calendar_link não está configurado nas variáveis de ambiente")
            return ("Parece que você gostaria de agendar uma reunião. "
                   "Por favor, entre em contato diretamente conosco para agendar um horário.")
        
        response = (
            "Ótima notícia! Você pode agendar uma reunião diretamente conosco através do nosso sistema de agendamento.\n\n"
            f"Acesse o link abaixo para escolher um horário disponível:\n{self.calendar_link}\n\n"
            "Se tiver alguma dúvida sobre o processo de agendamento, posso ajudar!"
        )
        
        logger.info("Gerada resposta de agendamento com link")
        return response
    
    async def handle_appointment_request(self, message_data):
        """
        Processa uma requisição de agendamento e retorna a resposta apropriada.
        
        Args:
            message_data: Dados da mensagem recebida (pode ser um dicionário ou objeto EvolutionWebhook)
            
        Returns:
            Optional[str]: Resposta a ser enviada ao usuário, ou None se não for 
                          uma solicitação de agendamento
        """
        # Extrair o texto da mensagem dependendo do tipo de objeto recebido
        message_text = None
        
        # Se for um objeto EvolutionWebhook, extrai o texto corretamente
        if hasattr(message_data, 'data'):
            message_text = message_data.get_text_content()
        # Caso receba como dicionário (formato do webhook bruto)
        elif isinstance(message_data, dict):
            # Tenta extrair o texto do corpo da mensagem
            message_content = message_data.get('data', {}).get('message', {})
            
            # Extrai o texto de diferentes possíveis campos
            if 'conversation' in message_content:
                message_text = message_content['conversation']
            elif 'extendedTextMessage' in message_content:
                message_text = message_content['extendedTextMessage'].get('text', '')
            elif message_content.get('audioMessage'):
                # Para mensagens de áudio, não podemos detectar intenção de agendamento no texto transcrito
                # A transcrição virá de outro lugar, então retornamos None aqui
                return None
        # Se tivermos um atributo body diretamente
        elif hasattr(message_data, 'body'):
            message_text = getattr(message_data, 'body', None)
        
        if not message_text:
            logger.debug("Mensagem não possui conteúdo de texto para análise de agendamento")
            return None
            
        if self.detect_scheduling_intent(message_text):
            return self.generate_scheduling_response()
            
        return None