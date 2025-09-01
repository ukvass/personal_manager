from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from importlib import resources as ilres
from starlette.exceptions import HTTPException as StarletteHTTPException


def register_exception_handlers(app: FastAPI) -> None:
    """Attach error handlers that render JSON for API and HTML for web UI."""

    # Prepare templates for web error pages
    templates_dir = ilres.files("app").joinpath("templates")
    templates = Jinja2Templates(directory=str(templates_dir))

    def _is_api_request(request: Request) -> bool:
        path = request.url.path
        if path.startswith("/api/"):
            return True
        # If client explicitly asks for JSON
        accept = request.headers.get("accept", "")
        return "application/json" in accept

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if _is_api_request(request):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail if isinstance(exc.detail, str) else "HTTPError",
                    "status": exc.status_code,
                    "path": request.url.path,
                },
            )
        # Web UI: render friendly pages
        status_code = exc.status_code
        template_name = "error_404.html" if status_code == 404 else "error_500.html"
        ctx = {
            "request": request,
            "status": status_code,
            "detail": exc.detail if isinstance(exc.detail, str) else None,
        }
        return templates.TemplateResponse(template_name, ctx, status_code=status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Treat validation issues as API-oriented; web forms handle errors explicitly
        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "status": 422,
                "path": request.url.path,
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if _is_api_request(request):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "status": 500,
                    "path": request.url.path,
                },
            )
        ctx = {"request": request, "status": 500, "detail": None}
        return templates.TemplateResponse("error_500.html", ctx, status_code=500)
