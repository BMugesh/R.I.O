"""Isolated FastAPI application for the R.I.O. public research demonstration."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from engine import (
    SIMULATION_NOTICE,
    create_demo_session,
    get_allowed_actions_info,
    get_demo_session,
    submit_session_decision,
    submit_session_interrupt,
)
from planner import DEMO_SCENARIOS, SANDBOX_DOCUMENTS
from schemas import (
    CreateSessionRequest,
    DecisionRequest,
    DemoSessionResponse,
    InterruptRequest,
    ScenariosResponse,
)
from security import (
    get_allowed_origins,
    get_app_env,
    get_client_ip,
    get_max_body_bytes,
    get_rate_limits,
    rate_limiter,
)


def create_app() -> FastAPI:
    is_prod = get_app_env() == "production"
    app = FastAPI(
        title="R.I.O. Public Research Demo API",
        version="0.2.0",
        description=(
            "Deliberately restricted, sandboxed demonstration API for R.I.O. "
            "(Reasoning Intelligence Orchestration). Does not expose local runtime capabilities."
        ),
        docs_url=None if is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if is_prod else "/openapi.json",
    )

    @app.middleware("http")
    async def enforce_body_limit_and_error_boundary(request: Request, call_next):
        max_bytes = get_max_body_bytes()
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_len = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header."},
                )
            if declared_len < 0:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid Content-Length header."},
                )
            if declared_len > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body exceeds maximum allowed size ({max_bytes} bytes)."
                    },
                )

        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if len(body) > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body exceeds maximum allowed size ({max_bytes} bytes)."
                    },
                )

        try:
            return await call_next(request)
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal sandbox error. No session state or secrets were exposed."
                },
            )

    allowed_origins = get_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/demo/sessions"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {
            "status": "healthy",
            "service": "rio-public-demo-api",
            "mode": "isolated_sandbox",
        }

    @app.get("/api/demo/scenarios", response_model=ScenariosResponse, tags=["demo"])
    async def list_scenarios(request: Request) -> ScenariosResponse:
        limits = get_rate_limits()
        ip = get_client_ip(request)
        rate_limiter.check(f"req:{ip}", limits["requests_per_min"], window_seconds=60)
        return ScenariosResponse(
            scenarios=DEMO_SCENARIOS,
            sandbox_documents=SANDBOX_DOCUMENTS,
            allowed_actions=get_allowed_actions_info(),
            simulation_notice=SIMULATION_NOTICE,
        )

    @app.post(
        "/api/demo/sessions",
        response_model=DemoSessionResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    async def create_session_endpoint(
        payload: CreateSessionRequest,
        request: Request,
    ) -> DemoSessionResponse:
        limits = get_rate_limits()
        ip = get_client_ip(request)
        rate_limiter.check(f"req:{ip}", limits["requests_per_min"], window_seconds=60)
        rate_limiter.check(f"create:{ip}", limits["create_per_min"], window_seconds=60)
        return await create_demo_session(task=payload.task, scenario_id=payload.scenario_id)

    @app.get(
        "/api/demo/sessions/{session_id}",
        response_model=DemoSessionResponse,
        tags=["demo"],
    )
    async def get_session_endpoint(session_id: str, request: Request) -> DemoSessionResponse:
        limits = get_rate_limits()
        ip = get_client_ip(request)
        rate_limiter.check(f"req:{ip}", limits["requests_per_min"], window_seconds=60)
        return await get_demo_session(session_id)

    @app.post(
        "/api/demo/sessions/{session_id}/decision",
        response_model=DemoSessionResponse,
        tags=["demo"],
    )
    async def submit_decision_endpoint(
        session_id: str,
        payload: DecisionRequest,
        request: Request,
    ) -> DemoSessionResponse:
        limits = get_rate_limits()
        ip = get_client_ip(request)
        rate_limiter.check(f"req:{ip}", limits["requests_per_min"], window_seconds=60)
        rate_limiter.check(f"mutate_ip:{ip}", limits["ip_mutations_per_min"], window_seconds=60)
        rate_limiter.check(
            f"mutate:{session_id}",
            limits["session_mutations_per_min"],
            window_seconds=60,
        )
        return await submit_session_decision(session_id=session_id, payload=payload)

    @app.post(
        "/api/demo/sessions/{session_id}/interrupt",
        response_model=DemoSessionResponse,
        tags=["demo"],
    )
    async def submit_interrupt_endpoint(
        session_id: str,
        payload: InterruptRequest,
        request: Request,
    ) -> DemoSessionResponse:
        limits = get_rate_limits()
        ip = get_client_ip(request)
        rate_limiter.check(f"req:{ip}", limits["requests_per_min"], window_seconds=60)
        rate_limiter.check(f"mutate_ip:{ip}", limits["ip_mutations_per_min"], window_seconds=60)
        rate_limiter.check(
            f"mutate:{session_id}",
            limits["session_mutations_per_min"],
            window_seconds=60,
        )
        return await submit_session_interrupt(session_id=session_id, payload=payload)

    return app


app = create_app()
