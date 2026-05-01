import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen3:latest"


class OllamaError(RuntimeError):
    pass


def get_ollama_config(app_config=None):
    app_config = app_config or {}
    return {
        "host": (app_config.get("OLLAMA_HOST") or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/"),
        "model": app_config.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL,
    }


def list_models(app_config=None, timeout=5):
    config = get_ollama_config(app_config)
    payload = _request_json(f"{config['host']}/api/tags", timeout=timeout)
    return payload.get("models", [])


def chat(messages, app_config=None, timeout=120):
    config = get_ollama_config(app_config)
    cleaned_messages = _normalize_messages(messages)

    payload = {
        "model": config["model"],
        "messages": cleaned_messages,
        "stream": False,
        "think": False,
    }
    response = _request_json(f"{config['host']}/api/chat", payload=payload, timeout=timeout)
    assistant_message = response.get("message") or {}
    content = assistant_message.get("content")

    if not isinstance(content, str):
        raise OllamaError("Ollama returned an unexpected chat response.")

    return {
        "model": response.get("model") or config["model"],
        "message": {"role": "assistant", "content": content},
        "done": response.get("done", True),
    }


def _normalize_messages(messages):
    if not isinstance(messages, list):
        raise ValueError("messages must be a list.")

    cleaned = []
    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            continue

        content = content.strip()
        if content:
            cleaned.append({"role": role, "content": content})

    if not cleaned or cleaned[-1]["role"] != "user":
        raise ValueError("The last chat message must be from the user.")

    return cleaned


def _request_json(url, payload=None, timeout=30):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise OllamaError(f"Could not connect to Ollama: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaError("Ollama request timed out.") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise OllamaError("Ollama returned invalid JSON.") from exc
