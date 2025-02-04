import warnings

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from utils.configs import port, enable_gateway, api_prefix
from utils.log import default_format, access_format

warnings.filterwarnings("ignore")

log_config = uvicorn.config.LOGGING_CONFIG
log_config["formatters"]["default"]["fmt"] = default_format
log_config["formatters"]["access"]["fmt"] = access_format

app = FastAPI(
	docs_url=f"/{api_prefix}/docs",    # 设置 Swagger UI 文档路径
	redoc_url=f"/{api_prefix}/redoc",  # 设置 Redoc 文档路径
	openapi_url=f"/{api_prefix}/openapi.json"  # 设置 OpenAPI JSON 路径
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
security_scheme = HTTPBearer()

from app import app

import api.chat2api

if enable_gateway:
	import gateway.share
	import gateway.auth
	import gateway.chatgpt
	import gateway.gpts
	import gateway.admin
	import gateway.v1
	import gateway.backend
else:
	@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"])
	async def reverse_proxy():
		raise HTTPException(status_code=404, detail="Gateway is disabled")

if __name__ == "__main__":
	uvicorn.run("app:app", host="0.0.0.0", port=port)
	# uvicorn.run("app:app", host="0.0.0.0", port=5005, ssl_keyfile="key.pem", ssl_certfile="cert.pem")