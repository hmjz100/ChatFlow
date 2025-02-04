import ast
import os

from dotenv import load_dotenv

from utils.log import log

load_dotenv(encoding="ascii")

def is_true(x):
	if isinstance(x, bool):
		return x
	if isinstance(x, str):
		return x.lower() in ['true', '1', 't', 'y', 'yes']
	elif isinstance(x, int):
		return x == 1
	else:
		return False

api_prefix = os.getenv('API_PREFIX', None)
authorization = os.getenv('AUTHORIZATION', '').replace(' ', '')
chatgpt_base_url = os.getenv('CHATGPT_BASE_URL', 'https://chatgpt.com').replace(' ', '')
auth_key = os.getenv('AUTH_KEY', None)
x_sign = os.getenv('X_SIGN', None)

ark0se_token_url = os.getenv('ARK' + 'OSE_TOKEN_URL', '').replace(' ', '')
if not ark0se_token_url:
	ark0se_token_url = os.getenv('ARK0SE_TOKEN_URL', None)
proxy_url = os.getenv('PROXY_URL', '').replace(' ', '')
sentinel_proxy_url = os.getenv('SENTINEL_PROXY_URL', None)
export_proxy_url = os.getenv('EXPORT_PROXY_URL', None)
file_host = os.getenv('FILE_HOST', None)
voice_host = os.getenv('VOICE_HOST', None)
impersonate_list_str = os.getenv('IMPERSONATE', '[]')
user_agents_list_str = os.getenv('USER_AGENTS', '[]')
device_tuple_str = os.getenv('DEVICE_TUPLE', '()')
browser_tuple_str = os.getenv('BROWSER_TUPLE', '()')
platform_tuple_str = os.getenv('PLATFORM_TUPLE', '()')

cf_file_url = os.getenv('CF_FILE_URL', None)
turnstile_solver_url = os.getenv('TURNSTILE_SOLVER_URL', None)

history_disabled = is_true(os.getenv('HISTORY_DISABLED', True))
pow_difficulty = os.getenv('POW_DIFFICULTY', '000032')
retry_times = int(os.getenv('RETRY_TIMES', 3))
conversation_only = is_true(os.getenv('CONVERSATION_ONLY', False))
enable_limit = is_true(os.getenv('ENABLE_LIMIT', True))
upload_by_url = is_true(os.getenv('UPLOAD_BY_URL', False))
check_model = is_true(os.getenv('CHECK_MODEL', False))
scheduled_refresh = is_true(os.getenv('SCHEDULED_REFRESH', False))
random_token = is_true(os.getenv('RANDOM_TOKEN', True))
oai_language = os.getenv('OAI_LANGUAGE', 'zh-CN')

authorization_list = authorization.split(',') if authorization else []
chatgpt_base_url_list = chatgpt_base_url.split(',') if chatgpt_base_url else []
ark0se_token_url_list = ark0se_token_url.split(',') if ark0se_token_url else []
proxy_url_list = proxy_url.split(',') if proxy_url else []
sentinel_proxy_url_list = sentinel_proxy_url.split(',') if sentinel_proxy_url else []
impersonate_list = ast.literal_eval(impersonate_list_str)
user_agents_list = ast.literal_eval(user_agents_list_str)
device_tuple = ast.literal_eval(device_tuple_str)
browser_tuple = ast.literal_eval(browser_tuple_str)
platform_tuple = ast.literal_eval(platform_tuple_str)

port = os.getenv('PORT', 5005)
enable_gateway = is_true(os.getenv('ENABLE_GATEWAY', False))
enable_homepage = is_true(os.getenv('ENABLE_HOMEPAGE', False))
auto_seed = is_true(os.getenv('AUTO_SEED', True))
force_no_history = is_true(os.getenv('FORCE_NO_HISTORY', False))
no_sentinel = is_true(os.getenv('NO_SENTINEL', False))

with open('version.txt') as f:
	version = f.read().strip().title()

title = f"FlowGPT v{version} | https://github.com/hmjz100/FlowGPT"
log_length = len(title)

def aligned(left_text, right_text, separator=" "):
	"""
	格式化字符串，使左侧文本左对齐，右侧文本右对齐，中间用指定的分隔符填充。
	
	参数:
		left_text (str): 左侧文本。
		right_text (str): 右侧文本。
		separator (str): 用于填充的分隔符，默认为空格。
	
	返回:
		str: 格式化后的字符串。
	"""
	if not right_text:
		right_text = "/"
	
	right_text = str(right_text)
	# 如果总长度不足以容纳两侧文本，则直接拼接
	if log_length < len(left_text) + len(right_text):
		return f"{left_text}{right_text}"
	
	# 计算需要填充的分隔符数量
	padding_length = log_length - len(left_text) - len(right_text)
	if padding_length <= 0:
		return f"{left_text}{right_text}"
	
	# 使用分隔符填充中间部分
	padding = separator * padding_length
	formatted_string = f"{left_text}{padding}{right_text}"
	return formatted_string

version_map = {
	"beta": {
		"message": "Beta version, not representative of the final quality",
		"color": 94
	},
	"canary": {
		"message": "Canary version, unstable and experimental",
		"color": 96
	}
}

log.info("-" * log_length)
log.info(title)

for version_type, details in version_map.items():
	if version_type in version.lower():
		log.custom(details['message'].title().center(log_length, " "), details['color'])
		break

log.info("-" * log_length)
log.info(" environment variables ".title().center(log_length, " "))
log.info(" (.env) ".center(log_length, " "))
log.info(" Security ".center(log_length, "-"))
log.info(aligned("API_PREFIX", api_prefix))
log.info(aligned("AUTHORIZATION", authorization_list))
log.info(aligned("AUTH_KEY", auth_key))
log.info(" Request ".center(log_length, "-"))
log.info(aligned("CHATGPT_BASE_URL", chatgpt_base_url_list))
log.info(aligned("PROXY_URL", proxy_url_list))
log.info(aligned("EXPORT_PROXY_URL", export_proxy_url))
log.info(aligned("FILE_HOST", file_host))
log.info(aligned("VOICE_HOST", voice_host))
log.info(aligned("IMPERSONATE", impersonate_list))
log.info(aligned("USER_AGENTS", user_agents_list))
log.info(" Functionality ".center(log_length, "-"))
log.info(aligned("HISTORY_DISABLED", history_disabled))
log.info(aligned("POW_DIFFICULTY", pow_difficulty))
log.info(aligned("RETRY_TIMES", retry_times))
log.info(aligned("CONVERSATION_ONLY", conversation_only))
log.info(aligned("ENABLE_LIMIT", enable_limit))
log.info(aligned("UPLOAD_BY_URL", upload_by_url))
log.info(aligned("CHECK_MODEL", check_model))
log.info(aligned("SCHEDULED_REFRESH", scheduled_refresh))
log.info(aligned("RANDOM_TOKEN", random_token))
log.info(aligned("OAI_LANGUAGE", oai_language))
log.info(" Gateway ".center(log_length, "-"))
log.info(aligned("PORT", port))
log.info(aligned("ENABLE_GATEWAY", enable_gateway))
log.info(aligned("ENABLE_HOMEPAGE", enable_homepage))
log.info(aligned("AUTO_SEED", auto_seed))
log.info(aligned("FORCE_NO_HISTORY", force_no_history))
log.info("-" * log_length)
