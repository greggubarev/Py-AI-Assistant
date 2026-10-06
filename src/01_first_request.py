"""Первый диалог через GigaChat API: OAuth, история и обновление токена."""
import json
import os
import ssl
import time
from urllib import error, parse, request
from uuid import uuid4

#token 
def get_access_token(tls: ssl.SSLContext, key: str) -> tuple[str, float]:
    form = parse.urlencode({
        "scope": os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    }).encode("ascii")
    auth = request.Request(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        data=form,
        headers={
            "Authorization": "Basic " + key,
            "RqUID": str(uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with request.urlopen(auth, context=tls, timeout=30) as response:
        data = json.load(response)
    token = data["access_token"]
    expires_at = float(data["expires_at"])
    if expires_at > 10_000_000_000:  # API может вернуть миллисекунды.
        expires_at /= 1000
    return token, expires_at

#message
def ask(tls: ssl.SSLContext, token: str, messages: list[dict]) -> str:
    payload = {
        "model": os.getenv("GIGACHAT_MODEL", "GigaChat-2"),
        "messages": messages,
    }
    chat = request.Request(
        "https://api.giga.chat/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(chat, context=tls, timeout=60) as response:
        data = json.load(response)
    answer = data["choices"][0]["message"]["content"]
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Модель вернула пустой текст")
    return answer

#dialog
def main() -> None:
    key = os.getenv("GIGACHAT_AUTH_KEY")
    if not key:
        raise SystemExit("Задайте GIGACHAT_AUTH_KEY в переменной окружения")

    # Если корневого сертификата нет в системе, укажите PEM через GIGACHAT_CA_FILE.
    tls = ssl.create_default_context(cafile=os.getenv("GIGACHAT_CA_FILE") or None)
    history = [
        {"role": "system", "content": "Объясняй понятия начинающему на простых примерах"}
    ]
    token = ""
    expires_at = 0.0
    print("Диалог начат. Задайте вопрос; /exit или «выход» — завершить.")

#waiting q
    while True:
        try:
            question = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДиалог завершён.")
            break
        if question.lower() in {"/exit", "выход"}:
            print("Диалог завершён.")
            break
        if not question:
            continue

#answer and save
        try:
            if not token or time.time() >= expires_at - 60:
                token, expires_at = get_access_token(tls, key)
            user_message = {"role": "user", "content": question}
            answer = ask(tls, token, [*history, user_message])
        except error.HTTPError as exc:
            print(f"Ошибка API: HTTP {exc.code}. Вопрос не добавлен в историю.")
            continue
        except (error.URLError, KeyError, IndexError, TypeError, ValueError) as exc:
            print(f"Ошибка запроса: {exc}. Вопрос не добавлен в историю.")
            continue

        print("Помощник:", answer)
        history.extend([user_message, {"role": "assistant", "content": answer}])


if __name__ == "__main__":
    main()
