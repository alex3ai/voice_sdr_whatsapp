# 🤖 Memória de Longo Prazo do Projeto

> **Regra:** Descreva lógica, não cole código. Mantenha objetivo.

## 1. Stack e Arquitetura
- Backend: FastAPI + PostgreSQL + Redis (Docker Compose)
- APIs: Azure TTS (REST), Evolution API (WhatsApp)
- Infra: Mínima (1 container app + 1 banco + 1 cache)

## 2. Mapa de Arquivos (Responsabilidades)
- main.py: Orquestrador (inicializa app + rotas)
- models/user.py: Modelo User com validações Pydantic
- services/whatsapp.py: Cliente assíncrono Evolution API
- utils/lock.py: Gerenciador de locks com Redis
- services/metrics.py: Serviço de métricas para o dashboard
- create_metrics_views.sql: Consultas e Views SQL para extração de métricas
- .ai/docs/: Documentação técnica do projeto

## 3. Log de Soluções
- ✅ [2026-02-10] Conflito Azure SDK → substituído por aiohttp + REST
- ✅ [2026-02-10] Loop conexão WhatsApp → implementado asyncio.Lock no /qrcode
- ⚠️ [2026-02-10] Voz robótica → ajustando SSML para pt-BR-AntonioNeural
- ✅ [2026-02-11] Dashboard de métricas → implementado serviço de métricas com Views SQL
- ✅ [2026-02-11] Consultas SQL → criadas Views para extração de métricas de conversas, tipos de mensagem, atividade e desempenho
- ✅ [2026-02-11] Endpoints de métricas → adicionados endpoints na API para fornecer dados ao dashboard
- ✅ [2026-02-11] Conexão ao banco → adicionado suporte para conexão ao PostgreSQL com asyncpg
- ✅ [2026-02-11] Configuração → adicionados parâmetros de conexão ao banco na configuração
- ✅ [2026-02-11] Documentação → atualizados arquivos de documentação para refletir a implementação do dashboard de métricas
- ✅ [2026-02-11] Views de métricas → implementadas 10 Views SQL para diferentes tipos de métricas do sistema