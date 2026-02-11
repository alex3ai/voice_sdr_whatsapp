# Estrutura de Dados e Persistência

Com base em .ai/docs/00_project-description.md e .ai/docs/01_user-stories.md, este é o esquema de banco de dados:

## 📌 Resumo Conceitual

- **Entidade:** Conversas
- **Propósito:** Armazenar e gerenciar o histórico de conversas entre o bot e os clientes
- **Regras de negócio críticas:** 
  - O histórico de conversas deve ser persistido para manter contexto entre interações
  - As conversas devem ser associadas a um identificador único de cliente
- **Relacionamentos:** 
  - 1:N com Mensagens (uma conversa → muitas mensagens)

- **Entidade:** Mensagens
- **Propósito:** Registrar cada mensagem trocada entre o cliente e o bot
- **Regras de negócio críticas:** 
  - As mensagens devem armazenar o tipo (áudio ou texto) e conteúdo
  - Devem ter timestamp para ordenação histórica
- **Relacionamentos:** 
  - N:1 com Conversas (muitas mensagens → uma conversa)

- **Entidade:** Agendamentos
- **Propósito:** Armazenar informações sobre reuniões agendadas pelo bot
- **Regras de negócio críticas:** 
  - O status do agendamento deve ser rastreável (pendente, confirmado, cancelado)
  - Deve estar vinculado a um cliente específico
- **Relacionamentos:** 
  - N:1 com Clientes (muitos agendamentos → um cliente)

- **Entidade:** Clientes
- **Propósito:** Manter informações dos clientes que interagem com o bot
- **Regras de negócio críticas:** 
  - O cliente deve ser identificado unicamente pelo ID do WhatsApp
  - Deve armazenar nome e informações relevantes para personalização
- **Relacionamentos:** 
  - 1:N com Conversas (um cliente → muitas conversas)
  - 1:N com Agendamentos (um cliente → muitos agendamentos)

## ⚙️ Especificação Técnica

## 📚 Visões (Views) do Sistema
Também conhecidas como "materalized views" ou visões não armazenadas, estas estruturas são criadas a partir de consultas SQL sobre as tabelas base e oferecem abstrações úteis para análise e monitoramento.

### Tabelas da Evolution API

#### messages (Tabela Original)
| Campo | Tipo | Observações |
|-------|------|-------------|
| id | text | ID da mensagem |
| remote_jid | text | ID do destinatário (cliente) |
| from_me | boolean | TRUE para mensagens enviadas pelo bot, FALSE para recebidas |
| message_type | text | Tipo da mensagem (audioMessage, conversation, etc.) |
| created_at | timestamp | Data/hora da criação da mensagem |
| content | text | Conteúdo textual da mensagem |

### Visões Analíticas

#### conversation_metrics
| Campo | Tipo | Observações |
|-------|------|-------------|
| data | date | Data da conversa |
| numero_de_conversas | bigint | Número de conversas distintas |
| total_mensagens | bigint | Total de mensagens na data |

#### active_conversations
| Campo | Tipo | Observações |
|-------|------|-------------|
| remote_jid | text | ID do cliente |
| total_mensagens | bigint | Total de mensagens |
| ultima_mensagem | timestamp | Data da última mensagem |
| primeira_mensagem | timestamp | Data da primeira mensagem |

#### message_type_distribution
| Campo | Tipo | Observações |
|-------|------|-------------|
| tipo_mensagem | text | Tipo categorizado da mensagem |
| quantidade | bigint | Quantidade de mensagens desse tipo |

### Visões de Performance

#### bot_response_rate
| Campo | Tipo | Observações |
|-------|------|-------------|
| mensagens_enviadas_pelo_bot | bigint | Total de mensagens enviadas pelo bot |
| mensagens_recebidas_do_cliente | bigint | Total de mensagens recebidas do cliente |
| total_mensagens | bigint | Total geral de mensagens |
| percentual_respostas | numeric | Percentual de respostas do bot |

#### daily_performance_metrics
| Campo | Tipo | Observações |
|-------|------|-------------|
| data | date | Data da medição |
| total_mensagens | bigint | Total de mensagens |
| mensagens_enviadas | bigint | Mensagens enviadas pelo bot |
| mensagens_recebidas | bigint | Mensagens recebidas do cliente |
| tempo_medio_resposta_segundos | numeric | Tempo médio de resposta |

### Visões de Engajamento

#### conversations_by_client
| Campo | Tipo | Observações |
|-------|------|-------------|
| remote_jid | text | ID do cliente |
| dias_comunicacao | bigint | Dias distintos de comunicação |
| total_mensagens | bigint | Total de mensagens trocadas |
| primeira_mensagem | timestamp | Data da primeira mensagem |
| ultima_mensagem | timestamp | Data da última mensagem |
| mensagens_bot | bigint | Mensagens enviadas pelo bot |
| mensagens_cliente | bigint | Mensagens recebidas do cliente |

### Visões Agregadas

#### comprehensive_conversation_metrics
| Campo | Tipo | Observações |
|-------|------|-------------|
| data | date | Data da medição |
| usuarios_unicos | bigint | Número de usuários únicos |
| total_mensagens | bigint | Total de mensagens |
| mensagens_enviadas | bigint | Mensagens enviadas pelo bot |
| mensagens_recebidas | bigint | Mensagens recebidas do cliente |
| taxa_resposta_percentual | numeric | Taxa de resposta do bot |
| usuarios_ativos_24h | bigint | Usuários ativos nas últimas 24h |

#### system_wide_metrics
| Campo | Tipo | Observações |
|-------|------|-------------|
| total_usuarios_atendidos | bigint | Total de usuários distintos atendidos |
| total_mensagens_processadas | bigint | Total de mensagens processadas |
| mensagens_enviadas_pelo_bot | bigint | Mensagens enviadas pelo bot |
| mensagens_recebidas_dos_clientes | bigint | Mensagens recebidas dos clientes |
| dias_atividade | bigint | Dias com atividade |
| primeira_interacao | timestamp | Data da primeira interação |
| ultima_interacao | timestamp | Data da última interação |
| proporcao_respostas | numeric | Proporção de respostas do bot |

### Visões de Padrões Temporais

#### hourly_activity
| Campo | Tipo | Observações |
|-------|------|-------------|
| hora_do_dia | integer | Hora do dia (0-23) |
| total_mensagens | bigint | Total de mensagens na hora |
| mensagens_recebidas | bigint | Mensagens recebidas na hora |
| mensagens_enviadas | bigint | Mensagens enviadas na hora |

#### weekly_activity
| Campo | Tipo | Observações |
|-------|------|-------------|
| dia_da_semana | integer | Dia da semana (0-6) |
| nome_dia | text | Nome do dia da semana |
| total_mensagens | bigint | Total de mensagens no dia |

### Conversas
| Campo | Tipo | Restrições | Observações |
|-------|------|------------|-------------|
| id | UUID | PK, obrigatório | Gerado automaticamente |
| cliente_id | VARCHAR(255) | Obrigatório | ID do cliente no WhatsApp |
| instancia_evolution | VARCHAR(100) | Obrigatório | Identificador da instância Evolution |
| status | VARCHAR(50) | DEFAULT 'ativa' | Valores: ativa, finalizada, bloqueada |
| created_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |

### Mensagens
| Campo | Tipo | Restrições | Observações |
|-------|------|------------|-------------|
| id | UUID | PK, obrigatório | Gerado automaticamente |
| conversa_id | UUID | FK, obrigatório | Referência à conversa |
| remetente | BOOLEAN | Obrigatório | TRUE para bot, FALSE para cliente |
| tipo_mensagem | VARCHAR(20) | Obrigatório | Valores: texto, audio, imagem |
| conteudo | TEXT | Obrigatório | Conteúdo da mensagem |
| midia_url | TEXT | Opcional | URL para conteúdo multimídia |
| created_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |

### Clientes
| Campo | Tipo | Restrições | Observações |
|-------|------|------------|-------------|
| id | UUID | PK, obrigatório | Gerado automaticamente |
| whatsapp_id | VARCHAR(255) | Único, obrigatório | ID do WhatsApp do cliente |
| nome | VARCHAR(255) | Opcional | Nome do cliente |
| status | VARCHAR(50) | DEFAULT 'ativo' | Valores: ativo, inativo, bloqueado |
| created_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |

### Agendamentos
| Campo | Tipo | Restrições | Observações |
|-------|------|------------|-------------|
| id | UUID | PK, obrigatório | Gerado automaticamente |
| cliente_id | UUID | FK, obrigatório | Referência ao cliente |
| titulo | VARCHAR(255) | Obrigatório | Título do agendamento |
| descricao | TEXT | Opcional | Detalhes do agendamento |
| data_inicio | TIMESTAMPTZ | Obrigatório | Horário de início |
| data_fim | TIMESTAMPTZ | Obrigatório | Horário de término |
| status | VARCHAR(50) | DEFAULT 'pendente' | Valores: pendente, confirmado, cancelado |
| criado_por_bot | BOOLEAN | DEFAULT TRUE | Indica se foi agendado pelo bot |
| created_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |
| updated_at | TIMESTAMPTZ | DEFAULT now() | Audit trail |

## ⚠️ Edge Cases Documentados

- [x] Cenário: Cliente deletado com agendamentos ativos → Ação: soft delete + manter histórico
- [x] Cenário: Dois agendamentos no mesmo horário/recurso → Ação: rejeitar com erro 409
- [x] Cenário: Dados ausentes em integração externa → Ação: fallback para valores padrão
- [x] Cenário: Mensagem recebida com tipo não suportado → Ação: registrar erro e notificar equipe
- [x] Cenário: Cliente tenta iniciar conversa com bot bloqueado → Ação: não responder e registrar tentativa