"""Explicit injection helpers; importing this module makes no network requests."""
import copy
import importlib
import sys
import types
from pathlib import Path
from urllib.parse import urlsplit
import requests


def load_core():
    """Load pure core without executing MoviePilot-dependent plugin __init__.py."""
    name = "metadatatranslate_fixture"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(Path(__file__).resolve().parents[2] / "plugins.v3/metadatatranslate")]
        sys.modules[name] = package
    return {part: importlib.import_module(name + "." + part) for part in ("config", "contracts", "providers", "service", "storage", "xmlops")}


def provider_factory(core, base="http://127.0.0.1:18765", scenario="success"):
    """Inject a local transport, including for DeepL's fixed production endpoint."""
    parsed = urlsplit(base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("Fixture transport only accepts a loopback HTTP server")

    def factory(name, config, secret):
        provider = core["providers"].create_provider(name, config, secret)
        provider.session.close()

        class LocalSession(requests.Session):
            def post(self, url, **kwargs):
                # The original vendor address is deliberately never sent.
                return super().post(base.rstrip("/") + "/" + name + "/" + scenario, **kwargs)

        provider.session = LocalSession()
        provider.session.trust_env = False
        return provider
    return factory


class FakeSource:
    def __init__(self, translations=None):
        self.calls = 0
        self.translations = translations if translations is not None else {
            "en-US": {"title": "A Journey", "overview": "A traveler returns home.", "tagline": "Every journey has a beginning."}}

    def fetch(self, identity):
        self.calls += 1
        return {"identity": {**identity, "entity_id": 42}, "translations": copy.deepcopy(self.translations),
                "original_language": "en", "supported_fields": ["title", "plot", "outline", "tagline"]}
