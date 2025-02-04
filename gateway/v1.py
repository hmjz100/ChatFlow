import json
import time
import uuid

from fastapi import Request
from fastapi.responses import Response

from app import app
from gateway.reverseProxy import web_reverse_proxy
from utils.kv_utils import set_value_for_key

@app.post("/v1/initialize")
async def initialize(request: Request):
	res = await web_reverse_proxy(request, f"v1/initialize?k=client-tnE5GCU2F2cTxRiMbvTczMDT1jpwIigZHsZSdqiy4u&st=javascript-client-react&sv=3.9.0&t={int(time.time() * 1000)}&sid={uuid.uuid4()}&se=1")

	if res and res.status_code == 200 and json.loads(res.body.decode()):
		initialize = json.loads(res.body.decode())
		set_value_for_key(initialize, "ip", "8.8.8.8")
		set_value_for_key(initialize, "country", "US")
		return Response(content=json.dumps(initialize, indent=4), media_type="application/json")
	else:
		return res

@app.post("/v1/rgstr")
async def rgstr():
	return Response(status_code=202, content=json.dumps({"success": True, "fake": True}, indent=4), media_type="application/json")

@app.get("/ces/v1/projects/oai/settings")
async def oai_settings():
	return Response(status_code=200, content=json.dumps({"integrations":{"Segment.io":{"apiHost":"chatgpt.com/ces/v1","apiKey":"oai"}}, "fake": True}, indent=4), media_type="application/json")

@app.post("/ces/{path:path}")
async def ces_v1():
	return Response(status_code=202, content=json.dumps({"success": True, "fake": True}, indent=4), media_type="application/json")
