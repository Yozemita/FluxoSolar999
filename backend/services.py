from sqlalchemy import func, select

from .database import AgentRun, Creative, MetricEvent, Product, Schedule, now
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
    totals = {f: sum(r["metrics"][f] for r in rows) for f in FIELDS}
    creatives = list(db.scalars(select(Creative)))
    planned = db.scalar(select(func.count()).select_from(Schedule).where(Schedule.status == "planned"))
    overdue = db.scalar(select(func.count()).select_from(Schedule).where(Schedule.status == "planned", Schedule.scheduled_for < now()))
    missing_disclosure = sum(not compliant(c) for c in creatives)
    insights = []
    if not sum(totals.values()):
        insights.append({"title": "Importe seu primeiro relatório", "detail": "As métricas ainda não foram informadas. Os resultados aparecerão depois da importação.", "view": "metrics"})
    if rows and not creatives:
        insights.append({"title": "Prepare um rascunho", "detail": "Seu catálogo já está disponível. Escolha um produto e prepare uma legenda e um briefing.", "view": "studio"})
    if missing_disclosure:
        insights.append({"title": "Revise a identificação de publicidade", "detail": f"{missing_disclosure} rascunho(s) sem identificação completa de publicidade e link de afiliado.", "view": "studio"})
    if overdue:
        insights.append({"title": "Confira sua agenda", "detail": f"{overdue} item(ns) planejado(s) com data passada. O painel não confirma publicação externa.", "view": "schedule"})
    prioritize = sum(r["recommendation"] == "prioritize" for r in rows)
    if prioritize:
        insights.append({"title": "Revise os produtos com resultado positivo", "detail": f"{prioritize} produto(s) com amostra mínima e comissão acima do gasto informado. É uma indicação heurística.", "view": "agents"})
    if totals["views"] and any(not r["sample_sufficient"] and any(r["metrics"].values()) for r in rows):
        insights.append({"title": "Continue coletando dados", "detail": "Há produtos com métricas abaixo da amostra mínima do ranking. Evite tratar uma amostra pequena como resultado conclusivo.", "view": "metrics"})
    recent = list(db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(5)))
    return {"products": len(rows), "creatives": db.scalar(select(func.count()).select_from(Creative)),
            "planned": planned, "overdue": overdue, "insights": insights,
            "totals": totals,
            "rates": {"ctr": totals["clicks"] / totals["views"] if totals["views"] else None,
                      "conversion": totals["conversions"] / totals["clicks"] if totals["clicks"] else None,
                      "roi": (totals["commission"] - totals["spend"]) / totals["spend"] if totals["spend"] else None},
            "activity": [agent_run_dict(r, include_result=False) for r in recent],
            "profit": round(sum(r["profit"] for r in rows), 2), "ranking": rows,
            "note": "Métricas importadas manualmente. Resultado = comissão − gasto informado; outros custos não incluídos."}


def create_draft(db, product):
    creative = Creative(product_id=product.id, title=product.title,
        caption=f"Conheça {product.title}. Confira os detalhes no link oficial da {product.merchant}. Publicidade • link de afiliado. #publi",
        prompt=f"Prepare uma peça de divulgação sobre {product.title}, código {product.external_code}. Use somente mídia autorizada e informações verificadas. Não invente preço, desconto, benefícios ou avaliações. Preserve a identidade do produto. Inclua identificação de publicidade.")
    db.add(creative)
    db.flush()
    return creative


def compliant(creative):
    caption = creative.caption.casefold()
    return ("afiliado" in caption) and any(word in caption for word in ("publicidade", "#publi"))


def run_agent(db, agent, product=None):
    if agent == "Creative":
        return {"creative": creative_dict(create_draft(db, product)), "message": "Legenda e briefing preparados por template para sua revisão."}
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


def agent_summary(agent, result):
    if agent == "Creative":
        return "Rascunho preparado para revisão."
    if agent == "Catalog":
        return f"{len(result.get('products', []))} produto(s) consultado(s) no catálogo."
    if agent == "Analytics":
        return f"Métricas consolidadas de {result.get('products', 0)} produto(s)."
    if agent in ("Scout", "Winner"):
        rows = result.get("ranking", [])
        enough = sum(bool(r.get("sample_sufficient")) for r in rows)
        return f"{enough} de {len(rows)} produto(s) com amostra mínima para análise."
    if agent == "Scheduler":
        return f"{len(result.get('planned', []))} item(ns) na agenda interna."
    rows = result.get("creatives", [])
    missing = sum(not r.get("disclosure_present", False) for r in rows)
    return f"{len(rows)} rascunho(s) verificado(s); {missing} precisa(m) revisar identificação de publicidade."


def agent_run_dict(row, include_result=True):
    data = {**public(row, ("id", "agent", "created")), "summary": agent_summary(row.agent, row.result)}
    if include_result:
        data["result"] = row.result
    return data
