"""Provider-independent configuration. Credentials never enter this model."""

import re
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, model_validator

FIELDS = {
    "title": "标题(title)",
    "plot": "剧情简介(plot)",
    "outline": "简短摘要(outline)",
    "tagline": "宣传语(tagline)",
}
PROVIDERS = {
    "deepl": "DeepL",
    "siliconflow_hunyuan": "硅基流动 · Hunyuan-MT",
    "openrouter": "OpenRouter",
    "gemini_native": "Gemini API",
    "chat_completions": "通用 Chat Completions",
}
DEFAULT_URLS = {
    "deepl": "https://api-free.deepl.com/v2/translate",
    "siliconflow_hunyuan": "https://api.siliconflow.cn/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "gemini_native": "https://generativelanguage.googleapis.com",
    "chat_completions": "",
}


def locale(value):
    value = value.strip().replace("_", "-")
    aliases = {
        "zh": "zh-CN",
        "zh-hans": "zh-CN",
        "zh-hant": "zh-TW",
        "zh-cn": "zh-CN",
        "zh-tw": "zh-TW",
        "zh-hk": "zh-TW",
    }
    if value.lower() in aliases:
        return aliases[value.lower()]
    parts = value.split("-")
    return "-".join(
        [parts[0].lower()] + [p.upper() if len(p) == 2 else p.title() for p in parts[1:]]
    )


class ProviderConfig(BaseModel):
    endpoint: str = ""
    model: str = ""
    deepl_plan: Literal["free", "pro"] = "free"
    api_version: Literal["v1", "v1beta"] = "v1beta"
    response_mode: Literal["prompt_json", "json_object", "json_schema"] = "prompt_json"
    max_chars: int = Field(default=12000, ge=100, le=100000)
    max_output_tokens: int = Field(default=4096, ge=128, le=32768)

    @model_validator(mode="after")
    def check(self):
        if self.endpoint:
            parsed = urlsplit(self.endpoint)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("服务地址必须为不含凭据、查询参数和片段的 HTTP(S) 地址")
        if self.model and not re.fullmatch(r"[\w./:@+-]+", self.model):
            raise ValueError("模型 ID 格式无效")
        return self


class Policy(BaseModel):
    id: str
    name: str = "简体中文补全"
    target_language: str = "zh-CN"
    fields: list[str] = Field(default_factory=lambda: ["plot", "outline"])
    kinds: list[Literal["movie", "tv", "season", "episode"]] = Field(
        default_factory=lambda: ["movie", "tv", "season", "episode"]
    )
    mode: Literal["source_only", "translate"] = "translate"
    fallback_languages: list[str] = Field(default_factory=lambda: ["zh-TW", "en-US", "original"])
    chinese_conversion: bool = True
    prefer_official: bool = True

    @model_validator(mode="after")
    def check(self):
        if not self.id.strip() or not self.fields or set(self.fields) - set(FIELDS):
            raise ValueError("策略需要 ID 和有效翻译字段")
        self.target_language = locale(self.target_language)
        if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", self.target_language):
            raise ValueError("目标语言代码无效")
        self.fields = list(dict.fromkeys(self.fields))
        self.fallback_languages = list(
            dict.fromkeys(locale(x) if x != "original" else x for x in self.fallback_languages)
        )
        if any(
            x != "original" and not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", x)
            for x in self.fallback_languages
        ):
            raise ValueError("备用语言代码无效")
        return self


def provider_defaults():
    result = {k: ProviderConfig(endpoint=v) for k, v in DEFAULT_URLS.items()}
    result["siliconflow_hunyuan"].model = "tencent/Hunyuan-MT-7B"
    result["gemini_native"].response_mode = "json_schema"
    return result


class Config(BaseModel):
    version: int = 1
    enabled: bool = False
    global_hook: bool = False
    active_provider: str = ""
    provider_configs: dict[str, ProviderConfig] = Field(default_factory=provider_defaults)
    policies: list[Policy] = Field(default_factory=lambda: [Policy(id="default")])
    default_policy: str = "default"
    timeout: int = Field(default=30, ge=5, le=120)
    concurrency: int = Field(default=1, ge=1, le=8)
    source_hours: int = Field(default=24, ge=1, le=720)
    missing_days: int = Field(default=7, ge=1, le=365)
    cache_days: int = Field(default=180, ge=1, le=3650)
    history_days: int = Field(default=30, ge=1, le=3650)

    @model_validator(mode="after")
    def check(self):
        if self.active_provider and self.active_provider not in PROVIDERS:
            raise ValueError("未知翻译服务")
        if set(self.provider_configs) - set(PROVIDERS):
            raise ValueError("配置包含未注册的翻译服务")
        self.provider_configs = {**provider_defaults(), **self.provider_configs}
        ids = [p.id for p in self.policies]
        if len(set(ids)) != len(ids) or self.default_policy not in ids:
            raise ValueError("策略 ID 必须唯一，默认策略必须存在")
        return self
