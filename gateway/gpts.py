import json

from fastapi import Request
from fastapi.responses import Response

from app import app
from gateway.chatgpt import chatgpt_html

with open("templates/gpts_context.json", "r", encoding="utf-8") as f:
	gpts_context = json.load(f)

@app.get("/gpts")
async def get_gpts(request: Request):
	#return {"kind": "store"}
	return await chatgpt_html(request)

@app.get("/gpts/{page}")
async def dynamic_child_page(page: str, request: Request):
	return await chatgpt_html(request)

@app.get("/g/g-{gizmo_id}")
async def get_gizmo_json(request: Request, gizmo_id: str):
	params = request.query_params
	if params.get("_data") == "routes/g.$gizmoId._index":
		return Response(content=json.dumps(gpts_context, indent=4), media_type="application/json")
	else:
		return await chatgpt_html(request)
