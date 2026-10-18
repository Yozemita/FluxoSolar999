# Implantação na Railway

## Origem e build

1. No serviço API, configure `Yozemita/FluxoSolar999` como origem e **main** como branch de deploy.
2. A raiz do serviço pode ser `/` ou `/backend`: cada contexto tem Dockerfile e configuração Railway próprios. O frontend está dentro de `backend/static/` e entra em ambas as imagens.
3. Configure **Start Command** como `sh /app/backend/start.sh`, healthcheck `/health`, timeout de 120 segundos e até cinco reinícios por falha. O `railway.json` do contexto escolhido também registra essas opções; confira os valores efetivos no serviço. O script expande a porta no shell. O comando antigo com `--port $PORT` falha quando a Railway o executa sem shell, pois o Uvicorn recebe o texto literal `$PORT`. O import `main:app` continua compatível com ambas as imagens.
4. Mantenha uma réplica. O script executa um processo Uvicorn em `0.0.0.0:$PORT`. Não fixe a porta 8000 na Railway.

O Dockerfile de produção não usa mounts de segredo, que foram rejeitados pelo validador Railway observado neste projeto. Fora do Codex, construa normalmente com `docker build -t fluxosolar:test .`. No ambiente Codex, que fornece CA de proxy, use:

```bash
python scripts/build_cloud.py --tag fluxosolar:test
python scripts/build_cloud.py --backend --tag fluxosolar:test-backend
```

O helper cria uma cópia temporária do Dockerfile e monta o certificado apenas no passo local de instalação. A cópia é removida após o build; o certificado não entra na imagem e o Dockerfile de produção não é modificado. TLS e verificação dos pacotes permanecem ativos.

O build isolado de `backend/` é verificado em CI junto ao build da raiz. O teste de imagem executa o comando legado, valida frontend, health, autenticação, dashboard e um agente; não depende de arquivos fora do contexto.

## Deploy automático e reconexão GitHub

O serviço acompanha a branch **main**, com **Wait for CI** ativado. Um push deve concluir o workflow `application-checks` com sucesso antes de a Railway publicar o mesmo commit. Confira o hash do commit no deploy, o status `SUCCESS` e o `/health`; uma origem conectada sozinha não comprova que o deploy automático funciona.

São necessárias a conta GitHub conectada à Railway e a permissão do aplicativo Railway para este repositório. Para renovar a conexão da conta, abra [Account Settings](https://railway.com/account), localize o cartão **GitHub** e use **⋯ → Reconnect**. As permissões do aplicativo ficam nas [instalações do GitHub](https://github.com/settings/installations). Depois, confira ou habilite o autodeploy do serviço para `main`.

## Variáveis no serviço API

| Nome | Configuração |
| --- | --- |
| `DATABASE_URL` | Referência Railway ao PostgreSQL do mesmo ambiente, por exemplo `${{Postgres.DATABASE_URL}}`; ajuste `Postgres` ao nome real do serviço. |
| `ADMIN_USERNAME` | `rapha` ou nome escolhido. |
| `ADMIN_PASSWORD` | Senha exclusiva com pelo menos 16 caracteres, inserida de forma segura nas variáveis Railway. Não copie senhas para GitHub. |
| `PUBLIC_BASE_URL` | URL HTTPS pública completa da API, sem barra final. Se omitida, a origem é derivada de `RAILWAY_PUBLIC_DOMAIN`, quando presente. |
| `COOKIE_SECURE` | `true` em produção HTTPS. |
| `REDIS_URL` | Opcional: referência `${{Redis.REDIS_URL}}`, ajustando o nome do serviço. |
| `S3_BUCKET` | Opcional: nome de bucket existente. |
| `S3_ENDPOINT_URL` | Endpoint HTTPS do armazenamento compatível, se não for AWS S3. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credenciais restritas ao bucket, fornecidas de forma segura no serviço API. |
| `AWS_DEFAULT_REGION` | Região do bucket. |

Variáveis configuradas no Codex **não são transferidas automaticamente para a Railway**. Credenciais existentes devem ser reutilizadas no serviço correto, sem publicar seus valores. Se o serviço já usa `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION` e `S3_ENDPOINT`, configure referências Railway dessas variáveis para os nomes `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` e `S3_ENDPOINT_URL`, respectivamente; preserve os valores seguros existentes.

O usuário é criado apenas se o banco não tiver proprietário. Alterar `ADMIN_PASSWORD` depois não troca o hash existente. Para trocar a senha e revogar sessões, execute `python -m backend.manage reset-password` no ambiente do serviço após configurar o novo valor seguro de `ADMIN_PASSWORD`.

## Validação de cada deploy

1. Confirme que a imagem construiu e o startup terminou. O `/health` precisa responder HTTP 200 com `status=ok` e `database=ready`.
2. Abra `/` e confirme o formulário de login; `/static/app.js` e `/static/style.css` devem responder 200.
3. Faça login com o proprietário configurado; confirme catálogo e dashboard. Rotas de dados retornam 401 sem sessão.
4. Confira `/api/status` autenticado: PostgreSQL deve aparecer como banco; Redis só aparece `ready` após um PING bem-sucedido. S3 configurado é identificado como não verificado até um upload real.
5. Faça um cadastro controlado, um redeploy e confirme que ele persiste. Preserve dados reais; não insira lotes de teste em relatórios de produção.
6. Confira logout. Confirme um backup e uma restauração em ambiente separado antes de considerar a operação validada.

Se `/health` falhar, confirme primeiro `DATABASE_URL`, rede privada PostgreSQL e `ADMIN_PASSWORD`. A aplicação não imprime credenciais nem detalhes de conexão nos erros públicos. Redis/S3 opcionais não impedem health do banco. Um badge de serviço criado na Railway não comprova uso pela API.

## S3

O navegador usa um POST temporário de cinco minutos, limitado ao tipo JPEG/PNG/WebP e 25 MB. Configure CORS do bucket para permitir POST apenas da origem HTTPS do painel e os campos exigidos pelo seu provedor. Mantenha objetos privados e a política restrita ao prefixo `fluxosolar/`. Não há leitura pública automática da imagem; a chave é vinculada ao rascunho após o upload.

## Retirada de work e migrações

A `work` era a origem Railway informada anteriormente. Troque a origem para **main**, faça o deploy e confirme o healthcheck antes de remover a branch remota. Um push na main não altera a origem do serviço na Railway.

Antes de mudar de servidor, faça backup consistente PostgreSQL, restaure no destino, valide login/dados/mídia, mude o domínio e monitore. Só remova o recurso antigo depois dessas verificações. Retenção de logs e backups do provedor segue as políticas dele; remover a aplicação não elimina necessariamente essas cópias.

Referências oficiais: [Dockerfile](https://docs.railway.com/guides/dockerfiles), [configuração como código](https://docs.railway.com/reference/config-as-code), [healthcheck](https://docs.railway.com/guides/healthchecks).
