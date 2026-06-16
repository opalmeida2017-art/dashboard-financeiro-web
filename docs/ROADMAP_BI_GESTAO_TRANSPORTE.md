# Roadmap BI — Gestão comercial de transportadora

Documento de planejamento (sem implementação). Baseado no estado atual do BIWEB com **leitura direta do banco SATI** (`SATI_DATABASE_URL` → schema **`c3332`**, ex.: `sat1_sati_is`).

**Objetivo:** evoluir de “quanto faturamos e gastamos” para “onde está o lucro, quem paga mal, qual rota/veículo/cliente puxa o resultado”.

---

## Fonte de dados (importante)

Hoje, com `USE_SATI_SOURCE=true` (padrão no `.env` e na instalação), **não há importação de Excel nem tabelas físicas `relFil*` no PostgreSQL do painel**. O robô baixa o dump SATI (`SATI-c3332-atual.zip`) e o `pg_restore` popula o schema **`c3332`**.

O código Python ainda usa nomes legados `relFilViagensCliente`, `relFilDespesasGerais`, etc. em `data_manager.get_data_as_dataframe()` — são **apelidos internos**. Por baixo, `sati_queries.py` executa SQL nas **tabelas reais do SATI**:

| Apelido no código (legado) | Tabelas SATI reais (`c3332`) | SQL em `sati_queries.py` |
|----------------------------|------------------------------|---------------------------|
| `relFilViagensCliente` | `conhecimento` + `cliente`, `veiculo`, `motorista`, `cidade`, `mercadoria`, `filial` | `_query_viagens` |
| `relFilViagensFatCliente` | `conhecimento` (subset faturável) | `_query_viagens_fat` |
| `relFilDespesasGerais` | `itemnota` + `nota` + `item` + `grupo` + `veiculo` + `negocio` | `_query_despesas` |
| `relFilContasPagarDet` | `itemnota` + `nota` + `duplicatapagar` | `_query_contas_pagar` |
| `relFilContasReceber` | `duplicatareceber` | `_query_contas_receber` |
| `relFilAcertoMot` | `conhecimento` (viagens com acerto) | `_query_acerto_motorista` |
| Fluxo operacional | `conhecimento`, `ordemcar`, `manif`, `documento`, … | `query_fluxo_viagem` |

**Tabelas auxiliares BIWEB** (schema `public`, não vêm do SATI): `despesas_viagem_associadas`, `despesas_viagem_excluidas`, `static_expense_groups`, `configuracoes_robo`.

Neste roadmap, as fases citam **sempre as tabelas/colunas do BD SATI**, não os nomes `relFil*`.

---

## Fase 0 — Baseline (já existe)

| Página | O que entrega hoje |
|--------|-------------------|
| Painel `/` | KPIs receita, custos, margem, a pagar/receber; gráfico receita vs despesas |
| Faturamento `/faturamento_detalhes` | Clientes, rotas, mercadorias, motoristas, filiais, volume kg |
| Despesas `/despesas_detalhes` | Grupos, filial, combustível, manutenção |
| Fluxo `/fluxo_viagem` | Trilha documental (ordem → CT-e → MDF-e → descarga) |
| Relatório viagem | DRE unitário por CT-e (modal/PDF) |

**Gap principal:** poucos cruzamentos receita × custo × prazo × km na mesma dimensão gerencial.

---

## Fase 1 — MVP comercial (3 gráficos + 2 KPIs)

**Prazo sugerido:** 2–3 sprints  
**Esforço:** baixo — reutiliza `sati_queries.py` / `data_manager.py` sobre o BD SATI  
**Público:** diretoria + comercial

### Entregas

| # | Nome | Tipo | Cruzamento de dados (BD SATI `c3332`) | Pergunta de gestão |
|---|------|------|----------------------------------------|-------------------|
| 1 | **Margem por cliente** | Barras horizontais (margem % + tamanho = faturamento) | `conhecimento.freteempresa` − custos (`itemnota` via `codacertomotorista` / `despesas_viagem_associadas`) por `conhecimento.numero` × `cliente.nome` | Quem fatura muito mas lucra pouco? |
| 2 | **Aging contas a receber** | Barras empilhadas (0–30 / 31–60 / 61–90 / 90+ dias) | `duplicatareceber.valorvencimento`, `datavencimento`, pendente (`codtransacao` IS NULL e `datapagamento` IS NULL) | Quanto está preso e há quanto tempo? |
| 3 | **Custo R$/km por placa** | Barras + linha de meta | `conhecimento.kmrodado` × custo placa (`itemnota` + `grupo` combustível/manutenção, `veiculo.placa`) | Qual caminhão destrói margem? |

### KPIs novos no painel

| KPI | Fórmula / fonte (BD) |
|-----|----------------------|
| **Ticket médio** | `SUM(conhecimento.freteempresa) / COUNT(DISTINCT conhecimento.numero)` no período |
| **Prazo médio recebimento** | Média `duplicatareceber.datapagamento − datavencimento` (quitados) ou dias em aberto |

### Onde colocar na UI

- Opção A: nova seção no **painel principal** (“Visão comercial”)
- Opção B: nova página **`/gestao_comercial`** com os 3 gráficos + KPIs

### Dependências técnicas

- Endpoint único: `GET /api/gestao_comercial_dashboard_data`
- Função em `data_manager.py`: agregar via SQL SATI ou DataFrames já carregados de `sati_queries.py`
- Rateio de custo por viagem: usar lógica já próxima de `get_relatorio_viagem_data`

### Critério de sucesso

- Diretor consegue responder em 30 s: “top 5 clientes por margem”, “quanto vence este mês”, “pior placa em R$/km”

---

## Fase 2 — Rentabilidade operacional (5 gráficos)

**Prazo sugerido:** 3–4 sprints após Fase 1  
**Esforço:** médio  
**Público:** comercial + operação + financeiro

### Entregas

| # | Nome | Tipo | Cruzamento | Decisão |
|---|------|------|------------|---------|
| 4 | **Heatmap rota (origem → destino)** | Matriz cor = margem % | `cidade` (origem/destino via `conhecimento.codcidadeorigem/destino`) × receita − custo | Quais rotas reajustar ou recusar? |
| 5 | **Frota própria vs agenciamento** | Barras agrupadas | `conhecimento.tipofrete` (P vs A/T) × `freteempresa` × custo × margem % | Onde investir em frota própria? |
| 6 | **Spread frete empresa − motorista** | Scatter (bolha = volume) | `conhecimento.freteempresa` vs `fretemotorista` + `comissao` | Spread cobre custo fixo? |
| 7 | **Concentração de receita (Pareto)** | Barras + linha 80% | % `freteempresa` por `cliente.nome` | Risco de dependência de poucos clientes |
| 8 | **km/l e R$/litro por placa** | Duplo eixo | `itemnota` (grupo combustível em `grupo.descricao`) × `conhecimento.kmrodado` × `veiculo.placa` | Desvio de consumo — fraude ou manutenção? |

### KPIs adicionais

- **% receita top 3 clientes**
- **Margem média frota própria vs terceiro**
- **km médio por viagem** (período)

### Dependências

- Incluir `itemnota.quantidade` na query de despesas se ainda não exposta (litros combustível)
- Spread motorista já está em `conhecimento.fretemotorista` / `freteempresa`

---

## Fase 3 — Caixa e crédito (painel financeiro)

**Prazo sugerido:** 2–3 sprints  
**Esforço:** médio  
**Público:** financeiro + diretoria

### Entregas

| # | Nome | Tipo | Cruzamento | Decisão |
|---|------|------|------------|---------|
| 9 | **Fluxo de caixa projetado 90 dias** | Área (entradas/saídas/saldo) | `duplicatareceber.datavencimento` − `duplicatapagar.datavencimento` | Caixa aguenta folha e pedágio? |
| 10 | **Ranking atraso por cliente** | Barras horizontais | Dias em aberto × `cliente` × `duplicatareceber.valorvencimento` | Bloquear carga para quem? |
| 11 | **AP por fornecedor e vencimento** | Barras empilhadas | `duplicatapagar` + `nota.codfornecedor` | Priorizar pagamentos |
| 12 | **Inadimplência %** | KPI + tendência mensal | AR vencido / AR total | Saúde do crédito |

### Regras de negócio a definir

- SLA de cobrança (ex.: alerta após 30 dias)
- Incluir ou não CT-es ainda não faturados na projeção
- Filtros de filial aplicados também em AR/AP (hoje KPIs globais)

---

## Fase 4 — Operação e compliance (documentos + SLA)

**Prazo sugerido:** 3–4 sprints  
**Esforço:** médio-alto (agrega fluxo + documentos)  
**Público:** operação + fiscal + comercial

### Entregas

| # | Nome | Tipo | Cruzamento | Decisão |
|---|------|------|------------|---------|
| 13 | **Tempo médio entre etapas** | Funil / barras | Datas do `query_fluxo_viagem` | Onde está o gargalo? |
| 14 | **% comprovante no prazo** | KPI + linha mensal | `documento` + SLA (ex. 48h pós viagem) | Quem atrasa faturamento? |
| 15 | **Saúde fiscal CT-e / MDF-e** | Doughnut + tendência | `conhecimento.ctestatus`, `manif.mdfestatus`, `conhecimento.cancelado` | Perda por rejeição SEFAZ? |
| 16 | **Índice de quebra** | Barras | `conhecimento.pesosaida` vs chegada, `valorquebra` × `mercadoria.descricao` / rota | Sinistro recorrente? |
| 17 | **Viagens encerradas vs abertas** | KPI manifesto | `manif` + `manifev` | Risco multa MDF-e |

### Dependências

- Materializar métricas do fluxo (hoje só timeline visual)
- Tabela de SLA configurável por apartamento (BIWEB `public`)

---

## Fase 5 — Painéis executivos (visão 360)

**Prazo sugerido:** contínuo após Fases 1–4  
**Esforço:** alto  
**Público:** C-level, reunião mensal

### Páginas sugeridas

| Painel | Conteúdo resumido |
|--------|-------------------|
| **Comercial 360** | Margem cliente + rota + Pareto + ticket médio + aging |
| **Frota 360** | R$/km + km/l + utilização + manutenção/km |
| **Motorista performance** | Faturamento + comissão + consumo + quebra + SLA comprovante |
| **Caixa transportadora** | Projeção 90d + aging + AP crítico |

### Recursos avançados (opcional)

- Export Excel/PDF do painel (reusar `relatorio_execucao.py`)
- Comparativo período anterior (MoM / YoY)
- Metas configuráveis (margem alvo, R$/km meta)
- Alertas por e-mail (`agendamento_email.py`)

---

## Matriz prioridade × esforço

```
                    ESFORÇO
                 Baixo    Médio    Alto
              ┌─────────┬─────────┬─────────┐
    Alto      │ Fase 1  │ Fase 2  │ Fase 5  │
 IMPACTO     │ MVP 3gr │ Rotas   │ 360     │
              ├─────────┼─────────┼─────────┤
    Médio     │ Ticket  │ Fase 3  │ Mapa    │
              │ Pareto  │ Caixa   │ rotas   │
              ├─────────┼─────────┼─────────┤
    Baixo     │ —       │ Fase 4  │ ML prev │
              │         │ SLA doc │ —       │
              └─────────┴─────────┴─────────┘
```

**Recomendação:** iniciar **Fase 1** imediatamente; validar com usuário; só então Fase 2 e 3 em paralelo (comercial + financeiro).

---

## Mapa de dados por fase (tabelas SATI `c3332`)

| Fase | Tabelas / objetos principais |
|------|------------------------------|
| 1 | `conhecimento`, `cliente`, `veiculo`, `itemnota`, `nota`, `grupo`, `duplicatareceber` + `public.despesas_viagem_associadas` |
| 2 | + `cidade`, `mercadoria`, `conhecimento.tipofrete`, `fretemotorista`, litros em `itemnota` |
| 3 | + `duplicatapagar`, vínculo `duplicatareceber` ↔ `cliente` (quando disponível no SATI) |
| 4 | + `query_fluxo_viagem` (`ordemcar`, `manif`, `manifconhecimento`, `documento`, `manifev`) |
| 5 | Agregação de todas + metas em `public` (BIWEB) |

---

## Checklist antes de cada fase

- [ ] Filtros globais (data, placa, filial) aplicados nos novos gráficos
- [ ] Leitura via `USE_SATI_SOURCE=true` e `SATI_DATABASE_URL` (modo atual); fallback Excel/`relFil*` físicas só se SATI desligado
- [ ] Performance: agregação SQL quando DataFrame > 50k linhas
- [ ] Textos dos eixos em português comercial (não jargão técnico)
- [ ] Tooltips com valor absoluto + % onde fizer sentido
- [ ] Mobile: gráficos críticos legíveis em tablet (diretoria em viagem)

---

## Cronograma indicativo

| Mês | Entrega |
|-----|---------|
| M1 | Fase 1 — MVP (3 gráficos + 2 KPIs) + página `/gestao_comercial` |
| M2 | Fase 2 — rotas, frota vs terceiro, spread motorista, Pareto |
| M3 | Fase 3 — aging detalhado, fluxo caixa 90d |
| M4 | Fase 4 — SLA documentos, quebra, fiscal agregado |
| M5+ | Fase 5 — painéis 360, metas, alertas, export |

*Ajustar conforme capacidade de desenvolvimento (1 dev vs equipe).*

---

## Métricas de adoção (pós-implantação)

| Métrica | Meta |
|---------|------|
| Acessos semanais à nova página comercial | ≥ 3 usuários gestão |
| Tempo médio na página | ≥ 2 min (leitura real) |
| Decisões registradas (opcional) | 1 reunião/mês usando o painel |
| Redução CT-es com margem negativa não vista | −10% em 6 meses |

---

## O que não entra neste roadmap

- Implementação de código (escopo deste documento é planejamento)
- Painel de licenças NFe (`/opt/nfe-web`) — produto separado
- Paineis legados removidos no Debian (Diretoria/Frota/Financeiro antigos)
- BI preditivo / machine learning (fase futura opcional)

---

*Última atualização: jun/2026 — fonte: BD SATI schema `c3332` via `sati_queries.py` (não relatórios Excel `relFil*`).*
