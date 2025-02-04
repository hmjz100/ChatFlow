import logging

default_format = "%(asctime)s | %(levelname)s | %(message)s"
access_format = r'%(asctime)s | %(levelname)s | %(status_code)s - %(request_line)s - %(client_addr)s'

logging.basicConfig(level=logging.INFO, format=default_format)

class log:
	@staticmethod
	def info(message):
		logging.info(str(message))

	@staticmethod
	def warning(message):
		logging.warning("\033[0;33m" + str(message) + "\033[0m")

	@staticmethod
	def error(message):
		logging.error("\033[0;31m" + str(message) + "\033[0m")
		# logging.error("\033[0;31m" + "-" * 50 + '\n| ' + str(message) + "\033[0m" + "\n" + "└" + "-" * 80)

	@staticmethod
	def debug(message):
		logging.debug("\033[0;37m" + str(message) + "\033[0m")

	@staticmethod
	def custom(message, color_code):
		"""
		自定义颜色的日志输出。
		
		参数:
			message (str): 要输出的消息。
			color_code (str): ANSI 颜色代码。
		"""
		logging.info(f"\033[0;{color_code}m{str(message)}\033[0m")

log = log()
