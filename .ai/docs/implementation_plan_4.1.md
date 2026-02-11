# Planejamento para Implementação do Item 4.1: Consultas SQL para Métricas

## Visão Geral

O item 4.1 da fase 4 do projeto visa criar consultas SQL (ou Views) no banco de dados existente para extrair métricas relevantes para o dashboard de monitoramento e análise de performance do bot.

## Análise do Banco de Dados

A partir da configuração do docker-compose.yml, é evidente que o sistema utiliza um banco de dados PostgreSQL para armazenar informações da Evolution API:

```yaml
# Banco de Dados (Postgres)
postgres:
  image: postgres:15
  environment:
    - POSTGRES_USER=evolution
    - POSTGRES_PASSWORD=evolution
    - POSTGRES_DB=evolution
  volumes:
    - evolution_postgres_data:/var/lib/postgresql/data
```

O banco de dados da Evolution API contém tabelas relacionadas às mensagens, instâncias e conexões do WhatsApp, que foram utilizadas para extrair as métricas necessárias.

## Métricas Relevantes para Extração

As seguintes métricas foram implementadas para o dashboard:

### Métricas de Conversa
1. Número total de conversas ativas
2. Número total de conversas finalizadas
3. Número de conversas por período (filtro de data)
4. Tempo médio de duração das conversas
5. Conversas por número de telefone/cliente

### Métricas de Mensagens
1. Total de mensagens recebidas/enviadas
2. Distribuição entre mensagens de áudio e texto
3. Média de mensagens por conversa
4. Taxa de resposta do bot
5. Tempo médio de resposta do bot

### Métricas de Performance
1. Taxa de sucesso/erro nas operações
2. Tempo médio de processamento do pipeline
3. Frequência de erros por tipo
4. Horários de maior atividade

## Plano de Implementação - STATUS ATUAL

### Etapa 1: Análise da Estrutura do Banco de Dados
- [x] Conectar ao banco de dados PostgreSQL da Evolution API
- [x] Mapear as tabelas existentes e seus relacionamentos (baseado na documentação oficial da Evolution API)
- [x] Identificar campos relevantes para as métricas desejadas
- [x] Documentar a estrutura encontrada em [02_database-structure.md](./02_database-structure.md)

### Etapa 2: Desenvolvimento das Consultas SQL
- [x] Criar consultas para métricas de conversas
- [x] Criar consultas para métricas de mensagens
- [x] Criar consultas para métricas de performance
- [x] Otimizar as consultas para performance adequada
- [x] Testar as consultas com dados reais

### Etapa 3: Criação de Views (se necessário)
- [x] Converter as consultas mais complexas em Views SQL
- [x] Garantir que as Views sejam atualizadas em tempo real
- [x] Documentar o propósito de cada View criada

### Etapa 4: Implementação de Funções de Apoio
- [x] Criar funções auxiliares para cálculos complexos
- [x] Implementar funções de agregação personalizadas (se necessário)

## Consultas SQL Implementadas

As consultas SQL e Views foram implementadas no arquivo [create_metrics_views.sql](../create_metrics_views.sql) e incluem:

### Views Criadas:
1. `conversation_metrics` - Métricas de conversas por período
2. `active_conversations` - Conversas ativas (últimas 24h)
3. `message_type_distribution` - Distribuição de tipos de mensagem
4. `bot_response_rate` - Taxa de resposta do bot
5. `daily_performance_metrics` - Métricas de performance por dia
6. `conversations_by_client` - Conversas agrupadas por cliente
7. `comprehensive_conversation_metrics` - Métricas completas de conversação
8. `system_wide_metrics` - Métricas amplas do sistema
9. `hourly_activity` - Atividade por hora do dia
10. `weekly_activity` - Atividade por dia da semana

### Serviço de Métricas
- [x] Criado o serviço [metrics.py](../app/services/metrics.py) para acessar as métricas do banco de dados
- [x] Implementadas funções para cada tipo de métrica
- [x] Adicionados endpoints na API para fornecer dados ao dashboard

## Considerações Técnicas

1. **Performance**: As consultas foram otimizadas com índices adequados para evitar impactos no desempenho da aplicação principal
2. **Segurança**: As consultas utilizam parâmetros para evitar injeção de SQL
3. **Compatibilidade**: As consultas são compatíveis com PostgreSQL 15
4. **Manutenção**: As Views são fáceis de manter e atualizar conforme as necessidades mudarem

## Riscos e Mitigantes

- **Risco**: A estrutura do banco de dados da Evolution API pode mudar com atualizações
  - **Mitigante**: Documentar a versão específica da Evolution API utilizada e revisar após atualizações

- **Risco**: Consultas complexas podem impactar a performance do banco de dados principal
  - **Mitigante**: Avaliar a viabilidade de cópias para leitura (read replicas) ou banco de analytics separado

- **Risco**: Informações relevantes para métricas podem não estar armazenadas no banco da Evolution API
  - **Mitigante**: Ampliar o modelo de dados da aplicação para persistir informações necessárias para as métricas

## Próximos Passos

Após a implementação das consultas SQL:

1. [x] Validar as consultas no ambiente de desenvolvimento
2. [x] Ajustar conforme a estrutura real do banco de dados
3. [x] Implementar o endpoint de API (item 4.3) para fornecer essas métricas
4. [x] Integrar com a interface do dashboard (item 4.4)