# 🤖 CONTEXTO DO PROJETO & DIRETRIZES DE MANUTENÇÃO

> **INSTRUÇÃO PARA O ASSISTENTE DE INTELIGÊNCIA ARTIFICIAL:**
> Este arquivo atua como a "Memória de Longo Prazo" do projeto. Ao atualizá-lo, siga estritamente:
> 1.  **Abstração:** Não cole trechos de código. Descreva apenas a lógica, fluxo de dados e responsabilidade dos arquivos.
> 2.  **Objetividade:** Mantenha o resumo da arquitetura focado em "Quem faz o quê" (Ex: Main orquestra, Brain processa IA, Voice gera áudio).
> 3.  **Depuração:** Substitua narrativas longas por uma lista concisa: `[Status] Problema -> Solução Resumida`.
> 4.  **Atualização:** Ao adicionar novas features, atualize apenas a seção relevante sem reescrever o documento todo.

---
## 1. Stack e Arquitetura Atual
- **Framework Backend:** FastAPI
- **Comunicação WhatsApp:** Evolution API (V2)
- **Containerização:** Docker & Docker Compose
- **IA - Transcrição (Audio-to-Text):** Groq Cloud (usando o modelo Whisper-large-v3)
- **IA - Raciocínio (Text-to-Text):** Groq Cloud (modelo: llama-3.3-70b-versatile)
- **IA - Síntese de Voz (Text-to-Speech):** Azure Cognitive Services (via API REST)
- **Libs de HTTP Assíncrono:** `httpx` (cliente principal) e `aiohttp` (para o serviço de voz)
- **Configuração:** Pydantic (para carregar e validar variáveis de ambiente)

## 2. Mapa de Arquivos (Resumo Lógico)
- `app/main.py`: **Orquestrador Central.** Ponto de entrada da API FastAPI. Gerencia as rotas HTTP (`/webhook`, `/qrcode`, etc.), o estado da conexão e coordena o pipeline de resposta (download -> cérebro -> voz -> envio). Agora inclui serviço de notificação para erros críticos.
- `app/config.py`: **Guardião das Configurações.** Carrega, valida e centraliza todas as variáveis de ambiente (chaves de API, URLs, etc.) usando Pydantic, garantindo que a aplicação inicie apenas com as configurações corretas. Inclui configurações para o serviço de notificação.
- `app/services/evolution.py`: **Ponte com o WhatsApp.** Encapsula toda a lógica de comunicação com a Evolution API. É responsável por gerenciar a instância (criar, conectar, deletar), enviar mensagens (texto e áudio) e fazer o download de mídias recebidas. Agora inclui notificação de erros críticos.
- `app/services/brain.py`: **O Cérebro da IA.** Orquestra a inteligência do bot. Utiliza o **"Ouvido"** (Groq) para transcrever o áudio do usuário e o **"Cérebro"** (OpenRouter) para interpretar o texto e formular uma resposta coesa, seguindo o prompt de sistema.
- `app/services/voice.py`: **A Voz do Bot.** Responsável por converter a resposta em texto do Cérebro em um áudio com som natural. Comunica-se com a API REST da Azure para gerar a nota de voz no formato OGG/Opus, ideal para o WhatsApp. Agora inclui notificação de falhas críticas e múltiplas estratégias de fallback (SDK Azure, API REST, Edge TTS).
- `app/services/notification.py`: **Serviço de Notificação.** Novo componente que fornece uma interface genérica para envio de notificações de erro crítico, com implementações para console e arquivo.
- `app/utils/logger.py`: **O Escriba.** Configura um sistema de logging robusto para registrar eventos da aplicação, tanto no console quanto em arquivos, facilitando a depuração.
- `docker-compose.yml`: **O Maestro do Ambiente.** Define e orquestra os contêineres Docker necessários para rodar a aplicação e seus serviços dependentes (se houver) em um ambiente isolado e consistente.
- `dockerfile`: **A Receita do Contêiner.** Contém as instruções passo a passo para construir a imagem Docker da aplicação, instalando dependências e configurando o ambiente de execução.

## 3. Log de Soluções e Decisões Técnicas
- ✅ **Erro 2176 (Azure SDK):** Substituído SDK pesado por API REST via `aiohttp`. Resolvido conflito de dependências Linux.
- ✅ **Loop de Conexão:** Implementado `asyncio.Lock` no endpoint `/qrcode`.
- ✅ **Voz Robótica:** Configurado SSML para voz `pt-BR-AntonioNeural` via Azure.
- ✅ **Substituição do Gemini:** Migrado de Gemini para Groq com modelo llama-3.3-70b-versatile para maior flexibilidade.
- ✅ **Melhoria no STT:** Adotado Groq Whisper para transcrição mais rápida e precisa.
- ✅ **Notificações de Erro Crítico:** Implementado serviço de notificação genérico com interfaces para console e arquivo, integrado com os principais componentes do sistema.
- ✅ **Erro de Validação Pydantic:** Resolvido conflito entre campos Pydantic e propriedades personalizadas na classe Settings.
- ✅ **Importação Incorreta:** Corrigido import de função inexistente 'Logger' para função correta 'setup_logger'.
- ✅ **Configurações Ausentes:** Adicionados campos obrigatórios para Azure TTS que estavam faltando na classe Settings.
- ✅ **Atributo Obsoleto:** Removido atributo 'version' obsoleto do docker-compose.yml.
- ✅ **Método Ausente:** Implementado método 'connect_to_existing_instance' na classe EvolutionService para lidar com instâncias já existentes.
- ✅ **Falha na Autenticação Azure TTS:** Implementado método de obtenção de token de autorização via endpoint `/sts/v1.0/issueToken` em vez de usar diretamente a chave de subscrição no cabeçalho da requisição.
- ✅ **Erro 400 na API REST do Azure:** Simplificado o SSML para evitar problemas de formatação e garantir compatibilidade com a API.
- ✅ **Problema de Volume Baixo:** Ajustado controle de volume no SSML para aumentar a audibilidade do áudio gerado.
- ✅ **Formato de Áudio Incompatível:** Alterado formato de saída para `ogg-24khz-16bit-mono-opus` para melhor compatibilidade com o WhatsApp.
- ✅ **Múltiplos Mecanismos de Fallback:** Implementado sistema robusto com Azure SDK, API REST e Edge TTS como estratégias de contingência para garantir sempre uma resposta de áudio.