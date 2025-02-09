import json
import random
import time
import re
from datetime import datetime, timezone

from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from starlette.background import BackgroundTask

import utils.globals as globals
from chatgpt.authorization import verify_token, get_req_token
from chatgpt.fp import get_fp
from utils.Client import Client
from utils.log import log
from utils.configs import chatgpt_base_url_list, sentinel_proxy_url_list, force_no_history, file_host, voice_host, log_length

def generate_current_time():
	current_time = datetime.now(timezone.utc)
	formatted_time = current_time.isoformat(timespec='microseconds').replace('+00:00', 'Z')
	return formatted_time

headers_reject_list = [
	"x-real-ip",
	"x-forwarded-for",
	"x-forwarded-proto",
	"x-forwarded-port",
	"x-forwarded-host",
	"x-forwarded-server",
	"cf-warp-tag-id",
	"cf-visitor",
	"cf-ray",
	"cf-connecting-ip",
	"cf-ipcountry",
	"cdn-loop",
	"remote-host",
	"x-frame-options",
	"x-xss-protection",
	"x-content-type-options",
	"content-security-policy",
	"host",
	"cookie",
	"connection",
	"content-length",
	"content-encoding",
	"x-middleware-prefetch",
	"x-nextjs-data",
	"purpose",
	"x-forwarded-uri",
	"x-forwarded-path",
	"x-forwarded-method",
	"x-forwarded-protocol",
	"x-forwarded-scheme",
	"cf-request-id",
	"cf-worker",
	"cf-access-client-id",
	"cf-access-client-device-type",
	"cf-access-client-device-model",
	"cf-access-client-device-name",
	"cf-access-client-device-brand",
	"x-middleware-prefetch",
	"x-forwarded-for",
	"x-forwarded-host",
	"x-forwarded-proto",
	"x-forwarded-server",
	"x-real-ip",
	"x-forwarded-port",
	"cf-connecting-ip",
	"cf-ipcountry",
	"cf-ray",
	"cf-visitor",
]

headers_accept_list = [
	"openai-sentinel-chat-requirements-token",
	"openai-sentinel-proof-token",
	"openai-sentinel-turnstile-token",
	"accept",
	"authorization",
	"x-authorization",
	"accept-encoding",
	"accept-language",
	"content-type",
	"oai-device-id",
	"oai-echo-logs",
	"oai-language",
	"sec-fetch-dest",
	"sec-fetch-mode",
	"sec-fetch-site",
	"x-ms-blob-type",
]

async def get_real_req_token(token):
	req_token = get_req_token(token)
	if len(req_token) == 45 or req_token.startswith("eyJhbGciOi"):
		return req_token
	else:
		req_token = get_req_token("", token)
		return req_token

def save_conversation(token, conversation_id, title=None):
	if conversation_id not in globals.conversation_map:
		conversation_detail = {
			"id": conversation_id,
			"title": title,
			"create_time": generate_current_time(),
			"update_time": generate_current_time()
		}
		globals.conversation_map[conversation_id] = conversation_detail
	else:
		globals.conversation_map[conversation_id]["update_time"] = generate_current_time()
		if title:
			globals.conversation_map[conversation_id]["title"] = title
	if conversation_id not in globals.seed_map[token]["conversations"]:
		globals.seed_map[token]["conversations"].insert(0, conversation_id)
	else:
		globals.seed_map[token]["conversations"].remove(conversation_id)
		globals.seed_map[token]["conversations"].insert(0, conversation_id)
	with open(globals.CONVERSATION_MAP_FILE, "w", encoding="utf-8") as f:
		json.dump(globals.conversation_map, f, indent=4)
	with open(globals.SEED_MAP_FILE, "w", encoding="utf-8") as f:
		json.dump(globals.seed_map, f, indent=4)
	if title:
		log.info(f"Conversation ID: {conversation_id}, Title: {title}")

async def content_generator(r, token, history=True):
	conversation_id = None
	title = None
	async for chunk in r.aiter_content():
		try:
			if history and (len(token) != 45 and not token.startswith("eyJhbGciOi")) and (not conversation_id or not title):
				chat_chunk = chunk.decode('utf-8')
				if not conversation_id or not title and chat_chunk.startswith("event: delta\n\ndata: {"):
					chunk_data = chat_chunk[19:]
					conversation_id = json.loads(chunk_data).get("v").get("conversation_id")
					if conversation_id:
						save_conversation(token, conversation_id)
						title = globals.conversation_map[conversation_id].get("title")
				if chat_chunk.startswith("data: {"):
					if "\n\nevent: delta" in chat_chunk:
						index = chat_chunk.find("\n\nevent: delta")
						chunk_data = chat_chunk[6:index]
					elif "\n\ndata: {" in chat_chunk:
						index = chat_chunk.find("\n\ndata: {")
						chunk_data = chat_chunk[6:index]
					else:
						chunk_data = chat_chunk[6:]
					chunk_data = chunk_data.strip()
					if conversation_id is None:
						conversation_id = json.loads(chunk_data).get("conversation_id")
						if conversation_id:
							save_conversation(token, conversation_id)
							title = globals.conversation_map[conversation_id].get("title")
					if title is None:
						title = json.loads(chunk_data).get("title")
						if title:
							save_conversation(token, conversation_id, title)
		except Exception as e:
			# log.error(e)
			# log.error(chunk.decode('utf-8'))
			pass
		yield chunk

async def web_reverse_proxy(request: Request, path: str):
	try:
		origin_host = request.url.netloc
		if request.url.is_secure:
			petrol = "https"
		else:
			petrol = "http"
		if "x-forwarded-proto" in request.headers:
			petrol = request.headers["x-forwarded-proto"]
		if "cf-visitor" in request.headers:
			cf_visitor = json.loads(request.headers["cf-visitor"])
			petrol = cf_visitor.get("scheme", petrol)

		# 修复Bug：输入多个相同键只能获取最后重复键的值
		params = {key: request.query_params.getlist(key) for key in request.query_params.keys()}
		params = {key: values[0] if len(values) == 1 else values for key, values in params.items()}

		request_cookies = dict(request.cookies)

		# headers = {
		#     key: value for key, value in request.headers.items()
		#     if (key.lower() not in ["host", "origin", "referer", "priority",
		#                             "oai-device-id"] and key.lower() not in headers_reject_list)
		# }
		headers = {
			key: value for key, value in request.headers.items()
			if (key.lower() in headers_accept_list)
		}

		base_url = random.choice(chatgpt_base_url_list) if chatgpt_base_url_list else "https://chatgpt.com"

		if path.endswith(".js.map") or "cdn-cgi/challenge-platform" in path or "api/v2/logs" in path:
			response = Response(content=f"<Error><Code>BlobNotFound</Code><Message>The specified blob does not exist. Time:{generate_current_time()}</Message></Error>", status_code=404, media_type="application/xml")
			return response

		if "assets/" in path:
			base_url = "https://cdn.oaistatic.com"
		if "voice/previews" in path:
			base_url = "https://persistent.oaistatic.com"
		if "file-" in path and "backend-api" not in path:
			base_url = "https://files.oaiusercontent.com"
		if "v1/" in path:
			base_url = "https://ab.chatgpt.com"
		if "sandbox" in path:
			base_url = "https://web-sandbox.oaiusercontent.com"
			path = path.replace("sandbox/", "")
		if "avatar/" in path:
			base_url = "https://s.gravatar.com"
			if params.get('s') == '480' and params.get('r') == 'pg' and params.get('d'):
				params['s'] = '100'

		token = headers.get("authorization", "") or headers.get("x-authorization", "")
		token = token.replace("Bearer ", "").strip()


		if token:
			req_token = await get_real_req_token(token)
			access_token = await verify_token(req_token)
			headers.update({"authorization": f"Bearer {access_token}"})
			headers.update({"x-authorization": f"Bearer {access_token}"})

		token = request.cookies.get("oai-flow-token", "")
		req_token = await get_real_req_token(token)

		fp = get_fp(req_token).copy()

		proxy_url = fp.pop("proxy_url", None)
		impersonate = fp.pop("impersonate", "safari15_3")
		user_agent = fp.get("user-agent")
		headers.update(fp)

		headers.update({
			# "accept-language": "en-US,en;q=0.9",
			"host": base_url.replace("https://", "").replace("http://", ""),
			"origin": base_url,
			"referer": f"{base_url}/"
		})

		if "file-" in path and "backend-api" not in path:
			headers.update({
				"origin": "https://chatgpt.com/",
				"referer": "https://chatgpt.com/"
			})

		if "v1/initialize" in path:
			headers.update({"user-agent": request.headers.get("user-agent")})
			if "statsig-api-key" not in headers:
				headers.update({
					"statsig-sdk-type": "js-client",
					"statsig-api-key": "client-tnE5GCU2F2cTxRiMbvTczMDT1jpwIigZHsZSdqiy4u",
					"statsig-sdk-version": "5.1.0",
					"statsig-client-time": int(time.time() * 1000),
				})

		data = await request.body()

		history = True

		if path.endswith("backend-api/conversation") or path.endswith("backend-alt/conversation"):
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

		if sentinel_proxy_url_list and "backend-api/sentinel/chat-requirements" in path:
			client = Client(proxy=random.choice(sentinel_proxy_url_list))
		else:
			client = Client(proxy=proxy_url, impersonate=impersonate)
		try:
			background = BackgroundTask(client.close)
			r = await client.request(request.method, f"{base_url}/{path}", params=params, headers=headers, cookies=request_cookies, data=data, stream=True, allow_redirects=False)

			if r.status_code == 307 or r.status_code == 302 or r.status_code == 301:
				return Response(status_code=307,
								headers={"Location": r.headers.get("Location")
								.replace("ab.chatgpt.com", origin_host)
								.replace("chatgpt.com", origin_host)
								.replace("cdn.oaistatic.com", origin_host)
								.replace("https", petrol)}, 
								background=background)
			elif 'stream' in r.headers.get("content-type", ""):
				log.info("-" * log_length)
				log.info(f"Request token: {req_token}")
				log.info(f"Request proxy: {proxy_url}")
				log.info(f"Request UA: {user_agent}")
				log.info(f"Request impersonate: {impersonate}")
				log.info("-" * log_length)
				conv_key = r.cookies.get("conv_key", "")
				response = StreamingResponse(content_generator(r, token, history), media_type=r.headers.get("content-type", ""), background=background)
				response.set_cookie("conv_key", value=conv_key)
				return response
			elif 'image' in r.headers.get("content-type", "") or "audio" in r.headers.get("content-type", "") or "video" in r.headers.get("content-type", ""):
				rheaders = dict(r.headers)

				# 修复浏览器无法解码
				if 'content-encoding' in rheaders:
					del rheaders['content-encoding']

				# 支持预览媒体而不是直接下载
				if 'content-disposition' in rheaders:
					rheaders['content-disposition'] = rheaders['content-disposition'].replace("attachment", "inline")

				response = Response(content=await r.acontent(), headers=rheaders, status_code=r.status_code, background=background)
				return response
			else:
				if path.endswith("backend-api/conversation") or path.endswith("backend-alt/conversation") or "/register-websocket" in path:
					response = Response(content=(await r.acontent()), media_type=r.headers.get("content-type"), status_code=r.status_code, background=background)
				else:
					content = await r.atext()

					# 关联的应用 - CallBack
					content = re.sub(r'\${window\.location\.origin}\/(aip|ccc|ca)\/', r'https://chatgpt.com/\1/', content)
					content = re.sub(r'(aip|ccc|ca)\/\:pluginId\/', r'https://chatgpt.com/\1/:pluginId/', content)

					content = (content
						# 前后端 API
						.replace("backend-anon", "backend-api")
						.replace("https://chatgpt.com/backend", f"{petrol}://{origin_host}/backend")
						.replace("https://chatgpt.com/public", f"{petrol}://{origin_host}/public")
						.replace("https://chatgpt.com/voice", f"{petrol}://{origin_host}/voice")
						.replace("https://chatgpt.com/api", f"{petrol}://{origin_host}/api")
						.replace("webrtc.chatgpt.com", voice_host if voice_host else "webrtc.chatgpt.com")
						# 前端显示
						.replace("https://cdn.oaistatic.com", f"{petrol}://{origin_host}")
						.replace("https://persistent.oaistatic.com", f"{petrol}://{origin_host}")
						.replace("https://files.oaiusercontent.com", f"{petrol}://{file_host if file_host else origin_host}")
						.replace("https://s.gravatar.com", f"{petrol}://{origin_host}")
						.replace("chromewebstore.google.com", "chromewebstore.crxsoso.com")
						# 伪遥测
						。replace("https://chatgpt.com/ces", f"{petrol}://{origin_host}/ces")
						。replace("${Mhe}/statsc/flush", f"{petrol}://{origin_host}/ces/statsc/flush")
						。replace("https://ab.chatgpt.com", f"{petrol}://{origin_host}")
						。replace("web-sandbox.oaiusercontent.com", f"{origin_host}/sandbox")
						# 禁止云收集数据
						。replace("browser-intake-datadoghq.com", f"0.0.0.0")
						。replace("datadoghq.com", f"0.0.0.0")
						。replace("ddog-gov.com", f"0.0.0.0")
						。replace("dd0g-gov.com", f"0.0.0.0")
						。replace("datad0g.com", f"0.0.0.0")
						# 翻译
						#.replace("By ChatGPT", "ChatGPT")
						#.replace("GPTs created by the ChatGPT team", "由 ChatGPT 官方创建的 GPTs")
						#.replace("Let me turn your imagination into imagery.", "让我将你的想象力转化为图像。")
						#.replace("Drop in any files and I can help analyze and visualize your data.", "上传任何文件，我可以帮助你分析并可视化数据。")
						#.replace("The latest version of GPT-4o with no additional capabilities.", "最新版本的 GPT-4o，没有额外的功能。")
						#.replace("I can browse the web to help you gather information or conduct research", "我可以浏览网页帮助你收集信息或进行研究。")
						#.replace("Ask me anything about stains,  settings, sorting and everything  laundry.", "问我任何关于污渍、设置、排序以及洗衣的一切问题。")
						#.replace("I help parents help their kids with  math. Need a 9pm refresher on  geometry proofs? I’m here for you.", "我帮助家长辅导孩子的数学。需要晚上9点复习几何证明？我在这里帮你。")
						。replace("给“{name}”发送消息", "问我任何事…")
						。replace("有什么可以帮忙的？", "今天能帮您些什么？")
						。replace("获取 ChatGPT 搜索扩展程序", "了解 “ChatGPT 搜索” 扩展")
						。replace("GPT 占位符", "占位 GPT")
						# 其它
						。replace('fill:"#0D0D0D"','fill:"currentColor"') # “新项目” 图标适配神色模式
						。replace("FP()","true") # 解除不显示 Sora 限制
						# .replace("https://chatgpt.com", f"{petrol}://{origin_host}") # 我才是 ChatGPT！
						# .replace("https", petrol) # 全都给我变协议
						)
					
					# 项目名称
					content = re.sub(r'(?<!OpenAI )ChatGPT(?! (Free|Plus|Pro|search|搜索))', 'FlowGPT', content)

					if base_url == "https://web-sandbox.oaiusercontent.com":
						content = content.replace("/assets", "/sandbox/assets")

					rheaders = dict(r.headers)
					rheaders = {
						"cache-control": rheaders.get("cache-control", ""),
						"content-type": rheaders.get("content-type", ""),
						"expires": rheaders.get("expires", ""),
						"content-disposition": rheaders.get("content-disposition", "")
					}

					response = Response(content=content, headers=rheaders, status_code=r.status_code, background=background)

				return response
		except Exception:
			await client.close()
	except HTTPException as e:
		raise e
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
