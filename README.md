# 🎙️ Voice SDR WhatsApp

Assistente de vendas autônomo (SDR Bot) que opera via WhatsApp, capaz de receber mensagens de áudio e texto, processá-las com IA e responder de forma contextualizada — simulando uma conversa humana fluida 24/7.

---

## 📋 Sumário

- [Visão Geral](#visão-geral)
- [Stack Tecnológica](#stack-tecnológica)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Configuração](#instalação-e-configuração)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Executando o Projeto](#executando-o-projeto)
- [Endpoints da API](#endpoints-da-api)
- [Dashboard de Métricas](#dashboard-de-métricas)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Testes](#testes)

---

## Visão Geral

O **Voice SDR WhatsApp** automatiza o primeiro contato e a qualificação de leads via WhatsApp. O bot:

- Recebe mensagens de **áudio** e **texto**
- Transcreve áudios com **Groq Whisper**
- Gera respostas contextualizadas com **LLaMA 3.3 70B** (via Groq)
- Converte respostas para voz com **Azure TTS** ou **Edge TTS**
- Detecta intenções de agendamento e fornece links de calendário
- Rejeita educadamente perguntas fora do escopo da empresa
- Expõe um dashboard de métricas para análise de desempenho

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Python + FastAPI |
| Servidor ASGI | Uvicorn |
| Gateway WhatsApp | Evolution API v2 |
| IA — Transcrição (STT) | Groq Whisper (`whisper-large-v3`) |
| IA — Raciocínio (LLM) | Groq LLaMA (`llama-3.3-70b-versatile`) |
| Síntese de Voz (TTS) | Azure Cognitive Services + Edge TTS (fallback) |
| Banco de Dados | PostgreSQL 15 |
| Cache | Redis |
| Containerização | Docker + Docker Compose |

---

## Arquitetura

```
WhatsApp ──► Evolution API ──► Webhook (/webhook/evolution)
                                        │
                              ┌─────────▼─────────┐
                              │   main.py          │
                              │  (Orquestrador)    │
                              └────────┬──────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
      ┌───────▼──────┐       ┌─────────▼────────┐    ┌────────▼───────┐
      │ evolution.py │       │   brain.py        │    │   voice.py     │
      │ (Download /  │       │ (Transcrição +    │    │ (Azure TTS /   │
      │   Envio)     │       │  LLM + Memória)   │    │  Edge TTS)     │
      └──────────────┘       └──────────────────┘    └────────────────┘
                                       │
                              ┌────────▼─────────┐
                              │ appointment.py    │
                              │ (Agendamento)     │
                              └──────────────────┘
```

### Pipeline de Processamento

1. **Recepção** — Evolution API dispara evento para o webhook
2. **Filtros** — Anti-flood, duplicatas, mensagens antigas (> 60s)
3. **Download** *(somente áudio)* — Mídia baixada via Base64
4. **Transcrição** *(somente áudio)* — Groq Whisper converte áudio → texto
5. **Intenção de Agendamento** — Verificação antes do LLM
6. **Raciocínio** — LLaMA gera resposta contextualizada com histórico
7. **Síntese de Voz** *(modo áudio)* — Azure TTS ou Edge TTS
8. **Envio** — Resposta enviada via Evolution API

---

## Funcionalidades

### Conversação
- Suporte a mensagens de **áudio** (PTT) e **texto**
- Histórico de conversa persistido em `chat_history.json`
- Janela de contexto de até 20 interações por usuário
- Respostas configuráveis como **áudio** ou **texto**

### Qualificação de Leads
- Persona SDR com foco nos serviços da empresa
- Filtragem automática de perguntas fora do escopo
- Detecção de intenção de agendamento com envio de link (Calendly/Google Agenda)

### Resiliência
- Retry com exponential backoff em todas as chamadas externas
- Proteção anti-flood com cache de IDs de mensagens processadas
- Rate limiting configurável por IP
- Fallback de TTS: Azure → Edge TTS

### Segurança
- Autenticação via `X-API-Key` em endpoints sensíveis
- Validação de assinatura HMAC-SHA256 dos webhooks
- Sanitização de dados de entrada

### Métricas
- Dashboard com Views SQL no PostgreSQL
- Endpoints REST para alimentar frontends ou ferramentas de BI
- Dados de volume, tipos de mensagem, taxa de resposta e atividade temporal

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/)
- Conta na [Groq](https://console.groq.com/) (STT + LLM)
- Conta no [Azure](https://azure.microsoft.com/) (opcional, para TTS de alta qualidade)
- Número de WhatsApp para conectar à Evolution API

---

## Instalação e Configuração

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/voice-sdr-whatsapp.git
cd voice-sdr-whatsapp
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas chaves (veja a seção [Variáveis de Ambiente](#variáveis-de-ambiente)).

### 3. Crie o arquivo de histórico

```bash
echo "{}" > chat_history.json
```

> **Windows:** Crie o arquivo manualmente como `chat_history.json` com conteúdo `{}`.

### 4. (Opcional) Configure as Views SQL de métricas

```bash
# Após o PostgreSQL estar rodando:
docker exec -i evolution_postgres psql -U evolution -d evolution < create_metrics_views.sql
```

---

## Variáveis de Ambiente

| Variável | Obrigatório | Descrição | Exemplo |
|---|---|---|---|
| `EVOLUTION_API_URL` | ✅ | URL da Evolution API | `http://evolution_whatsapp:8080` |
| `EVOLUTION_API_KEY` | ✅ | Chave global da Evolution API | `123456` |
| `EVOLUTION_INSTANCE_NAME` | ✅ | Nome da instância WhatsApp | `voice_sdr_v1` |
| `OPENAI_API_KEY` | ✅ | Chave da API Groq | `gsk_...` |
| `OPENAI_BASE_URL` | ✅ | Base URL do LLM | `https://api.groq.com/openai/v1/` |
| `OPENAI_MODEL` | ✅ | Modelo de linguagem | `llama-3.3-70b-versatile` |
| `GROQ_API_KEY` | ✅ | Chave Groq para Whisper (STT) | `gsk_...` |
| `AZURE_TTS_SUBSCRIPTION_KEY` | ⬜ | Chave Azure TTS | `abc123...` |
| `AZURE_TTS_REGION` | ⬜ | Região Azure | `brazilsouth` |
| `AZURE_TTS_VOICE_NAME` | ⬜ | Voz Azure | `pt-BR-AntonioNeural` |
| `EDGE_TTS_VOICE` | ⬜ | Voz Edge TTS (fallback) | `pt-BR-FrancisNeural` |
| `RESPONSE_TYPE` | ⬜ | Tipo de resposta | `audio` ou `text` |
| `CALENDAR_LINK` | ⬜ | Link de agendamento | `https://calendly.com/...` |
| `API_KEY` | ⬜ | Chave para proteger endpoints | `minha-chave-secreta` |
| `DATABASE_HOST` | ⬜ | Host do PostgreSQL | `postgres` |
| `DATABASE_PORT` | ⬜ | Porta do PostgreSQL | `5432` |
| `DATABASE_USER` | ⬜ | Usuário do banco | `evolution` |
| `DATABASE_PASSWORD` | ⬜ | Senha do banco | `evolution` |
| `DATABASE_NAME` | ⬜ | Nome do banco | `evolution` |
| `NOTIFICATION_TYPE` | ⬜ | Canal de notificação de erros | `console` ou `file` |
| `RATE_LIMIT_MAX_REQUESTS` | ⬜ | Máx. requisições por janela | `10` |
| `RATE_LIMIT_WINDOW_SECONDS` | ⬜ | Janela do rate limit (s) | `60` |

---

## Executando o Projeto

### Subir todos os serviços

```bash
docker compose up -d
```

Isso inicializa: PostgreSQL → Redis → Evolution API → SDR Bot

### Conectar ao WhatsApp

1. Acesse `http://localhost:8000/qrcode`
2. Escaneie o QR Code com seu WhatsApp
3. Aguarde a confirmação de conexão

### Verificar status

```bash
# Health check
curl http://localhost:8000/health

# Status e métricas em memória
curl http://localhost:8000/
```

### Parar os serviços

```bash
docker compose down
```

### Resetar a sessão WhatsApp

Acesse `http://localhost:8000/reset` para deletar a instância e gerar um novo QR Code.

---

## Endpoints da API

### Públicos (sem autenticação)

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/` | Dashboard JSON com métricas e status |
| `GET` | `/health` | Health check para o Docker |
| `GET` | `/qrcode` | Interface visual para conexão WhatsApp |
| `GET` | `/reset` | Reseta a instância WhatsApp |
| `POST` | `/webhook/evolution` | Webhook principal da Evolution API |

### Protegidos (requerem `X-API-Key` no header)

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/metrics/daily_conversations` | Métricas diárias de conversas |
| `GET` | `/metrics/active_chats` | Conversas ativas nas últimas 24h |
| `GET` | `/metrics/message_types` | Distribuição de tipos de mensagem |
| `GET` | `/metrics/bot_response_rate` | Taxa de resposta do bot |
| `GET` | `/metrics/system_wide` | KPIs gerais do sistema |

Todos os endpoints de métricas retornam dados no formato `{"data": [...]}`.

---

## Dashboard de Métricas

O sistema utiliza **Views SQL** no PostgreSQL para extração eficiente de métricas. As principais views são:

| View | Descrição |
|---|---|
| `conversation_metrics` | Conversas e mensagens por dia |
| `active_conversations` | Chats ativos nas últimas 24h |
| `message_type_distribution` | Áudio, texto, imagem, documento |
| `bot_response_rate` | Taxa de resposta do bot |
| `daily_performance_metrics` | Performance e tempo de resposta diário |
| `conversations_by_client` | Engajamento por número de cliente |
| `system_wide_metrics` | KPIs gerais do sistema |
| `hourly_activity` | Atividade por hora do dia |
| `weekly_activity` | Atividade por dia da semana |

Para criar as views, execute:

```bash
docker exec -i evolution_postgres psql -U evolution -d evolution < create_metrics_views.sql
```

---

## Estrutura do Projeto

```
voice-sdr-whatsapp/
│
├── app/
│   ├── main.py                  # Entrypoint FastAPI, rotas e pipeline
│   ├── config.py                # Configurações via Pydantic Settings
│   │
│   ├── models/
│   │   └── webhook.py           # Modelos Pydantic para Evolution API v2
│   │
│   ├── services/
│   │   ├── brain.py             # IA: transcrição, LLM, memória
│   │   ├── evolution.py         # Cliente Evolution API
│   │   ├── voice.py             # Azure TTS + Edge TTS
│   │   ├── metrics.py           # Serviço de métricas do PostgreSQL
│   │   ├── appointment.py       # Detecção de intenção de agendamento
│   │   └── notification.py      # Notificações de erros críticos
│   │
│   └── utils/
│       ├── logger.py            # Logger com handler de arquivo e console
│       ├── exceptions.py        # Exceções customizadas
│       ├── retry_handler.py     # Decorator de retry com exponential backoff
│       ├── security.py          # Autenticação, rate limiting e validação
│       └── files.py             # Gerenciamento de arquivos temporários
│
├── tests/
│   └── simulate.py              # Simulador de webhook para testes locais
│
├── create_metrics_views.sql     # Views SQL para o dashboard de métricas
├── dashboard_metrics.sql        # Views SQL alternativas
├── chat_history.example.json    # Exemplo do arquivo de histórico
├── docker-compose.yml           # Orquestração dos containers
├── Dockerfile                   # Build da aplicação Python
├── requirements.txt             # Dependências Python
└── .env.example                 # Exemplo de configuração
```

---

## Testes

### Simular um webhook de áudio

```bash
# Certifique-se que o bot está rodando em localhost:8000
python tests/simulate.py
```

Edite `tests/simulate.py` para alterar o número de destino e o tipo de mensagem antes de executar.

### Testar endpoints de métricas

```bash
curl -H "X-API-Key: sua-chave" http://localhost:8000/metrics/system_wide
```

---

## Solução de Problemas

**Bot não responde após escanear o QR Code**
Aguarde alguns segundos e verifique os logs: `docker compose logs sdr-bot -f`

**Erro de conexão com banco de dados nas métricas**
Confirme que `DATABASE_HOST=postgres` no `.env` e que o container do PostgreSQL está saudável: `docker compose ps`

**Voz robótica ou falha no TTS**
Verifique se `AZURE_TTS_SUBSCRIPTION_KEY` e `AZURE_TTS_REGION` estão corretos. O sistema fará fallback automático para Edge TTS.

**Mensagens não chegando ao webhook**
Confirme que `WEBHOOK_GLOBAL_URL` no `docker-compose.yml` aponta para o container correto (`http://voice_sdr_bot:8000/webhook/evolution`).

---

## Licença

Este projeto é privado e de uso interno. Todos os direitos reservados.
