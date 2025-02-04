import hashlib
import os
import json
from urllib.parse import quote

from fastapi import Request, Path
from fastapi.responses import Response, HTMLResponse, RedirectResponse

from app import app, templates

@app.get("/auth/login", response_class=HTMLResponse)
async def login_html(request: Request):
	token = request.cookies.get("oai-flow-token")
	if token:
		return RedirectResponse(url='/')

	response = templates.TemplateResponse("signin.html", {"request": request})
	return response

@app.get("/auth/logout", response_class=HTMLResponse)
async def logout_html(request: Request):
	token = request.cookies.get("oai-flow-token")
	if not token:
		return RedirectResponse(url='/')

	response = templates.TemplateResponse("signout.html", {"request": request})
	return response

@app.get("/api/auth/signin", response_class=HTMLResponse)
async def signin_html(request: Request):
	signin = request.query_params.get("signin")
	token = request.cookies.get("oai-flow-token")
	if not signin:
		return RedirectResponse(url='/auth/login')

	if token:
		return RedirectResponse(url='/')

	if len(signin) != 45 and not signin.startswith("eyJhbGciOi"):
		signin = quote(signin)

	response = HTMLResponse(content="Cookie added")
	response.set_cookie("oai-flow-token", value=signin, expires="Thu, 01 Jan 2099 00:00:00 GMT")
	return RedirectResponse(url='/', headers=response.headers)

@app.get("/api/auth/signout", response_class=HTMLResponse)
async def signout_html(request: Request):
	signout = request.query_params.get("signout")

	if not signout or signout != 'true':
		return RedirectResponse(url='/auth/logout')

	token = request.cookies.get("oai-flow-token")

	if not token:
		return RedirectResponse(url='/auth/login')

	if len(token) != 45 and not token.startswith("eyJhbGciOi"):
		token = quote(token)

	response = HTMLResponse(content="Cookie deleted")
	response.delete_cookie("oai-flow-token")
	return RedirectResponse(url='/', headers=response.headers)

@app.get("/auth/login/{path:path}", response_class=Response)
@app.get("/api/auth/signin/{path:path}", response_class=Response)
@app.get("/api/auth/callback/{path:path}", response_class=Response)
async def auth_3rd(request: Request, path: str):
	return RedirectResponse(url='/auth/login')

@app.get("/api/auth/csrf", response_class=Response)
async def auth_csrf(request: Request):
	csrf = {'csrfToken': hashlib.sha256(os.urandom(32)).hexdigest()}
	return Response(content=json.dumps(csrf, indent=4), status_code=200, media_type="application/json")

@app.post("/api/auth/sign{path}", response_class=Response)
async def auth_sign(request: Request, path: str = Path(..., regex="in|out")):
	sign = {'url':f'/auth/log{path}'}
	return Response(content=json.dumps(sign, indent=4), status_code=200, media_type="application/json")

@app.post("/api/auth/providers", response_class=Response)
async def auth_providers(request: Request):
	providers = {"auth0":{"id":"auth0","name":"Auth0","type":"oauth","signinUrl":"/api/auth/signin/auth0","callbackUrl":"/api/auth/callback/auth0"},"login-web":{"id":"login-web","name":"Auth0","type":"oauth","signinUrl":"/api/auth/signin/login-web","callbackUrl":"/api/auth/callback/login-web"},"openai":{"id":"openai","name":"openai","type":"oauth","signinUrl":"/api/auth/signin/openai","callbackUrl":"/api/auth/callback/openai"},"openai-sidetron":{"id":"openai-sidetron","name":"openai-sidetron","type":"oauth","signinUrl":"/api/auth/signin/openai-sidetron","callbackUrl":"/api/auth/callback/openai-sidetron"},"auth0-sidetron":{"id":"auth0-sidetron","name":"Auth0","type":"oauth","signinUrl":"/api/auth/signin/auth0-sidetron","callbackUrl":"/api/auth/callback/auth0-sidetron"}}
	return Response(content=json.dumps(providers, indent=4), status_code=200, media_type="application/json")