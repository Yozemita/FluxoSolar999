from sqlalchemy import func, select

from .database import Creative, MetricEvent, Product, Schedule
from .schemas import Metric

FIELDS = tuple(Metric.model_fields)
AGENTS = ("Scout", "Creative", "Catalog", "Scheduler", "Analytics", "Winner", "Compliance")


def public(row, fields):
    return {field: getattr(row, field) for field in fields}


def product_dict(row):
    return public(row, ("id", "merchant", "external_code", "title", "affiliate_url", "storefront_url"))


def creative_dict(row):
    return {**public(row, ("id", "product_id", "title", "caption", "prompt", "media_key", "created")), "type": "template_draft"}


def winner_score(metric):
    def rate(n, d):
        return n / d if d else 0.0
    return round(100 * (
        .25 * rate(metric.follows, metric.views) + .20 * rate(metric.profile_visits, metric.views)
        + .20 * rate(metric.clicks, metric.views) + .15 * rate(metric.conversions, metric.clicks)
        + .10 * rate(metric.shares, metric.views) + .10 * (metric.commission / max(metric.views / 1000, 1)) / 100
    ), 4)


def ranking(db):
    statement = select(MetricEvent.product_id, *[func.sum(getattr(MetricEvent, f)).label(f) for f in FIELDS]).group_by(MetricEvent.product_id)
    totals = {r.product_id: dict(r._mapping) for r in db.execute(statement)}
    rows = []
    for product in db.scalars(select(Product).order_by(Product.id)):
        data = {f: totals.get(product.id, {}).get(f, 0) for f in FIELDS}
        metric = Metric(**data)
        enough = metric.views >= 100 and metric.clicks >= 20 and metric.conversions >= 3
        rows.append({"product": product_dict(product), "metrics": data, "score": winner_score(metric) if enough else None,
                     "recommendation": ("prioritize" if metric.commission > metric.spend else "review") if enough else "collect_data",
                     "profit": round(metric.commission - metric.spend, 2), "sample_sufficient": enough})
    return sorted(rows, key=lambda r: (r["score"] is not None, r["score"] or 0), reverse=True)


def dashboard(db):
    rows = ranking(db)
    return {"products": len(rows), "creatives": db.scalar(select(func.count()).select_from(Creative)),
            "planned": db.scalar(select(func.count()).select_from(Schedule).where(Schedule.status == "planned")),
            "totals": {f: sum(r["metrics"][f] for r in rows) for f in FIELDS},
            "profit": round(sum(r["profit"] for r in rows), 2), "ranking": rows,
            "note": "Métricas importadas manualmente. Resultado = comissão − gasto informado; outros custos não incluídos."}


def create_draft(db, product):
    creative = Creative(product_id=product.id, title=product.title,
        caption=f"Conheça {product.title}. Confira os detalhes no link oficial da {product.merchant}. Publicidade • link de afiliado. #publi",
        prompt=f"Crie um vídeo vertical sobre {product.title}, código {product.external_code}. Use somente mídia autorizada e informações verificadas. Não invente preço, desconto, benefícios ou avaliações. Preserve a identidade do produto. Inclua identificação de publicidade.")
    db.add(creative)
    db.flush()
    return creative


def compliant(creative):
    caption = creative.caption.casefold()
    return ("afiliado" in caption) and any(word in caption for word in ("publicidade", "#publi"))


def run_agent(db, agent, product=None):
    if agent == "Creative":
        return {"creative": creative_dict(create_draft(db, product)), "message": "Rascunho por template criado. Nenhum vídeo foi gerado."}
    if agent == "Catalog":
        return {"products": [product_dict(p) for p in db.scalars(select(Product).order_by(Product.id))],
                "message": "Catálogo persistido; links validados no cadastro. Estoque e comissão não consultados."}
    if agent == "Analytics":
        return dashboard(db)
    if agent in ("Scout", "Winner"):
        return {"ranking": ranking(db), "message": "Heurística sobre métricas importadas, com amostra mínima de 100 views, 20 cliques e 3 conversões. Não representa significância estatística."}
    if agent == "Scheduler":
        return {"planned": [public(r, ("id", "creative_id", "channel", "scheduled_for", "status")) for r in db.scalars(select(Schedule).order_by(Schedule.scheduled_for))],
                "message": "Fila interna de planejamento. Nenhuma publicação externa executada."}
    return {"creatives": [{"id": c.id, "product_id": c.product_id, "disclosure_present": compliant(c)} for c in db.scalars(select(Creative))],
            "message": "Checagem da identificação de publicidade. Não audita mídia nem garante conformidade com a plataforma."}
