"""План задач: GigaChat выбирает функцию, Python проверяет и пишет файл."""
import json
from pathlib import Path

from assistant_profile import PROFILE
from gigachat_api import GigaChatAPI


FUNCTIONS = [
    {"name": "add_task", "description": "Добавляет задачу в план.",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}},
                    "required": ["title"]}},
    {"name": "list_tasks", "description": "Показывает задачи плана.",
     "parameters": {"type": "object", "properties": {}}},
]


#Читаем план - если файла ещё нет, возвращаем пустой список; повреждённые данные отклоняем
def load_plan(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or any(not isinstance(x, str) for x in data):
        raise ValueError("Повреждён файл плана")
    return data


#Выполняем проверенное действие - только Python после проверки имени и аргументов может записать задачу в файл
def execute_call(name: str, arguments: dict, path: Path) -> dict:
    tasks = load_plan(path)
    if name == "add_task":
        title = arguments.get("title")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 100:
            raise ValueError("Название задачи должно содержать 1–100 символов")
        title = title.strip()
        if title not in tasks:
            tasks.append(title)
            path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"added": title, "tasks": tasks}
    if name == "list_tasks":
        return {"tasks": tasks}
    raise ValueError("Неизвестная функция: " + name)


#Соединяем модель и функции - читаем предложенный вызов, выполняем его и отправляем результат модели для итогового ответа
def ask_plan(client: GigaChatAPI, question: str, path: Path) -> str:
    messages = [
        {"role": "system", "content":
         "Ты помощник по ведению задач. Для записи задачи вызывай add_task; "
         "для просмотра — list_tasks. Не утверждай, что действие выполнено, пока не получишь результат."},
        {"role": "user", "content": question[:500]},
    ]
    first = client.chat(messages, functions=FUNCTIONS)
    call = first["message"].get("function_call")
    if not call:
        return first["message"].get("content") or "Нет ответа"
    args = call.get("arguments") or {}
    if isinstance(args, str):
        args = json.loads(args)
    if not isinstance(args, dict):
        raise ValueError("Аргументы функции должны быть объектом")
    result = execute_call(call.get("name", ""), args, path)
    messages.append(first["message"])  # вместе с functions_state_id
    messages.append({"role": "function", "name": call["name"],
                     "content": json.dumps(result, ensure_ascii=False)})
    final = client.chat(messages, functions=FUNCTIONS, function_call_mode="none")
    return final["message"].get("content") or "Действие выполнено"


#Цикл позволяет добавить задачу, посмотреть список
if __name__ == "__main__":
    client = GigaChatAPI()
    plan = Path(__file__).with_name(PROFILE.plan_file)
    while True:
        question = input("План (/exit): ").strip()
        if question == "/exit":
            break
        if question:
            try:
                print(ask_plan(client, question, plan))
            except Exception as exc:
                print("Ошибка:", exc)
