# User Stories

## Dashboard de Métricas e Conversas

**Como** um gerente de vendas, **eu quero** ter acesso a um dashboard centralizado **para** poder visualizar as conversas em andamento, analisar o desempenho do SDR Bot e medir a eficácia das interações com os clientes.

-   **Valor de Negócio:**
    -   Permite a tomada de decisão baseada em dados.
    -   Aumenta a visibilidade sobre a performance do bot.
    -   Facilita a identificação de gargalos e oportunidades de melhoria.
-   **Critérios de Aceitação:**
    -   O dashboard deve exibir o número de conversas ativas e finalizadas.
    -   Deve ser possível filtrar conversas por período (data de início e fim).
    -   Métricas como tempo médio de resposta e número de interações por conversa devem ser visíveis.
    -   Deve haver uma interface para ler o histórico de uma conversa específica.

---

## Tratamento Avançado de Erros e Notificações

**Como** um desenvolvedor, **eu quero** que o sistema tenha um mecanismo robusto de tratamento de exceções **para** que falhas em qualquer etapa do pipeline (download, IA, TTS, envio) sejam capturadas, registradas e, se necessário, comunicadas a uma equipe de suporte.

-   **Valor Técnico:**
    -   Aumenta a resiliência e a confiabilidade do sistema.
    -   Facilita a depuração e a manutenção.
    -   Evita que o sistema "morra" silenciosamente.
-   **Critérios de Aceitação:**
    -   Falhas na comunicação com a Evolution API devem ser registradas com detalhes (endpoint, status code).
    -   Erros na API do Gemini (ex: conteúdo inapropriado, falha na transcrição) devem ser tratados de forma específica.
    -   Falhas na geração de áudio (TTS) devem ser capturadas.
    -   Implementar um sistema de *retries* com *exponential backoff* para falhas de rede.
    -   (Opcional) Enviar uma notificação (ex: para um canal do Slack ou Telegram) quando ocorrerem erros críticos.

---

## Suporte a Múltiplos Tipos de Mensagem

**Como** um usuário final, **eu quero** que o SDR Bot seja capaz de entender e responder a mensagens de texto, além de áudio, **para** que eu possa interagir da forma que for mais conveniente para mim.

-   **Valor de Negócio:**
    -   Aumenta o alcance e a usabilidade do bot.
    -   Melhora a experiência do cliente, oferecendo mais flexibilidade.
-   **Critérios de Aceitação:**
    -   O webhook deve ser capaz de diferenciar entre uma mensagem de áudio e uma de texto.
    -   Se a mensagem for de texto, o pipeline deve pular as etapas de download e transcrição de áudio.
    -   O texto da mensagem deve ser enviado diretamente ao "cérebro" (Gemini).
    -   A resposta pode ser em áudio (padrão) ou em texto, dependendo da configuração.

---

## Agendamento de Reuniões

**Como** um gerente de vendas, **eu quero** que o SDR Bot seja capaz de identificar a intenção de agendar uma reunião e coordenar um horário com o cliente **para** automatizar a conversão de um lead qualificado em uma reunião de vendas.

-   **Valor de Negócio:**
    -   Automatiza uma etapa crucial do funil de vendas.
    -   Reduz o trabalho manual da equipe de vendas.
    -   Acelera o processo de agendamento.
-   **Critérios de Aceitação:**
    -   A IA deve ser treinada ou instruída para reconhecer pedidos de agendamento.
    -   O bot deve ser capaz de consultar uma agenda (ex: Google Calendar, Calendly) via API para verificar a disponibilidade.
    -   O bot deve oferecer horários disponíveis para o cliente.
    -   Após a confirmação do cliente, o bot deve criar o evento na agenda e enviar um convite.
