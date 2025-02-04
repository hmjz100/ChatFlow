> [!NOTE]
> 此项目与原项目（不太）兼容。所以请不要进行“替换大法“来切换到本项目。
> 此项目仅供体验，离正式版还差好远呢！
> ——反正别替换就好。

# FlowGPT

一个简单又漂亮的 ChatGPT 代理。

支持与最新的 `reasoning` 系列模型以及经典模型进行对话。
 
此项目基于 [Chat2Api](https://github.com/lanqian528/chat2api)，但更注重于界面 UI 的舒适度。

项目的 API 回复格式与原始 API 保持一致，以适配更多客户端。

## 功能

### 对话界面
更漂亮了~
- 支持 官网历史 UI 镜像。（目前无法实现同步更新 UI）
- 支持 打开调试侧栏（于历史聊天的(…)菜单里打开）
- 支持 全系列模型以及 `GPTs`。
- 支持 输入 `RefreshToken` 直接使用。
- 支持 代理 Gravatar 头像。（须注册 Gravatar 设置头像后才可显示）
- 支持 Tokens 管理，可上传至后台号池
- 支持 从后台账号池随机抽取账号使用，输入 `SeedToken` 以使用随机账号。
- 账户操作 - `/auth/(login | logout)`
	- 更美观的界面
	- 在注销时，可选择取消注销以防止误操作。
	- 不再支持保留 `token` 的 Cookie，点击确认注销后会删除 Cookie。
- 快捷账户操作 (API) - `/api/auth/(signin | signout)/?(signin | signout)=XXX`
	- 登录 - `/api/auth/signin/?signin=XXX`。 
	XXX 可为 `AccessToken`、`RefreshToken` 或者 `SeedToken`（随机抽取）
	- 注销 - `/api/auth/signout/?signout=true`
	访问后将会删除本地保存的 `token` Cookie。
- 后端 - `/backend-(api | anon)/`
	- 使用共享账号（`SeedToken`）时，会对 `敏感信息接口` 及 `部分设置接口`，返回空值，以实现禁用的效果。


### 对话 API
和原项目差不多就是了
- 支持 `v1/models` 接口
- 支持 流式、非流式 传输
- 支持 画图、代码、联网 等高级功能
- 支持 `reasoning` 系列模型推理过程输出
- 支持 GPTs（传入模型名：gizmo-g-*）
- 支持 Team 账号（需传入 Team Account ID）
- 支持 上传图片、文件（格式与 OpenAI API 相同，支持 URL 和 base64）
- 支持 下载文件（需开启历史记录）
- 支持 作为网关使用、多机分布部署
- 支持 多账号轮询，以及输入 `AccessToken` 或 `RefreshToken`
- 支持 请求失败自动重试，自动轮询下一个 Token
- 支持 定时使用 `RefreshToken` 刷新 `AccessToken`
 - 每次启动将会全部非强制刷新一次，每 4 天晚上 3 点全部强制刷新一次。

### 不大可能的 TODO
- [ ] 支持与官网 UI 实时更新

## 使用说明

### 环境变量

每个环境变量都有默认值，如果不懂环境变量的含义，请不要设置，更不要传空值，字符串无需引号。

若是非 Docker 环境运行项目可通过在项目目录手动创建 .env 文件来定义环境变量。

| 分类 | 变量名 | 类型 | 默认值 | 描述 |
|------|-------|------|--------|-----|
| 安全 | API_PREFIX | 字符串 | / | API 前缀 |
| 安全 | AUTHORIZATION | 数组 | / | 多账号轮询授权码 |
| 安全 | AUTH_KEY | 字符串 | / | `auth_key` 请求头 |
| 请求 | CHATGPT_BASE_URL | 字符串 | `https://chatgpt.com` | ChatGPT 官网地址 |
| 请求 | PROXY_URL | 字符串/数组 | / | 全局代理 URL |
| 请求 | EXPORT_PROXY_URL | 字符串 | / | 出口代理 URL |
| 功能 | HISTORY_DISABLED | 布尔值 | `true` | API 请求禁用聊天记录 |
| 功能 | POW_DIFFICULTY | 字符串 | `00003a` | 要解决的工作量证明难度 |
| 功能 | RETRY_TIMES | 整数 | `3` | 出错重试次数 |
| 功能 | CONVERSATION_ONLY | 布尔值 | `false` | 是否直接使用对话接口，而不获取 PoW。 |
| 功能 | ENABLE_LIMIT | 布尔值 | `true` | 不突破官方次数限制 |
| 功能 | UPLOAD_BY_URL | 布尔值 | `false` | 按照 `URL+空格+正文` 进行对话 |
| 功能 | SCHEDULED_REFRESH | 布尔值 | `false` | 定时刷新 `AccessToken` |
| 功能 | RANDOM_TOKEN | 布尔值 | `true` | 是否随机选取后台 `Token` |
| 网关 | PORT | 整数 | `5005` | 服务监听端口 |
| 网关 | ENABLE_GATEWAY | 布尔值 | `false` | 启用网关模式 |
| 网关 | ENABLE_HOMEPAGE | 布尔值 | `false` | 显示网关主页为未登录的官网 |
| 网关 | AUTO_SEED | 布尔值 | `true` | 启用随机账号模式 |

由于篇幅有限（懒），更详细的变量介绍请参考原项目。

#### ENABLE_HOMEPAGE
开启后在跳转登录页面时可能会泄露代理地址国家，如果关闭，那么会显示为简陋的主页。

#### AUTHORIZATION
此变量是一个您给 FlowGPT 设置的一个授权码，设置后才可使用号池中的账号进行令牌轮询，请求时当作令牌传入。

### 后台管理
1. 运行程序。
2. 如果设置了 `API_PREFIX` 环境变量，那么请先访问 `/(API_PREFIX)` 设置 Cookie。
   - 访问后会自动跳转到 `/admin` 管理页面
   - 请保管好您的 `API_PREFIX` 密钥，以防被不法分子获取
3. 访问 `/admin` 可以查看现有 Tokens 数量，也可以上传新的 Tokens，或者清空 Tokens。
3. 请求时传入 “授权码“ 即可使用轮询的Tokens进行对话

### 对话界面
1. 配置环境变量 `ENABLE_GATEWAY` 为 `true`，然后运行程序。
2. 访问 `/auth/login` 登录页面，输入令牌。
   - 如果想要共享账号给他人，可以在管理页面上传 `RefreshToken` 或 `AccessToken`，这样他人就可用种子令牌随机使用。
4. 登录后即可使用。

### 对话 API
完全兼容 “OpenAI API“ 格式的返回，传入 `AccessToken` 或 `RefreshToken` 后即可使用
```bash
curl "http://127.0.0.1:5005/v1/chat/completions" \
	-H "Content-Type: application/json" \
	-H "Authorization: Bearer (令牌)" \
	-d '{
		"model": "gpt-4o-mini",
		"messages": [
			{
				"role": "system",
				"content": "You are a helpful assistant."
 			},
 			{
				"role": "user",
				"content": "Write a haiku that explains the concept of recursion."
			}
		]
	}'
```
将你账号的令牌作为 `(X-)Authorization: (令牌)` 传入即可。当然，也可传入你设置的环境变量 `AUTHORIZATION` 的值，将会从后台号池中轮询选择账号使用。

#### 获取访问令牌（`AccessToken`）
先登录 ChatGPT 官网，再打开 [https://chatgpt.com/api/auth/session](https://chatgpt.com/api/auth/session)，找到 `accessToken` 对应的值即为 AccrssToken。
#### 获取刷新令牌（`RefreshToken`）
需要使用 Apple 设备安装 ChatGPT 应用获取，详情请自行搜索。
#### 常见错误码
- `401` - 当前 IP 不支持免登录，请尝试更换 IP 地址，或者在环境变量 `PROXY_URL` 中设置代理，或者你的身份验证失败。
- `403` - 请在日志中查看具体报错信息。
- `429` - 当前 IP 请求1小时内请求超过限制，请稍后再试，或更换 IP。
- `500` - 服务器内部错误，请求失败。
- `502` - 服务器网关错误，或网络不可用，请尝试更换网络环境。

## 部署

### 普通部署
```bash
git clone https://github.com/hmjz100/FlowGPT
cd chat2api
pip install -r requirements.txt
python app.py
```

### Docker
暂时不可能……

## 许可证
MIT License

