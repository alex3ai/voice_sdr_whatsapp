import logging
import sys
from typing import Optional
from app.config import settings

# --- Função de Segurança (Do Gemini) ---
def sanitize_log(text: str) -> str:
    """
    Masca dados sensíveis para evitar vazamento de PII em logs.
    Essencial para conformidade com LGPD/GDPR.
    """
    if not text: return ""
    text_str = str(text)
    if len(text_str) <= 10: return "***"
    return f"{text_str[:4]}...{text_str[-4:]} (Len: {len(text_str)})"

# --- Formatter Visual (Do Claude) ---
class ColoredFormatter(logging.Formatter):
    """Formatter com cores, usado APENAS em desenvolvimento"""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Ciano
        'INFO': '\033[32m',     # Verde
        'WARNING': '\033[33m',  # Amarelo
        'ERROR': '\033[31m',    # Vermelho
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        # Aplica cor apenas no nome do nível
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        original_levelname = record.levelname
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        
        formatted = super().format(record)
        
        # Restaura para não afetar outros handlers
        record.levelname = original_levelname
        return formatted

def setup_logger(name: str) -> logging.Logger:
    """
    Configura logger com estratégia baseada no ambiente.
    Dev -> Colorido e detalhado.
    Prod -> Limpo e estruturado.
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
        
    # Nível definido no config.py (settings.log_level)
    level = getattr(logging, settings.log_level.upper())
    logger.setLevel(level)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    # Decisão de Formatação baseada no Ambiente
    if settings.environment == "development":
        # Formato visual do Claude para Dev Local
        formatter = ColoredFormatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        # Formato limpo do Gemini para Produção (sem cores ANSI que sujam o log)
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger

# Logger principal
logger = setup_logger("voice_sdr")