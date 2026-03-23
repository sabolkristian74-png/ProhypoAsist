ProHypo Asistent - verejny link 24/7

Ciel
- Aplikacia ma byt dostupna verejne stale, aj ked nie si prihlaseny na GitHub a nie si online.

Dolezite
- Na trvaly verejny link potrebujes server/VPS, ktory bezi nonstop.
- Docasny link cez tunel (ngrok/cloudflared) nie je trvaly, ked vypnes pocitac, link spadne.

Moznost A: VPS (bez GitHubu, odporucane)

1. Nahraj projekt na VPS (scp/rsync).
2. Na VPS nainstaluj Python 3 a vytvor virtualne prostredie.
3. Nainstaluj zavislosti: pip install -r requirements.txt
4. Spusti Gunicorn:

   gunicorn -b 0.0.0.0:8000 webapp:app

5. Nastav Nginx reverzny proxy na port 8000.
6. Pridaj HTTPS certifikat (napr. certbot).
7. Vytvor systemd service, aby appka bezala po restarte servera.

Priklad systemd service (subor /etc/systemd/system/prohypo.service)

[Unit]
Description=ProHypo Asistent
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/ProhypoAsist
Environment="PORT=8000"
ExecStart=/opt/ProhypoAsist/.venv/bin/gunicorn -b 0.0.0.0:8000 webapp:app
Restart=always

[Install]
WantedBy=multi-user.target

Aktivacia:
- sudo systemctl daemon-reload
- sudo systemctl enable prohypo
- sudo systemctl start prohypo
- sudo systemctl status prohypo

Moznost B: Docasny verejny link (len ked bezi tvoj pocitac)
- Spusti appku lokalne.
- Spusti tunel, napr. ngrok:
  ngrok http 5000

Bezpecnost
- Ak ma mat pristup ktokolvek s linkom, nepotrebujes login.
- Ak chces obmedzit pristup, doplnime jednoduche heslo alebo prihlasenie.
