# Estrutura de Dados e Persistência

Este documento descreve a arquitetura de dados, esquemas de banco de dados e a estratégia de persistência utilizada no projeto **Voice SDR WhatsApp**.

## 1. Resumo da Infraestrutura de Dados

O projeto utiliza dois serviços de dados essenciais que dão suporte à **Evolution API**. Embora a aplicação `sdr-bot` seja *stateless* (não mantém banco próprio), ela depende inteiramente da integridade desses dados para recuperar o contexto das conversas.

*   **PostgreSQL:** Banco de dados relacional (*Source of Truth*). Armazena o histórico de mensagens, contatos e configurações das instâncias. É fundamental para a memória da IA.
*   **Redis:** Armazenamento em memória (*Cache*). Gerencia sessões do WhatsApp (Baileys), filas de processamento e cache de mensagens recentes para alta performance.

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