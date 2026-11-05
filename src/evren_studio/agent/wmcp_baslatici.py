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


# ---- WindowText: masaüstü uygulamasının düz yazıları ---------------------------------------------------------------
# 0.8.8 Snapshot masaüstü uygulamalarında yalnız tıklanabilir öğeleri ve kutu değerlerini verir; düz yazıyı (etiket,
# durum çubuğu, sonuç metni) yalnız tarayıcı sayfasında listeler. 8. gerçek deneme: ajan 2+3'ü doğru yaptı ama "Sonuç: 5"
# etiketini göremediği için sonucu doğrulayamadı. Bu salt-okunur araç bir pencerenin yazılarını konumlarıyla verir.
# Sınır (gerçek Qt denemesi): uygulama etikete erişilebilir ad verdiyse Windows yalnız o adı bildirir, yazıyı değil.
TEXT_TOOL = "WindowText"
TEXT_TYPES = {"TextControl", "StatusBarControl", "HeaderItemControl", "TitleBarControl"}
TEXT_TOOL_DESC = ("Lists the static texts (labels, result texts, status bar, messages) of ONE open window with their "
                  "screen centers. Read-only. Use it after Snapshot when a label or result is not in the Snapshot tree. "
                  "window_name: part of the window title.")


def pick_window(windows: list[Any], window_name: str) -> Any:
    """Başlığı tam eşleşen, yoksa içeren ilk pencere (büyük/küçük harf duyarsız)."""
    want = (window_name or "").strip().casefold()
    if not want:
        return None
    exact = [w for w in windows if (getattr(w, "name", "") or "").strip().casefold() == want]
    part = [w for w in windows if want in (getattr(w, "name", "") or "").casefold()]
    return (exact or part or [None])[0]


def collect_texts(root: Any, limit: int = 200, max_visit: int = 3000, max_depth: int = 30) -> list[str]:
    """Kontrol ağacını gezip düz yazıları "(x,y) yazı" satırları olarak döndürür (sınırlı: dev pencerede takılmaz)."""
    out: list[str] = []
    seen: set[str] = set()
    stack = [(root, 0)]
    visits = 0
    while stack and len(out) < limit and visits < max_visit:
        node, depth = stack.pop()
        visits += 1
        try:
            kind = node.ControlTypeName
            name = (node.Name or "").strip()
        except Exception:
            continue
        if kind in TEXT_TYPES and name:
            try:
                r = node.BoundingRectangle
                pos = f"({(r.left + r.right) // 2},{(r.top + r.bottom) // 2})"
            except Exception:
                pos = "(?,?)"
            line = f"{pos} {name[:300]}"
            if line not in seen:
                seen.add(line)
                out.append(line)
        if depth < max_depth:
            try:
                kids = node.GetChildren() or []
            except Exception:
                kids = []
            stack.extend((k, depth + 1) for k in reversed(kids))
    return out


def window_text(desktop: Any, uia: Any, window_name: str, limit: int = 200) -> str:
    windows, _handles = desktop.get_windows()
    w = pick_window(windows, window_name)
    if w is None:
        names = ", ".join(sorted({getattr(x, "name", "") for x in windows if getattr(x, "name", "")}))[:600]
        return f"Window {window_name!r} not found. Open windows: {names or '(none)'}"
    texts = collect_texts(uia.ControlFromHandle(w.handle), limit=max(1, min(int(limit or 200), 500)))
    head = f"Texts of window {w.name!r}:"
    return head + ("\n" + "\n".join(texts) if texts else "\n(no static text found)")


def add_text_tool(tools_pkg: Any, uia: Any) -> bool:
    """Windows-MCP araç kaydına WindowText'i ekler. Eklendiyse True."""
    orig = getattr(tools_pkg, "register_all", None)
    if not callable(orig):
        return False

    def register_all(mcp, *a, **k):
        res = orig(mcp, *a, **k)
        get_desktop = k.get("get_desktop")
        try:
            from mcp.types import ToolAnnotations

            ann = ToolAnnotations(title=TEXT_TOOL, readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                                  openWorldHint=False)
        except Exception:
            ann = None

        def window_text_tool(window_name: str, limit: int = 200) -> str:
            return window_text(get_desktop(), uia, window_name, limit)

        kw = {"name": TEXT_TOOL, "description": TEXT_TOOL_DESC}
        if ann is not None:
            kw["annotations"] = ann
        mcp.tool(**kw)(window_text_tool)
        return res

    tools_pkg.register_all = register_all
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
    try:
        import windows_mcp.tools as tools_pkg

        text_ok = add_text_tool(tools_pkg, getattr(ds, "uia", None))
    except Exception as exc:
        text_ok = False
        print(f"[EVREN başlatıcı] {TEXT_TOOL} eklenemedi: {exc}", file=sys.stderr)
    print(f"[EVREN başlatıcı] {TEXT_TOOL} aracı {'eklendi' if text_ok else 'EKLENEMEDİ'}", file=sys.stderr)
    return ok


def main() -> None:
    _install()
    from windows_mcp.__main__ import main as wmcp_main

    sys.argv[0] = "windows-mcp"
    wmcp_main()


if __name__ == "__main__":
    main()
