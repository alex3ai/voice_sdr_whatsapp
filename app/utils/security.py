import hmac
import hashlib
import time
from typing import Dict, List
from collections import defaultdict
from app.config import settings
from app.utils.logger import setup_logger

# Armazenamento em memória para rate limiting (em produção, usar Redis)
rate_limit_storage: Dict[str, List[float]] = defaultdict(list)

logger = setup_logger(__name__)

def validate_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """
    Valida a assinatura SHA256 do webhook da Meta (HMAC).
    Garante que a mensagem realmente veio do WhatsApp.
    """
    if not signature_header:
        logger.warning("Tentativa de webhook sem cabeçalho de assinatura!")
        return False
        
    try:
        # O header vem no formato 'sha256=hash_aqui'
        parts = signature_header.split("=")
        if len(parts) != 2 or parts[0] != "sha256":
            logger.warning(f"Formato de assinatura inválido: {signature_header}")
            return False
            
        signature_hash = parts[1]
        
        # Calcula o HMAC esperado usando nosso APP_SECRET
        expected_hash = hmac.new(
            key=settings.app_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        # Comparação segura contra Timing Attacks
        is_valid = hmac.compare_digest(expected_hash, signature_hash)
        
        if not is_valid:
            logger.warning("Assinatura do webhook rejeitada (Hash mismatch)")
            
        return is_valid
    
    except Exception as e:
        logger.error(f"Erro crítico na validação de segurança: {e}")
        return False


def authenticate_request(api_key: str) -> bool:
    """
    Validação simples de chave de API para proteger os endpoints
    Em produção, considerar autenticação baseada em JWT com tokens
    """
    if not api_key:
        return False
    
    # Comparação segura contra timing attacks
    expected_key = settings.api_key or settings.evolution_api_key
    return hmac.compare_digest(api_key, expected_key)


def check_rate_limit(identifier: str, limit: int = 10, window: int = 60) -> bool:
    """
    Verifica se o identificador excedeu o limite de requisições por janela de tempo
    :param identifier: Identificador do cliente (IP, user_id, etc.)
    :param limit: Número máximo de requisições permitidas
    :param window: Janela de tempo em segundos
    :return: True se dentro do limite, False caso contrário
    """
    now = time.time()
    # Remove requisições antigas fora da janela
    rate_limit_storage[identifier] = [
        timestamp for timestamp in rate_limit_storage[identifier]
        if now - timestamp < window
    ]
    
    # Verifica se está dentro do limite
    if len(rate_limit_storage[identifier]) >= limit:
        return False
    
    # Adiciona a requisição atual
    rate_limit_storage[identifier].append(now)
    return True


def sanitize_phone_number(phone: str) -> str:
    """
    Normaliza números de telefone (remove +, -, espaços, parênteses).
    Útil para salvar no banco ou logs de forma padronizada.
    Ex: '+55 (11) 9999-9999' -> '551199999999'
    """
    if not phone:
        return ""
    return ''.join(filter(str.isdigit, phone))