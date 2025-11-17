#!/bin/bash
# Полная установка и запуск Ticket Bot

SERVICE_NAME="ticket-bot"
WORK_DIR="$(pwd)"
USER_NAME="$(whoami)"
PYTHON_BIN="$WORK_DIR/venv/bin/python3"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

echo "⚙️ Обновляем систему и ставим зависимости..."
sudo apt update --fix-missing -y
sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip unzip

echo "🐍 Создаём виртуальное окружение..."
python3 -m venv venv
source venv/bin/activate

echo "📦 Устанавливаем Python-зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

echo "📝 Создаём systemd сервис..."
if [ "$EUID" -ne 0 ]; then
  echo "❌ Запустите этот скрипт через sudo!"
  exit 1
fi

cat > $SERVICE_FILE <<EOL
[Unit]
Description=Telegram Ticket Bot
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$WORK_DIR
ExecStart=$PYTHON_BIN $WORK_DIR/ticket_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "✅ Установка завершена!"
echo "Теперь открой config.json и вставь свой TELEGRAM_TOKEN и CHANNEL_ID."
echo "Перезапуск бота: sudo systemctl restart $SERVICE_NAME"
echo "Проверка статуса: sudo systemctl status $SERVICE_NAME"
echo "Логи: journalctl -u $SERVICE_NAME -f"
