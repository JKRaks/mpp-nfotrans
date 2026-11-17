"""MoviePilot metadata translation plugin; never writes media files."""

import threading
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.deps import get_current_active_manage_user
from app.sdk.plugin import _PluginBase, PluginManager, ModuleManager
from app.sdk.logging import logger
from .config import Config, PROVIDERS
from .contracts import TranslationError
from .service import TranslationService
from .source import source_identity
from .storage import Storage


class SaveSettings(BaseModel):
    config: Config
    secrets: dict[str, str | None] = Field(default_factory=dict)


class Identity(BaseModel):
    kind: Literal["movie", "tv", "season", "episode"]
    tmdb_id: int = Field(gt=0)
    season: int | None = Field(default=None, ge=0)
    episode: int | None = Field(default=None, ge=1)
    lookup_episode: int | None = Field(default=None, ge=1)
    episode_group: str | None = None
    title: str = ""
    original_language: str | None = None


class Preview(BaseModel):
    identity: Identity
    nfo: str = Field(max_length=10000000)
    policy_id: str = "default"
    fields: list[str] | None = None
    overwrite: bool = False
    force: bool = False


class DeleteRecords(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=1000)


class ClearCache(BaseModel):
    kind: Literal["source", "translation", "all"] = "translation"


class MetadataTranslate(_PluginBase):
    plugin_name = "元数据翻译"
    plugin_desc = "补齐 TMDB 缺失语言；支持 DeepL、混元、OpenRouter、Gemini 和通用兼容接口。"
    plugin_icon = "https://raw.githubusercontent.com/JKRaks/mpp-nfotrans/main/plugins.v3/metadatatranslate/icon.png"
    plugin_version = "1.1.4"
    plugin_author = "NfoCheck Contributors"
    author_url = ""
    plugin_config_prefix = "metadatatranslate_"
    plugin_order = 49
    auth_level = 1
    _lifecycle_lock = threading.RLock()
    _checking_modules = threading.local()

    def init_plugin(self, config=None):
        with self._lifecycle_lock:
            self.stop_service()
            parsed = Config.model_validate(config or {})
            self.service = TranslationService(parsed, Storage(self.get_data_path()))

    def stop_service(self):
        with self._lifecycle_lock:
            service = getattr(self, "service", None)
            if service:
                service.close()
                self.service = None

    def get_state(self):
        return bool(
            getattr(self, "service", None)
            and self.service.config.enabled
            and not self.service.stop.is_set()
        )

    @staticmethod
    def get_render_mode():
        return "vue", "dist/assets"

    def get_form(self):
        return [], Config().model_dump()

    def get_page(self):
        return []

    def get_command(self):
        return []

    def get_service(self):
        return []

    def translation_service(self):
        """Versioned in-process service, resolved via PluginManager.get_plugin_attr."""
        return self.service

    identify = staticmethod(source_identity)

    def hook_conflicts(self):
        if getattr(self._checking_modules, "active", False):
            return []
        self._checking_modules.active = True
        try:
            manager = PluginManager()
            found = []
            for pid in manager.get_running_plugin_ids():
                getter = manager.get_plugin_attr(pid, "get_module")
                if not getter or getattr(getter, "__self__", None) is self:
                    continue
                try:
                    state = manager.get_plugin_attr(pid, "get_state")
                    if callable(state) and not state():
                        continue
                    table = getter() or {}
                    if "metadata_nfo" in table:
                        found.append(pid)
                except Exception:
                    found.append(pid)
            return found
        finally:
            self._checking_modules.active = False

    def get_module(self):
        if not self.get_state() or not self.service.config.global_hook:
            return {}
        if getattr(self._checking_modules, "active", False):
            return {"metadata_nfo": self.metadata_nfo}
        if self.hook_conflicts():
            return {}
        return {"metadata_nfo": self.metadata_nfo}

    @staticmethod
    def base_nfo(meta, mediainfo, season=None, episode=None):
        # Call only built-in module instances. Never re-enter ScrapingChain.metadata_nfo.
        for module in sorted(
            ModuleManager().get_running_modules("metadata_nfo"), key=lambda m: m.get_priority()
        ):
            value = module.metadata_nfo(
                meta=meta, mediainfo=mediainfo, season=season, episode=episode
            )
            if value:
                return value
        return None

    def metadata_nfo(self, meta, mediainfo, season=None, episode=None):
        if not self.get_state() or self.hook_conflicts():
            return None
        service = self.service
        try:
            with service.lease() as token:
                base = self.base_nfo(meta, mediainfo, season, episode)
                if not base:
                    return base
                try:
                    identity = source_identity(meta, mediainfo, season, episode)
                    return service.prepare_nfo(identity, base, token=token, generated=True)["nfo"]
                except Exception as exc:
                    code = exc.code if isinstance(exc, TranslationError) else type(exc).__name__
                    logger.warning(f"元数据翻译候选未增强：{code}")
                    try:
                        service.storage.record(
                            service.config.active_provider,
                            "failed",
                            "官方候选保留原文",
                            {"error_code": code},
                        )
                    except Exception:
                        logger.warning("元数据翻译调用记录未保存，仍保留官方候选")
                    return base
        except TranslationError:
            return None

    def api_settings(self, user=Depends(get_current_active_manage_user)):
        service = self.service
        return {
            "config": service.config.model_dump(),
            **service.describe(),
            "secret_set": {k: bool(v) for k, v in service.storage.secrets().items()},
            "hook_conflicts": self.hook_conflicts(),
            "cache": service.storage.stats(),
        }

    def api_save(self, payload: SaveSettings, user=Depends(get_current_active_manage_user)):
        if set(payload.secrets) - set(PROVIDERS):
            raise HTTPException(422, "未知密钥类型")
        with self._lifecycle_lock:
            service = self.service
            with service.gate:
                if service.leases:
                    raise HTTPException(409, "翻译任务运行中，请停止或等待结束后保存")
                service.storage.save_secrets(payload.secrets)
                self.update_config(payload.config.model_dump())
                self.init_plugin(payload.config.model_dump())
        return {"ok": True}

    @staticmethod
    def call(function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except TranslationError as exc:
            raise HTTPException(422, exc.result()) from None
        except (OSError, RuntimeError):
            raise HTTPException(503, "翻译存储或运行状态不可用") from None

    def api_test(self, user=Depends(get_current_active_manage_user)):
        return self.call(self.service.test_connection)

    def api_preview(self, payload: Preview, user=Depends(get_current_active_manage_user)):
        identity = payload.identity.model_dump()
        if identity["kind"] in {"season", "episode"} and identity["season"] is None:
            raise HTTPException(422, "季或单集需要季号")
        if identity["kind"] == "episode" and identity["episode"] is None:
            raise HTTPException(422, "单集需要集号")
        identity["lookup_episode"] = identity["lookup_episode"] or identity["episode"]
        return self.call(
            self.service.prepare_nfo,
            identity,
            payload.nfo,
            payload.policy_id,
            payload.fields,
            overwrite=payload.overwrite,
            force=payload.force,
        )

    def api_history(
        self,
        page: int = 1,
        page_size: int = 30,
        status: str = "",
        provider: str = "",
        user=Depends(get_current_active_manage_user),
    ):
        return self.service.storage.history(page, page_size, status, provider)

    def api_detail(self, id: int, user=Depends(get_current_active_manage_user)):
        value = self.service.storage.detail(id)
        if value is None:
            raise HTTPException(404, "记录不存在")
        return value

    def api_delete(self, payload: DeleteRecords, user=Depends(get_current_active_manage_user)):
        self.service.storage.delete_calls(payload.ids)
        return {"ok": True}

    def api_clear(self, payload: ClearCache, user=Depends(get_current_active_manage_user)):
        with self.service.gate:
            if self.service.leases:
                raise HTTPException(409, "任务运行中暂不可清理缓存")
            self.service.storage.clear(payload.kind)
        return {"ok": True, "cache": self.service.storage.stats()}

    def get_api(self):
        return [
            {
                "path": "/" + name,
                "endpoint": endpoint,
                "methods": [method],
                "auth": "bear",
                "summary": name,
            }
            for name, endpoint, method in [
                ("settings", self.api_settings, "GET"),
                ("settings", self.api_save, "POST"),
                ("test", self.api_test, "POST"),
                ("preview", self.api_preview, "POST"),
                ("history", self.api_history, "GET"),
                ("detail", self.api_detail, "GET"),
                ("delete", self.api_delete, "POST"),
                ("cache/clear", self.api_clear, "POST"),
            ]
        ]
