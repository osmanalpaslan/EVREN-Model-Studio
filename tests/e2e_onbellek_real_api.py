"""Önbellek dostu istek düzeni (Madde 22 B) — GERÇEK EVREN ile çok turlu oturumda önce/sonra ölçümü.

Kullanım:
    .\\.venv\\Scripts\\python.exe -u tests\\e2e_onbellek_real_api.py [model] [--eski]
--eski: EVREN_STUDIO_ONBELLEK_ESKI=1 (eski düzen: sistem istemi her adımda yeniden kurulur, tur ipucu/plan sistem
isteminde). Aynı saatte iki kez koşup karşılaştırın (EVREN yükü saatten saate değişir).

Senaryo (3 tur, proje haritası açık): 1) yardimci.py'ye fonksiyon ekle (harita değişir) 2) olmayan ayarlar.yaml'ı sor
(tura özel ipucu) 3) yardimci.py'yi özetle. Ölçüt: TUR BAŞI adımların önbellek oranı (önceki turların geçmişi önbellekten
okundu mu), toplam önbellek oranı, tur süreleri. Ücretsiz EVREN; kişisel veri yok.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if "--eski" in sys.argv:
    os.environ["EVREN_STUDIO_ONBELLEK_ESKI"] = "1"            # runner içe aktarılmadan ÖNCE
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("EVREN_GOZLEM_KAYNAK", "e2e")

import onbellek_raporu  # noqa: E402

from evren_studio.agent import runner as rmod  # noqa: E402
from evren_studio.agent.runner import AgentEvents, AgentRunner  # noqa: E402
from evren_studio.agent.tools import Workspace  # noqa: E402
from evren_studio.api.client import EvrenClient  # noqa: E402
from evren_studio.config import DEFAULT_BASE_URL  # noqa: E402
from evren_studio.db import Database  # noqa: E402
from evren_studio.secrets import load_api_key  # noqa: E402

TURLAR = [
    "yardimci.py dosyasına kare(x) adında, x'in karesini döndüren bir fonksiyon ekle. Başka dosyaya dokunma.",
    "ayarlar.yaml dosyasındaki timeout değeri kaç?",
    "yardimci.py dosyasındaki fonksiyonları tek cümleyle özetle.",
]
DOSYALAR = {
    "yardimci.py": '"""Yardımcı işlevler."""\n\n\ndef topla(a, b):\n    return a + b\n\n\ndef carp(a, b):\n    return a * b\n',
    "ana.py": "from yardimci import topla\n\n\nif __name__ == '__main__':\n    print(topla(2, 3))\n",
    "metin.py": "def ters(s):\n    return s[::-1]\n\n\ndef kelime_say(s):\n    return len(s.split())\n",
    "ayar.ini": "[genel]\ntimeout = 30\n",
    "README.md": "# Deneme\n\nKüçük yardımcı fonksiyonlar.\n",
}


def main() -> int:
    key = load_api_key()
    if not key:
        print("FAIL: API anahtarı yok")
        return 1
    model = next((a for a in sys.argv[1:] if not a.startswith("--")), "deepseek-v4.1-flash")
    print(f"düzen: {'ESKİ' if not rmod.FREEZE_SYSTEM else 'YENİ (dondurulmuş sabit istem + kuyruk notu)'} · model {model}",
          flush=True)
    client = EvrenClient(DEFAULT_BASE_URL, key, timeout=180, max_retries=1)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proje"
            root.mkdir()
            for rel, text in DOSYALAR.items():
                (root / rel).write_text(text, encoding="utf-8")
            db = Database(Path(tmp) / "e2e.db")
            sid = db.create_session(model, str(root), "auto")
            sureler = []
            for metin in TURLAR:
                db.add_session_message(sid, "user", metin)
                t0 = time.monotonic()
                AgentRunner(client, model, session_id=sid, store=db, events=AgentEvents(), workspace=Workspace(root),
                            mode="auto", stream=True, max_steps=12, project_map=True).run(db.get_session_messages(sid))
                sureler.append(time.monotonic() - t0)
            db.close()
            t = onbellek_raporu.rapor(Path(tmp) / "e2e.db", adim=True)
            ok = "def kare" in (root / "yardimci.py").read_text(encoding="utf-8")
    finally:
        client.close()
    o = onbellek_raporu.oran
    print(f"SONUÇ: {t['adim']} adım · önbellek {o(t['onbellek'], t['girdi'])} · 2.+ adım "
          f"{o(t['sonraki_onbellek'], t['sonraki_girdi'])} · TUR BAŞI {o(t['tur_basi_onbellek'], t['tur_basi_girdi'])} "
          f"({t['tur_basi_adim']} adım) · tur süreleri {[round(s) for s in sureler]} sn (toplam {sum(sureler):.0f}) · "
          f"kotadan düşmeyen {t['onbellek']} · görev {'GEÇTİ' if ok else 'KALDI'}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
