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

Deploy na Render

1. Otvor Render dashboard a vyber `New +` -> `Blueprint`.
2. Pripoj GitHub repozitar `sabolkristian74-png/ProhypoAsist`.
3. Render nacita konfiguraciu zo suboru `render.yaml`.
4. Spusti deploy.
5. Po dokonceni dostanes verejny link aplikacie.

Poznamka k 24/7

- Free plan na Renderi moze uspavat aplikaciu pri necinnosti.
- Ak chces stabilne 24/7 bez uspavania, zvol plateny plan (napr. `Starter`) alebo VPS.

Troubleshooting Render

- Ak log pise `No open HTTP ports detected on 0.0.0.0`, spusti `Manual sync`.
- Tento repozitar uz ma upraveny `startCommand` v `render.yaml` pre spolahlivejsi start.
