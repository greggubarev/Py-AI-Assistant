"""Минимальный REST-клиент GigaChat API без сторонних пакетов."""
from __future__ import annotations

import json
import os
import ssl
import time
from urllib import error, parse, request
from uuid import uuid4


class ApiError(RuntimeError):
    pass


#Настройки клиента
class GigaChatAPI:
    def __init__(self, *, auth_key: str | None = None, ca_file: str | None = None):
        self.auth_key = auth_key or os.getenv("GIGACHAT_AUTH_KEY")
        if not self.auth_key:
            raise ValueError("Задайте GIGACHAT_AUTH_KEY")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat-2")
        self.embedding_model = os.getenv("GIGACHAT_EMBED_MODEL", "Embeddings")
        self.tls = ssl.create_default_context(cafile=ca_file or os.getenv("GIGACHAT_CA_FILE") or None)
        self._access_token = ""
        self._expires_at = 0.0

#Общий POST-запрос
    def _send(self, url: str, body: bytes, headers: dict[str, str]) -> dict:
        call = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(call, context=self.tls, timeout=60) as response:
                return json.load(response)
        except error.HTTPError as exc:
            # Не печатаем тело ошибки целиком: некоторые сервисы отражают параметры запроса.
            raise ApiError(f"GigaChat API: HTTP {exc.code} при обращении к {url}") from exc
        except error.URLError as exc:
            raise ApiError(f"Нет соединения с {url}: {exc.reason}") from exc
        except (ValueError, KeyError) as exc:
            raise ApiError(f"Некорректный JSON от {url}") from exc

#Пока токен действителен, берём его из памяти
    def _token(self) -> str:
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        body = parse.urlencode({"scope": self.scope}).encode("ascii")
        data = self._send(
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            body,
            {
                "Authorization": "Basic " + self.auth_key,
                "RqUID": str(uuid4()),
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            self._access_token = data["access_token"]
            expiry = float(data["expires_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError("Ответ OAuth не содержит корректный токен") from exc
        self._expires_at = expiry / 1000 if expiry > 10_000_000_000 else expiry
        return self._access_token

#Добавляем Bearer-токен и JSON-заголовки к вызовам модели
    def _post(self, path: str, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return self._send(
            "https://api.giga.chat/v1/" + path,
            body,
            {
                "Authorization": "Bearer " + self._token(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

#Метод чата
    def chat(self, messages: list[dict], *, functions: list[dict] | None = None,
             response_format: dict | None = None,
             function_call_mode: str | None = None) -> dict:
        payload = {"model": self.model, "messages": messages}
        if functions:
            payload["functions"] = functions
        if function_call_mode is not None:
            if function_call_mode not in ("auto", "none"):
                raise ValueError("Режим функции должен быть auto или none")
            payload["function_call"] = function_call_mode
        elif functions:
            payload["function_call"] = "auto"
        if response_format:
            payload["response_format"] = response_format
        data = self._post("chat/completions", payload)
        try:
            choice = data["choices"][0]
            return {"message": choice["message"], "finish_reason": choice.get("finish_reason"),
                    "usage": data.get("usage", {})}
        except (KeyError, IndexError, TypeError) as exc:
            raise ApiError("Ответ чата не содержит choices[0].message") from exc

#Векторное представление
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post("embeddings", {"model": self.embedding_model, "input": texts})
        try:
            entries = sorted(data["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in entries]
            if len(vectors) != len(texts) or any(not vector for vector in vectors):
                raise ValueError("Неполный набор векторов")
            return vectors
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiError("Ответ embeddings не содержит полный набор векторов") from exc

#Список доступных моделей
    def models(self) -> list[str]:
        """Показать модели, доступные текущему ключу."""
        call = request.Request(
            "https://api.giga.chat/v1/models",
            headers={"Authorization": "Bearer " + self._token(), "Accept": "application/json"},
            method="GET",
        )
        try:
            with request.urlopen(call, context=self.tls, timeout=30) as response:
                data = json.load(response)
            return [entry["id"] for entry in data["data"]]
        except (error.HTTPError, error.URLError, KeyError, ValueError, TypeError) as exc:
            raise ApiError("Не удалось получить список моделей") from exc
