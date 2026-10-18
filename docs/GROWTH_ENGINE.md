# FluxoSolar: painel, dashboard e agentes

O projeto reúne a operação interna de afiliados: catálogo Shopee/SHEIN, legendas e briefings, imagens de produtos, métricas importadas e planejamento. A geração de vídeos é um projeto separado e não integra este painel.

## Fluxo disponível

`Produto -> Rascunho -> Revisão de publicidade -> Planejamento manual -> Importação de métricas -> Análise`

O dashboard mostra totais acumulados, CTR, conversão, resultado de mídia, ROI, ranking com amostra mínima, atividade dos agentes e próximos passos. Indicadores sem denominador aparecem sem valor calculado. Os relatórios são informados pelo proprietário; nenhuma coleta de redes sociais é simulada.

## Agentes internos

| Agente | Tarefa implementada |
| --- | --- |
| Scout | Analisa produtos a partir das métricas importadas e do limite de amostra. |
| Creative | Prepara legenda e briefing por template para revisão do proprietário. |
| Catalog | Consulta produtos e vínculos entre comerciante, código e link afiliado. |
| Scheduler | Consulta a agenda interna; a publicação externa é manual. |
| Analytics | Consolida métricas e resultado de mídia informado. |
| Winner | Aplica o ranking heurístico, sem alterar orçamentos ou anúncios. |
| Compliance | Confere identificação de publicidade e link de afiliado nas legendas. |

São tarefas determinísticas executadas sob demanda. Cada execução bem-sucedida tem resultado e data persistidos. A rotina de análise executa os seis agentes de consulta sem criar rascunhos. Não há orquestração por LLM nem trabalhadores de publicação social em operação.

## Persistência e implantação

- FastAPI serve API e frontend `backend/static/` no mesmo domínio, com login de proprietário.
- PostgreSQL é o banco da Railway; SQLite é somente a alternativa local de desenvolvimento.
- As tabelas guardam proprietário, sessões, tentativas de login, produtos, lotes de métricas, rascunhos, agenda, execuções e auditoria.
- O Redis configurado é verificado por PING; não é apresentado como fila de produção.
- O S3 opcional recebe somente imagens JPEG, PNG e WebP via autorização temporária.
- Existem builds completos na raiz e em `backend/`. Ambos incluem o dashboard e aceitam o comando `uvicorn main:app` usado em serviços Railway existentes.

O ranking exige 100 visualizações, 20 cliques e três conversões para calcular um score. Esses limites são heurísticos e não significância estatística. O resultado de mídia inclui somente comissão menos gasto informado; não representa lucro líquido.

## Integrações externas

Publicação social, sincronização automática de relatórios e anúncios dependem de integrações futuras. O painel não cria seguidores, visualizações, cliques, comentários ou contas artificiais. Não afirma estoque, preço, desconto ou comissão verificados em comerciantes externos.

Consulte [README](../README.md) para iniciar a aplicação e [Railway](RAILWAY.md) para requisitos de produção, healthcheck, credenciais e validação de dados.
