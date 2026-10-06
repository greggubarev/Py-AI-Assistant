"""Структурированный список шагов для произвольной задачи."""
import json

from gigachat_api import GigaChatAPI


STEPS_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "check": {"type": "string"},
    },
    "required": ["goal", "steps", "check"],
    "additionalProperties": False,
}


#Проверяем ответ локально - даже ответ по схеме дополнительно проверяем в Python: типы, пустые строки и число шагов
def validate_steps(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Результат должен быть объектом JSON")
    if not isinstance(data.get("goal"), str) or not data["goal"].strip():
        raise ValueError("Нет цели")
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 5:
        raise ValueError("Нужно от 1 до 5 шагов")
    if any(not isinstance(step, str) or not step.strip() for step in steps):
        raise ValueError("Шаги должны быть непустыми строками")
    if not isinstance(data.get("check"), str) or not data["check"].strip():
        raise ValueError("Нет критерия проверки")
    return data


#Просим составить шаги - отправляем задачу и схему, разбираем JSON и возвращаем только проверенные данные
def make_steps(client: GigaChatAPI, request: str) -> dict:
    if not request.strip():
        raise ValueError("Опишите задачу")
    result = client.chat(
        [{"role": "system", "content":
          "Разбей задачу пользователя на 1–5 конкретных шагов. "
          "Добавь признак завершения. Не утверждай, что шаги уже выполнены. "
          "Верни только данные по схеме."},
         {"role": "user", "content": request[:1000]}],
        response_format={"type": "json_schema", "schema": STEPS_SCHEMA, "strict": True},
    )
    raw = result["message"].get("content") or ""
    try:
        return validate_steps(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise ValueError("Ответ не является JSON") from exc


#Запросите шаги для своей задачи и посмотрите цель, список действий и критерий завершения
if __name__ == "__main__":
    result = make_steps(GigaChatAPI(), input("Какая задача? "))
    print("Цель:", result["goal"])
    for number, step in enumerate(result["steps"], 1):
        print(f"{number}. {step}")
    print("Проверка:", result["check"])

