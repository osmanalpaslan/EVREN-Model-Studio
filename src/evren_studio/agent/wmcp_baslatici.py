"""EVREN Studio — Windows-MCP başlatıcısı.

Bu dosya uygulamanın içinden DEĞİL, Windows-MCP'nin kendi Python ortamında (Python 3.14 venv) `python -P <bu dosya>
serve ...` ile çalışır; bu yüzden evren_studio'dan hiçbir şey içe aktarmaz. `-P` zorunludur: yoksa bu klasördeki
mcp.py, Windows-MCP'nin kullandığı `mcp` paketinin yerine geçerdi.

Neden var (2026-11-05 gerçek deneme): Windows-MCP 0.8.8 ekranı okurken (Snapshot) önce TÜM görünür pencerelerin UI
Automation bilgisini okur (`Desktop.get_controls_handles` → `get_windows`; ön plandaki pencere `get_foreground_window`).
Yanıt vermeyen bir pencere (ör. "Yanıt Vermiyor" durumundaki VS Code ve Windows'un onun yerine koyduğu dwm.exe hayalet
penceresi) bu okumayı dakikalarca kilitledi. 0.8.8'in `WINDOWS_MCP_EXCLUDE_PROCESSES` atlaması yalnız SONRAKİ öğe ağacı
taramasında uygulanıyor, bu iki adımda değil. Başlatıcı askıdaki pencereleri ve atlanan programların pencerelerini bu
iki adımdan da çıkarır, sonra Windows-MCP'yi olduğu gibi çalıştırır. Beklenen yerler bulunamazsa (başka sürüm)
hiçbir şeye dokunmadan çalıştırır.
"""
from __future__ import annotations

import sys
from typing import Any, Callable


def make_skip(is_hung: Callable[[int], bool], excluded: Callable[[], set[str]],
              name_of: Callable[[int], str | None]) -> Callable[[int], bool]:
    """Pencere atlanmalı mı: askıda (IsHungAppWindow) ya da sahibi atlanan programlardan biri."""
    def skip(hwnd: int) -> bool:
        try:
            if is_hung(hwnd):
                return True
        except Exception:
            pass
        try:
            names = excluded()
            if names:
                name = name_of(hwnd)
                return bool(name) and name.casefold() in names
        except Exception:
            pass
        return False
    return skip


def patch(desktop_cls: Any, uia: Any, skip: Callable[[int], bool]) -> bool:
    """Desktop'un pencere listesi ve ön plan okumasından atlanacak pencereleri çıkarır. Yamalandıysa True."""
    orig_handles = getattr(desktop_cls, "get_controls_handles", None)
    orig_fg = getattr(desktop_cls, "get_foreground_window", None)
    get_fg = getattr(uia, "GetForegroundWindow", None)
    if not (callable(orig_handles) and callable(orig_fg) and callable(get_fg)):
        return False

    def get_controls_handles(self, *a, **k):
        return {h for h in orig_handles(self, *a, **k) if not skip(h)}

    def get_foreground_window(self, *a, **k):
        try:
            h = get_fg()
        except Exception:
            h = 0
        if h and skip(h):
            return None          # ön plandaki pencere askıda: "etkin pencere yok" sayılır, diğerleri taranır
        return orig_fg(self, *a, **k)

    desktop_cls.get_controls_handles = get_controls_handles
    desktop_cls.get_foreground_window = get_foreground_window
    return True


def _install() -> bool:
    try:
        import ctypes

        from windows_mcp.desktop import service as ds
        from windows_mcp.tree import service as ts
    except Exception as exc:                    # başka sürüm/eksik modül: dokunmadan çalıştır
        print(f"[EVREN başlatıcı] yama atlandı: {exc}", file=sys.stderr)
        return False
    user32 = ctypes.windll.user32
    excluded = getattr(ts, "_excluded_process_names", lambda: set())
    name_of = getattr(ts, "_window_process_name", lambda _h: None)
    ok = patch(getattr(ds, "Desktop", None), getattr(ds, "uia", None),
               make_skip(lambda h: bool(user32.IsHungAppWindow(h)), excluded, name_of))
    print(f"[EVREN başlatıcı] askıdaki pencere koruması {'açık' if ok else 'UYGULANAMADI (beklenmeyen sürüm)'}",
          file=sys.stderr)
    return ok


def main() -> None:
    _install()
    from windows_mcp.__main__ import main as wmcp_main

    sys.argv[0] = "windows-mcp"
    wmcp_main()


if __name__ == "__main__":
    main()
