ProHypo Asistent

Tato aplikacia funguje lokalne bez GitHub uctu a bez prihlasenia do GitHubu.

Spustenie lokalne

1. Prejdite do priecinka projektu.
2. (Volitelne) vytvorte virtualne prostredie.
3. Nainstalujte zavislosti.
4. Spustite aplikaciu.

Linux / macOS

```bash
cd /cesta/k/ProhypoAsist
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash run.sh
```

Windows (PowerShell)

```powershell
cd C:\cesta\k\ProhypoAsist
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python "Prohpo asistent Final.py"
```

URL aplikacie

http://127.0.0.1:5000

Poznamka

- Subor `run.sh` uz nepouziva cesty viazane na Codespaces/GitHub.
- Ak nepouzivate virtualne prostredie, skript skusi `python3` alebo `python` automaticky.
