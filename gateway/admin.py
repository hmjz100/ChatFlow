import json

from fastapi import Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse

import utils.globals as globals
from app import app, templates
from utils.log import log
from utils.configs import api_prefix

if api_prefix:
	@app.get(f"/{api_prefix}", response_class=HTMLResponse)
	async def admin_cookie(request: Request):
		response = HTMLResponse(content="Cookie added")
		response.set_cookie("prefix", value=api_prefix, expires="Thu, 01 Jan 2099 00:00:00 GMT")
		return RedirectResponse(url='/admin', headers=response.headers)

@app.get("/admin", response_class=HTMLResponse)
async def admin_html(request: Request):
	prefix = request.cookies.get("prefix")
	if api_prefix and api_prefix != prefix:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

	tokens_count = len(set(globals.token_list) - set(globals.error_token_list))
	return templates.TemplateResponse("admin.html", {"request": request, "api_prefix": api_prefix, "tokens_count": tokens_count})

@app.get("/admin/tokens/error")
async def admin_tokens_error(request: Request):
	prefix = request.cookies.get("prefix")
	if api_prefix and api_prefix != prefix:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})
	
	return templates.TemplateResponse("callback.html", {
		"request": request,
		"title": "Error Tokens",
		"zh_title": "错误令牌",
		"message": "<br/>".join(list(set(globals.error_token_list))) or "/",
		"url": "/admin"
	})

@app.post("/admin/tokens/upload")
async def tokens_upload(request: Request, text: str = Form(None)):
	prefix = request.cookies.get("prefix")
	if api_prefix and api_prefix != prefix:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

	if not text:
		return templates.TemplateResponse("callback.html", {
			"request": request,
			"title": "Error",
			"zh_title": "错误",
			"message": "You entered a null value",
			"zh_message": "您输入的是空值",
			"url": "/admin"
		})

	lines = text.split("\n")
	for line in lines:
		if line.strip() and not line.startswith("#"):
			globals.token_list.append(line.strip())
			with open(globals.TOKENS_FILE, "a", encoding="utf-8") as f:
				f.write(line.strip() + "\n")
	
	log.info(f"Token count: {len(globals.token_list)}, Error token count: {len(globals.error_token_list)}")
	
	return templates.TemplateResponse("callback.html", {
		"request": request,
		"title": "Success",
		"zh_title": "成功",
		"message": "Token uploaded successfully",
		"zh_message": "令牌上传成功",
		"url": "/admin"
	})

@app.post("/admin/tokens/clear")
async def tokens_clear(request: Request):
	prefix = request.cookies.get("prefix")
	if api_prefix and api_prefix != prefix:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

	globals.token_list.clear()
	globals.error_token_list.clear()
	with open(globals.TOKENS_FILE, "w", encoding="utf-8") as f:
		pass
	with open(globals.ERROR_TOKENS_FILE, "w", encoding="utf-8") as f:
		pass
	log.info(f"Token count: {len(globals.token_list)}, Error token count: {len(globals.error_token_list)}")
	
	return templates.TemplateResponse("callback.html", {
		"request": request,
		"title": "Success",
		"zh_title": "成功",
		"message": "Token cleared successfully",
		"zh_message": "清空令牌成功",
		"url": "/admin"
	})

@app.post("/admin/tokens/seed_clear")
async def clear_seed_tokens(request: Request):
	prefix = request.cookies.get("prefix")
	if api_prefix and api_prefix != prefix:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

	globals.seed_map.clear()
	globals.conversation_map.clear()
	with open(globals.SEED_MAP_FILE, "w", encoding="utf-8") as f:
		f.write("{}")
	with open(globals.CONVERSATION_MAP_FILE, "w", encoding="utf-8") as f:
		f.write("{}")
	log.info(f"Seed token count: {len(globals.seed_map)}")
	
	return templates.TemplateResponse("callback.html", {
		"request": request,
		"title": "Success",
		"zh_title": "成功",
		"message": "Seed token cleared successfully.",
		"zh_message": "种子令牌清除成功",
		"url": "/admin"
	})