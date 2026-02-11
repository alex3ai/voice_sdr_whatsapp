# Documentação da Implementação - Tarefa 3.2

## Objetivo
Criar um módulo de notificação (`app/services/notification.py`) com uma interface genérica e uma implementação inicial (ex: log para um arquivo crítico ou print no console).

## Descrição
Esta implementação adiciona um serviço de notificação genérico ao sistema, permitindo que alertas e notificações de erros críticos sejam tratados de forma padronizada. O serviço oferece múltiplas implementações possíveis (console, arquivo) e pode ser facilmente estendido para incluir outros métodos de notificação (como email, Slack, etc.).

## Componentes Implementados

### 1. Interface de Notificação
- `NotificationService`: Classe abstrata que define a interface para serviços de notificação
- Métodos definidos: `send_alert` e `notify_error`

### 2. Implementações Disponíveis
- `ConsoleNotificationService`: Imprime notificações no console com cores diferenciadas por nível
- `FileNotificationService`: Grava notificações em um arquivo de log com timestamps

### 3. Fábrica de Serviços
- `get_notification_service`: Função que retorna a implementação configurada com base na variável de ambiente `NOTIFICATION_TYPE`

### 4. Configuração
Adicionadas as seguintes variáveis de configuração:
- `notification_type`: Tipo de notificação ('console' ou 'file'), padrão 'console'
- `notification_log_file_path`: Caminho para o arquivo de log quando usando notificação por arquivo

## Integração com o Sistema
O serviço de notificação foi integrado aos seguintes componentes:
- `app/services/evolution.py`: Notificações para erros críticos na API da Evolution
- `app/services/voice.py`: Notificações para falhas na API de síntese de voz da Azure
- `app/main.py`: Notificações para erros críticos no pipeline de processamento

## Benefícios
- Centralização do tratamento de notificações de erro
- Facilidade de configuração e troca entre diferentes métodos de notificação
- Extensibilidade para adicionar novos métodos de notificação
- Melhor monitoramento e observabilidade do sistema