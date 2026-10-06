"""История диалога хранится у приложения, не у API."""
from gigachat_api import GigaChatAPI
from assistant_profile import PROFILE, AssistantProfile


# Объект хранит свой список реплик. Два объекта ChatSession получат независимые истории
class ChatSession:
    def __init__(self, client: GigaChatAPI, profile: AssistantProfile = PROFILE):
        self.client = client
        self.profile = profile
        self.history: list[dict] = []

#Задаём вопрос с контекстом - отправляем system, последние реплики и новый user; успешные вопрос и ответ сохраняем парой
    def ask(self, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("Вопрос пуст")
        messages = [
            {"role": "system", "content": self.profile.chat_instruction},
            *self.history[-12:],
            {"role": "user", "content": question},
        ]
        result = self.client.chat(messages)
        print(result["usage"])
        answer = result["message"].get("content") or ""
        if not answer:
            raise ValueError("Модель вернула пустой ответ")
        self.history.extend([{"role": "user", "content": question},
                             {"role": "assistant", "content": answer}])
        self.history = self.history[-12:]
        return answer


#Добавляем консольный запуск
if __name__ == "__main__":
    session = ChatSession(GigaChatAPI())
    print("Введите вопрос или /exit")
    while True:
        question = input("Вы: ").strip()
        if question.lower() in {"/exit", "выход"}:
            print("Диалог завершён.")
            break
        if question:
            try:
                print("Помощник:", session.ask(question))
            except Exception as exc:
                print("Ошибка:", exc)
