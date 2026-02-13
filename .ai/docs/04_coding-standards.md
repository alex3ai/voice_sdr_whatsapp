# Padrões de Codificação

Este documento define os padrões de codificação e práticas recomendadas para o projeto Voice SDR WhatsApp.

## 1. Estrutura de Código

- Os módulos devem seguir a estrutura definida em `app/`:
  - `models/` - Modelos de dados para requisições e respostas
  - `services/` - Lógica de negócio desacoplada
  - `utils/` - Funções utilitárias
  - `config.py` - Gerenciamento de configurações

## 2. Estilo de Código

- **Python**: Seguir o padrão PEP 8
- **Nomenclatura**: Usar nomes descritivos para variáveis e funções
- **Comentários**: Explicar decisões complexas, não o óbvio
- **Docstrings**: Incluir docstrings em todas as classes e funções públicas

## 3. Gerenciamento de Exceções

- Usar blocos `try-except` para operações que possam falhar
- Criar classes de exceção específicas em `app/utils/exceptions.py`
- Registrar erros detalhados com o logger apropriado

## 4. Logging

- Usar o logger configurado em `app/utils/logger.py`
- Níveis apropriados: DEBUG, INFO, WARNING, ERROR
- Incluir contexto relevante nas mensagens de log

## 5. Tratamento de Retries

- Para operações de rede ou serviços externos, usar o decorador `@retry_with_backoff` em `app/utils/retry_handler.py`
- Configurar parâmetros apropriados de tentativas, atraso e fator de crescimento

## 6. Configurações

- Todas as configurações devem ser gerenciadas via `app/config.py`
- Usar variáveis de ambiente para configurações sensíveis
- Utilizar Pydantic para validação das configurações

## 7. Serviços

- Cada serviço deve ter responsabilidade única
- Implementar como classes com métodos bem definidos
- Criar instâncias singleton no final do módulo

## 8. Novos Padrões para o Sistema de Métricas

- **Padrão de Nomenclatura de Views**: As views SQL devem seguir o padrão `[nome_do_grupo]_metrics` (ex: `conversation_metrics`)
- **Documentação de Campos**: Todos os campos das views devem ser documentados com seu propósito e tipo
- **Tratamento de Erros**: O serviço de métricas deve implementar retry com backoff exponencial para falhas de conexão
- **Padrão de Retorno**: Métodos do serviço de métricas devem retornar listas de dicionários ou dicionários com campos bem definidos
- **Endpoints de API**: Os endpoints para métricas devem seguir o padrão `/metrics/[nome_do_grupo]` e retornar dados encapsulados em um objeto `{"data": [...]}` ou `{"data": {...}}`
- **Validação de Parâmetros**: Os endpoints devem validar parâmetros de entrada como datas e limites
- **Tipagem Adequada**: Utilizar tipagem adequada para os dados retornados pelos métodos de métricas

## 9. Segurança

- Não expor informações sensíveis nos logs
- Validar entradas recebidas via webhook
- Sanitizar dados antes de inserir em queries SQL