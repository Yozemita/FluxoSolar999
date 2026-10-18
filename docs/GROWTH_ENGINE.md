# FluxoSolar Growth Engine

## Visão

Painel futurista para organizar produtos afiliados, criativos, publicação, analytics e experimentos de crescimento orgânico. O sistema usa agentes/bots internos apenas para tarefas legítimas de bastidor; eles não criam contas falsas, seguidores, visualizações, cliques, comentários ou engajamento artificial e não contornam requisitos das plataformas.

## Visual

- interface dark futurista com dourado solar e detalhes inspirados em Tiphereth/Vênus de forma abstrata;
- dashboard responsivo com cards luminosos, microinterações e gráficos;
- modo catálogo para Shopee e SHEIN;
- produto sempre ligado ao ID/SKU, link afiliado, mídia e campanha corretos.

## Agentes internos

### Scout Agent
Analisa métricas importadas e encontra criativos/produtos com melhor desempenho real.

### Creative Agent
Gera sugestões de hooks, títulos, descrições, CTAs e hashtags relevantes para cada produto. Nunca cria alegações falsas.

### Catalog Agent
Mantém `merchant -> produto -> ID/SKU -> link afiliado -> foto/vídeo` e bloqueia associações conflitantes.

### Scheduler Agent
Monta uma fila de publicação e recomenda horários a partir de dados disponíveis. Publicação automática só por integrações oficiais/autorizadas.

### Analytics Agent
Calcula CTR, visitas ao perfil, seguidores atribuíveis quando disponíveis, conversão, receita e comissão. Separa alcance orgânico de mídia paga.

### Winner Agent
Pontua criativos com dados reais e recomenda quais formatos merecem novas variações. Pode usar exploração/explotação (multi-armed bandit) apenas para escolher criativos, nunca para fabricar tráfego.

### Compliance Agent
Valida disclosure de afiliado, consistência de produto/link, claims e regras de plataforma antes de liberar uma campanha.

## Funil

`Produto -> Catálogo -> Criativo -> Compliance -> Fila -> Publicação autorizada -> Analytics -> Winner Engine -> Nova variação`

## Dados mínimos

### Product
- id
- merchant: SHOPEE | SHEIN
- external_code
- title
- affiliate_url
- storefront_url opcional
- storefront_link_id opcional
- price_snapshot opcional
- commission_snapshot opcional
- created_at

### Creative
- id
- product_id
- media_path/media_url
- media_type
- hook
- caption
- hashtags
- disclosure
- status

### Campaign
- id
- creative_id
- channel
- scheduled_at
- publication_id opcional
- status
- organic_or_paid

### MetricSnapshot
- campaign_id
- captured_at
- views
- watch_time opcional
- completion_rate opcional
- likes
- comments
- shares
- profile_visits
- follows
- clicks
- conversions
- revenue
- commission

## Winner Score

Normalizar métricas por canal e janela temporal. Exemplo inicial:

`score = 0.25*follow_rate + 0.20*profile_visit_rate + 0.20*ctr + 0.15*conversion_rate + 0.10*share_rate + 0.10*commission_per_1k_views`

Pesos devem ser configuráveis e só usar métricas realmente disponíveis.

## Stack proposta

- Frontend: Next.js + TypeScript + Tailwind + shadcn/ui
- API: FastAPI
- Banco: PostgreSQL
- Filas: Redis + Celery/Dramatiq
- Objetos: S3/MinIO
- Analytics: PostgreSQL inicialmente; ClickHouse/PostHog opcional em escala
- Observabilidade: Prometheus + Grafana + Loki
- Deploy: Docker Compose + Caddy/Traefik

## Primeiros produtos cadastráveis

- Shopee: macaquinho canelado com zíper — ID `CBR-ZWT-AYN`
- SHEIN: vestido branco de renda — código `2533Q72`
- SHEIN: calça de pijama SweetSlumber — código `S6RNVSC`
- Shopee: vestido frente única com babado — ID `AKW-MJA-BNP`

Os links devem ser armazenados no banco/segredos de configuração apropriados e nunca cruzados entre produtos.

## Guardrails

1. Sem bots de seguidores, views, likes, comentários ou cliques.
2. Sem criação/operação de contas falsas.
3. Sem CAPTCHA bypass, device spoofing ou evasão de rate limits.
4. Sem automação de Promote/compra de anúncios sem aprovação humana e elegibilidade da conta.
5. Sem contornar requisitos de idade, TikTok Shop ou programas de afiliados.
6. Somente APIs, conectores e fluxos autorizados pelas plataformas.
7. Toda ação externa fica auditável em `audit_log`.

## Roadmap

1. Scaffold frontend/API/DB e autenticação do painel.
2. Catálogo afiliado e importação de mídia.
3. Creative Studio e templates de overlay com ID/SKU.
4. Scheduler e integrações oficiais.
5. Analytics + Winner Engine.
6. Agentes internos e fila de recomendações.
7. Observabilidade, backups e deploy self-hosted.
