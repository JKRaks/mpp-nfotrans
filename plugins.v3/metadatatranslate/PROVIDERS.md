# 翻译服务扩展契约 v1

扩展点位于 `contracts.py` 的 `TranslationProvider`，注册表位于 `providers.py` 的 `REGISTRY`。业务层不依赖 LLM 消息格式；云翻译、专用翻译模型与普通生成模型均使用同一批次结果契约。本期已经实现 DeepL、Hunyuan、OpenRouter、Gemini、通用 Chat Completions 五类适配。

## 输入与输出

`translate_batch(request: TranslationRequest) -> dict[str, dict]`：

- `items` 是 `TextItem(id, text, source_language)` 列表；ID 为不含路径和凭据的关联标识。输入不得无声截断。
- `target_language` 是规范化语言代码，例如 `zh-CN`；适配器自行转换供应商语言码。
- `context` 是作品名、类型和季集号等辅助上下文；不支持上下文的服务声明 `context=false`，不将其加入实际翻译请求和上下文缓存部分。
- `deadline` 是 monotonic 截止时间；每次请求和读取时调用 `request.check()`；`stop.is_set()` 为停止信号。
- 每个 ID 对应成功 `{status: "translated", text: "译文"}` 或 `TranslationError(...).result()`；可附加 usage、billed_characters、model、request_id 等已解析元数据。未知字段、空正文、截断、内容拦截不可计为成功。

同一批次可以部分成功。普通服务错误只影响本批字段，不触发备用供应商请求。序列调用的适配器保留已完成字段，后续超时分别记录失败；取消批次则不提交本批候选。

其余方法：`capabilities()` 描述 batch、context、detect_language、max_chars 等能力；`validate_config()` 检查配置；`close()` 释放会话。通过 `TranslationService(..., provider_factory=...)` 注入适配器工厂便于独立验收。生产默认工厂只从注册表选择用户配置的当前服务。

## 新增云翻译服务

1. 新建实现契约的适配器，原生请求中传原文、目标语言和可选来源语言，不拼 LLM 提示词。
2. 在 `PROVIDERS`、`DEFAULT_URLS`、`REGISTRY` 注册稳定 ID。配置专属参数放入有校验的配置模型，密钥继续通过独立 secret 参数传递。
3. 映射厂商鉴权、限流、额度、语言不支持、超时等错误；不向上透传响应正文、完整请求头或带凭据地址。
4. 为管理界面补充必要配置；所有策略仍只选择翻译语义，不选择供应商。
5. 契约改变时递增 `CONTRACT_VERSION`；改变提示词或输出语义时递增 `ADAPTER_VERSION`，使旧译文缓存失效。

扩展插槽不包含动态下载第三方脚本、自动发现密钥或自动切换供应商。要接入另一家云翻译，添加适配器并随插件交付即可。

## 错误约定

| code | 含义与重试 |
| --- | --- |
| auth / quota | 鉴权或明确额度耗尽；需调整账号或配置 |
| rate_limit | HTTP 429；采用 Retry-After，缺省 60 秒后可重试 |
| timeout / network / service | 超时、连接或服务错误；标记可重试，不在当前请求中重复收费调用 |
| unsupported / too_large | 模型、语言、参数或长度不支持；不静默截断或改请求模式 |
| invalid_response / truncated / blocked | 输出结构无效、截断或内容拦截；不写入相关字段 |
| not_configured / unavailable / policy_missing | 配置、插件状态或策略缺失 |
| source_unavailable / identity_unknown / unsupported_source | 来源获取失败、实体映射不确定或来源不在本期范围 |
| cancelled | 已停止，候选不提交 |

供应商将额度不足与速率限制均编码为 429 时，保留 `rate_limit` 和明确的“限流或配额不足”说明，不猜测剩余额度。使用量取供应商响应；未返回时不估算费用。

## 官方协议参考

- [DeepL 翻译请求](https://developers.deepl.com/api-reference/translate/request-translation)
- [硅基流动 Chat Completions](https://docs.siliconflow.cn/docs/api/chat-completions-post)、[Hunyuan-MT 模型说明](https://github.com/Tencent-Hunyuan/Hunyuan-MT/blob/main/README_CN.md)
- [OpenRouter 请求](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)、[上游路由](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Gemini API](https://ai.google.dev/api)、[结构化输出](https://ai.google.dev/gemini-api/docs/structured-output)
