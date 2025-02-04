import json
import random
import re
import time
import uuid
import hashlib

from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, Response
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

import utils.globals as globals
from app import app
from chatgpt.authorization import verify_token
from chatgpt.fp import get_fp
from chatgpt.proofofWork import get_answer_token, get_config, get_requirements_token
from gateway.chatgpt import chatgpt_html
from gateway.reverseProxy import web_reverse_proxy, content_generator, get_real_req_token, headers_reject_list, \
    headers_accept_list
from utils.Client import Client
from utils.log import log
from utils.configs import x_sign, turnstile_solver_url, chatgpt_base_url_list, no_sentinel, sentinel_proxy_url_list, \
	force_no_history

banned_paths = [
	"backend-api/accounts/logout_all", # 全部退出
	"backend-api/accounts/deactivate", # 删除账户
	"backend-api/accounts/data_export", # 数据导出
	"backend-api/payments", # 支付相关
	"backend-api/subscriptions", # 更改套餐
	"backend-api/user_system_messages", # 自定义提示
	"backend-api/memories", # 记忆
	"backend-api/settings/account_user_setting", # 修改设置
	"backend-api/settings/clear_account_user_memory", # 清除记忆
	"backend-api/shared_conversations", # 共享链接
	"backend-api/connectors", # 关联的应用
	"backend-api/gizmos", # 项目/GPTs
	"backend-api/gizmo_creator_profile", # 创建者个人资料
	"backend-api/conversations/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", # 对话
	"backend-api/accounts/mfa_info", # 二次验证
	"backend-api/accounts/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/invites", # 邀请账户
	"public-api/gizmos/discovery/mine", # 我的 GPTs
	# "admin", # 经典常谈
]
redirect_paths = []
chatgpt_paths = [
	"c/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
]

@app.get("/backend-api/accounts/check/v4-2023-04-27")
async def check_account(request: Request):
	token = request.headers.get("Authorization").replace("Bearer ", "")
	check_account_response = await web_reverse_proxy(request, "backend-api/accounts/check/v4-2023-04-27")
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return check_account_response
	else:
		check_account_str = check_account_response.body.decode('utf-8')
		check_account_info = json.loads(check_account_str)
		for key in check_account_info.get("accounts", {}).keys():
			account_id = check_account_info["accounts"][key]["account"]["account_id"]
			globals.seed_map[token]["user_id"] = \
				check_account_info["accounts"][key]["account"]["account_user_id"].split("__")[0]
			check_account_info["accounts"][key]["account"]["account_user_id"] = f"user-chatgpt__{account_id}"
		with open(globals.SEED_MAP_FILE, "w", encoding="utf-8") as f:
			json.dump(globals.seed_map, f, indent=4)
		return check_account_info

@app.get("/backend-api/gizmos/bootstrap")
async def get_gizmos_bootstrap(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/gizmos/bootstrap")
	else:
		return {"gizmos": []}

@app.get("/backend-api/gizmos/pinned")
async def get_gizmos_pinned(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/gizmos/pinned")
	else:
		return {"items": [], "cursor": None}

@app.get("/public-api/gizmos/discovery/recent")
async def get_gizmos_discovery_recent(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "public-api/gizmos/discovery/recent")
	else:
		return {
			"info": {
				"id": "recent",
				"title": "Recently Used",
			},
			"list": {
				"items": [],
				"cursor": None
			}
		}

@app.get("/backend-api/gizmos/snorlax/sidebar")
async def get_gizmos_snorlax_sidebar(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/gizmos/snorlax/sidebar")
	else:
		return {"items": [], "cursor": None}

@app.post("/backend-api/gizmos/snorlax/upsert")
async def get_gizmos_snorlax_upsert(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/gizmos/snorlax/upsert")
	else:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

@app.api_route("/backend-api/conversations", methods=["GET", "PATCH"])
async def get_conversations(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/conversations")
	if request.method == "GET":
		limit = int(request.query_params.get("limit", 28))
		offset = int(request.query_params.get("offset", 0))
		is_archived = request.query_params.get("is_archived", None)
		items = []
		for conversation_id in globals.seed_map.get(token, {}).get("conversations", []):
			conversation = globals.conversation_map.get(conversation_id, None)
			if conversation:
				if is_archived == "true":
					if conversation.get("is_archived", False):
						items.append(conversation)
				else:
					if not conversation.get("is_archived", False):
						items.append(conversation)
		items = items[int(offset):int(offset) + int(limit)]
		conversations = {
			"items": items,
			"total": len(items),
			"limit": limit,
			"offset": offset,
			"has_missing_conversations": False
		}
		return Response(content=json.dumps(conversations, indent=4), media_type="application/json")
	else:
		raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

@app.get("/backend-api/conversation/{conversation_id}")
async def update_conversation(request: Request, conversation_id: str):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "")
	conversation_details_response = await web_reverse_proxy(request, f"backend-api/conversation/{conversation_id}")
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return conversation_details_response
	else:
		conversation_details_str = conversation_details_response.body.decode('utf-8')
		conversation_details = json.loads(conversation_details_str)
		if conversation_id in globals.seed_map[token][
			"conversations"] and conversation_id in globals.conversation_map:
			globals.conversation_map[conversation_id]["title"] = conversation_details.get("title", None)
			globals.conversation_map[conversation_id]["is_archived"] = conversation_details.get("is_archived", False)
			globals.conversation_map[conversation_id]["conversation_template_id"] = conversation_details.get("conversation_template_id", None)
			globals.conversation_map[conversation_id]["gizmo_id"] = conversation_details.get("gizmo_id", None)
			globals.conversation_map[conversation_id]["async_status"] = conversation_details.get("async_status", None)
			with open(globals.CONVERSATION_MAP_FILE, "w", encoding="utf-8") as f:
				json.dump(globals.conversation_map, f, indent=4)
		return conversation_details_response

@app.patch("/backend-api/conversation/{conversation_id}")
async def patch_conversation(request: Request, conversation_id: str):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	patch_response = (await web_reverse_proxy(request, f"backend-api/conversation/{conversation_id}"))
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return patch_response
	else:
		data = await request.json()
		if conversation_id in globals.seed_map[token]["conversations"] and conversation_id in globals.conversation_map:
			if not data.get("is_visible", True):
				globals.conversation_map.pop(conversation_id)
				globals.seed_map[token]["conversations"].remove(conversation_id)
				with open(globals.SEED_MAP_FILE, "w", encoding="utf-8") as f:
					json.dump(globals.seed_map, f, indent=4)
			else:
				globals.conversation_map[conversation_id].update(data)
			with open(globals.CONVERSATION_MAP_FILE, "w", encoding="utf-8") as f:
				json.dump(globals.conversation_map, f, indent=4)
		return patch_response

@app.get("/backend-api/me")
async def get_me(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/me")
	else:
		me = {
			"object": "user",
			"id": f"org-{token}",
			"email": f"{token}@openai.com",
			"name": f"{token.title()}",
			"picture": f"/avatar/{hashlib.md5(token.encode()).hexdigest()}?s=480&r=pg&d=https%3A%2F%2Fcdn.auth0.com%2Favatars%2F{token[:2].lower()}.png",
			"created": int(time.time()),
			"phone_number": None,
			"mfa_flag_enabled": False,
			"amr": [],
			"groups": [],
			"orgs": {
				"object": "list",
				"data": [
					{
						"object": "organization",
						"id": "org-chatgpt",
						"created": 1715641300,
						"title": "Personal",
						"name": f"user-{token}",
						"description": f"Personal org for {token}@openai.com",
						"personal": True,
						"settings": {
							"threads_ui_visibility": "NONE",
							"usage_dashboard_visibility": "ANY_ROLE",
							"disable_user_api_keys": False
						},
						"parent_org_id": None,
						"is_default": True,
						"role": "owner",
						"is_scale_tier_authorized_purchaser": None,
						"is_scim_managed": False,
						"projects": {
							"object": "list",
							"data": []
						},
						"groups": [],
						"geography": None
					}
				]
			},
			"has_payg_project_spend_limit": True
		}
	return Response(content=json.dumps(me, indent=4), media_type="application/json")

@app.get("/backend-api/user_system_messages")
async def get_user_system_messages(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/user_system_messages")
	else:
		user_system_messages = {
			"object": "user_system_message_detail",
			"enabled": False,
			"about_user_message": "",
			"about_model_message": "",
			"name_user_message": "",
			"role_user_message": "",
			"traits_model_message": "",
			"other_user_message": "",
			"disabled_tools": []
		}
		return Response(content=json.dumps(user_system_messages, indent=4), media_type="application/json")

@app.get("/backend-api/memories")
async def get_memories(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/memories")
	else:
		memories = {
			"memories": [],
			"memory_max_tokens": 2000,
			"memory_num_tokens": 0
		}
		return Response(content=json.dumps(memories, indent=4), media_type="application/json")

@app.get("/backend-api/shared_conversations")
async def get_shared_conversations(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/shared_conversations")
	else:
		shared_conversations = {
			"items": [],
			"total": 0,
			"limit": 50,
			"offset": 0,
			"has_missing_conversations": False
		}
		return Response(content=json.dumps(shared_conversations, indent=4), media_type="application/json")

@app.get("/backend-api/gizmos/snorlax/sidebar")
async def get_snorlax_sidebar(request: Request):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) == 45 or token.startswith("eyJhbGciOi"):
		return await web_reverse_proxy(request, "backend-api/gizmos/snorlax/sidebar")
	else:
		snorlax_sidebar = {
			"items": [],
			"cursor": None
		}
		return Response(content=json.dumps(snorlax_sidebar, indent=4), media_type="application/json")

@app.get("/backend-api/model_icons")
async def get_me(request: Request):
	iconModels = {
		"bolt": {
			"icon_filled_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M12.566 2.11c1.003-1.188 2.93-.252 2.615 1.271L14.227 8h5.697c1.276 0 1.97 1.492 1.146 2.467L11.434 21.89c-1.003 1.19-2.93.253-2.615-1.27L9.772 16H4.076c-1.276 0-1.97-1.492-1.147-2.467L12.565 2.11Z\" clip-rule=\"evenodd\"/></svg>",
			"icon_outline_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M13.091 4.246 4.682 14H11a1 1 0 0 1 .973 1.23l-1.064 4.524L19.318 10H13a1 1 0 0 1-.973-1.229l1.064-4.525Zm-.848-2.08c1.195-1.386 3.448-.238 3.029 1.544L14.262 8h5.056c1.711 0 2.632 2.01 1.514 3.306l-9.075 10.528c-1.195 1.386-3.448.238-3.029-1.544L9.738 16H4.681c-1.711 0-2.632-2.01-1.514-3.306l9.075-10.527Z\"/></svg>",
		},
		"connected": {
			"icon_outline_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M12 7.42a22.323 22.323 0 0 0-2.453 2.127A22.323 22.323 0 0 0 7.42 12a22.32 22.32 0 0 0 2.127 2.453c.807.808 1.636 1.52 2.453 2.128a22.335 22.335 0 0 0 2.453-2.128A22.322 22.322 0 0 0 16.58 12a22.326 22.326 0 0 0-2.127-2.453A22.32 22.32 0 0 0 12 7.42Zm1.751-1.154a24.715 24.715 0 0 1 2.104 1.88 24.722 24.722 0 0 1 1.88 2.103c.316-.55.576-1.085.779-1.59.35-.878.507-1.625.503-2.206-.003-.574-.16-.913-.358-1.111-.199-.199-.537-.356-1.112-.36-.58-.003-1.328.153-2.205.504-.506.203-1.04.464-1.59.78Zm3.983 7.485a24.706 24.706 0 0 1-1.88 2.104 24.727 24.727 0 0 1-2.103 1.88 12.7 12.7 0 0 0 1.59.779c.878.35 1.625.507 2.206.503.574-.003.913-.16 1.111-.358.199-.199.356-.538.36-1.112.003-.58-.154-1.328-.504-2.205a12.688 12.688 0 0 0-.78-1.59ZM12 18.99c.89.57 1.768 1.03 2.605 1.364 1.026.41 2.036.652 2.955.646.925-.006 1.828-.267 2.5-.94.673-.672.934-1.575.94-2.5.006-.919-.236-1.929-.646-2.954A15.688 15.688 0 0 0 18.99 12c.57-.89 1.03-1.768 1.364-2.606.41-1.025.652-2.035.646-2.954-.006-.925-.267-1.828-.94-2.5-.672-.673-1.575-.934-2.5-.94-.919-.006-1.929.235-2.954.646-.838.335-1.716.795-2.606 1.364a15.69 15.69 0 0 0-2.606-1.364C8.37 3.236 7.36 2.994 6.44 3c-.925.006-1.828.267-2.5.94-.673.672-.934 1.575-.94 2.5-.006.919.235 1.929.646 2.955A15.69 15.69 0 0 0 5.01 12c-.57.89-1.03 1.768-1.364 2.605-.41 1.026-.652 2.036-.646 2.955.006.925.267 1.828.94 2.5.672.673 1.575.934 2.5.94.92.006 1.93-.235 2.955-.646A15.697 15.697 0 0 0 12 18.99Zm-1.751-1.255a24.714 24.714 0 0 1-2.104-1.88 24.713 24.713 0 0 1-1.88-2.104c-.315.55-.576 1.085-.779 1.59-.35.878-.507 1.625-.503 2.206.003.574.16.913.359 1.111.198.199.537.356 1.111.36.58.003 1.328-.153 2.205-.504.506-.203 1.04-.463 1.59-.78Zm-3.983-7.486a24.727 24.727 0 0 1 1.88-2.104 24.724 24.724 0 0 1 2.103-1.88 12.696 12.696 0 0 0-1.59-.779c-.878-.35-1.625-.507-2.206-.503-.574.003-.913.16-1.111.359-.199.198-.356.537-.36 1.111-.003.58.153 1.328.504 2.205.203.506.464 1.04.78 1.59Z\" clip-rule=\"evenodd\"/></svg>",
			"icon_filled_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" fill-rule=\"evenodd\" d=\"M12 7.42a22.323 22.323 0 0 0-2.453 2.127A22.323 22.323 0 0 0 7.42 12a22.32 22.32 0 0 0 2.127 2.453c.807.808 1.636 1.52 2.453 2.128a22.335 22.335 0 0 0 2.453-2.128A22.322 22.322 0 0 0 16.58 12a22.326 22.326 0 0 0-2.127-2.453A22.32 22.32 0 0 0 12 7.42Zm1.751-1.154a24.715 24.715 0 0 1 2.104 1.88 24.722 24.722 0 0 1 1.88 2.103c.316-.55.576-1.085.779-1.59.35-.878.507-1.625.503-2.206-.003-.574-.16-.913-.358-1.111-.199-.199-.537-.356-1.112-.36-.58-.003-1.328.153-2.205.504-.506.203-1.04.464-1.59.78Zm3.983 7.485a24.706 24.706 0 0 1-1.88 2.104 24.727 24.727 0 0 1-2.103 1.88 12.7 12.7 0 0 0 1.59.779c.878.35 1.625.507 2.206.503.574-.003.913-.16 1.111-.358.199-.199.356-.538.36-1.112.003-.58-.154-1.328-.504-2.205a12.688 12.688 0 0 0-.78-1.59ZM12 18.99c.89.57 1.768 1.03 2.605 1.364 1.026.41 2.036.652 2.955.646.925-.006 1.828-.267 2.5-.94.673-.672.934-1.575.94-2.5.006-.919-.236-1.929-.646-2.954A15.688 15.688 0 0 0 18.99 12c.57-.89 1.03-1.768 1.364-2.606.41-1.025.652-2.035.646-2.954-.006-.925-.267-1.828-.94-2.5-.672-.673-1.575-.934-2.5-.94-.919-.006-1.929.235-2.954.646-.838.335-1.716.795-2.606 1.364a15.69 15.69 0 0 0-2.606-1.364C8.37 3.236 7.36 2.994 6.44 3c-.925.006-1.828.267-2.5.94-.673.672-.934 1.575-.94 2.5-.006.919.235 1.929.646 2.955A15.69 15.69 0 0 0 5.01 12c-.57.89-1.03 1.768-1.364 2.605-.41 1.026-.652 2.036-.646 2.955.006.925.267 1.828.94 2.5.672.673 1.575.934 2.5.94.92.006 1.93-.235 2.955-.646A15.697 15.697 0 0 0 12 18.99Zm-1.751-1.255a24.714 24.714 0 0 1-2.104-1.88 24.713 24.713 0 0 1-1.88-2.104c-.315.55-.576 1.085-.779 1.59-.35.878-.507 1.625-.503 2.206.003.574.16.913.359 1.111.198.199.537.356 1.111.36.58.003 1.328-.153 2.205-.504.506-.203 1.04-.463 1.59-.78Zm-3.983-7.486a24.727 24.727 0 0 1 1.88-2.104 24.724 24.724 0 0 1 2.103-1.88 12.696 12.696 0 0 0-1.59-.779c-.878-.35-1.625-.507-2.206-.503-.574.003-.913.16-1.111.359-.199.198-.356.537-.36 1.111-.003.58.153 1.328.504 2.205.203.506.464 1.04.78 1.59Z\" clip-rule=\"evenodd\"/></svg>",
		},
		"star": {
			"icon_filled_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M12.001 1.75c.496 0 .913.373.969.866.306 2.705 1.126 4.66 2.44 6 1.31 1.333 3.223 2.17 5.95 2.412a.976.976 0 0 1-.002 1.945c-2.682.232-4.637 1.067-5.977 2.408-1.34 1.34-2.176 3.295-2.408 5.977a.976.976 0 0 1-1.945.002c-.243-2.727-1.08-4.64-2.412-5.95-1.34-1.314-3.295-2.134-6-2.44a.976.976 0 0 1-.002-1.94c2.75-.317 4.665-1.137 5.972-2.444 1.307-1.307 2.127-3.221 2.444-5.972a.976.976 0 0 1 .971-.864Z\"/></svg>",
			"icon_outline_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M12.001 1.5a1 1 0 0 1 .993.887c.313 2.77 1.153 4.775 2.5 6.146 1.34 1.366 3.3 2.223 6.095 2.47a1 1 0 0 1-.003 1.993c-2.747.238-4.75 1.094-6.123 2.467-1.373 1.374-2.229 3.376-2.467 6.123a1 1 0 0 1-1.992.003c-.248-2.795-1.105-4.754-2.47-6.095-1.372-1.347-3.376-2.187-6.147-2.5a1 1 0 0 1-.002-1.987c2.818-.325 4.779-1.165 6.118-2.504 1.339-1.34 2.179-3.3 2.504-6.118A1 1 0 0 1 12 1.5ZM6.725 11.998c1.234.503 2.309 1.184 3.21 2.069.877.861 1.56 1.888 2.063 3.076.5-1.187 1.18-2.223 2.051-3.094.871-.87 1.907-1.55 3.094-2.05-1.188-.503-2.215-1.187-3.076-2.064-.885-.901-1.566-1.976-2.069-3.21-.505 1.235-1.19 2.3-2.081 3.192-.891.89-1.957 1.576-3.192 2.082Z\"/></svg>",
		},
		"stars": {
			"icon_filled_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M19.92.897a.447.447 0 0 0-.89-.001c-.12 1.051-.433 1.773-.922 2.262-.49.49-1.21.801-2.262.923a.447.447 0 0 0 0 .888c1.035.117 1.772.43 2.274.922.499.49.817 1.21.91 2.251a.447.447 0 0 0 .89 0c.09-1.024.407-1.76.91-2.263.502-.502 1.238-.82 2.261-.908a.447.447 0 0 0 .001-.891c-1.04-.093-1.76-.411-2.25-.91-.493-.502-.806-1.24-.923-2.273ZM11.993 3.82a1.15 1.15 0 0 0-2.285-.002c-.312 2.704-1.115 4.559-2.373 5.817-1.258 1.258-3.113 2.06-5.817 2.373a1.15 1.15 0 0 0 .003 2.285c2.658.3 4.555 1.104 5.845 2.37 1.283 1.26 2.1 3.112 2.338 5.789a1.15 1.15 0 0 0 2.292-.003c.227-2.631 1.045-4.525 2.336-5.817 1.292-1.291 3.186-2.109 5.817-2.336a1.15 1.15 0 0 0 .003-2.291c-2.677-.238-4.529-1.056-5.789-2.34-1.266-1.29-2.07-3.186-2.37-5.844Z\"/></svg>",
			"icon_outline_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M19.898.855a.4.4 0 0 0-.795 0c-.123 1.064-.44 1.802-.943 2.305-.503.503-1.241.82-2.306.943a.4.4 0 0 0 .001.794c1.047.119 1.801.436 2.317.942.512.504.836 1.241.93 2.296a.4.4 0 0 0 .796 0c.09-1.038.413-1.792.93-2.308.515-.516 1.269-.839 2.306-.928a.4.4 0 0 0 .001-.797c-1.055-.094-1.792-.418-2.296-.93-.506-.516-.823-1.27-.941-2.317Z\"/><path fill=\"currentColor\" d=\"M12.001 1.5a1 1 0 0 1 .993.887c.313 2.77 1.153 4.775 2.5 6.146 1.34 1.366 3.3 2.223 6.095 2.47a1 1 0 0 1-.003 1.993c-2.747.238-4.75 1.094-6.123 2.467-1.373 1.374-2.229 3.376-2.467 6.123a1 1 0 0 1-1.992.003c-.248-2.795-1.105-4.754-2.47-6.095-1.372-1.347-3.376-2.187-6.147-2.5a1 1 0 0 1-.002-1.987c2.818-.325 4.779-1.165 6.118-2.504 1.339-1.34 2.179-3.3 2.504-6.118A1 1 0 0 1 12 1.5ZM6.725 11.998c1.234.503 2.309 1.184 3.21 2.069.877.861 1.56 1.888 2.063 3.076.5-1.187 1.18-2.223 2.051-3.094.871-.87 1.907-1.55 3.094-2.05-1.188-.503-2.215-1.187-3.076-2.064-.885-.901-1.566-1.976-2.069-3.21-.505 1.235-1.19 2.3-2.081 3.192-.891.89-1.957 1.576-3.192 2.082Z\"/></svg>",
		},
		"reasoning_mini": {
			"icon_filled_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M5.625 11.542C3.264 12 1.75 12.707 1.75 13.5 1.75 14.88 6.34 16 12 16s10.25-1.12 10.25-2.5c0-.793-1.514-1.5-3.875-1.958-3.913-.759-4.477-5.638-5.162-8.814A1.24 1.24 0 0 0 12 1.75a1.24 1.24 0 0 0-1.213.978c-.685 3.176-1.25 8.055-5.162 8.814ZM14.386 17.935a43.306 43.306 0 0 1-4.772 0c.464.986.835 2.09 1.154 3.341A1.28 1.28 0 0 0 12 22.25a1.28 1.28 0 0 0 1.232-.974c.319-1.25.69-2.355 1.154-3.34Z\"/></svg>",
			"icon_outline_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M14.445 17.935a45.497 45.497 0 0 1-4.89 0c.475.986.856 2.09 1.183 3.341a1.306 1.306 0 0 0 2.524 0c.327-1.25.708-2.355 1.183-3.34ZM4.784 13c.17.06.357.121.564.182 1.613.472 3.965.793 6.652.793 2.687 0 5.039-.321 6.651-.793.208-.06.396-.122.565-.182-.43-.153-.965-.305-1.603-.443-1.532-.329-3.573-1.15-4.548-3.166-.445-.92-.783-1.914-1.065-2.93-.282 1.016-.62 2.01-1.065 2.93-.975 2.016-3.016 2.837-4.548 3.166-.638.138-1.173.29-1.603.443Zm1.157-2.42c1.294-.278 2.551-.883 3.117-2.053.769-1.59 1.187-3.482 1.647-5.567l.051-.232A1.264 1.264 0 0 1 12 1.75c.599 0 1.117.406 1.244.978l.051.232c.46 2.085.878 3.978 1.647 5.567.566 1.17 1.823 1.775 3.117 2.053 2.541.546 4.191 1.427 4.191 2.42 0 1.657-4.59 3-10.25 3S1.75 14.657 1.75 13c0-.993 1.65-1.874 4.19-2.42Z\"/></svg>",
		},
		"reasoning": {
			"icon_filled_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M22.25 4.5a2.75 2.75 0 1 1-5.5 0 2.75 2.75 0 0 1 5.5 0ZM7.615 11.064c-.55.66-1.384.968-2.226 1.131-2.217.43-3.639 1.094-3.639 1.838 0 1.297 4.31 2.348 9.625 2.348 5.316 0 9.625-1.05 9.625-2.348 0-.744-1.422-1.408-3.64-1.838-.841-.163-1.676-.472-2.225-1.13-1.46-1.754-1.977-4.16-2.573-6.928l-.048-.219A1.164 1.164 0 0 0 11.375 3c-.549 0-1.024.382-1.14.918l-.046.219c-.597 2.768-1.115 5.174-2.574 6.927ZM13.615 18.198a40.664 40.664 0 0 1-4.48 0c.435.925.784 1.963 1.084 3.138.135.531.607.914 1.156.914.549 0 1.021-.383 1.156-.914.3-1.175.65-2.212 1.084-3.138Z\"/></svg>",
			"icon_outline_src": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"24\" height=\"24\" fill=\"none\" viewBox=\"0 0 24 24\"><path fill=\"currentColor\" d=\"M4.924 13.113c.163.06.344.12.544.18 1.554.466 3.82.783 6.41.783 2.59 0 4.856-.317 6.41-.783.2-.06.381-.12.544-.18-.415-.152-.93-.302-1.545-.438-1.476-.324-3.443-1.136-4.382-3.127-.43-.908-.755-1.89-1.027-2.895-.272 1.004-.598 1.987-1.026 2.895-.94 1.99-2.907 2.803-4.383 3.127-.616.136-1.13.286-1.545.438Zm15.018-.576s-.004.007-.018.019c.01-.013.018-.019.018-.019Zm-16.11.019c-.014-.012-.018-.019-.018-.019l.018.019Zm2.207-1.834c1.247-.274 2.459-.872 3.004-2.027.74-1.57 1.143-3.44 1.587-5.5l.05-.23A1.225 1.225 0 0 1 11.878 2c.577 0 1.077.401 1.199.966l.05.23c.443 2.06.845 3.929 1.586 5.499.545 1.155 1.757 1.753 3.004 2.027 2.45.54 4.04 1.41 4.04 2.39 0 1.637-4.424 2.964-9.879 2.964C6.423 16.076 2 14.75 2 13.113c0-.981 1.59-1.851 4.039-2.39ZM14.235 17.988a42.76 42.76 0 0 1-4.713 0c.457.973.825 2.065 1.14 3.3.142.56.639.962 1.216.962s1.074-.403 1.217-.962c.315-1.235.682-2.327 1.14-3.3ZM19.5 5.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2Zm0 2a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z\"/></svg>",
		}
	}
	model_icons = {
		"auto_acd64": iconModels["connected"], # 自动
		"gpt_3.5_gd1j": iconModels["bolt"], # 3.5 4o-mini
		"gpt_4": iconModels["star"], # 4
		"AG8PqS2q": iconModels["stars"], # 4o
		"9fdGgEgJ": iconModels["stars"], # 4o-canvas
		"o1_mini": iconModels["reasoning_mini"], # o1-mini
		"o1": iconModels["reasoning"], # o1
		"o1_pro": iconModels["reasoning"], # o1-pro
		"o3_mini": iconModels["reasoning_mini"], # o3-mini
		"o3_mini_high": iconModels["reasoning_mini"], # o3-mini-high
	}
	return Response(content=json.dumps(model_icons, indent=4), media_type="application/json")

@app.get("/backend-api/edge")
@app.post("/backend-api/edge")
async def edge():
	return Response(status_code=204)

if no_sentinel:
	openai_sentinel_tokens_cache = {}

	@app.post("/backend-api/sentinel/chat-requirements")
	async def sentinel_chat_conversations(request: Request):
		token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
		req_token = await get_real_req_token(token)
		access_token = await verify_token(req_token)
		fp = get_fp(req_token).copy()
		proxy_url = fp.pop("proxy_url", None)
		impersonate = fp.pop("impersonate", "safari15_3")
		user_agent = fp.get("user-agent",
							"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0")

		host_url = random.choice(chatgpt_base_url_list) if chatgpt_base_url_list else "https://chatgpt.com"
		proof_token = None
		turnstile_token = None

		# headers = {
		#     key: value for key, value in request.headers.items()
		#     if (key.lower() not in ["host", "origin", "referer", "priority", "sec-ch-ua-platform", "sec-ch-ua",
		#                             "sec-ch-ua-mobile", "oai-device-id"] and key.lower() not in headers_reject_list)
		# }
		headers = {
			key: value for key, value in request.headers.items()
			if (key.lower() in headers_accept_list)
		}
		headers.update(fp)
		headers.update({"authorization": f"Bearer {access_token}"})
		client = Client(proxy=proxy_url, impersonate=impersonate)
		if sentinel_proxy_url_list:
			clients = Client(proxy=random.choice(sentinel_proxy_url_list), impersonate=impersonate)
		else:
			clients = client

		try:
			config = get_config(user_agent)
			p = get_requirements_token(config)
			data = {'p': p}
			r = await clients.post(f'{host_url}/backend-api/sentinel/chat-requirements', headers=headers, json=data, timeout=10)
			if r.status_code != 200:
				raise HTTPException(status_code=r.status_code, detail="Failed to get chat requirements")
			resp = r.json()
			turnstile = resp.get('turnstile', {})
			turnstile_required = turnstile.get('required')
			if turnstile_required:
				turnstile_dx = turnstile.get("dx")
				try:
					if turnstile_solver_url:
						res = await client.post(turnstile_solver_url, json={"url": "https://chatgpt.com", "p": p, "dx": turnstile_dx})
						turnstile_token = res.json().get("t")
				except Exception as e:
					log.info(f"Turnstile ignored: {e}")

			proofofwork = resp.get('proofofwork', {})
			proofofwork_required = proofofwork.get('required')
			if proofofwork_required:
				proofofwork_diff = proofofwork.get("difficulty")
				proofofwork_seed = proofofwork.get("seed")
				proof_token, solved = await run_in_threadpool(
					get_answer_token, proofofwork_seed, proofofwork_diff, config
				)
				if not solved:
					raise HTTPException(status_code=403, detail="Failed to solve proof of work")
			chat_token = resp.get('token')

			openai_sentinel_tokens_cache[req_token] = {
				"chat_token": chat_token,
				"proof_token": proof_token,
				"turnstile_token": turnstile_token
			}
		except Exception as e:
			log.error(f"Sentinel failed: {e}")

		return {
			"arkose": {
				"dx": None,
				"required": False
			},
			"persona": "chatgpt-paid",
			"proofofwork": {
				"difficulty": None,
				"required": False,
				"seed": None
			},
			"token": str(uuid.uuid4()),
			"turnstile": {
				"dx": None,
				"required": False
			}
		}

	@app.post("/backend-alt/conversation")
	@app.post("/backend-api/conversation")
	async def chat_conversations(request: Request):
		token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
		req_token = await get_real_req_token(token)
		access_token = await verify_token(req_token)
		fp = get_fp(req_token).copy()
		proxy_url = fp.pop("proxy_url", None)
		impersonate = fp.pop("impersonate", "safari15_3")
		user_agent = fp.get("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0")

		host_url = random.choice(chatgpt_base_url_list) if chatgpt_base_url_list else "https://chatgpt.com"
		proof_token = None
		turnstile_token = None

		# headers = {
		#     key: value for key, value in request.headers.items()
		#     if (key.lower() not in ["host", "origin", "referer", "priority", "sec-ch-ua-platform", "sec-ch-ua",
		#                             "sec-ch-ua-mobile", "oai-device-id"] and key.lower() not in headers_reject_list)
		# }
		headers = {
			key: value for key, value in request.headers.items()
			if (key.lower() in headers_accept_list)
		}
		headers.update(fp)
		headers.update({"authorization": f"Bearer {access_token}"})

		try:
			client = Client(proxy=proxy_url, impersonate=impersonate)
			if sentinel_proxy_url_list:
				clients = Client(proxy=random.choice(sentinel_proxy_url_list), impersonate=impersonate)
			else:
				clients = client

			sentinel_tokens = openai_sentinel_tokens_cache.get(req_token, {})
			openai_sentinel_tokens_cache.pop(req_token, None)
			if not sentinel_tokens:
				config = get_config(user_agent)
				p = get_requirements_token(config)
				data = {'p': p}
				r = await clients.post(f'{host_url}/backend-api/sentinel/chat-requirements', headers=headers, json=data, timeout=10)
				resp = r.json()
				turnstile = resp.get('turnstile', {})
				turnstile_required = turnstile.get('required')
				if turnstile_required:
					turnstile_dx = turnstile.get("dx")
					try:
						if turnstile_solver_url:
							res = await client.post(turnstile_solver_url,
													json={"url": "https://chatgpt.com", "p": p, "dx": turnstile_dx})
							turnstile_token = res.json().get("t")
					except Exception as e:
						log.info(f"Turnstile ignored: {e}")

				proofofwork = resp.get('proofofwork', {})
				proofofwork_required = proofofwork.get('required')
				if proofofwork_required:
					proofofwork_diff = proofofwork.get("difficulty")
					proofofwork_seed = proofofwork.get("seed")
					proof_token, solved = await run_in_threadpool(
						get_answer_token, proofofwork_seed, proofofwork_diff, config
					)
					if not solved:
						raise HTTPException(status_code=403, detail="Failed to solve proof of work")
				chat_token = resp.get('token')
				headers.update({
					"openai-sentinel-chat-requirements-token": chat_token,
					"openai-sentinel-proof-token": proof_token,
					"openai-sentinel-turnstile-token": turnstile_token,
				})
			else:
				headers.update({
					"openai-sentinel-chat-requirements-token": sentinel_tokens.get("chat_token", ""),
					"openai-sentinel-proof-token": sentinel_tokens.get("proof_token", ""),
					"openai-sentinel-turnstile-token": sentinel_tokens.get("turnstile_token", "")
				})
		except Exception as e:
			log.error(f"Sentinel failed: {e}")
			return Response(status_code=403, content="Sentinel failed")

		params = dict(request.query_params)
		data = await request.body()
		request_cookies = dict(request.cookies)

		async def c_close(client, clients):
			if client:
				await client.close()
				del client
			if clients:
				await clients.close()
				del clients

		history = True
		try:
			req_json = json.loads(data)
			history = not req_json.get("history_and_training_disabled", False)
		except Exception:
			pass
		if force_no_history:
			history = False
			req_json = json.loads(data)
			req_json["history_and_training_disabled"] = True
			data = json.dumps(req_json).encode("utf-8")

		background = BackgroundTask(c_close, client, clients)
		r = await client.post_stream(f"{host_url}{request.url.path}", params=params, headers=headers, cookies=request_cookies, data=data, stream=True, allow_redirects=False)
		rheaders = r.headers
		log.info(f"Request token: {req_token}")
		log.info(f"Request proxy: {proxy_url}")
		log.info(f"Request UA: {user_agent}")
		log.info(f"Request impersonate: {impersonate}")
		if x_sign:
			rheaders.update({"x-sign": x_sign})
		if 'stream' in rheaders.get("content-type", ""):
			conv_key = r.cookies.get("conv_key", "")
			response = StreamingResponse(content_generator(r, token, history), headers=rheaders, media_type=r.headers.get("content-type", ""), background=background)
			response.set_cookie("conv_key", value=conv_key)
			return response
		else:
			return Response(content=(await r.atext()), headers=rheaders, media_type=rheaders.get("content-type"),
							status_code=r.status_code, background=background)

@app.api_route("/backend-anon/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"])
async def reverse_proxy(request: Request, path: str):
	return RedirectResponse(url=f'/backend-api/{path}', headers=request.headers, status_code=307)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"])
async def reverse_proxy(request: Request, path: str):
	token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.headers.get("X-Authorization", "").replace("Bearer ", "") or "chatgpt"
	if len(token) != 45 and not token.startswith("eyJhbGciOi"):
		for banned_path in banned_paths:
			if re.match(banned_path, path):
				raise HTTPException(status_code=403, detail={"message": "Access denied - You do not have permission to access this resource"})

	for chatgpt_path in chatgpt_paths:
		if re.match(chatgpt_path, path):
			return await chatgpt_html(request)

	for redirect_path in redirect_paths:
		if re.match(redirect_path, path):
			redirect_url = str(request.base_url)
			response = RedirectResponse(url=f"{redirect_url}auth/login", status_code=302)
			return response

	return await web_reverse_proxy(request, path)
