"""Translation orchestration, versioned leases and field-level provenance."""
import copy
import threading
import time
import uuid
from contextlib import contextmanager
from .config import FIELDS, PROVIDERS, locale
from .contracts import ADAPTER_VERSION, CONTRACT_VERSION, Stop, TextItem, TranslationError, TranslationRequest, digest
from .providers import create_provider
from .source import TmdbSource, value_at, FIELD_SOURCE
from .xmlops import parse, patch, texts, text_hash

DONE = {"kept", "translated", "official", "converted", "not_applicable"}


class TranslationService:
    def __init__(self, config, storage, source=None, provider_factory=create_provider):
        self.config, self.storage = config, storage
        self.source = source or TmdbSource()
        self.provider_factory = provider_factory
        self.stop = threading.Event()
        self.gate = threading.RLock()
        self.leases = set()
        self.semaphore = threading.BoundedSemaphore(config.concurrency)
        self.flights = [threading.Lock() for _ in range(64)]
        self.revision = digest(config.model_dump())
        self.storage.prune(config.history_days)

    def describe(self):
        return {"contract_version": CONTRACT_VERSION, "enabled": self.config.enabled and not self.stop.is_set(),
                "active_provider": self.config.active_provider, "revision": self.revision, "fields": FIELDS,
                "policies": [p.model_dump() for p in self.config.policies], "default_policy": self.config.default_policy,
                "busy": bool(self.leases), "providers": PROVIDERS}

    def begin_batch(self):
        with self.gate:
            if not self.config.enabled or self.stop.is_set():
                raise TranslationError("unavailable", "元数据翻译插件未启用或正在停止")
            token = uuid.uuid4().hex
            self.leases.add(token)
            return token

    def end_batch(self, token):
        with self.gate: self.leases.discard(token)

    @contextmanager
    def lease(self, token=None):
        owned = token is None
        if owned: token = self.begin_batch()
        with self.gate:
            if token not in self.leases or self.stop.is_set():
                raise TranslationError("cancelled", "翻译批次已结束")
        try: yield token
        finally:
            if owned: self.end_batch(token)

    def close(self):
        self.stop.set()
        end = time.monotonic() + self.config.timeout + 5
        while self.leases and time.monotonic() < end:
            time.sleep(.05)
        if self.leases: raise RuntimeError("翻译任务仍在退出，请稍后重载")
        self.storage.close()

    def policy(self, policy_id, fields=None):
        policy = next((p for p in self.config.policies if p.id == (policy_id or self.config.default_policy)), None)
        if not policy: raise TranslationError("policy_missing", "翻译策略不存在")
        if fields is not None and (not fields or set(fields) - set(policy.fields)):
            raise TranslationError("unsupported_field", "所选字段必须属于翻译策略的字段范围")
        return policy, list(fields if fields is not None else policy.fields)

    def snapshot(self, identity):
        key = digest(identity)
        cached = self.storage.get("source", key)
        if cached is not None: return cached
        result = self.source.fetch(identity)
        self.storage.put("source", key, result, self.config.source_hours * 3600)
        return result

    def assess(self, identity, nfo, policy_id=None, fields=None, provenance=None, token=None, overwrite=False, force=False):
        with self.lease(token):
            policy, fields = self.policy(policy_id, fields)
            current = texts(parse(nfo))
            if identity["kind"] not in policy.kinds:
                return {"fields": {f: {"status": "not_applicable", "message": "策略未选择该媒体层级"} for f in fields}, "identity": identity}
            source = self.snapshot(identity)
            results = {}
            provenance = provenance or {}
            for field in fields:
                local = current[field]
                if field not in source["supported_fields"]:
                    results[field] = {"status": "not_applicable", "message": "该来源层级不支持此字段"}; continue
                if local is None:
                    results[field] = {"status": "language_unknown", "message": "存在重复文字节点"}; continue
                official, official_lang = value_at(source, policy.target_language, field)
                previous = provenance.get(field, {})
                owned = bool(previous.get("output_hash") and previous["output_hash"] == text_hash(local))
                same_target = owned and previous.get("target_language") == policy.target_language
                languages = [lang for lang, vals in source["translations"].items() if local and local == (vals.get(FIELD_SOURCE[field]) or "").strip()]
                is_target = bool(local and official and local == official)
                base = {"before": local, "target_language": policy.target_language, "source_identity": source["identity"]}
                if previous and not owned and not overwrite:
                    results[field] = {**base, "status": "protected", "message": "字段已被修改，默认保留"}; continue
                if is_target or (same_target and not force and (not official or not policy.prefer_official or previous.get("origin") == "official")):
                    results[field] = {**base, "status": "kept", "message": "已有目标语言内容"}; continue
                if local and not owned and not languages and not overwrite:
                    results[field] = {**base, "status": "language_unknown", "message": "本地内容无法与来源对应，默认保留"}; continue
                if official and not (force and owned and previous.get("origin") in {"translated", "converted"}):
                    results[field] = {**base, "status": "source_available", "text": official, "source_language": official_lang, "origin": "official"}; continue
                found = None
                for fallback in policy.fallback_languages:
                    language = source["original_language"] if fallback == "original" else fallback
                    if not language: continue
                    value, actual_language = value_at(source, language, field)
                    if not value: continue
                    convertible = policy.chinese_conversion and actual_language.startswith("zh") and policy.target_language.startswith("zh")
                    if convertible or policy.mode == "translate":
                        found = {**base, "status": "needs_translation", "source_text": value, "source_language": actual_language,
                                 "origin": "converted" if convertible else "translated"}; break
                results[field] = found or {**base, "status": "no_source_text", "message": "无可用目标译文或备用原文", "retryable": True,
                                           "next_retry_at": time.time() + self.config.missing_days * 86400}
            return {"fields": results, "identity": source["identity"], "policy": policy.model_dump(), "revision": self.revision}

    def translate(self, items, target, context, stop=None, force=False, identity=None):
        name = self.config.active_provider
        if not name: raise TranslationError("not_configured", "尚未选择全局翻译服务")
        config = self.config.provider_configs[name]
        secret = self.storage.secrets().get(name, "")
        provider = self.provider_factory(name, config, secret)
        effective_context = context if provider.capabilities().get("context") else {}
        fingerprint = digest([name, config.model_dump(), ADAPTER_VERSION, identity])
        # A bounded lock stripe coalesces matching requests without an ever-growing lock map.
        key = digest([fingerprint, target, effective_context, [(i.id, i.text, i.source_language) for i in items]])
        deadline = time.monotonic() + self.config.timeout
        request = TranslationRequest(items, target, effective_context, deadline, Stop(self.stop, stop))
        lock = self.flights[int(key[:4], 16) % len(self.flights)]
        acquired = False
        try:
            while not lock.acquire(timeout=.1): request.check()
            acquired = True
            result, missing, cache_keys = {}, [], {}
            for item in items:
                cache_keys[item.id] = digest([fingerprint, target, effective_context, item.source_language, item.text])
                cached = None if force else self.storage.get("translation", cache_keys[item.id])
                if cached is not None: result[item.id] = {**cached, "cache_hit": True}
                else: missing.append(item)
            if missing:
                while not self.semaphore.acquire(timeout=.1): request.check()
                try:
                    request.items = missing
                    request.check()
                    provider.validate_config()
                    fresh = provider.translate_batch(request)
                    # Adapters validate each response deadline. A later item timing out must
                    # not discard earlier successes from a sequential provider.
                    if request.stop.is_set(): raise TranslationError("cancelled", "翻译任务已停止")
                    for item in missing:
                        value = fresh.get(item.id) or TranslationError("invalid_response", "缺少该字段的翻译结果").result()
                        if value.get("status") == "translated":
                            self.storage.put("translation", cache_keys[item.id], value, self.config.cache_days * 86400)
                        result[item.id] = {**value, "cache_hit": False}
                finally: self.semaphore.release()
            return result
        finally:
            if acquired: lock.release()
            provider.close()

    def prepare_nfo(self, identity, nfo, policy_id=None, fields=None, provenance=None, token=None, stop=None, overwrite=False, force=False, generated=False, deferred=None):
        with self.lease(token) as active:
            assessed = self.assess(identity, nfo, policy_id, fields, provenance, active, overwrite or generated, force)
            results = assessed["fields"]
            if not force and not overwrite:
                for field, previous in (deferred or {}).items():
                    if field in results and previous.get("next_retry_at", 0) > time.time() and results[field]["status"] not in DONE | {"source_available"}:
                        results[field] = copy.deepcopy(previous)
            replacements, items, field_ids = {}, [], {}
            for field, result in results.items():
                if result["status"] == "source_available":
                    replacements[field] = result["text"]; result["status"] = "official"
                elif result["status"] == "needs_translation":
                    if result["origin"] == "converted":
                        try:
                            from zhconv import convert
                            replacements[field] = convert(result["source_text"], "zh-hans" if result["target_language"] == "zh-CN" else "zh-hant")
                            result.update(status="converted", text=replacements[field])
                        except ImportError:
                            result.update(TranslationError("not_configured", "缺少 zhconv 繁简转换依赖").result())
                    else:
                        item_id = digest([result["source_text"], result["source_language"]])[:16]
                        field_ids[field] = item_id
                        if not any(i.id == item_id for i in items): items.append(TextItem(item_id, result["source_text"], result["source_language"]))
            if items:
                try:
                    context = {"title": identity.get("title", ""), "kind": identity["kind"], "season": identity.get("season"), "episode": identity.get("episode")}
                    translated = self.translate(items, assessed["policy"]["target_language"], context, stop, force, assessed["identity"])
                except TranslationError as exc:
                    if exc.code == "cancelled": raise
                    translated = {i.id: exc.result() for i in items}
                for field, item_id in field_ids.items():
                    results[field].update(translated[item_id])
                    if results[field]["status"] == "translated": replacements[field] = results[field]["text"]
            if Stop(self.stop, stop).is_set(): raise TranslationError("cancelled", "任务已停止，译文未提交")
            candidate, changed = patch(nfo, replacements)
            written = {}
            for field, result in results.items():
                if field in replacements:
                    written[field] = {"output_hash": text_hash(replacements[field]), "target_language": result["target_language"],
                                      "origin": result["status"], "source_hash": text_hash(result.get("source_text", result.get("text", ""))),
                                      "source_language": result.get("source_language"), "provider": self.config.active_provider,
                                      "revision": self.revision, "identity": assessed["identity"]}
            pending = [field for field, result in results.items() if result["status"] not in DONE]
            output = {"nfo": candidate.decode("utf-8"), "fields": results, "changed_fields": changed, "pending_fields": pending,
                      "provenance": written, "revision": self.revision, "identity": assessed["identity"]}
            record = {k: v for k, v in output.items() if k != "nfo"}
            output["record_id"] = self.storage.record(self.config.active_provider, "partial" if pending else "complete",
                                                      f"{identity['kind']} · {len(changed)} 字段候选变化 · {len(pending)} 字段待处理", record)
            return output

    def test_connection(self):
        with self.lease():
            result = self.translate([TextItem("sample", "A traveler returns home.", "en")], "zh-CN", {}, force=True)
            self.storage.record(self.config.active_provider, result["sample"]["status"], "手动连接测试", result)
            return result
