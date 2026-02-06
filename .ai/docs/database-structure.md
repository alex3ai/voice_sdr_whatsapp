# Estrutura de Dados e Persistência

Este documento descreve a arquitetura de dados, esquemas de banco de dados e a estratégia de persistência utilizada no projeto **Voice SDR WhatsApp**.

## 1. Arquitetura de Dados e Serviços

A arquitetura do projeto é dividida em dois componentes principais: a **Evolution API**, que gerencia a comunicação com o WhatsApp e a persistência dos dados, e o **SDR Bot**, que contém a lógica de negócio e a inteligência artificial.

### a. Infraestrutura da Evolution API

A Evolution API é a camada responsável por toda a interação com a plataforma do WhatsApp. Ela depende de dois serviços de dados essenciais:

*   **PostgreSQL:** Atua como o banco de dados principal (*Source of Truth*). Armazena o histórico de mensagens, contatos e configurações das instâncias, garantindo a memória de longo prazo para as interações.
*   **Redis:** Utilizado como um armazenamento em memória de alta performance (*Cache*). Gerencia as sessões ativas do WhatsApp (Baileys), filas de processamento e armazena dados temporários para agilizar as operações.

### b. Arquitetura do SDR Bot

O **SDR Bot** (`sdr-bot`) é a aplicação que implementa o agente de vendas inteligente. Sua arquitetura foi projetada para ser desacoplada e eficiente:

*   **Imagem Leve:** O bot é executado em um contêiner Docker baseado na imagem `python:3.10-slim`, garantindo um ambiente de execução enxuto e com baixo consumo de recursos.
*   **Stateless e Desacoplado:** A aplicação é *stateless*, ou seja, não mantém um banco de dados próprio. Ela consome os dados exclusivamente através da **Evolution API**.
*   **Sem Dependência de Drivers:** Por interagir apenas com a API via REST, o `sdr-bot` não necessita de drivers de banco de dados (como `psycopg2`) ou qualquer conexão direta com o PostgreSQL ou Redis. Isso simplifica sua configuração e o torna mais seguro e fácil de manter.

## 2. Serviços de Dados

Os serviços são orquestrados via `docker-compose.yml` e não expõem portas para a internet pública, apenas para a rede interna Docker `voice_sdr_network`.

### a. PostgreSQL
*   **Imagem Docker:** `postgres:15`
*   **Nome do Contêiner:** `evolution_postgres`
*   **Banco de Dados:** `evolution`
*   **Usuário:** `evolution`
*   **Volume:** `./evolution_data/postgres` mapeado para `/var/lib/postgresql/data`.

### b. Redis
*   **Imagem Docker:** `redis:alpine`
*   **Nome do Contêiner:** `evolution_redis`
*   **Volume:** `./evolution_data/redis` mapeado para `/data`.
*   **Configuração:** Persistência AOF ativada (`appendonly yes`) para evitar perda de sessão em caso de restart.

## 3. Volumes Persistentes (Bind Mounts)

Para garantir a durabilidade dos dados entre reinicializações de contêineres ou do servidor host, os seguintes diretórios locais são mapeados:

| Diretório no Host | Destino no Container | Descrição Técnica |
| :--- | :--- | :--- |
| `./evolution_data/postgres` | `/var/lib/postgresql/data` | Arquivos binários do DB (Tabelas, Índices, WAL). |
| `./evolution_data/redis` | `/data` | Arquivo `appendonly.aof` (Log de operações do Redis). |
| `./evolution_data/instances` | `/evolution/instances` | Credenciais de autenticação do Baileys (tokens de sessão). |
| `./evolution_data/store` | `/evolution/store` | Cache de mídia e arquivos temporários da API. |

## 4. Esquemas de Dados e Contexto

A Evolution API v2 utiliza o **Prisma ORM** para gerenciar o esquema do banco. A aplicação `sdr-bot` não acessa o banco diretamente via SQL, mas consome esses dados através dos endpoints REST da Evolution API (ex: `/chat/findMessages`).

Para que a Inteligência Artificial (Gemini) tenha memória, a variável de ambiente `DATABASE_SAVE_DATA_NEW_MESSAGE=true` foi ativada na Evolution API. Isso garante que cada interação seja salva na tabela `Message` do Postgres.

### Tabela Lógica: Message (Abstração)

Abaixo, a representação dos dados que a Evolution API persiste e entrega ao `sdr-bot` quando o histórico é solicitado.

| Campo (Conceitual) | Tipo de Dado | Origem no Webhook / API | Descrição |
| :--- | :--- | :--- | :--- |
| **id** | `String` | `data.key.id` | Identificador único da mensagem no WhatsApp. |
| **remoteJid** | `String` | `data.key.remoteJid` | ID do chat/usuário (ex: `551199999999@s.whatsapp.net`). Chave principal para busca de contexto. |
| **fromMe** | `Boolean` | `data.key.fromMe` | Define se a mensagem foi enviada pelo Bot (`true`) ou pelo Cliente (`false`). Essencial para a IA saber quem falou o quê. |
| **instanceId** | `String` | `instance` | Vincula a mensagem à instância `voice_sdr_v4`. |
| **pushName** | `String` | `data.pushName` | Nome público do usuário (usado pela IA para personalização). |
| **messageType** | `String` | `data.messageType` | Ex: `audioMessage`, `conversation`, `extendedTextMessage`. |
| **body** | `Text` | `data.message...` | O conteúdo transcrito ou textual da mensagem. |
| **mediaUrl** | `Text` | `data.message.audioMessage.url` | Link interno para o arquivo de áudio (se houver). |
| **createdAt** | `DateTime` | `date_time` | Timestamp da mensagem. Usado para ordenar o histórico enviado ao Gemini. |

## 5. Fluxo de Persistência e Recuperação

1.  **Escrita (Write):** Quando o cliente envia um áudio, a Evolution API processa o recebimento e grava automaticamente o registro no PostgreSQL (graças à flag `SAVE_DATA_NEW_MESSAGE`).
2.  **Notificação:** Simultaneamente, a Evolution API dispara o Webhook para o `sdr-bot`.
3.  **Leitura (Read):** O `sdr-bot` recebe o webhook e executa uma chamada `GET /chat/findMessages/{remoteJid}` para a Evolution API.
4.  **Consulta:** A Evolution API consulta o PostgreSQL, recupera as últimas mensagens (ex: últimas 10) e retorna o JSON para o `sdr-bot`.
5.  **Contexto:** O `sdr-bot` injeta esse histórico no prompt do Gemini.