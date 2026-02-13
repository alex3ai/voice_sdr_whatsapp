# Planejamento para Implementação do Item 5.1: MVP de Agendamento de Reuniões

## Visão Geral

O item 5.1 da fase 5 do projeto visa implementar uma solução mínima viável (MVP) para agendamento de reuniões, onde o bot enviará um link do Calendly ou Google Agenda para que o cliente possa agendar uma reunião por conta própria. Esta abordagem simples resolve a maioria dos casos de uso sem exigir integrações complexas.

## Objetivo

Permitir que o bot identifique quando um cliente deseja agendar uma reunião e responda automaticamente com um link de agendamento (Calendly ou Google Agenda), redirecionando o cliente para o processo de agendamento externo.

## Requisitos Funcionais

1. **Detecção de intenção de agendamento**: O bot deve reconhecer quando o cliente expressa desejo de agendar uma reunião
2. **Resposta com link de agendamento**: O bot deve enviar automaticamente um link pré-configurado para agendamento
3. **Integração com ferramenta externa**: Configuração de um link Calendly ou Google Agenda que direcione para a agenda da empresa
4. **Fluxo de conversa contínuo**: Após o envio do link, o bot deve continuar a interação normalmente

## Requisitos Técnicos

1. **Configuração de variável de ambiente**: Armazenar o link de agendamento em variável de ambiente
2. **Extensão da lógica de IA**: Atualizar as instruções da IA para reconhecer intenções de agendamento
3. **Armazenamento de contexto**: Registrar quando um cliente recebeu o link de agendamento para fins de acompanhamento

## Plano de Implementação

### Etapa 1: Preparação da Infraestrutura
- [ ] Criar conta de teste no Calendly ou Google Agenda para fins de desenvolvimento
- [ ] Configurar o link de agendamento com informações da empresa
- [ ] Definir a variável de ambiente `CALENDAR_LINK` no arquivo de configuração
- [ ] Atualizar o arquivo [.env.example](file:///c%3A/Users/alex_/Desktop/PE33/Projetos%20PE33/Projeto%2020%20-%20voice_sdr_whatsapp/voice_sdr_whatsapp/.env.example) com a nova variável

### Etapa 2: Atualização da Lógica de IA
- [ ] Modificar as instruções do assistente para reconhecer frases como "gostaria de agendar uma reunião", "podemos marcar uma reunião?", etc.
- [ ] Adicionar ao prompt da IA a instrução de incluir o link de agendamento quando detectar intenção de marcação
- [ ] Definir gatilhos claros para quando o bot deve responder com o link de agendamento

### Etapa 3: Implementação do Serviço de Agendamento
- [ ] Criar novo serviço em [app/services/appointment.py](file:///c%3A/Users/alex_/Desktop/PE33/Projetos%20PE33/Projeto%2020%20-%20voice_sdr_whatsapp/voice_sdr_whatsapp/app/services/appointment.py) para gerenciar a lógica de agendamento
- [ ] Implementar função para detectar intenções de agendamento nas mensagens recebidas
- [ ] Implementar função para gerar a resposta com o link de agendamento
- [ ] Adicionar integração com o serviço de notificação para registrar quando um link é enviado

### Etapa 4: Atualização do Pipeline Principal
- [ ] Modificar a função de processamento do webhook em [app/services/brain.py](file:///c%3A/Users/alex_/Desktop/PE33/Projetos%20PE33/Projeto%2020%20-%20voice_sdr_whatsapp/voice_sdr_whatsapp/app/services/brain.py) para incluir verificação de intenção de agendamento
- [ ] Adicionar condição para chamar o serviço de agendamento antes da chamada à IA
- [ ] Implementar lógica para enviar resposta com link de agendamento sem chamar a IA, caso a intenção seja clara

### Etapa 5: Testes e Validação
- [ ] Criar testes unitários para a detecção de intenções de agendamento
- [ ] Testar o fluxo completo desde a recepção da mensagem até o envio do link
- [ ] Validar que o link de agendamento funciona corretamente
- [ ] Verificar se o histórico de conversas continua funcionando após o envio do link

## Considerações Técnicas

1. **Detecção de intenção**: Utilizar palavras-chave e expressões regulares para identificar intenções de agendamento antes de processar pela IA
2. **Personalização do link**: Considerar a possibilidade de personalizar o link com informações do cliente para melhor rastreamento
3. **Tratamento de múltiplas intenções**: Garantir que o bot não envie o link repetidamente em uma mesma conversa
4. **Registro de métricas**: Registrar envios de links de agendamento para análise de conversão

## Riscos e Mitigantes

- **Risco**: O bot pode enviar o link de agendamento em situações inadequadas
  - **Mitigante**: Implementar lógica de detecção precisa e limitar envios por sessão de conversa

- **Risco**: Baixa conversão do link de agendamento
  - **Mitigante**: Monitorar métricas e considerar a evolução para a implementação completa (item 5.2)

- **Risco**: Cliente não entende o propósito do link enviado
  - **Mitigante**: Melhorar a mensagem de contexto que acompanha o link de agendamento

## Próximos Passos

Após a implementação do MVP:

1. [ ] Realizar testes com usuários reais para validar a eficácia
2. [ ] Coletar métricas de uso e conversão do link de agendamento
3. [ ] Avaliar necessidade de evolução para a implementação completa (item 5.2)
4. [ ] Documentar resultados para tomada de decisão sobre a implementação do item 5.2