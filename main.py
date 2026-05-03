import os
import json
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
start_total = time.time()

class IpService:

    API_URL = "https://api.ipify.org?format=json"

    def get_ip(self):

        response = requests.get(self.API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["ip"]


class GeoService:

    BASE_URL = "https://ipinfo.io"

    def get_geo_info(self, ip: str):
        url = f"{self.BASE_URL}/{ip}/geo"

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "ip": ip,
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
            "location": data.get("loc"),
            "org": data.get("org"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }


class Saver:

    def save_to_json(self, data: dict, filename: str = "ip_info.json"):
        filepath = os.path.join(os.path.dirname(__file__), filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return filepath


class YandexDiskService:

    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://cloud-api.yandex.net/v1/disk"
        self.headers = {
            "Authorization": f"OAuth {token}",
            "Content-Type": "application/json"
        }

    def create_folder(self, folder_path: str):
        url = f"{self.base_url}/resources"
        params = {"path": folder_path}

        response = requests.put(url, headers=self.headers, params=params)

        if response.status_code in (201, 409):
            return True
        else:
            raise Exception(f"Ошибка создания папки: {response.text}")

    def upload_file(self, local_path: str, remote_path: str):

        url = f"{self.base_url}/resources/upload"
        params = {"path": remote_path, "overwrite": True}

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        upload_url = response.json().get("href")

        with open(local_path, "rb") as f:
            upload_response = requests.put(upload_url, files={"file": f})
            upload_response.raise_for_status()

        return True


# ============= ОСНОВНАЯ ФУНКЦИЯ =============

def main():
    end = time.perf_counter()
    time.sleep(0)
    print(f"3,2,1 🚀 ПОЕХАЛИ!!! запуск Ip Detector, {time.time() - start_total:.3f} сек.")
    print()
    YANDEX_DISK_TOKEN = os.getenv("YANDEX_DISK_TOKEN")

    if not YANDEX_DISK_TOKEN:

        print(f"❌ ОШИБКА: Токен не найден в .env файле! {time.time() - start_total:.3f} сек.")
        print(f"   Убедитесь, что в файле .env есть строка: {time.time() - start_total:.3f} сек.")
        print(f"   YANDEX_DISK_TOKEN=ваш_токен, {time.time() - start_total:.3f} сек.")
        print()
        return

    print(f"✓ Токен успешно загружен из .env (длина: {len(YANDEX_DISK_TOKEN)} символов, {time.time() - start_total:.3f} сек.)")

    print(f"\n📡 Получаем IP-адрес...{time.time() - start_total:.3f} сек.")
    ip_service = IpService()
    ip = ip_service.get_ip()
    print(f"   Ваш IP: {ip}")

    print(f"\n🗺️ Получаем географические данные... {time.time() - start_total:.3f} сек.")
    geo_service = GeoService()
    geo_data = geo_service.get_geo_info(ip)
    print(f"   Город: {geo_data['city']}, Страна: {geo_data['country']}")

    print(f"\n💾 Сохраняем в JSON-файл... {time.time() - start_total:.3f} сек.")
    saver = Saver()
    filepath = saver.save_to_json(geo_data, "ip_info.json")
    print(f"   Файл сохранён: {filepath}")

    print(f"\n☁️ Загружаем на Яндекс.Диск... {time.time() - start_total:.3f} сек.")

    yandex = YandexDiskService(YANDEX_DISK_TOKEN)

    folder_name = "IpDetector"
    print(f"   Создаём папку '{folder_name}'...")

    yandex.create_folder(folder_name)
    print(f"   ✅ Папка создана/уже существует")

    remote_path = f"{folder_name}/ip_info.json"
    print(f"   Загружаем файл в '{remote_path}'...")

    yandex.upload_file(filepath, remote_path)
    print(f"   ✅ Файл успешно загружен")

    os.remove(filepath)
    print("   🗑️ Локальный JSON-файл удалён")


    print("\n" + "=" * 50)
    print("✅ ГОТОВО! Файл загружен на Яндекс.Диск!")
    print(f"   Папка: {folder_name}")
    print(f"   Файл: {remote_path}")
    print(f"   Ссылка: https://disk.yandex.ru/client/disk/{folder_name}")
    print("=" * 50)
    print(f'✅На выполнение программы потребовалось {time.time() - start_total:.3f} сек.✅')
    print("=" * 50)


if __name__ == "__main__":
    main()