/*
 * SQL Views e Consultas para Extração de Métricas do Dashboard
 * 
 * Este arquivo contém as consultas SQL e Views necessárias para extrair
 * métricas relevantes para o dashboard de monitoramento e análise de 
 * performance do bot Voice SDR WhatsApp.
 */

-- ==========================================
-- VIEW: Métricas de Conversas por Período
-- ==========================================
CREATE OR REPLACE VIEW conversation_metrics AS
SELECT 
    DATE(created_at) as data,
    COUNT(DISTINCT remote_jid) as numero_de_conversas,
    COUNT(*) as total_mensagens
FROM messages
GROUP BY DATE(created_at);

-- ==========================================
-- VIEW: Conversas Ativas (últimas 24h)
-- ==========================================
CREATE OR REPLACE VIEW active_conversations AS
SELECT 
    remote_jid,
    COUNT(*) as total_mensagens,
    MAX(created_at) as ultima_mensagem,
    MIN(created_at) as primeira_mensagem
FROM messages
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY remote_jid;

-- ==========================================
-- VIEW: Distribuição de Tipos de Mensagem
-- ==========================================
CREATE OR REPLACE VIEW message_type_distribution AS
SELECT 
    CASE 
        WHEN message_type LIKE '%audio%' THEN 'Áudio'
        WHEN message_type LIKE '%text%' OR message_type LIKE '%conversation%' THEN 'Texto'
        WHEN message_type LIKE '%image%' THEN 'Imagem'
        WHEN message_type LIKE '%document%' THEN 'Documento'
        ELSE 'Outro'
    END as tipo_mensagem,
    COUNT(*) as quantidade
FROM messages
GROUP BY 
    CASE 
        WHEN message_type LIKE '%audio%' THEN 'Áudio'
        WHEN message_type LIKE '%text%' OR message_type LIKE '%conversation%' THEN 'Texto'
        WHEN message_type LIKE '%image%' THEN 'Imagem'
        WHEN message_type LIKE '%document%' THEN 'Documento'
        ELSE 'Outro'
    END;

-- ==========================================
-- VIEW: Taxa de Resposta do Bot
-- ==========================================
CREATE OR REPLACE VIEW bot_response_rate AS
SELECT 
    SUM(CASE WHEN from_me = true THEN 1 ELSE 0 END) as mensagens_enviadas_pelo_bot,
    SUM(CASE WHEN from_me = false THEN 1 ELSE 0 END) as mensagens_recebidas_do_cliente,
    COUNT(*) as total_mensagens,
    ROUND(
        100.0 * SUM(CASE WHEN from_me = true THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(*), 0), 
        2
    ) as percentual_respostas
FROM messages;

-- ==========================================
-- VIEW: Métricas de Performance por Dia
-- ==========================================
CREATE OR REPLACE VIEW daily_performance_metrics AS
SELECT 
    DATE(created_at) as data,
    COUNT(*) as total_mensagens,
    SUM(CASE WHEN from_me = true THEN 1 ELSE 0 END) as mensagens_enviadas,
    SUM(CASE WHEN from_me = false THEN 1 ELSE 0 END) as mensagens_recebidas,
    ROUND(AVG(EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (
        PARTITION BY remote_jid ORDER BY created_at
    )))), 2) as tempo_medio_resposta_segundos
FROM messages
GROUP BY DATE(created_at);

-- ==========================================
-- VIEW: Conversas por Número de Cliente
-- ==========================================
CREATE OR REPLACE VIEW conversations_by_client AS
SELECT 
    remote_jid,
    COUNT(DISTINCT DATE(created_at)) as dias_comunicacao,
    COUNT(*) as total_mensagens,
    MIN(created_at) as primeira_mensagem,
    MAX(created_at) as ultima_mensagem,
    SUM(CASE WHEN from_me = true THEN 1 ELSE 0 END) as mensagens_bot,
    SUM(CASE WHEN from_me = false THEN 1 ELSE 0 END) as mensagens_cliente
FROM messages
GROUP BY remote_jid
ORDER BY total_mensagens DESC;

-- ==========================================
-- VIEW: Métricas Completas de Conversação
-- ==========================================
CREATE OR REPLACE VIEW comprehensive_conversation_metrics AS
SELECT
    DATE(m.created_at) as data,
    COUNT(DISTINCT m.remote_jid) as usuarios_unicos,
    COUNT(m.id) as total_mensagens,
    SUM(CASE WHEN m.from_me = true THEN 1 ELSE 0 END) as mensagens_enviadas,
    SUM(CASE WHEN m.from_me = false THEN 1 ELSE 0 END) as mensagens_recebidas,
    ROUND(
        100.0 * SUM(CASE WHEN m.from_me = true THEN 1 ELSE 0 END) / 
        NULLIF(COUNT(m.id), 0), 
        2
    ) as taxa_resposta_percentual,
    COUNT(DISTINCT CASE WHEN m.created_at >= NOW() - INTERVAL '24 hours' THEN m.remote_jid END) as usuarios_ativos_24h
FROM messages m
GROUP BY DATE(m.created_at);

-- ==========================================
-- CONSULTA: Métricas Gerais do Sistema
-- ==========================================
CREATE OR REPLACE VIEW system_wide_metrics AS
SELECT
    (SELECT COUNT(DISTINCT remote_jid) FROM messages) as total_usuarios_atendidos,
    (SELECT COUNT(*) FROM messages) as total_mensagens_processadas,
    (SELECT COUNT(*) FROM messages WHERE from_me = true) as mensagens_enviadas_pelo_bot,
    (SELECT COUNT(*) FROM messages WHERE from_me = false) as mensagens_recebidas_dos_clientes,
    (SELECT COUNT(DISTINCT DATE(created_at)) FROM messages) as dias_atividade,
    (SELECT MIN(created_at) FROM messages) as primeira_interacao,
    (SELECT MAX(created_at) FROM messages) as ultima_interacao,
    ROUND(
        100.0 * (SELECT COUNT(*) FROM messages WHERE from_me = true) / 
        (SELECT COUNT(*) FROM messages), 
        2
    ) as proporcao_respostas
FROM messages
LIMIT 1;

-- ==========================================
-- CONSULTA: Métricas por Hora do Dia (Pico de Atividade)
-- ==========================================
CREATE OR REPLACE VIEW hourly_activity AS
SELECT
    EXTRACT(HOUR FROM created_at) as hora_do_dia,
    COUNT(*) as total_mensagens,
    SUM(CASE WHEN from_me = false THEN 1 ELSE 0 END) as mensagens_recebidas,
    SUM(CASE WHEN from_me = true THEN 1 ELSE 0 END) as mensagens_enviadas
FROM messages
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY hora_do_dia;

-- ==========================================
-- CONSULTA: Métricas por Dia da Semana
-- ==========================================
CREATE OR REPLACE VIEW weekly_activity AS
SELECT
    EXTRACT(DOW FROM created_at) as dia_da_semana,
    TO_CHAR(created_at, 'Day') as nome_dia,
    COUNT(*) as total_mensagens,
    AVG(CASE WHEN from_me = false THEN 
        EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (
            PARTITION BY remote_jid ORDER BY created_at
        ))) END) as tempo_medio_resposta_seg
FROM messages
GROUP BY EXTRACT(DOW FROM created_at), TO_CHAR(created_at, 'Day')
ORDER BY dia_da_semana;