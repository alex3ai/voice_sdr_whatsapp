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

- [ ] Cenário: Cliente deletado com agendamentos ativos → Ação: soft delete + manter histórico
- [ ] Cenário: Dois agendamentos no mesmo horário/recurso → Ação: rejeitar com erro 409
- [ ] Cenário: Dados ausentes em integração externa → Ação: fallback para valores padrão
- [ ] Cenário: Mensagem recebida com tipo não suportado → Ação: registrar erro e notificar equipe
- [ ] Cenário: Cliente tenta iniciar conversa com bot bloqueado → Ação: não responder e registrar tentativa