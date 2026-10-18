from datetime import datetime
from enum import Enum
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="FluxoSolar Growth Engine", version="0.1.0")

class Merchant(str, Enum):
    SHOPEE = "SHOPEE"
    SHEIN = "SHEIN"

class Product(BaseModel):
    id: int
    merchant: Merchant
    external_code: str
    title: str
    affiliate_url: HttpUrl
    storefront_url: Optional[HttpUrl] = None

class Metric(BaseModel):
    views: int = 0
    profile_visits: int = 0
    follows: int = 0
    clicks: int = 0
    conversions: int = 0
    shares: int = 0
    commission: float = 0

PRODUCTS = {
    1: Product(id=1, merchant=Merchant.SHOPEE, external_code="CBR-ZWT-AYN", title="Macaquinho canelado com zíper", affiliate_url="https://br.shp.ee/q24wptkc?fromSource=copy_link&smtt=0.0.9"),
    2: Product(id=2, merchant=Merchant.SHEIN, external_code="2533Q72", title="Vestido branco de renda", affiliate_url="https://onelink.shein.com/57/65ewa287r6f5?ismg_ol=EU413VfJpkO_01_KOC-C"),
    3: Product(id=3, merchant=Merchant.SHEIN, external_code="S6RNVSC", title="Calça de pijama SweetSlumber", affiliate_url="https://onelink.shein.com/57/65ewi2apt56l?ismg_ol=2BTrFSfMy9J_01_KOC-C"),
    4: Product(id=4, merchant=Merchant.SHOPEE, external_code="AKW-MJA-BNP", title="Vestido frente única com babado", affiliate_url="https://collshp.com/exterminador777345?linkId=44923047&view=storefront"),
}
METRICS: dict[int, Metric] = {}

def rate(n: int, d: int) -> float:
    return n / d if d else 0.0

def winner_score(m: Metric) -> float:
    return round(100 * (
        .25 * rate(m.follows, m.views) +
        .20 * rate(m.profile_visits, m.views) +
        .20 * rate(m.clicks, m.views) +
        .15 * rate(m.conversions, m.clicks) +
        .10 * rate(m.shares, m.views) +
        .10 * (m.commission / max(m.views / 1000, 1)) / 100
    ), 4)

@app.get("/health")
def health():
    return {"status": "ok", "service": "FluxoSolar Growth Engine", "time": datetime.utcnow().isoformat()}

@app.get("/products")
def products():
    return list(PRODUCTS.values())

@app.get("/products/{product_id}")
def product(product_id: int):
    if product_id not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    return PRODUCTS[product_id]

@app.put("/metrics/{product_id}")
def set_metrics(product_id: int, metric: Metric):
    if product_id not in PRODUCTS:
        raise HTTPException(404, "Product not found")
    METRICS[product_id] = metric
    return {"product": PRODUCTS[product_id], "metrics": metric, "winner_score": winner_score(metric)}

@app.get("/winners")
def winners():
    rows = [{"product": PRODUCTS[i], "metrics": m, "score": winner_score(m)} for i, m in METRICS.items()]
    return sorted(rows, key=lambda x: x["score"], reverse=True)

@app.get("/agents")
def agents():
    return {
        "agents": ["Scout", "Creative", "Catalog", "Scheduler", "Analytics", "Winner", "Compliance"],
        "guardrail": "No fake accounts, followers, views, clicks, comments, CAPTCHA bypass or platform evasion."
    }
