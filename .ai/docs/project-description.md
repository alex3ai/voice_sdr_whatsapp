# Descrição do Projeto: Voice SDR WhatsApp

## 1. Objetivo do Projeto

O projeto **Voice SDR WhatsApp** é um assistente de vendas autônomo (Sales Development Representative - SDR) que opera via WhatsApp. Seu principal objetivo é receber mensagens de áudio de clientes, processar o conteúdo com Inteligência Artificial para entender a intenção, e responder de forma contextualizada com uma nova mensagem de áudio, simulando uma conversa humana fluida.

O sistema é projetado para automatizar o primeiro contato e a qualificação de leads, respondendo a perguntas frequentes e coletando informações iniciais 24/7.

Embora o sdr-bot não possua banco de dados próprio (stateless), ele utiliza a Evolution API como fonte de histórico. Para garantir o contexto da conversação na IA, o bot consulta o histórico de mensagens via API REST (/chat/findMessages) antes de processar cada resposta.
---

## 2. Stack Tecnológica

A solução é construída sobre um ecossistema de serviços containerizados, orquestrados com Docker Compose.

-   **Linguagem Principal:** Python
-   **Framework Backend:** FastAPI (versão `0.115.0`)
-   **Servidor ASGI:** Uvicorn

### Serviços Essenciais:
-   **WhatsApp Gateway:** Evolution API (Imagem Docker `atendai/evolution-api:v2.3.0`)
-   **Inteligência Artificial (Cérebro):** Arquitetura híbrida com Groq (Whisper) para transcrição e OpenRouter/Gemini para inteligência.
-   **Conversão de Texto para Fala (TTS):** Azure Cognitive Services (API REST)
-   **Banco de Dados (para Evolution API):** PostgreSQL 15
-   **Cache (para Evolution API):** Redis

### Containerização:
-   **Orquestração:** Docker Compose (`docker-compose.yml`)
-   **Imagens:** Dockerfile customizado para a aplicação Python e imagens públicas para os demais serviços.

---

## 3. Arquitetura da Aplicação

A arquitetura é baseada em microsserviços desacoplados que se comunicam através de uma rede Docker interna.

-   **Ponto de Entrada:** O serviço `sdr-bot` expõe uma API RESTful construída com FastAPI. O endpoint principal é um `webhook` (`/webhook/evolution`) que recebe eventos da Evolution API.
-   **Fluxo de Mensagens (Pipeline de Áudio):**
    1.  A **Evolution API** recebe uma mensagem de áudio no WhatsApp e dispara um evento para o webhook do `sdr-bot`.
    2.  O `sdr-bot` recebe o evento e inicia uma tarefa em background para não bloquear a API.
    3.  **Download:** O áudio é baixado da Evolution API.
    4.  **Transcrição (Ouvido):** O arquivo de áudio é enviado para a API do **Groq**, que utiliza o modelo **Whisper** para transcrevê-lo rapidamente.
    5.  **Inteligência (Cérebro):** O texto transcrito é enviado para um provedor de IA (**OpenRouter** ou **Gemini**) para gerar uma resposta textual contextualizada.
    6.  **Geração de Voz (TTS):** O texto gerado pela IA é convertido em um novo arquivo de áudio usando a API REST do **Azure Cognitive Services**.
    7.  **Envio da Resposta:** O novo áudio é enviado de volta para a Evolution API, que o encaminha para o usuário no WhatsApp como uma resposta à mensagem original.
-   **Camadas da Aplicação (`app/`):**
    -   `main.py`: Entrypoint da API, gerenciamento de rotas e webhooks.
    -   `services/`: Lógica de negócio desacoplada.
        -   `evolution.py`: Comunicação com a Evolution API.
        -   `brain.py`: Interação com o Google Gemini.
        -   `voice.py`: Geração de áudio.
    -   `utils/`: Funções auxiliares (logs, manipulação de arquivos).
    -   `config.py`: Gerenciamento de configurações via variáveis de ambiente.

---

## 4. Estado Atual do Desenvolvimento

O projeto está em um estágio funcional e bem estruturado.

-   A infraestrutura com Docker Compose está completa e funcional, permitindo que todo o ecossistema seja iniciado com um único comando.
-   O pipeline principal de processamento de áudio (receber, entender, responder) está implementado e operacional.
-   Possui uma interface web simples para facilitar a conexão com o WhatsApp através da leitura de um QR Code.
-   Endpoints de monitoramento (`/health`, `/status`) e um dashboard básico (`/`) estão implementados.
-   O código está organizado, comentado e utiliza boas práticas como o uso de tarefas em background e gerenciamento centralizado de configurações.
-   O sistema está pronto para testes em um ambiente de desenvolvimento e potencialmente para implantação em produção com as devidas configurações de segurança e escalabilidade.
