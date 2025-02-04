import json
import random
import uuid

import ua_generator
from ua_generator.data.version import VersionRange
from ua_generator.options import Options

import utils.globals as globals
from utils import configs

def get_fp(req_token):
	fp = globals.fp_map.get(req_token, {})
	if fp and fp.get("user-agent") and fp.get("impersonate"):
		if "proxy_url" in fp.keys() and (fp["proxy_url"] is None or fp["proxy_url"] not in configs.proxy_url_list):
			fp["proxy_url"] = random.choice(configs.proxy_url_list) if configs.proxy_url_list else None
			globals.fp_map[req_token] = fp
			with open(globals.FP_FILE, "w", encoding="utf-8") as f:
				json.dump(globals.fp_map, f, indent=4)
		if globals.impersonate_list and "impersonate" in fp.keys() and fp["impersonate"] not in globals.impersonate_list:
			fp["impersonate"] = random.choice(globals.impersonate_list)
			globals.fp_map[req_token] = fp
			with open(globals.FP_FILE, "w", encoding="utf-8") as f:
				json.dump(globals.fp_map, f, indent=4)
		if configs.user_agents_list and "user-agent" in fp.keys() and fp["user-agent"] not in configs.user_agents_list:
			fp["user-agent"] = random.choice(configs.user_agents_list)
			globals.fp_map[req_token] = fp
			with open(globals.FP_FILE, "w", encoding="utf-8") as f:
				json.dump(globals.fp_map, f, indent=4)
		fp = {k.lower(): v for k, v in fp.items()}
		return fp
	else:
		options = Options(version_ranges={
			'chrome': VersionRange(min_version=124),
			'edge': VersionRange(min_version=124),
		})
		ua = ua_generator.generate(
			device=configs.device_tuple if configs.device_tuple else ('desktop'),
			browser=configs.browser_tuple if configs.browser_tuple else ('chrome', 'edge', 'firefox', 'safari'),
			platform=configs.platform_tuple if configs.platform_tuple else ('windows', 'macos'),
			options=options
		)
		fp = {
			"user-agent": ua.text if not configs.user_agents_list else random.choice(configs.user_agents_list),
			"impersonate": random.choice(globals.impersonate_list),
			"proxy_url": random.choice(configs.proxy_url_list) if configs.proxy_url_list else None,
			"oai-device-id": str(uuid.uuid4())
		}
		if ua.device == "desktop" and ua.browser in ("chrome", "edge"):
			fp["sec-ch-ua-platform"] = ua.ch.platform
			fp["sec-ch-ua"] = ua.ch.brands
			fp["sec-ch-ua-mobile"] = ua.ch.mobile

		if not req_token:
			return fp
		else:
			globals.fp_map[req_token] = fp
			with open(globals.FP_FILE, "w", encoding="utf-8") as f:
				json.dump(globals.fp_map, f, indent=4)
			return fp
