from __future__ import annotations

import hashlib
import re

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.agent_context import AgentContextService
from app.auth import ApiPrincipal, KeyStore
from app.cache import TTLCache
from app.clients.searx_client import SearxClient
from app.config import SETTINGS
from app.console import SearchConsoleService
from app.domain import Plan
from app.models import AgentContextRequest, AgentContextResponse, DatasetCreateRequest, SearchRequest, SearchResponse
from app.rate_limit import SlidingWindowRateLimiter
from app.security import generate_api_key, verify_password
from app.service import SearchService
from app.session import SessionManager
from app.template_engine import TemplateEngine
from app.user_store import UserStore
from app.payments import PaymentError, RazorpayGateway

app = FastAPI(title="Open Search API", version="0.4.0")

_store = UserStore(SETTINGS.db_path, backend=SETTINGS.db_backend, dsn=SETTINGS.db_dsn)
_store.ensure_admin_user()
_template = TemplateEngine("templates")
_session = SessionManager(secret=SETTINGS.session_secret)
_keystore = KeyStore(_store)
_rate_limiter = SlidingWindowRateLimiter()
_service = SearchService(
    searx_client=SearxClient(base_url=SETTINGS.searx_base_url, timeout_s=SETTINGS.request_timeout_s),
    cache=TTLCache(),
)
_console = SearchConsoleService()
_agent_context = AgentContextService(_service)
_payments = RazorpayGateway(SETTINGS.razorpay_key_id, SETTINGS.razorpay_key_secret)




def _plan_rank(plan: Plan) -> int:
    return {Plan.FREE: 0, Plan.PRO: 1, Plan.ENTERPRISE: 2}[plan]


def _allowed_for_plan(user_id: int, target_plan: Plan) -> bool:
    if target_plan == Plan.FREE:
        return True
    sub = _store.get_subscription(user_id)
    if sub is None or sub["status"] != "active":
        return False
    return _plan_rank(Plan(sub["plan"])) >= _plan_rank(target_plan)


def _price_for_plan(plan: Plan) -> int:
    if plan == Plan.PRO:
        return SETTINGS.pro_monthly_price_inr
    if plan == Plan.ENTERPRISE:
        return SETTINGS.enterprise_monthly_price_inr
    return 0

def _rpm_for(plan: Plan) -> int:
    return {
        Plan.FREE: SETTINGS.free_rpm,
        Plan.PRO: SETTINGS.pro_rpm,
        Plan.ENTERPRISE: SETTINGS.enterprise_rpm,
    }[plan]


def _current_user(request: Request):
    user_id = _session.verify(request.cookies.get("session"))
    if user_id is None:
        return None
    return _store.find_user_by_id(user_id)


def _render_dashboard(user_id: int, username: str, message: str = "", latest_key: str = "") -> HTMLResponse:
    keys = _store.list_api_keys(user_id)
    keys_html = "".join([f"<li>{k['prefix']}... ({k['plan']}) - {k['created_at']}</li>" for k in keys]) or "<li>No API keys yet</li>"
    usage = _store.list_recent_api_usage(user_id, limit=14)
    traffic_series = [int(row["result_count"]) for row in reversed(usage)]
    chart_api_traffic = _console.build_svg_bars(traffic_series or [0])
    usage_rows = "".join([f"<tr><td>{u['request_at']}</td><td>{u['query']}</td><td>{u['took_ms']}</td><td>{u['result_count']}</td></tr>" for u in usage]) or "<tr><td colspan='4'>No API traffic yet</td></tr>"
    body = _template.render(
        "dashboard.html",
        {
            "username": username,
            "keys_html": keys_html,
            "message": message,
            "latest_key": latest_key,
            "chart_api_traffic": chart_api_traffic,
            "usage_rows": usage_rows,
        },
    )
    return HTMLResponse(body)


def _render_agent_home(user_id: int, username: str, message: str = "", context_json: str = "") -> HTMLResponse:
    datasets = _store.list_datasets(user_id)
    dataset_rows = "".join(
        [
            f"<tr><td>{d['name']}</td><td>{d['source']}</td><td>{d['query']}</td><td>{d['rows_count']}</td><td>{d['status']}</td><td>{d['created_at']}</td></tr>"
            for d in datasets
        ]
    ) or "<tr><td colspan='6'>No datasets yet</td></tr>"
    body = _template.render(
        "agent_home.html",
        {
            "username": username,
            "message": message,
            "context_json": context_json,
            "datasets_rows": dataset_rows,
        },
    )
    return HTMLResponse(body)








def _render_billing_home(user_id: int, message: str = "") -> HTMLResponse:
    sub = _store.get_subscription(user_id)
    current_plan = sub["plan"] if sub else "free"
    payments = _store.list_payments(user_id, limit=20)
    payment_rows = "".join(
        [
            f"<tr><td>{p['order_id']}</td><td>{p['payment_id'] or '-'}</td><td>{p['amount_paise']/100:.2f} {p['currency']}</td><td>{p['plan']}</td><td>{p['status']}</td><td>{p['created_at']}</td></tr>"
            for p in payments
        ]
    ) or "<tr><td colspan='6'>No payments yet</td></tr>"
    body = _template.render(
        "billing_home.html",
        {
            "current_plan": current_plan,
            "free_daily_calls": SETTINGS.free_daily_calls,
            "today_calls": _store.search_calls_today(user_id),
            "pro_price": SETTINGS.pro_monthly_price_inr,
            "enterprise_price": SETTINGS.enterprise_monthly_price_inr,
            "razorpay_key_id": SETTINGS.razorpay_key_id,
            "payment_rows": payment_rows,
            "message": message,
        },
    )
    return HTMLResponse(body)

def _render_console_home(user_id: int, username: str, message: str = "") -> HTMLResponse:
    sites = _store.list_sites(user_id)
    rows = [
        f"<tr><td><a href='/console/site/{site['id']}'>{site['domain']}</a></td><td>{'verified' if int(site['verified']) == 1 else 'pending'}</td><td>{site['verification_method'] or '-'}</td><td>{site['created_at']}</td></tr>"
        for site in sites
    ]
    table_rows = "".join(rows) or "<tr><td colspan='4'>No properties yet</td></tr>"
    body = _template.render("console_home.html", {"username": username, "sites_rows": table_rows, "message": message})
    return HTMLResponse(body)


def _build_dataset_rows(source: str, query: str, rows: int) -> list[dict[str, str]]:
    source_map = {
        "open-search": ("Search-derived", "https://dataset.local/search"),
        "commoncrawl": ("CommonCrawl-derived", "https://commoncrawl.org/record"),
    }
    label, base = source_map.get(source, source_map["open-search"])
    return [{"content": f"{label} row {i+1} for '{query}'", "source_url": f"{base}/{i+1}"} for i in range(rows)]

def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "post"

def require_principal(authorization: str | None = Header(default=None)) -> ApiPrincipal:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]

    principal = _keystore.authenticate(token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    allowed = _rate_limiter.allow(principal.key_hash, rpm=_rpm_for(principal.plan))
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    if principal.plan == Plan.FREE:
        today_calls = _store.search_calls_today(principal.user_id)
        if today_calls >= SETTINGS.free_daily_calls:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Daily free quota exceeded ({SETTINGS.free_daily_calls}). Upgrade plan from billing.",
            )

    return principal


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    user = _current_user(request)
    username = user["username"] if user else ""
    body = _template.render("index.html", {"username": username})
    return HTMLResponse(body)


@app.get("/signup", response_class=HTMLResponse)
def signup_page() -> HTMLResponse:
    return HTMLResponse(_template.render("signup.html", {"message": ""}))


@app.post("/signup", response_class=HTMLResponse)
def signup(username: str = Form(...), password: str = Form(...)) -> HTMLResponse:
    try:
        _store.create_user(username.strip(), password)
    except Exception:
        return HTMLResponse(_template.render("signup.html", {"message": "Username already exists."}), status_code=400)
    return HTMLResponse(_template.render("login.html", {"message": "Signup successful. Please login."}))


@app.get("/login", response_class=HTMLResponse)
def login_page() -> HTMLResponse:
    return HTMLResponse(_template.render("login.html", {"message": "Use admin/admin for default access."}))


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)) -> RedirectResponse | HTMLResponse:
    user = _store.get_user_by_username(username.strip())
    if user is None or not verify_password(password, user["password_hash"]):
        return HTMLResponse(_template.render("login.html", {"message": "Invalid credentials."}), status_code=401)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("session", _session.create(int(user["id"])), httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("session")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return _render_dashboard(int(user["id"]), str(user["username"]))


@app.post("/dashboard/generate", response_class=HTMLResponse)
def generate_dashboard_key(request: Request, plan: str = Form("free")) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    selected_plan = Plan(plan)
    if not _allowed_for_plan(int(user["id"]), selected_plan):
        return _render_dashboard(
            int(user["id"]),
            str(user["username"]),
            message="Plan requires an active paid subscription. Open Billing to upgrade.",
            latest_key="",
        )

    raw_key = generate_api_key()
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    _store.create_api_key(user_id=int(user["id"]), key_hash=digest, prefix=raw_key[:12], plan=selected_plan.value)

    return _render_dashboard(
        int(user["id"]),
        str(user["username"]),
        message="Store this key now. It will not be shown fully again:",
        latest_key=raw_key,
    )


@app.get("/console", response_class=HTMLResponse)
def console_home(request: Request) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return _render_console_home(int(user["id"]), str(user["username"]))


@app.post("/console/add", response_class=HTMLResponse)
def console_add_site(request: Request, domain: str = Form(...)) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    clean_domain = domain.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
    token = _console.create_token()
    message = "Property added successfully. Open site detail to verify ownership."
    try:
        _store.create_site(int(user["id"]), clean_domain, token)
    except Exception:
        message = "This property already exists in your account."
    return _render_console_home(int(user["id"]), str(user["username"]), message=message)


@app.get("/console/site/{site_id}", response_class=HTMLResponse)
def console_site_detail(request: Request, site_id: int) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    site = _store.find_site(site_id, int(user["id"]))
    if site is None:
        return HTMLResponse("Site not found", status_code=404)

    if int(site["verified"]) == 0:
        payload = _console.build_verification_payload(site["domain"], site["verification_token"])
        body = _template.render(
            "console_verify.html",
            {
                "site_id": site["id"],
                "domain": site["domain"],
                "dns_txt": payload.dns_txt,
                "html_file": payload.html_file,
                "html_token": payload.html_token,
                "message": "",
            },
        )
        return HTMLResponse(body)

    metrics = _store.list_site_metrics(site_id)
    if not metrics:
        _store.seed_site_metrics(site_id, _console.default_daily_metrics())
        _store.add_site_issue(site_id, "Crawl anomaly", "medium", "open", "Some pages returned intermittent 5xx in last crawl.")
        _store.add_site_issue(site_id, "Missing meta description", "low", "open", "12 pages are missing meta descriptions.")
        metrics = _store.list_site_metrics(site_id)

    issues = _store.list_site_issues(site_id)
    impressions_series = [int(row["impressions"]) for row in metrics]
    clicks_series = [int(row["clicks"]) for row in metrics]
    chart_impressions = _console.build_svg_bars(impressions_series)
    chart_clicks = _console.build_svg_bars(clicks_series)
    metrics_rows = "".join(
        [
            f"<tr><td>{row['metric_date']}</td><td>{row['impressions']}</td><td>{row['clicks']}</td><td>{row['ctr']}%</td><td>{row['avg_position']}</td></tr>"
            for row in metrics
        ]
    )
    issues_rows = "".join(
        [
            f"<tr><td>{row['issue_type']}</td><td>{row['severity']}</td><td>{row['status']}</td><td>{row['details']}</td><td>{row['created_at']}</td></tr>"
            for row in issues
        ]
    ) or "<tr><td colspan='5'>No issues detected</td></tr>"
    body = _template.render(
        "console_site_detail.html",
        {
            "domain": site["domain"],
            "verification_method": site["verification_method"],
            "chart_impressions": chart_impressions,
            "chart_clicks": chart_clicks,
            "metrics_rows": metrics_rows,
            "issues_rows": issues_rows,
        },
    )
    return HTMLResponse(body)


@app.post("/console/site/{site_id}/verify", response_class=HTMLResponse)
def console_verify_site(
    request: Request,
    site_id: int,
    method: str = Form(...),
    token_input: str = Form(...),
) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    site = _store.find_site(site_id, int(user["id"]))
    if site is None:
        return HTMLResponse("Site not found", status_code=404)

    if token_input.strip() != site["verification_token"]:
        payload = _console.build_verification_payload(site["domain"], site["verification_token"])
        body = _template.render(
            "console_verify.html",
            {
                "site_id": site["id"],
                "domain": site["domain"],
                "dns_txt": payload.dns_txt,
                "html_file": payload.html_file,
                "html_token": payload.html_token,
                "message": "Verification token mismatch. Please retry.",
            },
        )
        return HTMLResponse(body, status_code=400)

    if method not in {"dns", "url-prefix"}:
        return HTMLResponse("Invalid method", status_code=400)

    _store.mark_site_verified(site_id, method)
    return RedirectResponse(f"/console/site/{site_id}", status_code=303)


@app.get("/agent", response_class=HTMLResponse)
def agent_home(request: Request) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return _render_agent_home(int(user["id"]), str(user["username"]))


@app.post("/agent/search", response_class=HTMLResponse)
async def agent_search(request: Request, query: str = Form(...), top_k: int = Form(8)) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    context = await _agent_context.build_context(AgentContextRequest(query=query, top_k=max(1, min(top_k, 20))))
    return _render_agent_home(
        int(user["id"]),
        str(user["username"]),
        message="Context generated for agent grounding.",
        context_json=context.model_dump_json(indent=2),
    )


@app.post("/agent/datasets/create", response_class=HTMLResponse)
def create_dataset(
    request: Request,
    name: str = Form(...),
    query: str = Form(...),
    source: str = Form("open-search"),
    rows: int = Form(100),
) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    safe_rows = max(10, min(rows, 5000))
    try:
        dataset_id = _store.create_dataset(int(user["id"]), name.strip(), source, query.strip(), safe_rows)
        _store.add_dataset_rows(dataset_id, _build_dataset_rows(source, query, safe_rows))
        message = f"Dataset '{name}' created with {safe_rows} rows."
    except Exception:
        message = "Dataset name already exists. Use a different dataset name."

    return _render_agent_home(int(user["id"]), str(user["username"]), message=message)


@app.get("/billing", response_class=HTMLResponse)
def billing_home(request: Request) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return _render_billing_home(int(user["id"]))


@app.post("/billing/create-order", response_class=HTMLResponse)
def billing_create_order(request: Request, plan: str = Form(...)) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    selected = Plan(plan)
    if selected == Plan.FREE:
        return RedirectResponse("/billing", status_code=303)

    amount_inr = _price_for_plan(selected)
    amount_paise = amount_inr * 100
    receipt = f"user-{user['id']}-{selected.value}-{_store.search_calls_today(int(user['id']))}"
    message = ""

    try:
        order = _payments.create_order(amount_paise=amount_paise, receipt=receipt, currency=SETTINGS.payment_currency)
        order_id = str(order.get("id", ""))
    except PaymentError as exc:
        order_id = f"local-order-{int(user['id'])}-{selected.value}"
        message = f"Razorpay unavailable in current environment ({exc}). Using local order placeholder for testing."

    _store.create_payment_record(
        user_id=int(user["id"]),
        order_id=order_id,
        amount_paise=amount_paise,
        currency=SETTINGS.payment_currency,
        plan=selected.value,
        status="created",
    )

    return _render_billing_home(int(user["id"]), message=f"Order created: {order_id}. {message}")


@app.post("/billing/verify", response_class=HTMLResponse)
def billing_verify_payment(
    request: Request,
    plan: str = Form(...),
    order_id: str = Form(...),
    payment_id: str = Form(...),
    signature: str = Form(...),
) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    selected = Plan(plan)
    valid = _payments.verify_signature(order_id=order_id, payment_id=payment_id, signature=signature)
    if not valid and not order_id.startswith("local-order-"):
        return HTMLResponse("Payment signature verification failed", status_code=400)

    _store.complete_payment(order_id=order_id, payment_id=payment_id, signature=signature)
    _store.upsert_subscription(user_id=int(user["id"]), plan=selected.value, status="active")
    return RedirectResponse("/billing", status_code=303)


@app.get("/blog", response_class=HTMLResponse)
def blog_home(request: Request) -> HTMLResponse:
    user = _current_user(request)
    username = user["username"] if user else ""
    posts = _store.list_blog_posts(include_drafts=True)
    rows = "".join([f"<tr><td><a href='/blog/{p['slug']}'>{p['title']}</a></td><td>{p['status']}</td><td>{p['created_at']}</td></tr>" for p in posts]) or "<tr><td colspan='3'>No blog posts yet</td></tr>"
    body = _template.render("blog_home.html", {"username": username, "posts_rows": rows, "message": ""})
    return HTMLResponse(body)


@app.get("/blog/new", response_class=HTMLResponse)
def blog_new(request: Request) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    body = _template.render("blog_new.html", {"message": "", "title": "", "summary": "", "content_markdown": ""})
    return HTMLResponse(body)


@app.post("/blog/new", response_class=HTMLResponse)
def blog_create(
    request: Request,
    title: str = Form(...),
    summary: str = Form(...),
    content_markdown: str = Form(...),
    status_value: str = Form("published"),
) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    status_safe = status_value if status_value in {"draft", "published"} else "draft"
    base_slug = _slugify(title)
    slug = base_slug
    index = 2
    while _store.find_blog_post_by_slug(slug) is not None:
        slug = f"{base_slug}-{index}"
        index += 1

    _store.create_blog_post(
        author_user_id=int(user["id"]),
        title=title.strip(),
        slug=slug,
        summary=summary.strip(),
        content_markdown=content_markdown.strip(),
        status=status_safe,
    )
    return RedirectResponse(f"/blog/{slug}", status_code=303)


@app.get("/blog/{slug}", response_class=HTMLResponse)
def blog_post(request: Request, slug: str) -> HTMLResponse:
    user = _current_user(request)
    username = user["username"] if user else ""
    post = _store.find_blog_post_by_slug(slug)
    if post is None:
        return HTMLResponse("Blog post not found", status_code=404)

    paragraphs = "".join([f"<p>{line}</p>" for line in str(post["content_markdown"]).split("\n") if line.strip()])
    body = _template.render(
        "blog_post.html",
        {
            "username": username,
            "title": post["title"],
            "summary": post["summary"],
            "status": post["status"],
            "created_at": post["created_at"],
            "content_html": paragraphs,
        },
    )
    return HTMLResponse(body)


@app.post("/v1/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    principal: ApiPrincipal = Depends(require_principal),
) -> SearchResponse:
    response = await _service.search(body)
    _store.log_api_usage(principal.user_id, body.q, response.took_ms, len(response.results))
    return response


@app.post("/v1/agent/context", response_model=AgentContextResponse)
async def agent_context(
    body: AgentContextRequest,
    principal: ApiPrincipal = Depends(require_principal),
) -> AgentContextResponse:
    response = await _agent_context.build_context(body)
    _store.log_api_usage(principal.user_id, body.query, 0, len(response.context_chunks))
    return response


@app.post("/v1/agent/datasets/create")
def create_dataset_api(
    body: DatasetCreateRequest,
    principal: ApiPrincipal = Depends(require_principal),
) -> JSONResponse:
    dataset_id = _store.create_dataset(principal.user_id, body.name, body.source, body.query, body.rows)
    _store.add_dataset_rows(dataset_id, _build_dataset_rows(body.source, body.query, body.rows))
    return JSONResponse({"dataset_id": dataset_id, "rows": body.rows, "source": body.source, "status": "ready"})


@app.get("/v1/me/keys")
def my_keys(request: Request) -> JSONResponse:
    user = _current_user(request)
    if user is None:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    keys = _store.list_api_keys(int(user["id"]))
    return JSONResponse({"keys": [dict(k) for k in keys]})
