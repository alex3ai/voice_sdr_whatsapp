# User Stories

Com base em .ai/docs/00_project-description.md, estas são as user stories no formato especificado:

- [ ] **Como** um gerente de vendas, **quero** ter acesso a um dashboard centralizado **para** poder visualizar as conversas em andamento, analisar o desempenho do SDR Bot e medir a eficácia das interações com os clientes.
  **Critérios:**
  - Dado que o dashboard esteja disponível, quando o gerente acessar o sistema, então deverá visualizar métricas de conversas ativas e finalizadas
  - Regra de negócio: O dashboard deve exibir número de conversas ativas e finalizadas
  - Edge case: O dashboard deve permitir filtrar conversas por período (data de início e fim)

- [ ] **Como** um desenvolvedor, **quero** que o sistema tenha um mecanismo robusto de tratamento de exceções **para** que falhas em qualquer etapa do pipeline (download, IA, TTS, envio) sejam capturadas, registradas e, se necessário, comunicadas a uma equipe de suporte.
  **Critérios:**
  - Dado uma falha na comunicação com a Evolution API, quando o sistema tentar se comunicar, então deverá registrar detalhes (endpoint, status code)
  - Regra de negócio: Erros na API do OpenRouter (ex: conteúdo inapropriado, falha na transcrição) devem ser tratados de forma específica
  - Edge case: Implementar um sistema de *retries* com *exponential backoff* para falhas de rede

- [ ] **Como** um usuário final, **quero** que o SDR Bot seja capaz de entender e responder a mensagens de texto, além de áudio, **para** que eu possa interagir da forma que for mais conveniente para mim.
  **Critérios:**
  - Dado que o webhook receba uma mensagem, quando for do tipo texto, então deverá ser diferenciada de uma mensagem de áudio
  - Regra de negócio: Se a mensagem for de texto, o pipeline deve pular as etapas de download e transcrição de áudio
  - Edge case: A resposta pode ser em áudio (padrão) ou em texto, dependendo da configuração

- [ ] **Como** um gerente de vendas, **quero** que o SDR Bot seja capaz de identificar a intenção de agendar uma reunião e coordenar um horário com o cliente **para** automatizar a conversão de um lead qualificado em uma reunião de vendas.
  **Critérios:**
  - Dado que o cliente demonstre interesse em agendar uma reunião, quando a IA processar a mensagem, então deverá reconhecer a intenção
  - Regra de negócio: O bot deve ser capaz de consultar uma agenda (ex: Google Calendar, Calendly) via API para verificar a disponibilidade
  - Edge case: Após a confirmação do cliente, o bot deve criar o evento na agenda e enviar um convite