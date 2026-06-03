# IP Detector

Непрерывный мониторинг IP-адреса с автосохранением геоданных на Яндекс.Диск.

## Возможности

- 🔄 Непрерывная работа с интервалом 60 секунд
- 📍 Определение геолокации по IP
- ☁️ Автоматическая загрузка на Яндекс.Диск
- 📝 Детальное логирование всех событий
- 🛡️ Graceful shutdown (Ctrl+C)
- 📊 Статистика работы

## Установка

```bash
# Клонирование репозитория
git clone https://github.com/YOUR_USERNAME/Ip-Detector.git
cd Ip-Detector

# Установка зависимостей
pip install -r requirements.txt

# Настройка .env файла
echo "YANDEX_DISK_TOKEN=ваш_токен" > .env