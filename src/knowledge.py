"""Чтение документов, сохранённый индекс и поиск по смыслу."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from assistant_profile import PROFILE
from cloud_embeddings import CloudEmbeddingsAPI


#Делим документы на фрагменты - читаем выбранные текстовые файлы и сохраняем имя источника рядом с каждым небольшим фрагментом
def read_chunks(folder: Path, max_chars: int = 1000) -> list[dict[str, str]]:
    chunks = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        for paragraph in text.split("\n\n"):
            clean = " ".join(paragraph.split())
            for start in range(0, len(clean), max_chars):
                piece = clean[start:start + max_chars]
                if piece:
                    chunks.append({"source": path.name, "text": piece})
    return chunks


#Определяем изменения - хеш зависит от текстов и модели эмбеддингов; по нему решаем, можно ли взять готовый индекс
def fingerprint(chunks: list[dict], model: str) -> str:
    content = json.dumps({"chunks": chunks, "model": model}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


#Создаём или загружаем индекс - используем сохранённые векторы при совпадении хеша, иначе запрашиваем новые пакетами и сохраняем их
def build_index(client: CloudEmbeddingsAPI, folder: Path, index_file: Path) -> list[dict]:
    chunks = read_chunks(folder)
    if not chunks:
        raise ValueError("Добавьте .md, .txt или .py в " + str(folder))
    digest = fingerprint(chunks, client.embedding_model)
    if index_file.exists():
        try:
            cached = json.loads(index_file.read_text(encoding="utf-8"))
            if cached.get("fingerprint") == digest:
                return cached["items"]
        except (ValueError, KeyError, TypeError):
            pass  # повреждённый индекс пересоздаём
    items = []
    for start in range(0, len(chunks), 16):
        batch = chunks[start:start + 16]
        vectors = client.embed_documents([part["text"] for part in batch])
        items.extend({**part, "vector": vector} for part, vector in zip(batch, vectors))
    saved = {"fingerprint": digest, "model": client.embedding_model, "items": items}
    index_file.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    return items


#Сравниваем два вектора - косинусная близость показывает, насколько похожи направления векторов
def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Несовместимые размерности векторов")
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return dot / norm if norm else 0.0


#Находим подходящие фрагменты - получаем вектор вопроса, сортируем фрагменты по сходству и берём лучшие
def search(client: CloudEmbeddingsAPI, items: list[dict], query: str, limit: int = 3) -> list[dict]:
    if not query.strip():
        return []
    vector = client.embed_query(query)
    ranked = [{"source": item["source"], "text": item["text"],
               "score": cosine(vector, item["vector"])} for item in items]
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]


#Проверяем поиск без генерации - запускаем файл отдельно, чтобы увидеть источники и оценки сходства до добавления RAG
if __name__ == "__main__":
    from openai import APIConnectionError

    root = Path(__file__).resolve().parent
    client = CloudEmbeddingsAPI()
    items = build_index(client, root / PROFILE.knowledge_folder, root / "index.cloudru.json")
    while True:
        question = input("Поиск (/exit): ").strip()
        if question == "/exit":
            break
        try:
            hits = search(client, items, question)
        except APIConnectionError as exc:
            print(f"Cloud.ru не ответил ({type(exc).__name__}). Повторите вопрос.")
            continue
        for hit in hits:
            print(f'{hit["source"]} ({hit["score"]:.3f}): {hit["text"][:180]}')

