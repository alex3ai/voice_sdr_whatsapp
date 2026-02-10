import asyncio
import random
import functools
from typing import Callable, Type, Tuple, Any
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator que implementa retry com exponential backoff para chamadas de API externas.
    
    Args:
        max_retries: Número máximo de tentativas
        base_delay: Delay inicial em segundos
        max_delay: Delay máximo em segundos
        backoff_factor: Fator de multiplicação para o delay
        exceptions: Tupla de exceções que devem causar retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Última tentativa, lançar exceção
                        logger.error(
                            f"Função {func.__name__} falhou após {max_retries + 1} tentativas. "
                            f"Última exceção: {type(e).__name__}: {e}"
                        )
                        raise e
                    
                    # Calcular delay com jitter para evitar thundering herd
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    jitter = random.uniform(0, 0.1 * delay)  # Adiciona variação de até 10%
                    total_delay = delay + jitter
                    
                    logger.warning(
                        f"Tentativa {attempt + 1} de {max_retries + 1} falhou para {func.__name__}. "
                        f"Retentando em {total_delay:.2f}s. Erro: {type(e).__name__}: {e}"
                    )
                    
                    await asyncio.sleep(total_delay)
            
            # Este ponto não deve ser alcançado, mas está aqui por segurança
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def get_retryable_exceptions():
    """
    Retorna uma tupla de exceções comuns que indicam que uma operação pode ser retentada.
    """
    import httpx
    import aiohttp
    
    return (
        httpx.RequestError,      # Erros de conexão e timeout
        httpx.TimeoutException,  # Timeout específico
        httpx.NetworkError,      # Erros de rede
        httpx.PoolTimeout,       # Timeout no pool de conexões
        aiohttp.ClientError,     # Erros gerais do cliente aiohttp
        aiohttp.ServerTimeoutError,  # Timeout do servidor
        aiohttp.ServerConnectionError,  # Erro de conexão com servidor
        ConnectionError,         # Erros genéricos de conexão
        TimeoutError,            # Timeout genérico
    )