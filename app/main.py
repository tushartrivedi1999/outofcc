from __future__ import annotations

import hashlib

from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.auth import ApiPrincipal, KeyStore
from app.cache import TTLCache
from app.clients.searx_client import SearxClient
from app.config import SETTINGS
from app.domain import Plan
from app.models import SearchRequest, SearchResponse
from app.rate_limit import SlidingWindowRateLimiter
from app.security import generate_api_key, verify_password
from app.service import SearchService
from app.session import SessionManager
from app.template_engine import TemplateEngine
from app.user_store import UserStore

app = FastAPI(title="Open Search API", version="0.2.0")

_store = UserStore(SETTINGS.db_path)
_store.ensure_admin_user()
_template = TemplateEngine("templates")
_session = SessionManager(secret=SETTINGS.session_secret)
_keystore = KeyStore(_store)
_rate_limiter = SlidingWindowRateLimiter()
_service = SearchService(
    searx_client=SearxClient(base_url=SETTINGS.searx_base_url, timeout_s=SETTINGS.request_timeout_s),
    cache=TTLCache(),
)


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
    keys = _store.list_api_keys(int(user["id"]))
    keys_html = "".join([f"<li>{k['prefix']}... ({k['plan']}) - {k['created_at']}</li>" for k in keys]) or "<li>No API keys yet</li>"
    body = _template.render(
        "dashboard.html",
        {
            "username": user["username"],
            "keys_html": keys_html,
            "message": "",
            "latest_key": "",
        },
    )
    return HTMLResponse(body)


@app.post("/dashboard/generate", response_class=HTMLResponse)
def generate_dashboard_key(request: Request, plan: str = Form("free")) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)

    selected_plan = Plan(plan)
    raw_key = generate_api_key()
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    _store.create_api_key(user_id=int(user["id"]), key_hash=digest, prefix=raw_key[:12], plan=selected_plan.value)

    keys = _store.list_api_keys(int(user["id"]))
    keys_html = "".join([f"<li>{k['prefix']}... ({k['plan']}) - {k['created_at']}</li>" for k in keys])
    body = _template.render(
        "dashboard.html",
        {
            "username": user["username"],
            "keys_html": keys_html,
            "message": "Store this key now. It will not be shown fully again:",
            "latest_key": raw_key,
        },
    )
    return HTMLResponse(body)


@app.post("/v1/search", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    _principal: ApiPrincipal = Depends(require_principal),
) -> SearchResponse:
    return await _service.search(body)


@app.get("/v1/me/keys")
def my_keys(request: Request) -> JSONResponse:
    user = _current_user(request)
    if user is None:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    keys = _store.list_api_keys(int(user["id"]))
    return JSONResponse({"keys": [dict(k) for k in keys]})
