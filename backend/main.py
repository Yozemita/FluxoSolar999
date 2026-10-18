import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from .database import AgentRun, Audit, Base, Creative, MetricEvent, Owner, Product, Schedule, Session, make_database, now
from .limits import RequestBodyLimit
from .schemas import AgentInput, CreativeInput, CreativeUpdate, Login, MediaInput, Metric, MetricImport, ProductInput, ScheduleInput
from .security import COOKIE, SESSION_SECONDS, authenticate, bootstrap, digest
from .services import AGENTS, agent_run_dict, compliant, create_draft, creative_dict, dashboard, product_dict, public, ranking, run_agent, winner_score

log = logging.getLogger("fluxosolar")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
INITIAL_PRODUCTS = [
    ("SHOPEE", "CBR-ZWT-AYN", "Macaquinho canelado com zíper", "https://br.shp.ee/q24wptkc?fromSource=copy_link&smtt=0.0.9"),
    ("SHEIN", "2533Q72", "Vestido branco de renda", "https://onelink.shein.com/57/65ewa287r6f5?ismg_ol=EU413VfJpkO_01_KOC-C"),
    ("SHEIN", "S6RNVSC", "Calça de pijama SweetSlumber", "https://onelink.shein.com/57/65ewi2apt56l?ismg_ol=2BTrFSfMy9J_01_KOC-C"),
    ("SHOPEE", "AKW-MJA-BNP", "Vestido frente única com babado", "https://collshp.com/exterminador777345?linkId=44923047&view=storefront"),
]


def db_session(request: Request):
    with request.app.state.sessions() as session:
        yield session


def owner(request: Request, db=Depends(db_session)):
    session = db.scalar(select(Session).where(Session.digest == digest(request.cookies.get(COOKIE, "")), Session.expires > now()))
    if session is None:
        raise HTTPException(401, "Faça login para continuar.")
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("X-FluxoSolar-CSRF") != "1":
        raise HTTPException(403, "Cabeçalho CSRF ausente.")
    return session.owner_id


def find_product(db, product_id):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Produto não encontrado.")
    return product


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Registro duplicado ou referência inválida.") from None


def make_app(database_url=None):
    @asynccontextmanager
    async def lifespan(app):
        engine, sessions = make_database(database_url)
        app.state.engine, app.state.sessions = engine, sessions
        try:
            for attempt in range(6):
                try:
                    await run_in_threadpool(Base.metadata.create_all, engine)
                    break
                except SQLAlchemyError:
                    if attempt == 5:
                        raise RuntimeError("Database initialization failed. Check DATABASE_URL and PostgreSQL service/network access.") from None
                    log.warning("Waiting for database readiness (%s/6)", attempt + 1)
                    await run_in_threadpool(time.sleep, 2)
            with sessions() as db:
                bootstrap(db)
                for merchant, code, title, url in INITIAL_PRODUCTS:
                    if not db.scalar(select(Product.id).where(Product.external_code == code)):
                        db.add(Product(merchant=merchant, external_code=code, title=title, affiliate_url=url))
                db.commit()
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="FluxoSolar Growth Engine", version="0.2.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(RequestBodyLimit)
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            expected = os.getenv("PUBLIC_BASE_URL", str(request.base_url)).rstrip("/")
            if (origin and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' https:; img-src 'self' https: data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if request.url.path != "/health" and not request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, _error):
        log.error("Database request failed; connection details and SQL parameters omitted")
        return JSONResponse({"detail": "Banco indisponível. Tente novamente."}, status_code=503)

    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")

    @app.get("/health")
    def health(db=Depends(db_session)):
        try:
            db.execute(text("SELECT 1"))
            return {"status": "ok", "service": "FluxoSolar Growth Engine", "database": "ready"}
        except SQLAlchemyError:
            return JSONResponse({"status": "unavailable", "database": "unavailable"}, status_code=503)

    @app.post("/api/auth/login")
    def login(body: Login, request: Request, response: Response, db=Depends(db_session)):
        token = authenticate(db, body.username, body.password, request.client.host if request.client else "unknown")
        old = request.cookies.get(COOKIE)
        if old:
            db.execute(delete(Session).where(Session.digest == digest(old)))
            db.commit()
        response.set_cookie(COOKIE, token, httponly=True, secure=os.getenv("COOKIE_SECURE", "true").lower() == "true", samesite="strict", max_age=SESSION_SECONDS)
        return {"authenticated": True}

    @app.get("/api/auth/me")
    def me(owner_id=Depends(owner), db=Depends(db_session)):
        return {"username": db.get(Owner, owner_id).username}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response, _owner=Depends(owner), db=Depends(db_session)):
        db.execute(delete(Session).where(Session.digest == digest(request.cookies.get(COOKIE, ""))))
        db.add(Audit(action="logout"))
        db.commit()
        response.delete_cookie(COOKIE)
        return {"authenticated": False}

    @app.get("/products", dependencies=[Depends(owner)])
    @app.get("/api/products", dependencies=[Depends(owner)])
    def products(db=Depends(db_session)):
        return [product_dict(p) for p in db.scalars(select(Product).order_by(Product.id))]

    @app.get("/products/{product_id}", dependencies=[Depends(owner)])
    @app.get("/api/products/{product_id}", dependencies=[Depends(owner)])
    def product(product_id: int, db=Depends(db_session)):
        return product_dict(find_product(db, product_id))

    @app.post("/api/products", status_code=201, dependencies=[Depends(owner)])
    def add_product(body: ProductInput, db=Depends(db_session)):
        row = Product(**body.model_dump(mode="json"))
        db.add(row)
        db.add(Audit(action="product.create"))
        commit(db)
        return product_dict(row)

    @app.put("/api/products/{product_id}", dependencies=[Depends(owner)])
    def update_product(product_id: int, body: ProductInput, db=Depends(db_session)):
        row = find_product(db, product_id)
        for key, value in body.model_dump(mode="json").items():
            setattr(row, key, value)
        db.add(Audit(action="product.update"))
        commit(db)
        return product_dict(row)

    @app.post("/api/metrics", status_code=201, dependencies=[Depends(owner)])
    def import_metrics(body: MetricImport, response: Response, db=Depends(db_session)):
        find_product(db, body.product_id)
        values = body.model_dump()
        existing = db.get(MetricEvent, body.event_id)
        if existing:
            if any(getattr(existing, k) != v for k, v in values.items()):
                raise HTTPException(409, "event_id já utilizado com valores diferentes.")
            response.status_code = 200
            return {"imported": False, "duplicate": True}
        db.add(MetricEvent(**values))
        db.add(Audit(action="metrics.import"))
        commit(db)
        return {"imported": True, "duplicate": False}

    @app.put("/metrics/{product_id}", dependencies=[Depends(owner)])
    @app.put("/api/metrics/{product_id}", dependencies=[Depends(owner)])
    def set_metrics(product_id: int, body: Metric, db=Depends(db_session)):
        find_product(db, product_id)
        event_id = f"manual:{product_id}"
        row = db.get(MetricEvent, event_id)
        if not row:
            row = MetricEvent(event_id=event_id, product_id=product_id)
            db.add(row)
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        db.add(Audit(action="metrics.replace_manual_snapshot"))
        db.commit()
        return {"product_id": product_id, "metrics": body.model_dump(), "winner_score": winner_score(body),
                "note": "Substitui apenas o snapshot manual. Eventos incrementais importados continuam no total."}

    @app.get("/winners", dependencies=[Depends(owner)])
    @app.get("/api/winners", dependencies=[Depends(owner)])
    def winners(db=Depends(db_session)):
        return ranking(db)

    @app.get("/api/dashboard", dependencies=[Depends(owner)])
    def get_dashboard(db=Depends(db_session)):
        return dashboard(db)

    @app.get("/api/creatives", dependencies=[Depends(owner)])
    def creatives(db=Depends(db_session)):
        return [creative_dict(c) for c in db.scalars(select(Creative).order_by(Creative.id.desc()).limit(200))]

    @app.post("/api/creatives", status_code=201, dependencies=[Depends(owner)])
    def draft(body: CreativeInput, db=Depends(db_session)):
        creative = create_draft(db, find_product(db, body.product_id))
        db.add(Audit(action="creative.create"))
        db.commit()
        return creative_dict(creative)

    @app.put("/api/creatives/{creative_id}", dependencies=[Depends(owner)])
    def edit_creative(creative_id: int, body: CreativeUpdate, db=Depends(db_session)):
        row = db.get(Creative, creative_id)
        if not row:
            raise HTTPException(404, "Criativo não encontrado.")
        if body.media_key and not body.media_key.startswith("fluxosolar/"):
            raise HTTPException(422, "Chave de mídia inválida.")
        for key, value in body.model_dump().items():
            setattr(row, key, value)
        db.add(Audit(action="creative.update"))
        db.commit()
        return creative_dict(row)

    @app.get("/api/schedules", dependencies=[Depends(owner)])
    def schedules(db=Depends(db_session)):
        return [public(s, ("id", "creative_id", "channel", "scheduled_for", "status")) for s in db.scalars(select(Schedule).order_by(Schedule.scheduled_for))]

    @app.post("/api/schedules", status_code=201, dependencies=[Depends(owner)])
    def schedule(body: ScheduleInput, db=Depends(db_session)):
        creative = db.get(Creative, body.creative_id)
        if not creative:
            raise HTTPException(404, "Criativo não encontrado.")
        if not compliant(creative):
            raise HTTPException(422, "Inclua publicidade/#publi e identificação de link de afiliado na legenda.")
        if body.scheduled_for <= now():
            raise HTTPException(422, "Escolha uma data futura.")
        row = Schedule(**body.model_dump())
        db.add(row)
        db.add(Audit(action="schedule.plan"))
        db.commit()
        return {**public(row, ("id", "creative_id", "channel", "scheduled_for", "status")), "external_publication": "not_connected"}

    @app.get("/agents", dependencies=[Depends(owner)])
    @app.get("/api/agents", dependencies=[Depends(owner)])
    def agents():
        return {"agents": list(AGENTS), "execution": "local_on_demand", "external_publication": "not_connected"}

    @app.post("/api/agents/{agent}/run", status_code=201, dependencies=[Depends(owner)])
    def agent_run(agent: str, body: AgentInput, db=Depends(db_session)):
        if agent not in AGENTS:
            raise HTTPException(404, "Agente não encontrado.")
        product = find_product(db, body.product_id) if body.product_id else None
        if agent == "Creative" and product is None:
            raise HTTPException(422, "Selecione um produto para criar o rascunho.")
        result = jsonable_encoder(run_agent(db, agent, product))
        row = AgentRun(agent=agent, result=result)
        db.add(row)
        db.add(Audit(action=f"agent.{agent}"))
        db.commit()
        return agent_run_dict(row)

    @app.get("/api/agent-runs", dependencies=[Depends(owner)])
    def agent_runs(db=Depends(db_session)):
        return [agent_run_dict(r) for r in db.scalars(select(AgentRun).order_by(AgentRun.id.desc()).limit(50))]

    @app.get("/api/status", dependencies=[Depends(owner)])
    def status(request: Request):
        redis_status = "not_configured"
        if os.getenv("REDIS_URL"):
            import redis
            try:
                with redis.Redis.from_url(os.environ["REDIS_URL"], socket_timeout=2, socket_connect_timeout=2) as client:
                    redis_status = "ready" if client.ping() else "unavailable"
            except redis.RedisError:
                redis_status = "unavailable"
        return {"database": request.app.state.engine.dialect.name, "redis": redis_status,
                "s3": "configured_unverified" if os.getenv("S3_BUCKET") else "not_configured",
                "video_generation": "not_connected", "social_publishing": "not_connected", "paid_ads": "not_connected",
                "agents": "local_on_demand", "version": "0.2.0"}

    @app.post("/api/media/uploads", dependencies=[Depends(owner)])
    def media_upload(body: MediaInput):
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise HTTPException(503, "Configure um bucket S3 e credenciais para enviar mídia.")
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
        extensions = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "video/mp4": "mp4"}
        key = f"fluxosolar/{secrets.token_hex(20)}.{extensions[body.content_type]}"
        try:
            client = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT_URL"), region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
            signed = client.generate_presigned_post(Bucket=bucket, Key=key, Fields={"Content-Type": body.content_type},
                Conditions=[{"Content-Type": body.content_type}, ["content-length-range", 1, 25 * 1024 * 1024]], ExpiresIn=300)
            return {"key": key, "upload": signed, "expires_in": 300}
        except (BotoCoreError, ClientError):
            raise HTTPException(503, "Não foi possível autorizar o upload S3. Verifique a configuração do serviço.") from None

    return app


app = make_app()
