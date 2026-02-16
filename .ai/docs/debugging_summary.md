# 🤖 Memória de Longo Prazo do Projeto

> **Regra:** Descreva lógica, não cole código. Mantenha objetivo.

## 1. Stack e Arquitetura
- Backend: FastAPI + PostgreSQL + Redis (Docker Compose)
- APIs: Azure TTS (REST), Evolution API (WhatsApp), OpenAI/Groq (IA)
- Infra: Mínima (1 container app + 1 banco + 1 cache)

## 2. Mapa de Arquivos (Responsabilidades)
- main.py: Orquestrador (inicializa app + rotas + proteção anti-flood)
- models/user.py: Modelo User com validações Pydantic
- models/webhook.py: Modelos Pydantic para validação do webhook da Evolution API v2
- services/evolution.py: Cliente assíncrono Evolution API (com retry e tratamento de erros)
- services/brain.py: Serviço de IA com OpenAI/Groq (raciocínio, audição e memória persistente)
- services/voice.py: Geração de áudio com Azure TTS (com retry)
- services/metrics.py: Serviço de métricas para o dashboard (com retry e backoff exponencial)
- services/appointment.py: Serviço de agendamento de reuniões
- services/notification.py: Serviço de notificação para erros críticos
- utils/lock.py: Gerenciador de locks com Redis
- utils/retry_handler.py: Implementação de retry com backoff exponencial
- utils/exceptions.py: Classes de exceções customizadas
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
- ✅ [2026-02-12] Serviço de retry → implementado mecanismo de retry com backoff exponencial para chamadas de API externas
- ✅ [2026-02-13] Serviço de agendamento → implementado AppointmentService para detectar intenções de agendamento e fornecer links de calendário
- ✅ [2026-02-13] Correção de histórico → corrigido problema de ordenação de timestamps no histórico de conversas
- ✅ [2026-02-14] Serviço de notificação → implementado sistema para notificar sobre erros críticos no pipeline
- ✅ [2026-02-14] Proteção anti-flood → implementada verificação de mensagens duplicadas e rate limiting