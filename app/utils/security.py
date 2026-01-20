import hmac
import hashlib
from app.config import settings
from app.utils.logger import logger

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

def sanitize_phone_number(phone: str) -> str:
    """
    Normaliza números de telefone (remove +, -, espaços, parênteses).
    Útil para salvar no banco ou logs de forma padronizada.
    Ex: '+55 (11) 9999-9999' -> '551199999999'
    """
    if not phone:
        return ""
    return ''.join(filter(str.isdigit, phone))