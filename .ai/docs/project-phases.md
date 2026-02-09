# Plano de Execução do Projeto: Voice SDR WhatsApp

Este documento detalha as fases e tarefas planejadas para a evolução do projeto, com base nas `User Stories` e no estado atual da aplicação.

---

## Fase 1: Refatoração e Adequação

**Objetivo:** Fortalecer a base do código existente para garantir que ele seja robusto, testável e preparado para receber novas funcionalidades.

-   [x] **1.1.** Revisar e centralizar o tratamento de exceções nos serviços (`app/services/`). Implementar exceções customizadas para falhas de comunicação com APIs externas (Evolution, OpenRouter).
-   [x] **1.2.** Padronizar o uso do logger (`app/utils/logger.py`) em todos os módulos, garantindo que os logs sejam estruturados e informativos.
-   [x] **1.3.** Validar o fluxo de recuperação de histórico de conversas (`/chat/findMessages`) para garantir que o contexto está sendo enviado corretamente à IA em todas as interações.
-   [x] **1.4.** Mover a lógica de processamento do webhook em`main.py` para uma função dedicada em `app/services/brain.py` para melhorar a organização.
-   [x] **1.5.** Migração de TTS para Azure REST e STT para Groq.

---

## Fase 2: Suporte a Múltiplos Tipos de Mensagem

**Objetivo:** Implementar a capacidade do bot de processar e responder a mensagens de texto, além de áudio.

-   [x] **2.1.** Modificar o modelo de dados em `app/models/webhook.py` para tratar eventos de mensagem de texto (`text`).
-   [x] **2.2.** Atualizar o endpoint do webhook em  `main.py` para identificar o tipo de mensagem recebida (áudio vs. texto).
-   [x] **2.3.** Adaptar a lógica principal para que, ao receber uma mensagem de texto, o fluxo pule as etapas de download e transcrição de áudio.
-   [x] **2.4.** Adicionar uma variável de ambiente (`RESPONSE_TYPE`) em `app/config.py` para permitir configurar o tipo de resposta (áudio ou texto).
-   [x] **2.5.** Implementar a lógica de resposta para que o bot envie uma mensagem de texto se `RESPONSE_TYPE` for definido como `text`.

---

## Fase 3: Tratamento Avançado de Erros e Notificações

**Objetivo:** Aumentar a resiliência do sistema com mecanismos avançados de tratamento de falhas.

-   [ ] **3.1.** Implementar uma função *wrapper* ou decorador com lógica de *retries* e *exponential backoff* para todas as chamadas de API externas nos serviços.
-   [ ] **3.2.** Criar um módulo de notificação (`app/services/notification.py`) com uma interface genérica e uma implementação inicial (ex: log para um arquivo crítico ou print no console).
-   [ ] **3.3.** Integrar o serviço de notificação para que erros críticos no pipeline disparem um alerta.

---

## Fase 4: Dashboard de Métricas e Conversas

**Objetivo:** Desenvolver uma interface web para monitoramento de conversas e análise de performance do bot.

-   [ ] **4.1.** criar consultas SQL (ou Views) no banco existente para extrair as métricas.
-   [ ] **4.2.** Criar uma nova aplicação web (ex: com FastAPI e templates Jinja2, ou um framework frontend como React) para o dashboard.
-   [ ] **4.3.** Desenvolver os endpoints de API para alimentar o dashboard com as métricas (nº de conversas, tempo médio de resposta, etc.).
-   [ ] **4.4.** Implementar a interface do usuário (UI) para exibir as métricas e permitir a visualização do histórico de conversas.
-   [ ] **4.5.** Adicionar filtros por período de data na API e na UI do dashboard.

---

## Fase 5: Agendamento de Reuniões

**Objetivo:** Capacitar o bot a identificar a intenção de agendamento e coordenar horários com os clientes.

-   [ ] **5.1** (MVP): O bot apenas envia um link do Calendly/Google Agenda para o cliente agendar sozinho. (Fácil, resolve 80% do problema).
-   [ ] **5.2** (Full): Integração via API para agendar diretamente pelo chat (Difícil, fazer só se o 5.1 não converter bem).