import atexit
import tempfile
import uuid
import time
from pathlib import Path
from typing import Generator
from contextlib import contextmanager
from app.utils.logger import setup_logger # &lt;--- Importa a FUNÇÃO

logger = setup_logger(__name__) # &lt;--- Cria o logger localmente

# Diretório temporário dedicado para a aplicação
# Usa gettempdir() do SO mas cria uma subpasta para organização
APP_TEMP_DIR = Path(tempfile.gettempdir()) / "voice_sdr_whatsapp"
APP_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Registro em memória dos arquivos criados por este processo
_temp_files_registry = set()

def get_temp_filename(extension: str, prefix: str = "audio") -> Path:
    """
    Gera um caminho único para arquivo temporário e o registra.
    """
    if not extension.startswith('.'):
        extension = f'.{extension}'
    
    unique_name = f"{prefix}_{uuid.uuid4().hex}{extension}"
    file_path = APP_TEMP_DIR / unique_name
    
    # Registra para garantia de limpeza
    _temp_files_registry.add(str(file_path))
    
    return file_path

def safe_remove(file_path: str | Path) -> bool:
    """
    Remove arquivo de forma segura, sem travar se não existir.
    """
    if not file_path:
        return False
        
    path_obj = Path(file_path)
    str_path = str(path_obj)
    
    try:
        if path_obj.exists():
            path_obj.unlink()
            logger.debug(f"Arquivo removido: {path_obj.name}")
            
        # Remove do registro se existir
        if str_path in _temp_files_registry:
            _temp_files_registry.discard(str_path)
            
        return True
    except Exception as e:
        logger.warning(f"Falha ao remover {str_path}: {e}")
        return False

def cleanup_temp_files(max_age_hours: int = 1):
    """
    Cron job: Remove arquivos órfãos (ex: de crashes anteriores).
    """
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    removed_count = 0
    
    logger.info("Iniciando varredura de limpeza de arquivos temporários...")
    
    try:
        for file_path in APP_TEMP_DIR.iterdir():
            if file_path.is_file():
                # Verifica idade do arquivo
                try:
                    file_age = current_time - file_path.stat().st_mtime
                except FileNotFoundError:
                    continue # Arquivo já foi removido por outro processo

                if file_age > max_age_seconds:
                    if safe_remove(file_path):
                        removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Limpeza concluída: {removed_count} arquivos antigos removidos.")
    
    except Exception as e:
        logger.error(f"Erro crítico na rotina de limpeza: {e}")

def cleanup_on_exit():
    """Hook para limpar tudo quando a aplicação encerrar."""
    if _temp_files_registry:
        logger.info(f"Encerrando: limpando {len(_temp_files_registry)} arquivos temporários...")
        # Cria uma cópia da lista para iterar com segurança
        for file_path in list(_temp_files_registry):
            safe_remove(file_path)

# Registra o hook de saída
atexit.register(cleanup_on_exit)

@contextmanager
def temp_file(extension: str, prefix: str = "audio") -> Generator[Path, None, None]:
    """
    Context Manager para uso seguro de arquivos.
    
    Exemplo:
        with temp_file(".ogg") as path:
            gravar_audio(path)
            enviar_audio(path)
        # Aqui o arquivo já foi deletado automaticamente!
    """
    path = get_temp_filename(extension, prefix)
    try:
        yield path
    finally:
        safe_remove(path)

def get_file_size_mb(file_path: str | Path) -> float:
    """Retorna tamanho em MB com segurança."""
    try:
        return Path(file_path).stat().st_size / (1024 * 1024)
    except Exception:
        return 0.0