import asyncio
import types
import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Request, HTTPException, Form, Security
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from starlette.background import BackgroundTask

from gateway.reverseProxy import get_real_req_token

import utils.globals as globals
from app import app, templates, security_scheme
from gateway.reverseProxy import web_reverse_proxy
from chatgpt.ChatService import ChatService
from chatgpt.authorization import refresh_all_tokens
from utils.log import log
from utils.configs import api_prefix, scheduled_refresh
from utils.retry import async_retry

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def app_start():
	if scheduled_refresh:
		scheduler.add_job(id='refresh', func=refresh_all_tokens, trigger='cron', hour=3, minute=0, day='*/2',  kwargs={'force_refresh': True})
		scheduler.start()
		asyncio.get_event_loop().call_later(0, lambda: asyncio.create_task(refresh_all_tokens(force_refresh=False)))

async def to_send_conversation(request_data, req_token):
	chat_service = ChatService(req_token)
	try:
		await chat_service.set_dynamic_data(request_data)
		await chat_service.get_chat_requirements()
		return chat_service
	except HTTPException as e:
		await chat_service.close_client()
		raise HTTPException(status_code=e.status_code, detail=e.detail)
	except Exception as e:
		await chat_service.close_client()
		log.error(f"Server error, {str(e)}")
		raise HTTPException(status_code=500, detail="Server error")

async def process(request_data, req_token):
	chat_service = await to_send_conversation(request_data, req_token)
	await chat_service.prepare_send_conversation()
	res = await chat_service.send_conversation()
	return chat_service, res

@app.post(f"/{api_prefix}/v1/chat/completions" if api_prefix else "/v1/chat/completions")
async def send_conversation(request: Request, credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
	req_token = credentials.credentials

	try:
		request_data = await request.json()
	except Exception:
		raise HTTPException(status_code=400, detail={"error": "Invalid JSON body"})
	chat_service, res = await async_retry(process, request_data, req_token)
	try:
		if isinstance(res, types.AsyncGeneratorType):
			background = BackgroundTask(chat_service.close_client)
			return StreamingResponse(res, media_type="text/event-stream", background=background)
		else:
			background = BackgroundTask(chat_service.close_client)
			return JSONResponse(res, media_type="application/json", background=background)
	except HTTPException as e:
		await chat_service.close_client()
		if e.status_code == 500:
			log.error(f"Server error, {str(e)}")
			raise HTTPException(status_code=500, detail="Server error")
		raise HTTPException(status_code=e.status_code, detail=e.detail)
	except Exception as e:
		await chat_service.close_client()
		log.error(f"Server error, {str(e)}")
		raise HTTPException(status_code=500, detail="Server error")
	
@app.get(f"/{api_prefix}/v1/models" if api_prefix else "/v1/models")
async def get_models(request: Request, credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
	if not credentials.credentials:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

	res = await web_reverse_proxy(request, f"/backend-api/models")

	if res and res.status_code == 200 and json.loads(res.body.decode()):
		data = json.loads(res.body.decode())
		exclude_models = {"auto", "gpt-4o-canmore"}
		filtered_models = [
			{
				"id": category["default_model"],
				"object": "model",
				"owned_by": "FlowGPT"
			}
			for category in data.get("categories", [])
			if category.get("default_model") not in exclude_models
		]
		models = {
			"data": filtered_models
		}
		return Response(content=json.dumps(models, indent=4), media_type="application/json")
	else:
		return res