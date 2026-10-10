"""Текстовые эмбеддинги через Cloud.ru Foundation Models."""
from __future__ import annotations

import os


class CloudEmbeddingsAPI:
    def __init__(self, *, api_key: str | None = None, sdk_client=None):
        self.embedding_model = "ai-sage/Giga-Embeddings-instruct-480M"
        if sdk_client is not None:
            self.client = sdk_client
            return
        key = api_key or os.getenv("CLOUD_RU_API_KEY")
        if not key:
            raise ValueError("Задайте CLOUD_RU_API_KEY")
        from openai import OpenAI
        self.client = OpenAI(
            api_key=key,
            base_url="https://foundation-models.api.cloud.ru/v1",
        )

#Кодируем фрагменты - отправляем тексты пачкой и получаем вектор для каждого фрагмента в исходном порядке
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        entries = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in entries]
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise ValueError("Cloud.ru вернул неполный набор векторов")
        return vectors

#Кодируем вопрос
    def embed_query(self, question: str) -> list[float]:
        instruction = "Найди фрагменты документов, которые помогают ответить на вопрос."
        query = f"Instruct: {instruction}\nQuery: {question}"
        return self.embed_documents([query])[0]


if __name__ == "__main__":
    vector = CloudEmbeddingsAPI().embed_query("Когда проверить список задач?")
    print("Cloud.ru: получен вектор из", len(vector), "чисел")
