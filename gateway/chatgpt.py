import json
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from gateway.reverseProxy import web_reverse_proxy

from app import app, templates
from utils.kv_utils import set_value_for_key
import utils.configs as configs

with open("templates/chatgpt_context.json", "r", encoding="utf-8") as f:
	chatgpt_context = json.load(f)

@app.get("/", response_class=HTMLResponse)
@app.get("/tasks")
@app.get("/ccc/{path}")
async def chatgpt_html(request: Request):
	token = request.cookies.get("oai-flow-token")
	if not token:
		if configs.enable_homepage:
			response = await web_reverse_proxy(request, "/")
		else:
			response = templates.TemplateResponse("home.html", {"request": request})
		return response

	if len(token) != 45 and not token.startswith("eyJhbGciOi"):
		token = quote(token)

	user_remix_context = chatgpt_context.copy()
	set_value_for_key(user_remix_context, "user", {"id": "user-chatgpt"})
	set_value_for_key(user_remix_context, "accessToken", token)

	response = templates.TemplateResponse("base.html", {"request": request, "remix_context": user_remix_context})
	return response

app.mount("/static", StaticFiles(directory="templates/static"), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")