import os
import json
import requests
import time
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
CONFIG = {
    'check_interval': 1,  # Интервал проверки в секундах (1 минута)
    'log_dir': 'logs',
    'log_file': 'ip_detector.log',
    'max_log_size': 10 * 1024 * 1024,  # 10 MB
    'backup_count': 5,
    'folder_name': 'IpDetector',
    'json_filename': 'ip_info.json'
}


class LoggerSetup:
    """Настройка системы логирования"""

    @staticmethod
    def setup_logger() -> logging.Logger:
        """Настройка логгера с ротацией файлов"""

        # Создаем директорию для логов если её нет
        Path(CONFIG['log_dir']).mkdir(exist_ok=True)

        # Настройка логгера
        logger = logging.getLogger('IpDetector')
        logger.setLevel(logging.INFO)

        # Формат логов
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Хендлер для файла с ротацией
        log_file_path = Path(CONFIG['log_dir']) / CONFIG['log_file']
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=CONFIG['max_log_size'],
            backupCount=CONFIG['backup_count'],
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Хендлер для консоли
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        return logger


class IpService:
    """Сервис для получения IP-адреса"""

    API_URL = "https://api.ipify.org?format=json"
    BACKUP_URLS = [
        "https://api.my-ip.io/ip.json",
        "https://ipapi.co/json/"
    ]

    def get_ip(self, logger: logging.Logger) -> Optional[str]:
        """
        Получение IP-адреса с нескольких попытками
        """
        try:
            response = requests.get(self.API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            ip = data["ip"]
            logger.debug(f"IP получен: {ip}")
            return ip
        except Exception as e:
            logger.warning(f"Ошибка при получении IP из основного источника: {e}")

            # Пробуем резервные источники
            for backup_url in self.BACKUP_URLS:
                try:
                    response = requests.get(backup_url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    ip = data.get('ip') if 'ip' in data else data.get('ip_address')
                    if ip:
                        logger.info(f"IP получен из резервного источника: {backup_url}")
                        return ip
                except Exception as backup_e:
                    logger.debug(f"Резервный источник {backup_url} не сработал: {backup_e}")
                    continue

            logger.error("Не удалось получить IP ни из одного источника")
            return None


class GeoService:
    """Сервис для получения геоданных по IP"""

    BASE_URL = "https://ipinfo.io"

    def get_geo_info(self, ip: str, logger: logging.Logger) -> Optional[Dict[str, Any]]:
        """
        Получение географической информации об IP
        """
        if not ip:
            logger.error("Не передан IP-адрес для геолокации")
            return None

        url = f"{self.BASE_URL}/{ip}/geo"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            geo_data = {
                "ip": ip,
                "city": data.get("city", "Неизвестно"),
                "region": data.get("region", "Неизвестно"),
                "country": data.get("country", "Неизвестно"),
                "location": data.get("loc", "Неизвестно"),
                "org": data.get("org", "Неизвестно"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            logger.debug(f"Геоданные получены для {ip}: {geo_data['city']}, {geo_data['country']}")
            return geo_data

        except requests.RequestException as e:
            logger.error(f"Ошибка при получении геоданных: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return None


class Saver:
    """Сервис для сохранения данных в JSON"""

    @staticmethod
    def save_to_json(data: Dict[str, Any], logger: logging.Logger) -> Optional[str]:
        """
        Сохранение данных в JSON файл
        """
        if not data:
            logger.error("Нет данных для сохранения")
            return None

        try:
            filepath = Path(__file__).parent / CONFIG['json_filename']

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info(f"Данные сохранены в {filepath}")
            return str(filepath)

        except IOError as e:
            logger.error(f"Ошибка при сохранении файла: {e}")
            return None


class YandexDiskService:
    """Сервис для работы с Яндекс.Диском"""

    def __init__(self, token: str, logger: logging.Logger):
        self.token = token
        self.logger = logger
        self.base_url = "https://cloud-api.yandex.net/v1/disk"
        self.headers = {
            "Authorization": f"OAuth {token}",
            "Content-Type": "application/json"
        }

    def create_folder(self, folder_path: str) -> bool:
        """
        Создание папки на Яндекс.Диске
        """
        url = f"{self.base_url}/resources"
        params = {"path": folder_path}

        try:
            response = requests.put(url, headers=self.headers, params=params)

            if response.status_code == 201:
                self.logger.info(f"Папка '{folder_path}' создана на Яндекс.Диске")
                return True
            elif response.status_code == 409:
                self.logger.debug(f"Папка '{folder_path}' уже существует")
                return True
            else:
                self.logger.error(f"Ошибка создания папки: {response.text}")
                return False

        except requests.RequestException as e:
            self.logger.error(f"Сетевая ошибка при создании папки: {e}")
            return False

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        Загрузка файла на Яндекс.Диск
        """
        try:
            # Получаем URL для загрузки
            url = f"{self.base_url}/resources/upload"
            params = {"path": remote_path, "overwrite": True}

            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            upload_url = response.json().get("href")

            if not upload_url:
                self.logger.error("Не получен URL для загрузки")
                return False

            # Загружаем файл
            with open(local_path, "rb") as f:
                upload_response = requests.put(upload_url, files={"file": f})
                upload_response.raise_for_status()

            self.logger.info(f"Файл '{remote_path}' успешно загружен на Яндекс.Диск")
            return True

        except FileNotFoundError:
            self.logger.error(f"Локальный файл не найден: {local_path}")
            return False
        except requests.RequestException as e:
            self.logger.error(f"Ошибка при загрузке файла: {e}")
            return False


class IpDetectorDaemon:
    """Основной класс демона для непрерывной работы"""

    def __init__(self):
        self.logger = None
        self.running = True
        self.iteration_count = 0
        self.success_count = 0
        self.error_count = 0

    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown"""

        def signal_handler(signum, frame):
            self.logger.info(f"Получен сигнал {signum}, завершение работы...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def cleanup_old_files(self):
        """Очистка старых локальных файлов"""
        try:
            json_path = Path(__file__).parent / CONFIG['json_filename']
            if json_path.exists():
                json_path.unlink()
                self.logger.debug("Старый JSON файл удалён")
        except Exception as e:
            self.logger.warning(f"Ошибка при очистке файлов: {e}")

    def check_token(self) -> Optional[str]:
        """Проверка наличия токена Яндекс.Диска"""
        token = os.getenv("YANDEX_DISK_TOKEN")

        if not token:
            self.logger.error("ТОКЕН НЕ НАЙДЕН! Проверьте файл .env")
            self.logger.error("Добавьте строку: YANDEX_DISK_TOKEN=ваш_токен")
            return None

        self.logger.info(f"Токен загружен (длина: {len(token)} символов)")
        return token

    def process_iteration(self, yandex_service: YandexDiskService) -> bool:
        """
        Одна итерация получения IP, геоданных и загрузки
        Возвращает True при успешном выполнении
        """
        self.iteration_count += 1
        iteration_start = time.time()

        self.logger.info(f"=" * 60)
        self.logger.info(f"Итерация #{self.iteration_count} начата")

        # 1. Получаем IP
        ip_service = IpService()
        ip = ip_service.get_ip(self.logger)

        if not ip:
            self.logger.error("❌ Не удалось получить IP-адрес")
            return False

        self.logger.info(f"📡 Текущий IP: {ip}")

        # 2. Получаем геоданные
        geo_service = GeoService()
        geo_data = geo_service.get_geo_info(ip, self.logger)

        if not geo_data:
            self.logger.error("❌ Не удалось получить геоданные")
            return False

        self.logger.info(f"🗺️ Геоданные: {geo_data['city']}, {geo_data['country']}")

        # 3. Сохраняем в JSON
        saver = Saver()
        filepath = saver.save_to_json(geo_data, self.logger)

        if not filepath:
            self.logger.error("❌ Не удалось сохранить JSON файл")
            return False

        # 4. Загружаем на Яндекс.Диск
        remote_path = f"{CONFIG['folder_name']}/{CONFIG['json_filename']}"

        if yandex_service.upload_file(filepath, remote_path):
            self.logger.info(f"✅ Файл успешно загружен на Яндекс.Диск: {remote_path}")
            self.success_count += 1

            # Удаляем локальный файл
            try:
                os.remove(filepath)
                self.logger.debug("Локальный JSON файл удалён")
            except Exception as e:
                self.logger.warning(f"Не удалось удалить локальный файл: {e}")

            iteration_time = time.time() - iteration_start
            self.logger.info(f"✅ Итерация #{self.iteration_count} завершена за {iteration_time:.2f} сек.")
            self.logger.info(f"📊 Статистика: Успешно: {self.success_count}, Ошибок: {self.error_count}")

            return True
        else:
            self.logger.error("❌ Не удалось загрузить файл на Яндекс.Диск")
            return False

    def run(self):
        """Основной цикл работы демона"""

        # Настройка логирования
        self.logger = LoggerSetup.setup_logger()
        self.logger.info("=" * 70)
        self.logger.info("🚀 IP DETECTOR ДЕМОН ЗАПУЩЕН")
        self.logger.info(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"⏱️ Интервал проверки: {CONFIG['check_interval']} секунд")
        self.logger.info(f"📁 Папка на Яндекс.Диске: {CONFIG['folder_name']}")
        self.logger.info("=" * 70)

        # Настройка обработчиков сигналов
        self.setup_signal_handlers()

        # Проверка токена
        token = self.check_token()
        if not token:
            self.logger.error("Не удалось запустить демон: отсутствует токен")
            return

        # Инициализация сервиса Яндекс.Диска
        yandex_service = YandexDiskService(token, self.logger)

        # Создаем папку на Яндекс.Диске (если не существует)
        if not yandex_service.create_folder(CONFIG['folder_name']):
            self.logger.warning("Не удалось создать папку на Яндекс.Диске, но продолжаем работу")

        # Очистка старых файлов
        self.cleanup_old_files()

        # Основной цикл
        last_success_time = time.time()

        while self.running:
            try:
                # Выполняем итерацию
                success = self.process_iteration(yandex_service)

                if not success:
                    self.error_count += 1
                    self.logger.warning(f"Итерация #{self.iteration_count} завершена с ошибкой")

                # Ожидание до следующей проверки
                if self.running:
                    next_check = CONFIG['check_interval']
                    self.logger.info(f"💤 Ожидание {next_check} секунд до следующей проверки...")

                    # Ожидание с возможностью прерывания
                    for _ in range(next_check):
                        if not self.running:
                            break
                        time.sleep(1)

            except KeyboardInterrupt:
                self.logger.info("Получено прерывание от клавиатуры")
                break
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка в основном цикле: {e}", exc_info=True)
                self.error_count += 1
                time.sleep(5)  # Пауза при ошибке

        # Завершение работы
        self.logger.info("=" * 70)
        self.logger.info("🛑 IP DETECTOR ДЕМОН ОСТАНОВЛЕН")
        self.logger.info(f"📊 Итоговая статистика:")
        self.logger.info(f"   - Всего итераций: {self.iteration_count}")
        self.logger.info(f"   - Успешных: {self.success_count}")
        self.logger.info(f"   - Ошибок: {self.error_count}")
        self.logger.info(f"📅 Время остановки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 70)


def main():
    """Точка входа в программу"""
    daemon = IpDetectorDaemon()
    daemon.run()


if __name__ == "__main__":
    main()