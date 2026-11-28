

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from app.config import DEFAULT_CONFIG_DIR


@dataclass
class AIResponse:
    ok: bool
    text: str = ""
    error: str = ""
    model: str = ""


GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
]

GEMINI_DIRECT_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]


def _clean_key(raw: str) -> str:
    val = raw.strip()
    if "=" in val and not val.startswith(("AIza", "sk-", "gsk_")):
        val = val.split("=", 1)[1].strip()
    return val.strip('"').strip("'")


def _read_key_file(name: str) -> str:
    kp = DEFAULT_CONFIG_DIR / name
    if kp.is_file():
        try:
            return _clean_key(kp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return ""


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


class GeminiClient:
    def __init__(self, model: str = "llama-3.3-70b-versatile", timeout: int = 20) -> None:
        _load_local_env()
        self.default_model = model
        self.timeout = timeout

    def _get_json(self, url: str, headers: dict[str, str] | None = None) -> dict | None:
        req_headers = {"User-Agent": "N1BroX-Terminal/1.0", **(headers or {})}
        req = urllib.request.Request(url, headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            return None

    def _post_json(self, url: str, payload: dict, headers: dict[str, str]) -> tuple[int, dict | str]:
        req_headers = {"User-Agent": "N1BroX-Terminal/1.0", **headers}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return resp.status, json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                return e.code, json.loads(body)
            except Exception:
                return e.code, body
        except Exception as exc:
            return 0, str(exc)

    # ── 1. Groq (Ultra-fast LPU) ──
    def _discover_groq_models(self, api_key: str) -> list[str]:
        data = self._get_json(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if not isinstance(data, dict):
            return []
        skip = ("whisper", "tts", "guard", "vision", "orpheus")
        found: list[str] = []
        for item in data.get("data", []):
            mid = item.get("id", "")
            if mid and not any(t in mid.lower() for t in skip):
                found.append(mid)
        return found[:4]

    def _call_groq(self, prompt: str, api_key: str) -> AIResponse:
        candidates = list(GROQ_MODELS)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        last_err = ""
        tried: set[str] = set()
        idx = 0

        while idx < len(candidates):
            m = candidates[idx]
            idx += 1
            if m in tried:
                continue
            tried.add(m)

            payload = {"model": m, "messages": [{"role": "user", "content": prompt}]}
            status, body = self._post_json("https://api.groq.com/openai/v1/chat/completions", payload, headers)
            if status == 200 and isinstance(body, dict):
                try:
                    text = body["choices"][0]["message"]["content"].strip()
                    if text:
                        return AIResponse(ok=True, text=text, model=f"groq/{m}")
                except Exception:
                    pass

            detail = body.get("error", {}).get("message", "") if isinstance(body, dict) else str(body)[:140]
            last_err = f"Groq ({m}) HTTP {status}: {detail}"
            if status == 404 and idx == len(candidates):
                for disc in self._discover_groq_models(api_key):
                    if any(bad in disc.lower() for bad in ("allam", "whisper", "guard", "tts", "playai")):
                        continue
                    if disc not in tried:
                        candidates.append(disc)
            if status not in (0, 404, 429, 500, 502, 503):
                break

        return AIResponse(ok=False, error=last_err or "Groq request failed.")

    # ── 2. Google Gemini Direct ──
    def _discover_google_models(self, api_key: str) -> list[str]:
        data = self._get_json(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
        if not isinstance(data, dict):
            return []
        skip = ("embedding", "tts", "audio", "image", "veo", "imagen", "robotics", "computer-use", "deep-research", "aqa")
        found: list[str] = []
        for item in data.get("models", []):
            methods = item.get("supportedGenerationMethods", [])
            name = item.get("name", "").removeprefix("models/")
            if "generateContent" in methods and "gemini" in name and not any(t in name for t in skip):
                found.append(name)
        found.sort(key=lambda n: (0 if "flash-lite" in n else 1 if "flash" in n else 2, 1 if "preview" in n else 0))
        return found[:4]

    def _call_google_direct(self, prompt: str, api_key: str) -> AIResponse:
        candidates = self._discover_google_models(api_key) or list(GEMINI_DIRECT_MODELS)
        last_err = ""
        for m in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            payloads = [
                {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}},
                {"contents": [{"parts": [{"text": prompt}]}]},
            ]
            status = 0
            for idx, payload in enumerate(payloads):
                status, body = self._post_json(url, payload, {"Content-Type": "application/json"})
                if status == 200 and isinstance(body, dict):
                    try:
                        parts = body["candidates"][0]["content"]["parts"]
                        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                        if not text:
                            text = "".join(p.get("text", "") for p in parts).strip()
                        if text:
                            return AIResponse(ok=True, text=text, model=f"google/{m}")
                    except Exception:
                        pass
                detail = body.get("error", {}).get("message", "") if isinstance(body, dict) else str(body)[:140]
                last_err = f"Google ({m}) HTTP {status}: {detail}"
                if status == 400 and idx == 0:
                    continue
                break
            if status not in (0, 400, 404, 429, 500, 502, 503, 504):
                break
        return AIResponse(ok=False, error=last_err or "Google Gemini request failed.")

    # ── 3. OpenRouter Free Fallback ──
    def _discover_openrouter_free(self, api_key: str) -> list[str]:
        models = ["openrouter/free"]
        data = self._get_json("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"})
        if isinstance(data, dict):
            for item in data.get("data", []):
                mid = item.get("id", "")
                if mid.endswith(":free") and mid not in models:
                    models.append(mid)
                if len(models) >= 5:
                    break
        return models

    def _call_openrouter(self, prompt: str, api_key: str, preferred_model: str) -> AIResponse:
        models = self._discover_openrouter_free(api_key)
        if preferred_model and preferred_model not in models and ":free" in preferred_model:
            models.insert(0, preferred_model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://n1brox.local",
            "X-Title": "N1BroX Terminal",
        }
        last_err = ""
        for m in models:
            payload = {"model": m, "messages": [{"role": "user", "content": prompt}]}
            status, body = self._post_json("https://openrouter.ai/api/v1/chat/completions", payload, headers)
            if status == 200 and isinstance(body, dict):
                try:
                    text = body["choices"][0]["message"]["content"].strip()
                    if text:
                        return AIResponse(ok=True, text=text, model=f"openrouter/{m}")
                except Exception:
                    pass
            if status in (0, 404, 429, 502, 503):
                last_err = f"OpenRouter ({m}) HTTP {status}"
                continue
            last_err = f"OpenRouter HTTP {status}: {str(body)[:160]}"
            break
        return AIResponse(ok=False, error=last_err or "OpenRouter free models unavailable.")

    def generate(self, prompt: str, model: str | None = None) -> AIResponse:
        _load_local_env()
        groq_key = _clean_key(os.environ.get("GROQ_API_KEY") or _read_key_file("groq_key"))
        gemini_key = _clean_key(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or _read_key_file("gemini_key")
        )
        openrouter_key = _clean_key(os.environ.get("OPENROUTER_API_KEY") or _read_key_file("openrouter_key"))

        errors: list[str] = []

        if groq_key:
            res = self._call_groq(prompt, groq_key)
            if res.ok:
                return res
            errors.append(res.error)

        if gemini_key:
            res = self._call_google_direct(prompt, gemini_key)
            if res.ok:
                return res
            errors.append(res.error)

        if openrouter_key:
            res = self._call_openrouter(prompt, openrouter_key, model or self.default_model)
            if res.ok:
                return res
            errors.append(res.error)

        if errors:
            return AIResponse(ok=False, error=" | ".join(errors))

        return AIResponse(
            ok=False,
            error="No API key found in ~/.config/n1brox-terminal/ (groq_key, gemini_key, or openrouter_key).",
        )
