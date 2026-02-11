"""
Serviço de Métricas para o Dashboard de Monitoramento
"""
import asyncio
import asyncpg
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.config import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class MetricsService:
    """
    Serviço responsável por obter métricas do banco de dados da Evolution API
    para exibição no dashboard de monitoramento.
    """
    
    def __init__(self):
        self.connection_string = settings.database_connection_uri
    
    async def get_db_connection(self, max_retries: int = 3, initial_retry_delay: float = 1.0):
        """
        Obtém uma conexão com o banco de dados com lógica de retry e backoff exponencial
        
        Args:
            max_retries: Número máximo de tentativas de conexão
            initial_retry_delay: Atraso inicial entre tentativas em segundos
            
        Returns:
            Conexão com o banco de dados
        """
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                conn = await asyncpg.connect(
                    host=settings.database_host,
                    port=settings.database_port,
                    user=settings.database_user,
                    password=settings.database_password,
                    database=settings.database_name,
                    timeout=5  # 5 seconds connection timeout
                )
                logger.info(f"Conexão com o banco de dados estabelecida na tentativa {attempt + 1}")
                return conn
            except (OSError, asyncpg.PostgresError) as e:
                last_exception = e
                retry_delay = initial_retry_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Tentativa {attempt + 1} falhou. Tentando novamente em {retry_delay:.1f} segundos. Erro: {e}")
                await asyncio.sleep(retry_delay)
        
        logger.error(f"Falha ao conectar ao banco de dados após {max_retries} tentativas")
        raise ConnectionError(f"Não foi possível conectar ao banco de dados após {max_retries} tentativas. Último erro: {last_exception}") from last_exception
    
    async def get_daily_conversation_metrics(self, start_date: Optional[datetime] = None, 
                                           end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Obtém métricas diárias de conversas
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        query = """
        SELECT 
            data,
            numero_de_conversas,
            total_mensagens
        FROM conversation_metrics
        WHERE data BETWEEN $1 AND $2
        ORDER BY data DESC
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query, start_date, end_date)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter métricas diárias de conversas: {e}")
            return []
    
    async def get_active_conversations(self) -> List[Dict[str, Any]]:
        """
        Obtém conversas ativas nas últimas 24h
        """
        query = """
        SELECT 
            remote_jid,
            total_mensagens,
            ultima_mensagem,
            primeira_mensagem
        FROM active_conversations
        ORDER BY ultima_mensagem DESC
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter conversas ativas: {e}")
            return []
    
    async def get_message_type_distribution(self) -> List[Dict[str, Any]]:
        """
        Obtém a distribuição de tipos de mensagens
        """
        query = """
        SELECT 
            tipo_mensagem,
            quantidade
        FROM message_type_distribution
        ORDER BY quantidade DESC
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter distribuição de tipos de mensagem: {e}")
            return []
    
    async def get_bot_response_rate(self) -> Dict[str, Any]:
        """
        Obtém a taxa de resposta do bot
        """
        query = """
        SELECT 
            mensagens_enviadas_pelo_bot,
            mensagens_recebidas_do_cliente,
            total_mensagens,
            percentual_respostas
        FROM bot_response_rate
        LIMIT 1
        """
        
        try:
            conn = await self.get_db_connection()
            row = await conn.fetchrow(query)
            await conn.close()
            
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"Erro ao obter taxa de resposta do bot: {e}")
            return {}
    
    async def get_daily_performance_metrics(self, start_date: Optional[datetime] = None, 
                                          end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Obtém métricas de performance diárias
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        query = """
        SELECT 
            data,
            total_mensagens,
            mensagens_enviadas,
            mensagens_recebidas,
            tempo_medio_resposta_segundos
        FROM daily_performance_metrics
        WHERE data BETWEEN $1 AND $2
        ORDER BY data DESC
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query, start_date, end_date)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter métricas de performance diárias: {e}")
            return []
    
    async def get_conversations_by_client(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtém as conversas agrupadas por cliente
        """
        query = """
        SELECT 
            remote_jid,
            dias_comunicacao,
            total_mensagens,
            primeira_mensagem,
            ultima_mensagem,
            mensagens_bot,
            mensagens_cliente
        FROM conversations_by_client
        ORDER BY total_mensagens DESC
        LIMIT $1
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query, limit)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter conversas por cliente: {e}")
            return []
    
    async def get_system_wide_metrics(self) -> Dict[str, Any]:
        """
        Obtém métricas amplas do sistema
        """
        query = """
        SELECT * FROM system_wide_metrics
        LIMIT 1
        """
        
        try:
            conn = await self.get_db_connection()
            row = await conn.fetchrow(query)
            await conn.close()
            
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"Erro ao obter métricas amplas do sistema: {e}")
            return {}
    
    async def get_hourly_activity(self) -> List[Dict[str, Any]]:
        """
        Obtém a atividade por hora do dia
        """
        query = """
        SELECT 
            hora_do_dia,
            total_mensagens,
            mensagens_recebidas,
            mensagens_enviadas
        FROM hourly_activity
        ORDER BY hora_do_dia
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter atividade por hora: {e}")
            return []
    
    async def get_weekly_activity(self) -> List[Dict[str, Any]]:
        """
        Obtém a atividade por dia da semana
        """
        query = """
        SELECT 
            dia_da_semana,
            nome_dia,
            total_mensagens,
            tempo_medio_resposta_seg
        FROM weekly_activity
        ORDER BY dia_da_semana
        """
        
        try:
            conn = await self.get_db_connection()
            rows = await conn.fetch(query)
            await conn.close()
            
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Erro ao obter atividade semanal: {e}")
            return []


# Instância singleton do serviço de métricas
metrics_service = MetricsService()