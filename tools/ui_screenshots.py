"""Arayüz ekran görüntüleri — görsel kontrol için (gerçek API çağrısı yapılmaz).

Kullanım: python tools/ui_screenshots.py <cikti_klasoru> [koyu|açık]
EVREN_STUDIO_DATA_DIR ortam değişkeni geçici bir klasöre ayarlanmalıdır.
"""
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

out = Path(sys.argv[1])
theme_name = sys.argv[2] if len(sys.argv) > 2 else "koyu"
data_dir = Path(os.environ["EVREN_STUDIO_DATA_DIR"])
data_dir.mkdir(parents=True, exist_ok=True)
(data_dir / "config.json").write_text(json.dumps({"theme": theme_name}), encoding="utf-8")

from evren_studio.agent.runner import ApprovalRequest, ToolCall  # noqa: E402
from evren_studio.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
w = MainWindow()
w.resize(1440, 900)
w.show()
ws_dir = Path(__file__).resolve().parents[1]
db = w.ctx.db


def seed():
    sid = db.create_session("glm-5.3", str(ws_dir), "onayli", title="Config yükleme hatasını düzelt")
    db.add_session_message(sid, "user", "Ayarlar açılışta okunmuyor gibi, kontrol edip düzeltir misin?")
    db.add_session_message(
        sid, "assistant", "Önce ayar yükleme koduna bakıyorum.",
        reasoning="Kullanıcı ayarların okunmadığını söylüyor. AppContext ve ConfigStore'u incelemeliyim.",
        tool_calls=[
            {"id": "c1", "name": "search_files", "arguments": json.dumps({"pattern": "store.load"})},
            {"id": "c2", "name": "read_file", "arguments": json.dumps({"path": "src/evren_studio/config.py"})},
        ], model="glm-5.3")
    db.add_session_message(sid, "tool", "Eşleşme bulunamadı.", tool_call_id="c1", name="search_files",
                           meta={"summary": "Arandı: “store.load” — 0 sonuç", "output": "Eşleşme bulunamadı."})
    db.add_session_message(sid, "tool", "...", tool_call_id="c2", name="read_file",
                           meta={"summary": "Okundu: src/evren_studio/config.py", "output": "1\t\"\"\"Uygulama yapılandırması.\n2\t..."})
    diff = ("--- a/src/evren_studio/ui/app_context.py\n+++ b/src/evren_studio/ui/app_context.py\n"
            "@@ -18,7 +18,8 @@\n class AppContext:\n     def __init__(self, settings=None):\n"
            "-        self.settings = settings or Settings()\n-        self.store = ConfigStore(self.settings.resolved_data_dir())\n"
            "+        self.store = ConfigStore(default_data_dir())\n+        self.settings = settings or self.store.load()\n"
            "         self.db = Database(...)\n")
    db.add_session_message(
        sid, "assistant",
        "Sorunu buldum: `AppContext` ayarları hiç **yüklemiyor**, her açılışta varsayılan "
        "`Settings()` kullanılıyor. Düzeltme:\n\n```python\nself.store = ConfigStore(default_data_dir())\n"
        "self.settings = settings or self.store.load()\n```",
        tool_calls=[{"id": "c3", "name": "edit_file", "arguments": json.dumps({"path": "src/evren_studio/ui/app_context.py"})},
                    {"id": "c4", "name": "run_command", "arguments": json.dumps({"command": "python -m pytest -q"})}],
        model="glm-5.3")
    db.add_session_message(sid, "tool", "Düzenlendi", tool_call_id="c3", name="edit_file",
                           meta={"summary": "Düzenlendi: src/evren_studio/ui/app_context.py  +2 −2", "diff": diff})
    db.add_session_message(sid, "tool", "Çıkış kodu: 0", tool_call_id="c4", name="run_command",
                           meta={"summary": "Çalıştırıldı: python -m pytest -q (çıkış 0)", "exit_code": 0,
                                 "output": "........................................\n61 passed in 5.2s", "duration": 5.2})
    db.add_session_message(sid, "assistant",
                           "Tamamlandı. Ayarlar artık açılışta okunuyor.\n\n- `app_context.py` güncellendi\n"
                           "- Tüm testler geçti (61/61)\n\nDoğrulanmayan: gerçek uygulamada tema değişikliği.",
                           model="glm-5.3")
    db.set_session_todos(sid, [
        {"content": "Ayar yükleme kodunu incele", "status": "completed"},
        {"content": "AppContext düzeltmesi", "status": "completed"},
        {"content": "Testleri çalıştır", "status": "in_progress"},
        {"content": "Belgeleri güncelle", "status": "pending"},
    ])
    db.add_file_change(sid, None, "src/evren_studio/ui/app_context.py",
                       "self.settings = settings or Settings()\n", "self.settings = settings or self.store.load()\n")
    db.create_session("glm-5.3", None, title="Python async/await nedir?")
    return sid


def snap(name):
    app.processEvents()
    w.grab().save(str(out / f"{name}.png"))


def step1():
    snap(f"new_welcome_{theme_name}")
    sid = seed()
    w.sidebar.refresh()
    w.open_session(sid)
    QTimer.singleShot(500, step2)


def step2():
    snap(f"new_session_{theme_name}")
    # Canlı onay kutusu: hazırlanan gerçek diff ile
    call = ToolCall("c9", "run_command", '{"command": "git status"}', {"command": "git status"})
    aw = w.session.transcript
    from evren_studio.ui.transcript import AssistantMessageWidget
    a = AssistantMessageWidget("glm-5.3", True)
    a.finalize("Değişiklikleri kontrol etmek için git durumuna bakacağım.")
    tw = a.add_tool("c9", "run_command", {"command": "git status"})
    aw.add(a)
    req = ApprovalRequest(call, "exec", "Komut çalıştırılsın mı?", "git status", prefix="git status")
    tw.show_approval(req)
    w.session.composer.set_running(True)
    QTimer.singleShot(500, step3)


def step3():
    snap(f"new_approval_{theme_name}")
    w.session.composer.set_running(False)
    w.show_page("settings")
    QTimer.singleShot(300, step4)


def step4():
    snap(f"new_settings_{theme_name}")
    w.show_page("models")
    QTimer.singleShot(300, step5)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, model, messages, stream=False, cancel=None, on_delta=None,
             on_reasoning=None, tools=None, **kw):
        import time as _t
        from evren_studio.api.client import ChatResult
        r = self.responses.pop(0) if self.responses else ChatResult(content="(bitti)", finish_reason="stop")
        if on_reasoning:
            on_reasoning("Kullanıcı sıfıra bölme hatasının ele alınmasını istiyor. Önce dosyayı okumalıyım.")
        for part in (r.content or "").split(" "):
            on_delta(part + " ", "")
            _t.sleep(0.01)
        return r

    def close(self):
        pass


def step5():
    import shutil
    from evren_studio.api.client import ChatResult
    snap(f"new_models_{theme_name}")
    demo = Path(__file__).resolve().parents[1] / "build" / "demo"
    shutil.rmtree(demo, ignore_errors=True)
    demo.mkdir()
    (demo / "hesap.py").write_text(
        "def bol(a, b):\n    return a / b\n\n\ndef topla(a, b):\n    return a + b\n", encoding="utf-8")
    fake = FakeClient([
        ChatResult(content="Önce dosyayı okuyorum.", tool_calls=[
            {"id": "r1", "name": "read_file", "arguments": json.dumps({"path": "hesap.py"})},
            {"id": "t1", "name": "update_todos", "arguments": json.dumps({"todos": [
                {"content": "hesap.py dosyasını incele", "status": "completed"},
                {"content": "Sıfıra bölme kontrolü ekle", "status": "in_progress"},
                {"content": "Testleri çalıştır", "status": "pending"}]})}]),
        ChatResult(content="`bol` fonksiyonuna sıfıra bölme kontrolü ekliyorum.", tool_calls=[
            {"id": "e1", "name": "edit_file", "arguments": json.dumps({
                "path": "hesap.py", "old_string": "def bol(a, b):\n    return a / b",
                "new_string": "def bol(a, b):\n    if b == 0:\n        raise ValueError(\"Sıfıra bölünemez\")\n    return a / b"})}]),
        ChatResult(content="Tamamlandı. `bol(a, 0)` artık anlaşılır bir `ValueError` fırlatıyor.",
                   finish_reason="stop"),
    ])
    w.ctx._cached_key = "evren_llm_SAHTE_ANAHTAR_123456"
    w.ctx.make_client = lambda log_sink=None: fake
    w.new_session()
    w.session.welcome._choose(str(demo))
    w.session.send("bol fonksiyonu sıfıra bölünce çöküyor, düzeltir misin?")
    QTimer.singleShot(1500, step6)


def step6():
    from evren_studio.ui.transcript import ApprovalWidget
    snap(f"live_approval_{theme_name}")
    boxes = w.session.findChildren(ApprovalWidget)
    if boxes:
        boxes[0]._decide("allow")
    QTimer.singleShot(1500, step7)


def step7():
    w.panel.show_tab("changes")
    snap(f"live_done_{theme_name}")
    app.quit()


QTimer.singleShot(700, step1)
app.exec()
print("SHOTS_OK")
