import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import RequestStatusException, StatusException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Период времени за который должны отобразиться состояния проектов
TIMESTAMP = {'form_date': 0}

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='log_records.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверяет наличие всех необходимых переменных окружения."""
    if not PRACTICUM_TOKEN:
        logger.critical(
            f'Отсутствуют обязательная переменная'
            f'окружения: {PRACTICUM_TOKEN}'
        )
        raise SystemExit(f'Отсутствует {PRACTICUM_TOKEN}.')

    if not TELEGRAM_TOKEN:
        logger.critical(
            f'Отсутствуют обязательные переменные'
            f'окружения.{TELEGRAM_TOKEN}'
        )
        raise SystemExit(f'Отсутствует {TELEGRAM_TOKEN}.')

    if not TELEGRAM_CHAT_ID:
        logger.critical(
            f'Отсутствуют обязательные переменные'
            f'окружения.{TELEGRAM_CHAT_ID}'
        )
        raise SystemExit(f'Отсутствует {TELEGRAM_CHAT_ID}.')


def send_message(bot: telegram.Bot, message: str):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Отправлено сообщение: {message}')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения: {error}.')


def get_api_answer(timestamp: dict) -> dict:
    """Запрашивает информацию о состоянии проектов за определенный период."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=timestamp
        )

    except requests.ConnectionError as error:
        logger.error(
            f'Сбой в программе. Эндпоинт {ENDPOINT} недоступен. {error}'
        )
        raise RequestStatusException(f'Отсутствует ответ. {error}.')
    except requests.RequestException as error:
        logger.error(f'Сбой в программе. {error}')
        raise RequestStatusException(f'Сбой в программе. {error}.')

    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error(
            f'Статус ответа с эндпоинта: {homework_statuses.status_code}'
        )
        raise RequestStatusException(
            f'Статус ответа с эндпоинта: {homework_statuses.status_code}'
        )

    return homework_statuses.json()


def check_response(response: dict):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('В ответ API должен передаваться словарь (dict).')
        raise TypeError('В ответ API должен передаваться словарь (dict).')

    elif 'homeworks' not in response:
        logger.error('В ответе API отсутствует ключ homework.')
        raise KeyError('В ответе API отсутствует ключ homework.')

    elif not isinstance(response['homeworks'], list):
        logger.error(
            'В ответе API под ключом homework должен передаваться список.'
        )
        raise TypeError(
            'В ответе API под ключом homework должен передаваться список.'
        )

    elif not isinstance(response['current_date'], int):
        logger.error(
            'В ответе API под ключом current_date'
            'должно возвращаться число.'
        )
        raise TypeError(
            'В ответе API под ключом current_date'
            'должно возвращаться число.'
        )


def parse_status(homework: dict) -> str:
    """Извлекает статус конкретной домашней работы."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
        verdict = HOMEWORK_VERDICTS[status]

        return f'Изменился статус проверки работы "{homework_name}". {verdict}'

    except KeyError as error:
        logger.error(f'В ответе API нет ключа {error}')
        raise KeyError
    except StatusException as error:
        logger.error(f'Статус {error} отсутствует в {HOMEWORK_VERDICTS}.')
    except Exception as error:
        logger.error(f'В ответе API возникла ошибка {error}.')


def main():
    """Основная логика работы бота."""
    # Проверяем наличие всех необходимых токенов и переменных
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    homework_status = ''

    while True:
        try:
            # Запрашиваем состояния проектов за временной период TIMESTAMP
            response = get_api_answer({'form_date': timestamp})

            # Проверяем ответ API на соответствие
            check_response(response)

            # Проверяем статус последней домашней работы
            homework = response['homeworks'][0]
            homework_new_status = parse_status(homework)

            if homework_new_status not in homework_status:
                send_message(bot, homework_new_status)
                homework_status = homework_new_status

        except KeyError as error:
            logger.error(f'В API ответе отсутствуют ключи: {error}')
        except Exception as error:
            logger.error(f'Возникла проблема: {error}')

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
