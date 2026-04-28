"""Асинхронная версия Telegram бота с расширенным функционалом."""
import os
import asyncio
from typing import Any, Optional, Dict, List, cast

import aiohttp  # type: ignore[import-not-found]
import requests  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-not-found]
# тип для проверки find()
from bs4.element import Tag  # type: ignore[import-not-found]
from dotenv import load_dotenv  # type: ignore[import-not-found]

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
OPENWEATHER_API_KEY: str = os.getenv('OPENWEATHER_API_KEY', '')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env файле")
if not OPENWEATHER_API_KEY:
    raise ValueError("OPENWEATHER_API_KEY не установлен в .env файле")

TELEGRAM_API_URL: str = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
OPENWEATHER_API_URL: str = (
    "https://api.openweathermap.org/data/2.5/weather"
)
LONG_POLL_TIMEOUT: int = 30

# Константы для цитат
QUOTE_SOURCE_URL: str = "https://quotes.toscrape.com/"
QUOTE_REQUEST_TIMEOUT: int = 5

# Словарь для хранения состояний пользователей (FSM)
user_states: Dict[int, str] = {}


async def send_message(
    session: aiohttp.ClientSession,
    chat_id: int,
    text: str
) -> Dict[str, Any]:
    """Асинхронно отправляет сообщение пользователю."""
    payload = {"chat_id": chat_id, "text": text}
    async with session.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json=payload
    ) as response:
        response.raise_for_status()
        return cast(Dict[str, Any], await response.json())


async def get_updates(
    session: aiohttp.ClientSession,
    offset: Optional[int] = None,
    timeout: int = LONG_POLL_TIMEOUT
) -> Dict[str, Any]:
    """Асинхронно получает обновления от Telegram."""
    params: Dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset

    async with session.get(
        f"{TELEGRAM_API_URL}/getUpdates",
        params=params,
        timeout=aiohttp.ClientTimeout(total=timeout + 5)
    ) as response:
        response.raise_for_status()
        return cast(Dict[str, Any], await response.json())


def get_daily_quote() -> str:
    """Синхронно получает цитату через requests + BeautifulSoup."""
    try:
        response = requests.get(
            QUOTE_SOURCE_URL,
            timeout=QUOTE_REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        quote_block = soup.find("div", class_="quote")
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
        return ('"The only limit to our realization of tomorrow will '
                'be our doubts of today." — Franklin D. Roosevelt')


async def get_daily_quote_async() -> str:
    """Асинхронная обёртка над синхронным get_daily_quote."""
    return await asyncio.to_thread(get_daily_quote)


async def scrape_rbc_news(session: aiohttp.ClientSession) -> str:
    """Скрапит заголовки с РБК."""
    try:
        url = "https://www.rbc.ru/"
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; '
                'Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
        }
        async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers=headers,
                ssl=False
        ) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            titles: List[str] = []

            selectors = [
                'a.main__feed__link span.main__feed__title',
                '.main__big__title',
                '.news-feed__item__title',
                'span[class*="title"]',
            ]

            for selector in selectors:
                items = soup.select(selector)
                for item in items:
                    text = item.get_text().strip()
                    if text and len(text) > 15 and text not in titles:
                        titles.append(text)
                    if len(titles) >= 3:
                        break
                if len(titles) >= 3:
                    break

            if not titles:
                return "РБК: не удалось получить заголовки"

            result = "РБК:\n"
            for i, title in enumerate(titles[:3], 1):
                result += f"{i}. {title}\n"
            return result.strip()
    except Exception:
        return "РБК: ошибка"


async def scrape_lenta_news(session: aiohttp.ClientSession) -> str:
    """Скрапит заголовки с Lenta.ru."""
    try:
        url = "https://lenta.ru/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers=headers
        ) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            titles: List[str] = []

            selectors = '.card-full-news__title, .card-mini__title'
            for item in soup.select(selectors)[:3]:
                text = item.get_text().strip()
                if text and len(text) > 10:
                    titles.append(text)

            if not titles:
                return "Лента.ру: не удалось получить заголовки"

            result = "Лента.ру:\n"
            for i, title in enumerate(titles, 1):
                result += f"{i}. {title}\n"
            return result.strip()
    except Exception as e:
        return f"Ошибка Лента.ру: {str(e)[:50]}"


async def scrape_ria_news(session: aiohttp.ClientSession) -> str:
    """Скрапит заголовки с РИА Новости."""
    try:
        url = "https://ria.ru/"
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36'
            )
        }
        async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                headers=headers,
                ssl=False
        ) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            titles: List[str] = []

            selectors = '.list-item__title, .cell-list__item-title'
            for item in soup.select(selectors)[:10]:
                text = item.get_text().strip()
                if text and len(text) > 15 and text not in titles:
                    titles.append(text)
                if len(titles) >= 3:
                    break

            if not titles:
                return "РИА Новости: не удалось получить заголовки"

            result = "РИА Новости:\n"
            for i, title in enumerate(titles[:3], 1):
                result += f"{i}. {title}\n"
            return result.strip()
    except Exception:
        return "РИА Новости: ошибка"


async def get_weather(session: aiohttp.ClientSession, city: str) -> str:
    """Получает погоду для города через OpenWeatherMap API."""
    try:
        params = {
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "ru"
        }
        async with session.get(
            OPENWEATHER_API_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 404:
                return (
                    f"Город '{city}' не найден. "
                    "Попробуйте другое название."
                )

            response.raise_for_status()
            data = await response.json()

            city_name = data["name"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            description = data["weather"][0]["description"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            return (
                f"Погода в городе {city_name}:\n"
                f"Температура: {temp:.1f}°C "
                f"(ощущается как {feels_like:.1f}°C)\n"
                f"Описание: {description}\n"
                f"Влажность: {humidity}%\n"
                f"Скорость ветра: {wind_speed} м/с"
            )
    except Exception as e:
        return f"Ошибка при получении погоды: {str(e)}"


async def handle_message(
    session: aiohttp.ClientSession,
    chat_id: int,
    user_id: int,
    text: str,
    username: str
) -> None:
    """Обрабатывает входящее сообщение."""
    if user_id in user_states and user_states[user_id] == 'waiting_for_city':
        print(f"Получен город от @{username}: {text}")
        weather_info = await get_weather(session, text)
        await send_message(session, chat_id, weather_info)
        del user_states[user_id]
        print("Отправлена погода\n")
        return

    if text == "/start":
        welcome = (
            "Привет! Я асинхронный бот.\n\n"
            "Доступные команды:\n"
            "/quote - случайная цитата\n"
            "/headlines - свежие новости из 3 источников\n"
            "/weather - узнать погоду в городе\n\n"
            "Или просто отправь мне любое сообщение, и я повторю его!"
        )
        await send_message(session, chat_id, welcome)
        print("Отправлено приветствие\n")

    elif text == "/quote":
        quote = await get_daily_quote_async()
        await send_message(session, chat_id, quote)
        print("Отправлена цитата\n")

    elif text == "/headlines":
        await send_message(
            session, chat_id, "Собираю новости, подождите..."
        )
        print("Запущен конкурентный скрапинг новостей...")

        results = await asyncio.gather(
            scrape_rbc_news(session),
            scrape_lenta_news(session),
            scrape_ria_news(session),
            return_exceptions=True
        )

        headlines = "Свежие российские новости:\n\n"
        for result in results:
            if isinstance(result, str):
                headlines += result + "\n\n"
            else:
                headlines += f"Ошибка: {result}\n\n"

        await send_message(session, chat_id, headlines.strip())
        print("Отправлены новости\n")

    elif text == "/weather":
        user_states[user_id] = 'waiting_for_city'
        await send_message(
            session, chat_id, "Пожалуйста, введите название города."
        )
        print("Запрошен город (FSM активирован)\n")

    elif text.startswith("/"):
        await send_message(session, chat_id, f"Неизвестная команда: {text}")
        print("Неизвестная команда\n")

    else:
        await send_message(session, chat_id, text)
        print(f"Эхо: {text}\n")


async def process_update(
    session: aiohttp.ClientSession,
    update: Dict[str, Any]
) -> int:
    """Обрабатывает одно обновление."""
    offset = cast(int, update["update_id"]) + 1

    if "message" not in update:
        return offset

    message = update["message"]
    chat_id = cast(int, message["chat"]["id"])
    user_id = cast(int, message["from"]["id"])
    text = message.get("text", "")
    username = message["from"].get("username", "Unknown")

    print(f"Сообщение от @{username}: {text}")

    asyncio.create_task(
        handle_message(session, chat_id, user_id, text, username)
    )

    return offset


async def run_bot(session: aiohttp.ClientSession) -> None:
    """Основной цикл работы бота."""
    offset: Optional[int] = None

    while True:
        try:
            updates = await get_updates(session, offset)

            if not updates.get("ok"):
                print(f"Ошибка API: {updates}")
                await asyncio.sleep(1)
                continue

            for update in updates.get("result", []):
                offset = await process_update(session, update)

        except KeyboardInterrupt:
            print("\n\nБот остановлен пользователем")
            break
        except Exception as e:
            print(f"Ошибка: {e}")
            await asyncio.sleep(1)


async def main() -> None:
    """Основной асинхронный цикл бота."""
    async with aiohttp.ClientSession() as session:
        print("Проверка подключения к боту...")
        try:
            async with session.get(
                f"{TELEGRAM_API_URL}/getMe"
            ) as response:
                bot_info = await response.json()
                if bot_info.get("ok"):
                    username = bot_info["result"]["username"]
                    print(f"Асинхронный бот запущен: @{username}")
                else:
                    print("Ошибка при подключении к боту")
                    return
        except Exception as e:
            print(f"Не удалось подключиться к боту: {e}")
            return

        print("Ожидание сообщений...")
        print("Нажмите Ctrl+C для остановки\n")

        await run_bot(session)


if __name__ == "__main__":
    asyncio.run(main())
