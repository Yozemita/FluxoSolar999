# FluxoSolar Growth Engine

Painel privado para organizar produtos afiliados, rascunhos, métricas e planejamento. FastAPI serve a API e o frontend no mesmo domínio. PostgreSQL guarda catálogo, sessões, métricas, criativos, agenda, execuções de agentes e auditoria.

## O que está implementado

- Login de proprietário com scrypt, sessão opaca de oito horas, cookie HttpOnly/SameSite e logout com revogação. Rotas de dados exigem login; escritas exigem `X-FluxoSolar-CSRF: 1`.
- Cadastro/edição de produtos Shopee e SHEIN, validação do comerciante e preservação integral da URL afiliada.
- Quatro produtos do catálogo original são inseridos sem duplicação no primeiro startup. Não se verifica remotamente preço, estoque, atribuição ou propriedade desses links.
- Importação incremental idempotente por `event_id`; agregação persistente e ranking heurístico com amostra mínima. Resultado de mídia = comissão menos gasto informado.
- Creative Studio: cria e edita legendas e briefings por template para os produtos cadastrados.
- Agenda interna com validação de disclosure e data futura. Ela não publica automaticamente.
- Sete agentes internos com execução síncrona sob demanda e histórico persistido: consulta/análise de catálogo, métricas, ranking, agenda, disclosure e criação de rascunho.
- Dashboard com visualizações, cliques e conversões acumulados, CTR, conversão e ROI de mídia; taxas sem base aparecem como indisponíveis. Próximos passos identificam falta de dados, publicidade ausente e itens de agenda com data passada.
- Rotina para executar seis análises em sequência, sem criar rascunhos; histórico com resumos legíveis, datas e filtro por agente. Busca de produtos por nome/código e comerciante, navegação preservada ao recarregar e manutenção das alterações de texto não salvas ao atualizar os dados.
- Upload de imagens JPEG, PNG ou WebP para bucket S3 por autorização temporária, quando configurado. Não envia credenciais permanentes ao navegador.
- `/health` executa uma consulta real ao banco; retorna 503 se o banco estiver indisponível. Redis é uma conexão opcional diagnosticada em `/api/status`, não uma fila de tarefas em operação nesta versão.

## Desenvolvimento

Requer Python 3.12. Use o checkout existente; não é necessário criar worktree.

```bash
python3.12 -m venv .venv-growth
. .venv-growth/bin/activate
pip install -r requirements-dev.txt
# Configure ADMIN_PASSWORD com segurança no ambiente (mínimo 16 caracteres).
export ADMIN_USERNAME=rapha
export COOKIE_SECURE=false
export PUBLIC_BASE_URL=http://127.0.0.1:8000
sh scripts/start.sh
```

Sem `DATABASE_URL`, desenvolvimento usa `data/growth.db`, separado do banco da versão antiga do ZIP. Em uma instância Railway identificada por `RAILWAY_ENVIRONMENT_ID`, a ausência de `DATABASE_URL` impede o startup para evitar uso acidental de SQLite efêmero. `.env.example` é somente referência; o app não carrega `.env` automaticamente.

```bash
python -m pytest -q
python -m pip check
node --check backend/static/app.js
```

Para testar também PostgreSQL, configure `TEST_DATABASE_URL` para **um banco dedicado a testes**. A suíte cria/remove schemas `test_fs_<uuid>` próprios e executa os mesmos casos nos dois bancos. Não aponte testes para produção.

## Railway

Siga [o guia de implantação](docs/RAILWAY.md). Há builds completos para a raiz do repositório e para `backend/`. O frontend está em `backend/static/`, acompanha a API em ambos os builds e funciona também com o comando legado `uvicorn main:app`. A API usa `PORT` injetada pela Railway e healthcheck `/health`.

Um push não comprova que o deploy terminou. Confirme os logs e faça uma requisição HTTP ao domínio público; valide também login e persistência após redeploy. O resultado precisa corresponder ao commit enviado.

## Limites

O escopo é painel, dashboard, catálogo, planejamento e agentes internos. Geração de vídeos fica fora deste projeto. Publicação social, sincronização Shopee/SHEIN e anúncios não estão conectados. Os agentes operam apenas sobre dados locais e importados. Nenhum seguidor, visualização, clique ou comentário é fabricado.

A inicialização cria o esquema desta versão. Alterações futuras em tabelas existentes exigirão migrações versionadas e backup; `create_all` não altera colunas existentes. Esta versão mantém uma réplica e um processo API. Faça backups PostgreSQL e teste a restauração antes de dados operacionais relevantes. Não há garantia de hospedagem gratuita nem de resultado comercial.
