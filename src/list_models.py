"""Показать модели, доступные текущему проекту API."""
from gigachat_api import GigaChatAPI

for name in GigaChatAPI().models():
    print(name)
