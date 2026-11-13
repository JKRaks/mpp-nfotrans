"""Local HTTP fixtures for an external tester. Never forwards requests to a vendor.

Run explicitly: python3 tests/translation/mock_server.py --port 18765
POST /<provider>/<scenario>; GET /calls lists redacted request shapes.
This file is a fixture, not an executed acceptance test.
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROVIDERS = {"deepl", "siliconflow_hunyuan", "openrouter", "gemini_native", "chat_completions"}


class Handler(BaseHTTPRequestHandler):
    calls = []
    lock = threading.Lock()

    def log_message(self, *args): pass

    def send(self, status, body, raw=False):
        data = body.encode() if raw else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        if status == 429: self.send_header("Retry-After", "3")
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass

    def do_GET(self):
        if self.path != "/calls": return self.send(404, {})
        with self.lock: calls = list(self.calls)
        self.send(200, calls)

    def do_DELETE(self):
        if self.path != "/calls": return self.send(404, {})
        with self.lock: self.calls.clear()
        self.send(200, {"ok": True})

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if len(parts) != 2 or parts[0] not in PROVIDERS: return self.send(404, {})
        provider, scenario = parts
        length = int(self.headers.get("Content-Length", 0))
        if length > 1024 * 1024: return self.send(413, {})
        try: body = json.loads(self.rfile.read(length))
        except ValueError: return self.send(400, {})
        auth = self.headers.get("Authorization", "")
        valid_auth = (self.headers.get("x-goog-api-key") == "fixture-token" if provider == "gemini_native" else
                      auth == ("DeepL-Auth-Key " if provider == "deepl" else "Bearer ") + "fixture-token")
        if not valid_auth: return self.send(401, {"error": {"code": "fixture_auth"}})
        # Retain request bodies from synthetic fixtures, never credential headers.
        with self.lock:
            self.calls.append({"provider": provider, "scenario": scenario, "body": body})
            number = sum(c["provider"] == provider and c["scenario"] == scenario for c in self.calls)
        if scenario.startswith("http-"):
            return self.send(int(scenario[5:]), {"error": {"code": "fixture_failure", "message": "fixture-token must never appear in product errors"}})
        if scenario == "delay": time.sleep(7)
        if scenario == "malformed": return self.send(200, "{broken", raw=True)
        try:
            if provider == "deepl":
                assert isinstance(body["text"], list) and "messages" not in body and body["target_lang"]
                translations = [{"text": "" if scenario == "empty" or scenario == "partial" and i else "译文：" + value,
                                 "detected_source_language": "EN", "billed_characters": len(value)} for i, value in enumerate(body["text"])]
                return self.send(200, {"translations": translations[:-1] if scenario == "missing" else translations})
            if provider == "gemini_native":
                assert "messages" not in body and "contents" in body
                request = json.loads(body["contents"][0]["parts"][0]["text"])
            elif provider == "siliconflow_hunyuan":
                assert len(body["messages"]) == 1 and "response_format" not in body and body["stream"] is False
                if scenario == "partial" and number % 2 == 0: return self.send(429, {"error": {"code": "rate_limit"}})
                request = None
            else:
                assert body["stream"] is False
                request = json.loads(body["messages"][-1]["content"])
                if provider == "openrouter": assert body["provider"]["allow_fallbacks"] is False and "models" not in body
            if request is None:
                text = "" if scenario == "empty" else "旅人回到了家乡。"
            else:
                value = {key: "" if scenario == "empty" else "译文：" + value for key, value in request["texts"].items()}
                if scenario in {"partial", "missing"} and value: value.pop(list(value)[-1])
                if scenario == "unknown": value["not_requested"] = "不应被接受"
                text = json.dumps(value, ensure_ascii=False)
            if provider == "gemini_native":
                if scenario == "blocked": return self.send(200, {"promptFeedback": {"blockReason": "SAFETY"}})
                return self.send(200, {"candidates": [{"finishReason": "MAX_TOKENS" if scenario == "truncated" else "STOP",
                    "content": {"parts": [{"text": text}]}}], "modelVersion": "fixture-gemini", "usageMetadata": {"totalTokenCount": 20}})
            return self.send(200, {"id": "fixture-request", "model": body["model"], "usage": {"total_tokens": 20},
                "choices": [{"finish_reason": "length" if scenario == "truncated" else "content_filter" if scenario == "blocked" else "stop",
                             "message": {"role": "assistant", "content": text}}]})
        except (AssertionError, KeyError, TypeError, IndexError, ValueError):
            self.send(422, {"error": {"code": "fixture_contract_mismatch"}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    print(f"Synthetic translation fixtures: http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
