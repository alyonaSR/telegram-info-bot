"""Синхронная версия Telegram бота."""
import os
import time
from typing import Any, Optional, Dict, cast

import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-not-found]
from bs4.element import Tag  # type: ignore[import-not-found]
from dotenv import load_dotenv  # type: ignore[import-not-found]

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env файле")

TELEGRAM_API_URL: str = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
LONG_POLL_TIMEOUT: int = 30
API_REQUEST_TIMEOUT: int = 10  # секунды таймаута для HTTP-запросов
# дополнительное время поверх LONG_POLL_TIMEOUT
UPDATE_EXTRA_TIMEOUT: int = 5
QUOTE_REQUEST_TIMEOUT: int = 5  # сек. таймаут запроса сайта с цитатами
QUOTE_SOURCE_URL: str = "https://quotes.toscrape.com/"


def get_me() -> Dict[str, Any]:
    """Получает информацию о боте через метод getMe.

    Returns:
        Dict[str, Any]: Информация о боте
    """
    response = requests.get(
        f"{TELEGRAM_API_URL}/getMe",
        timeout=API_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return cast(Dict[str, Any], response.json())


def send_message(chat_id: int, text: str) -> Dict[str, Any]:
    """Отправляет сообщение пользователю через метод sendMessage."""
    payload = {"chat_id": chat_id, "text": text}
    response = requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json=payload,
        timeout=API_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return cast(Dict[str, Any], response.json())


def get_updates(
    offset: Optional[int] = None,
    timeout: int = LONG_POLL_TIMEOUT,
) -> Dict[str, Any]:
    """Получает обновления от Telegram через long polling."""
    params: Dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        f"{TELEGRAM_API_URL}/getUpdates",
        params=params,
        timeout=timeout + UPDATE_EXTRA_TIMEOUT,
    )
    response.raise_for_status()
    return cast(Dict[str, Any], response.json())


def get_daily_quote() -> str:
    """Получает случайную цитату через веб-скрапинг.

    Returns:
        str: Форматированная цитата с автором
    """
    try:
        response = requests.get(
            QUOTE_SOURCE_URL,
            timeout=QUOTE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        quote_block = soup.find("div", class_="quote")
        # Явно проверяем тип, чтобы mypy понял, что это Tag, а не str
        if not isinstance(quote_block, Tag):
            raise ValueError("Не удалось найти блок с цитатой")

        text_tag = quote_block.find("span", class_="text")
        author_tag = quote_block.find("small", class_="author")

        if not isinstance(text_tag, Tag) or not isinstance(author_tag, Tag):
            raise ValueError("Не удалось найти текст цитаты или автора")

        text = text_tag.get_text(strip=True)
        author = author_tag.get_text(strip=True)

        return f"{text} — {author}"

    except Exception:
        # Запасной вариант, если сайт недоступен
        return ('"The only limit to our realization of tomorrow will '
                'be our doubts of today." — Franklin D. Roosevelt')


def handle_message(chat_id: int, text: str, username: str) -> None:
    """Обрабатывает входящее сообщение."""
    if text == "/start":
        welcome = (
            "Привет! Я синхронный бот.\n\n"
            "Доступные команды:\n"
            "/quote - случайная цитата\n\n"
            "Или просто отправь мне любое сообщение, "
            "и я повторю его!"
        )
        send_message(chat_id, welcome)
        print("Отправлено приветствие\n")

    elif text == "/quote":
        quote = get_daily_quote()
        send_message(chat_id, quote)
        print("Отправлена цитата\n")

    elif text.startswith("/"):
        send_message(chat_id, f"Неизвестная команда: {text}")
        print("Неизвестная команда\n")

    else:
        send_message(chat_id, text)
        print(f"Эхо: {text}\n")


def process_update(update: Dict[str, Any]) -> Optional[int]:
    """Обрабатывает одно обновление."""
    offset = cast(int, update["update_id"]) + 1

    if "message" not in update:
        return offset

    message = update["message"]
    chat_id = cast(int, message["chat"]["id"])
    text = message.get("text", "")
    user = message.get("from", {})
    username = user.get("username", "Unknown")

    print(f"Сообщение от @{username}: {text}")
    handle_message(chat_id, text, username)

    return offset


def run_bot() -> None:
    """Основной цикл работы бота."""
    offset: Optional[int] = None

    while True:
        try:
            updates = get_updates(offset)

            if not updates.get("ok"):
                print(f"Ошибка API: {updates}")
                time.sleep(1)
                continue

            for update in updates.get("result", []):
                offset = process_update(update)

        except KeyboardInterrupt:
            print("\n\nБот остановлен пользователем")
            break
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(1)


def main() -> None:
    """Точка входа в программу."""
    print("Проверка подключения к боту...")
    try:
        bot_info = get_me()
        if bot_info.get("ok"):
            username = bot_info["result"]["username"]
            print(f"Бот успешно запущен: @{username}")
        else:
            print("Ошибка при подключении к боту")
            return
    except Exception as e:
        print(f"Не удалось подключиться к боту: {e}")
        return

    print("Ожидание сообщений...")
    print("Нажмите Ctrl+C для остановки\n")

    run_bot()


if __name__ == "__main__":
    main()
