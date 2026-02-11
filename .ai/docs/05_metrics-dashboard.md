# Documentação do Dashboard de Métricas

## Visão Geral

O sistema Voice SDR WhatsApp inclui um conjunto abrangente de métricas para monitoramento e análise de desempenho. Estas métricas são extraídas do banco de dados da Evolution API usando Views SQL otimizadas e um serviço dedicado de métricas.

## Componentes do Sistema de Métricas

### 1. Views SQL

O sistema de métricas é baseado em Views SQL pré-computadas que otimizam o desempenho das consultas. Estas Views são atualizadas em tempo real conforme novos dados entram no banco de dados.

Localização: [create_metrics_views.sql](../create_metrics_views.sql)

### 2. Serviço de Métricas

O serviço [metrics.py](../app/services/metrics.py) fornece métodos para acessar e processar as métricas do banco de dados, com lógica de retry e tratamento de erros.

### 3. Endpoints da API

Os endpoints da API fornecem dados estruturados para alimentar o dashboard:

- `/metrics/daily_conversations` - Métricas diárias de conversas
- `/metrics/active_chats` - Conversas ativas nas últimas 24h
- `/metrics/message_types` - Distribuição de tipos de mensagem
- `/metrics/bot_response_rate` - Taxa de resposta do bot
- `/metrics/system_wide` - Métricas amplas do sistema

## Métricas Disponíveis

### Métricas de Conversas Diárias

A View `conversation_metrics` fornece:

- Data específica
- Número de conversas distintas
- Total de mensagens

### Métricas de Conversas Ativas

A View `active_conversations` fornece:

- Lista de JIDs ativos (últimas 24h)
- Total de mensagens por conversa
- Timestamps de primeira e última mensagem

### Distribuição de Tipos de Mensagem

A View `message_type_distribution` categoriza mensagens em:

- Áudio
- Texto
- Imagem
- Documento
- Outros

### Taxa de Resposta do Bot

A View `bot_response_rate` calcula:

- Total de mensagens enviadas pelo bot
- Total de mensagens recebidas de clientes
- Percentual de respostas do bot

### Métricas de Performance Diária

A View `daily_performance_metrics` fornece:

- Total de mensagens por dia
- Mensagens enviadas/recebidas
- Tempo médio de resposta

### Métricas Ampla do Sistema

A View `system_wide_metrics` fornece KPIs gerais:

- Total de usuários atendidos
- Total de mensagens processadas
- Proporção de respostas do bot
- Dias de atividade

## Configuração do Banco de Dados

Para que as métricas funcionem corretamente, é necessário:

1. Conexão com o banco PostgreSQL da Evolution API
2. Permissões de leitura nas tabelas necessárias
3. Execução do script [create_metrics_views.sql](../create_metrics_views.sql) para criar as Views

### Variáveis de Ambiente

O serviço de métricas requer as seguintes variáveis de ambiente:

```
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=evolution
DATABASE_PASSWORD=evolution
DATABASE_NAME=evolution
```

## Implementação Técnica

### Serviço de Métricas ([app/services/metrics.py](file:///c%3A/Users/alex_/Desktop/PE33/Projetos PE33/Projeto 20 - voice_sdr_whatsapp/voice_sdr_whatsapp/app/services/metrics.py))

O serviço implementa:

- Lógica de retry com backoff exponencial para conexões com falha
- Consultas específicas para cada tipo de métrica
- Tratamento de erros detalhado
- Logs de auditoria

### Estratégias de Conexão

O serviço usa `asyncpg` para conexões assíncronas com o PostgreSQL e implementa:

- Retry com backoff exponencial
- Timeout configurável
- Logging detalhado de tentativas

## Testes

O sistema inclui testes específicos para validar o funcionamento das métricas:

- [tests/test_metrics.py](../tests/test_metrics.py) - Testes unitários para o serviço de métricas
- Verificação de conectividade com o banco de dados
- Validação dos dados retornados por cada métrica

## Boas Práticas

- As Views SQL são otimizadas para minimizar o impacto no banco de dados principal
- O serviço de métricas implementa timeouts e retry para lidar com falhas temporárias
- Os dados são retornados em formato JSON padronizado para fácil integração com interfaces
- O sistema é projetado para escalar com o aumento de volume de dados