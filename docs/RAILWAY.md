# Implantação na Railway

## Origem e build

1. No serviço API, configure `Yozemita/FluxoSolar999` como origem e **main** como branch de deploy.
2. Defina a raiz do serviço como `/` (raiz do repositório), não `/backend`. O frontend precisa entrar na mesma imagem.
3. Use `/railway.json`. Ele seleciona o Dockerfile, `sh scripts/start.sh`, `/health`, timeout de 120 segundos e até cinco reinícios por falha.
4. Mantenha uma réplica. O script executa um processo Uvicorn em `0.0.0.0:$PORT`. Não fixe a porta 8000 na Railway.

O Dockerfile pode ser construído fora do Codex sem qualquer segredo de build. No ambiente Codex, que fornece CA de proxy, teste com:

```bash
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t fluxosolar:test .
```

O certificado é montado temporariamente no passo de instalação; não entra na imagem. TLS e verificação dos pacotes permanecem ativos.

## Variáveis no serviço API

| Nome | Configuração |
| --- | --- |
| `DATABASE_URL` | Referência Railway ao PostgreSQL do mesmo ambiente, por exemplo `${{Postgres.DATABASE_URL}}`; ajuste `Postgres` ao nome real do serviço. |
| `ADMIN_USERNAME` | `rapha` ou nome escolhido. |
| `ADMIN_PASSWORD` | Senha exclusiva com pelo menos 16 caracteres, inserida de forma segura nas variáveis Railway. Não copie senhas para GitHub. |
| `PUBLIC_BASE_URL` | URL HTTPS pública completa da API, sem barra final. |
| `COOKIE_SECURE` | `true` em produção HTTPS. |
| `REDIS_URL` | Opcional: referência `${{Redis.REDIS_URL}}`, ajustando o nome do serviço. |
| `S3_BUCKET` | Opcional: nome de bucket existente. |
| `S3_ENDPOINT_URL` | Endpoint HTTPS do armazenamento compatível, se não for AWS S3. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credenciais restritas ao bucket, fornecidas de forma segura no serviço API. |
| `AWS_DEFAULT_REGION` | Região do bucket. |

Variáveis configuradas no Codex **não são transferidas automaticamente para a Railway**. Credenciais existentes devem ser reutilizadas no serviço correto, sem publicar seus valores.

O usuário é criado apenas se o banco não tiver proprietário. Alterar `ADMIN_PASSWORD` depois não troca o hash existente. Para trocar a senha e revogar sessões, execute `python -m scripts.manage reset-password` no ambiente do serviço após configurar o novo valor seguro de `ADMIN_PASSWORD`.

## Validação de cada deploy

1. Confirme que a imagem construiu e o startup terminou. O `/health` precisa responder HTTP 200 com `status=ok` e `database=ready`.
2. Abra `/` e confirme o formulário de login; `/static/app.js` e `/static/style.css` devem responder 200.
3. Faça login com o proprietário configurado; confirme catálogo e dashboard. Rotas de dados retornam 401 sem sessão.
4. Confira `/api/status` autenticado: PostgreSQL deve aparecer como banco; Redis só aparece `ready` após um PING bem-sucedido. S3 configurado é identificado como não verificado até um upload real.
5. Faça um cadastro controlado, um redeploy e confirme que ele persiste. Preserve dados reais; não insira lotes de teste em relatórios de produção.
6. Confira logout. Confirme um backup e uma restauração em ambiente separado antes de considerar a operação validada.

Se `/health` falhar, confirme primeiro `DATABASE_URL`, rede privada PostgreSQL e `ADMIN_PASSWORD`. A aplicação não imprime credenciais nem detalhes de conexão nos erros públicos. Redis/S3 opcionais não impedem health do banco. Um badge de serviço criado na Railway não comprova uso pela API.

## S3

O navegador usa um POST temporário de cinco minutos, limitado ao tipo JPEG/PNG/WebP/MP4 e 25 MB. Configure CORS do bucket para permitir POST apenas da origem HTTPS do painel e os campos exigidos pelo seu provedor. Mantenha objetos privados e a política restrita ao prefixo `fluxosolar/`. Não há leitura pública automática da mídia; a chave é vinculada ao rascunho após o upload.

## Retirada de work e migrações

A `work` era a origem Railway informada anteriormente. Troque a origem para **main**, faça o deploy e confirme o healthcheck antes de remover a branch remota. Um push na main não altera a origem do serviço na Railway.

Antes de mudar de servidor, faça backup consistente PostgreSQL, restaure no destino, valide login/dados/mídia, mude o domínio e monitore. Só remova o recurso antigo depois dessas verificações. Retenção de logs e backups do provedor segue as políticas dele; remover a aplicação não elimina necessariamente essas cópias.

Referências oficiais: [Dockerfile](https://docs.railway.com/guides/dockerfiles), [configuração como código](https://docs.railway.com/reference/config-as-code), [healthcheck](https://docs.railway.com/guides/healthchecks).
