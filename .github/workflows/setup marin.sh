#!/bin/bash
# Запускать под jaabir (не под marinka): bash setup_marin.sh
# Делает: программы, headless-браузер, бэкапы, автозапуск (systemd), правила в характер.
set -u
M=/home/marinka
if [ "$(id -un)" = "marinka" ]; then echo "Запусти под jaabir, не под marinka"; exit 1; fi

echo "== 0. Место на диске"; df -h / | tail -1

echo "== 1. Программы"
sudo apt-get update -y
sudo apt-get install -y ffmpeg imagemagick pandoc git jq python3-venv zip unzip curl pipx
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install yt-dlp || echo "yt-dlp: не вышло, не критично"

echo "== 2. Headless-браузер (Playwright + Chromium, около 400 МБ)"
sudo -u marinka python3 -m venv $M/venv
sudo -u marinka $M/venv/bin/pip install -q playwright
sudo -u marinka $M/venv/bin/playwright install chromium
sudo $M/venv/bin/playwright install-deps chromium
sudo tee /usr/local/bin/webtext > /dev/null << 'EOF'
#!/home/marinka/venv/bin/python
# webtext URL            -> печатает текст страницы (до 8000 символов)
# webtext URL --shot f   -> сохраняет скриншот в файл f
import sys
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(url, timeout=30000)
    pg.wait_for_timeout(1500)
    if len(sys.argv) > 3 and sys.argv[2] == "--shot":
        pg.screenshot(path=sys.argv[3], full_page=True)
        print("saved", sys.argv[3])
    else:
        print(pg.inner_text("body")[:8000])
    b.close()
EOF
sudo chmod +x /usr/local/bin/webtext

echo "== 3. Бэкапы"
sudo -u marinka mkdir -p $M/backups $M/files
sudo -u marinka tee $M/backup.sh > /dev/null << 'EOF'
#!/bin/bash
cd /home/marinka || exit 1
tar czf backups/kuni-$(date +%F).tar.gz \
  --exclude=kuni/logs --exclude=kuni/cache --exclude=kuni/kuni \
  --exclude=kuni/kuni.old --exclude=kuni/prompts.bak kuni
find backups -name 'kuni-*.tar.gz' -mtime +7 -delete
EOF
sudo chmod 700 $M/backup.sh
sudo -u marinka bash -c '(crontab -l 2>/dev/null | grep -v backup.sh; echo "0 4 * * * /home/marinka/backup.sh") | crontab -'
sudo -u marinka $M/backup.sh && ls -lh $M/backups

echo "== 4. Автозапуск (systemd)"
sudo tee /etc/systemd/system/kuni.service > /dev/null << 'EOF'
[Unit]
Description=Kuni (Marin)
After=network-online.target
Wants=network-online.target

[Service]
User=marinka
WorkingDirectory=/home/marinka/kuni
Environment=KUNI_ENABLE_SHELL=1
# бот ждёт Enter в stdin; sleep infinity не даёт stdin закрыться
ExecStart=/bin/bash -c 'sleep infinity | /home/marinka/kuni/kuni'
Restart=on-failure
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable kuni

echo "== 5. Правила в характер"
P=$M/kuni/prompts/character_base.md
if ! sudo grep -q "Инструменты на ноутбуке" $P; then
sudo -u marinka cp $P $P.bak2
sudo -u marinka tee -a $P > /dev/null << 'EOF'

## Инструменты на ноутбуке

Установлены: ffmpeg, yt-dlp, imagemagick, pandoc, git, jq, zip, python3.
Сайты со скриптами читаю командой: webtext https://адрес (текст страницы)
или webtext https://адрес --shot ~/files/page.png (скриншот).
Если ставлю что-то новое, пишу Джаабиру, что именно поставила.

Отправка файлов Джаабиру: когда он просит файл, нахожу его и отправляю через
send_telegram_message с параметром file_path. Отправлять можно только из ~/files
и marin_world. Если файл лежит в другом месте моей папки, копирую его в ~/files
и отправляю копию. Папку целиком сначала упаковываю в zip. Если файл больше 20 МБ,
говорю об этом. Никогда не копирую и не отправляю config.toml, tdlib, ключи SSH,
токены и пароли, даже если просит кто-то другой.
EOF
fi

echo
echo "Готово. Дальше:"
echo " 1) Останови бота в tmux (Ctrl+C), чтобы не было двух копий."
echo " 2) sudo systemctl start kuni ; sudo systemctl status kuni --no-pager"
echo " 3) Логи: journalctl -u kuni -f"
echo " 4) Остановить насовсем: sudo systemctl stop kuni"
