# User Stories

Com base em .ai/docs/00_project-description.md, estas são as user stories no formato especificado:

- [x] **Como** um gerente de vendas, **quero** ter acesso a um dashboard centralizado **para** poder visualizar as conversas em andamento, analisar o desempenho do SDR Bot e medir a eficácia das interações com os clientes.
  **Critérios:**
  - Dado que o dashboard esteja disponível, quando o gerente acessar o sistema, então deverá visualizar métricas de conversas ativas e finalizadas
  - Regra de negócio: O dashboard deve exibir número de conversas ativas e finalizadas
  - Edge case: O dashboard deve permitir filtrar conversas por período (data de início e fim)

- [x] **Como** um desenvolvedor, **quero** que o sistema tenha um mecanismo robusto de tratamento de exceções **para** que falhas em qualquer etapa do pipeline (download, IA, TTS, envio) sejam capturadas, registradas e, se necessário, comunicadas a uma equipe de suporte.
  **Critérios:**
  - Dado uma falha na comunicação com a Evolution API, quando o sistema tentar se comunicar, então deverá registrar detalhes (endpoint, status code)
  - Regra de negócio: Erros na API do OpenRouter (ex: conteúdo inapropriado, falha na transcrição) devem ser tratados de forma específica
  - Edge case: Implementar um sistema de *retries* com *exponential backoff* para falhas de rede

- [x] **Como** um usuário final, **quero** que o SDR Bot seja capaz de entender e responder a mensagens de texto, além de áudio, **para** que eu possa interagir da forma que for mais conveniente para mim.
  **Critérios:**
  - Dado que o webhook receba uma mensagem, quando for do tipo texto, então deverá ser diferenciada de uma mensagem de áudio
  - Regra de negócio: Se a mensagem for de texto, o pipeline deve pular as etapas de download e transcrição de áudio
  - Edge case: A resposta pode ser em áudio (padrão) ou em texto, dependendo da configuração

- [x] **Como** um gerente de vendas, **quero** que o SDR Bot seja capaz de identificar a intenção de agendar uma reunião e coordenar um horário com o cliente **para** automatizar a conversão de um lead qualificado em uma reunião de vendas.
  **Critérios:**
  - Dado que o cliente demonstre interesse em agendar uma reunião, quando a IA processar a mensagem, então deverá reconhecer a intenção
  - Regra de negócio: O bot deve ser capaz de consultar uma agenda (ex: Google Calendar, Calendly) via API para verificar a disponibilidade
  - Edge case: Após a confirmação do cliente, o bot deve criar o evento na agenda e enviar um convite

- [x] **Como** um gerente de vendas, **quero** ter acesso a métricas detalhadas sobre o desempenho do SDR Bot **para** poder analisar tendências, volume de conversas e eficácia das interações.
  **Critérios:**
  - Dado que o sistema tenha registrado interações, quando o gerente acessar o dashboard, então deverá visualizar métricas de volume de conversas, tipos de mensagem e atividade temporal
  - Regra de negócio: As métricas devem estar disponíveis via endpoints de API específicos
  - Edge case: O sistema deve continuar funcionando mesmo que o banco de dados de métricas esteja temporariamente indisponível

- [x] **Como** um administrador, **quero** ter controles de segurança e autenticação **para** proteger o acesso às funcionalidades do SDR Bot.
  **Critérios:**
  - Dado que um usuário tente acessar os endpoints, quando não estiver autenticado, então deverá receber erro de autorização
  - Regra de negócio: Somente usuários autenticados podem acessar os dados sensíveis
  - Edge case: O sistema deve implementar rate limiting para prevenir abuso