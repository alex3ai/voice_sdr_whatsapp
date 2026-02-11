import abc
import logging
from datetime import datetime
from typing import Optional
from ..utils.logger import setup_logger  # Importa a função correta
from ..config import settings  # Importa a instância de configuração

logger = setup_logger(__name__)  # Usa a função correta para criar o logger

class NotificationService(abc.ABC):
    """Interface abstrata para serviços de notificação"""
    
    @abc.abstractmethod
    def send_alert(self, message: str, level: str = "info", context: Optional[dict] = None):
        """Envia um alerta com o nível especificado"""
        pass

    @abc.abstractmethod
    def notify_error(self, error: Exception, context: Optional[dict] = None):
        """Notifica um erro crítico"""
        pass


class ConsoleNotificationService(NotificationService):
    """Implementação de notificação via console"""
    
    def send_alert(self, message: str, level: str = "info", context: Optional[dict] = None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {level.upper()}: {message}"
        
        if context:
            formatted_message += f" | Context: {context}"
            
        if level.lower() == "error":
            print(f"\033[91m{formatted_message}\033[0m")  # Vermelho
        elif level.lower() == "warning":
            print(f"\033[93m{formatted_message}\033[0m")  # Amarelo
        elif level.lower() == "critical":
            print(f"\033[95m{formatted_message}\033[0m")  # Roxo
        else:
            print(formatted_message)

    def notify_error(self, error: Exception, context: Optional[dict] = None):
        self.send_alert(
            f"Critical Error: {str(error)}",
            level="critical",
            context=context
        )


class FileNotificationService(NotificationService):
    """Implementação de notificação via arquivo"""
    
    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = log_file_path or settings.notification_log_file_path  # Usa o novo campo da configuração
        
    def send_alert(self, message: str, level: str = "info", context: Optional[dict] = None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {level.upper()}: {message}"
        
        if context:
            formatted_message += f" | Context: {context}"
        
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(formatted_message + "\n")
        except Exception as e:
            print(f"Falha ao escrever no arquivo de log: {e}")

    def notify_error(self, error: Exception, context: Optional[dict] = None):
        self.send_alert(
            f"Critical Error: {str(error)}",
            level="critical",
            context=context
        )


def get_notification_service() -> NotificationService:
    """Factory para obter o serviço de notificação configurado"""
    notification_type = settings.notification_type.lower()  # Usa o novo campo da configuração
    
    if notification_type == "file":
        return FileNotificationService()
    else:  # Default to console
        return ConsoleNotificationService()