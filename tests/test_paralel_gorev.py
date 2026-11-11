"""Proje görevlerini ayrı git çalışma kopyalarında aynı anda yapma (Madde 20 B3, 2026-11-11; CAID yöntemi).

Gerçek git deposuyla: bağımsız görevler aynı anda koşar ve proje dalına birleştirilir; çakışan / doğrulanamayan paralel
deneme SIRAYLA yeniden yapılır (iş kaybolmaz); bağımlılık bilgisi yoksa, git yoksa, ayar kapalıysa eski sıralı davranış.
Güvenlik: kopyaya bağlanan .venv / node_modules silinirken projedeki asıl klasör SİLİNMEZ.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

from evren_studio.agent import project as pj
from tests.test_project_agent import _git_repo

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git yok")


def tasks(*deps: list[int]) -> list[pj.Task]:
    return [pj.Task(idx=i + 1, title=f"görev {i + 1}", criteria="ok", depends=list(d)) for i, d in enumerate(deps)]


class Fake:
    def __init__(self, root: Path, writes: dict[int, tuple[str, str]], review_fail: set[int] | None = None,
                 parallel: int = 3):
        self.root, self.writes, self.review_fail = root, writes, set(review_fail or ())
        self.parallel = parallel
        self.seq: list[int] = []
        self.par: list[int] = []
        self.prompts: dict[int, list[str]] = {}
        self.active = self.peak = 0
        self.lock = threading.Lock()
        self.seen_links: list[bool] = []
        self.cancel = False

    def _write(self, task, root):
        name, text = self.writes[task.idx]
        (root / name).write_text(text, encoding="utf-8")

    def run_task(self, task, prompt, fallback):          # sıralı: ana klasörde
        self.seq.append(task.idx)
        self.prompts.setdefault(task.idx, []).append(prompt)
        self._write(task, self.root)
        return pj.TaskRun(stopped="done", summary="yaptım", model="m")

    def run_task_in(self, task, prompt, root):          # paralel: çalışma kopyasında
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.par.append(task.idx)
        self.prompts.setdefault(task.idx, []).append(prompt)
        self.seen_links.append((root / ".venv" / "py.txt").exists())
        time.sleep(0.3)                                   # aynı anda çalıştıklarını görmek için
        self._write(task, root)
        with self.lock:
            self.active -= 1
        return pj.TaskRun(stopped="done", summary="yaptım", model="m")

    def review(self, messages):
        body = messages[-1]["content"]
        bad = any(f"Görev: görev {i}\n" in body for i in self.review_fail)
        return '{"tamam": %s, "neden": "%s"}' % ("false" if bad else "true", "eksik" if bad else "tamam")

    def hooks(self, worktree_root: Path, **kw):
        return pj.ProjectHooks(run_task=self.run_task, review=self.review, run_check=lambda c: (0, "OK"),
                               save=lambda st: None, run_task_in=self.run_task_in,
                               run_check_in=lambda c, r: (0, "OK"), parallel=self.parallel,
                               worktree_root=worktree_root, cancelled=lambda: self.cancel, sleep=lambda s: None, **kw)


def _git(root, *a):
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, encoding="utf-8").stdout


@needs_git
def test_bagimsiz_gorevler_ayni_anda_ve_birlestirilir(tmp_path):
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A=1\n"), 2: ("b.py", "B=2\n"), 3: ("c.py", "C=3\n"), 4: ("README.md", "# son\n")})
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [], [1, 2, 3]))
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "bitti" and [t.status for t in out.tasks] == ["bitti"] * 4
    assert sorted(fake.par) == [1, 2, 3] and fake.peak >= 2              # gerçekten aynı anda
    assert fake.seq == [4]                                               # toparlama tek başına, ana klasörde
    for f in ("a.py", "b.py", "c.py"):
        assert (root / f).is_file()                                      # birleştirildi
    log = _git(root, "log", "--oneline")
    assert log.count("(paralel)") == 3
    assert not any(wts.rglob("*.py"))                                    # kopyalar temizlendi
    assert "gorev-" not in _git(root, "branch")                          # geçici dallar silindi
    assert _git(root, "branch", "--show-current").strip() == out.branch


@needs_git
def test_cakisan_paralel_sonuc_sirayla_yeniden_yapilir(tmp_path):
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("ortak.py", "X=1\n"), 2: ("ortak.py", "X=2\n"), 3: ("c.py", "C\n"), 4: ("d.py", "D\n")})
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [], [1, 2, 3]))
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "bitti" and all(t.status == "bitti" for t in out.tasks)
    conflicted = [t for t in out.tasks if t.seq_only]
    assert len(conflicted) == 1 and conflicted[0].idx in fake.seq          # iş kaybolmadı: sırayla yapıldı
    assert "çakışma" in fake.prompts[conflicted[0].idx][-1]               # geri bildirim taşındı
    assert _git(root, "status", "--porcelain").strip() == ""              # yarım birleştirme kalmadı
    assert "<<<<<<<" not in (root / "ortak.py").read_text(encoding="utf-8")


@needs_git
def test_dogrulanamayan_paralel_deneme_geri_bildirimle_sirayla(tmp_path):
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")}, review_fail={2})
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    reviewed = {"n": 0}
    orig = fake.review

    def review_once(messages):                       # görev 2 yalnız paralel denemede (ilk incelemede) reddedilir
        if "Görev: görev 2\n" in messages[-1]["content"]:
            reviewed["n"] += 1
            if reviewed["n"] > 1:
                return '{"tamam": true, "neden": "tamam"}'
        return orig(messages)
    fake.review = review_once
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "bitti"
    t2 = out.tasks[1]
    assert t2.seq_only and 2 in fake.seq and pj.PAR_NOTE not in (t2.note or "")
    assert "eksik" in fake.prompts[2][-1]                                 # paralel denemenin dersi istemde
    assert (root / "b.py").read_text(encoding="utf-8") == "B\n"


@needs_git
@pytest.mark.parametrize("durum", ["bagimlilik_yok", "ayar_kapali", "git_yok"])
def test_kapali_kalmasi_gereken_durumlarda_sirayla(tmp_path, durum):
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    if durum != "git_yok":
        _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")},
                parallel=1 if durum == "ayar_kapali" else 3)
    deps = ([], [], []) if durum == "bagimlilik_yok" else ([], [], [1, 2])
    st = pj.ProjectState(goal="hedef", tasks=tasks(*deps))
    out = pj.ProjectRunner(st, root, fake.hooks(wts), use_git=durum != "git_yok").run()
    assert out.status == "bitti" and fake.par == [] and fake.seq == [1, 2, 3]
    if durum == "bagimlilik_yok":
        assert any("bağımlılıkları belirtilmemiş" in x for x in out.log)


@needs_git
def test_venv_baglantisi_kopyada_var_projede_silinmez(tmp_path):
    """EN KRİTİK: kopya silinirken bağlantının içine girilip projenin .venv'i SİLİNMEMELİ."""
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@t", "commit", "-qm", "ig"], cwd=root, check=True)
    (root / ".venv").mkdir()
    (root / ".venv" / "py.txt").write_text("yorumlayıcı", encoding="utf-8")
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")})
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "bitti" and fake.seen_links and all(fake.seen_links)   # kopyada .venv görünüyordu
    assert (root / ".venv" / "py.txt").read_text(encoding="utf-8") == "yorumlayıcı"  # ASIL KLASÖR SAĞLAM
    assert ".venv" not in _git(root, "log", "--stat")                         # bağlantı commit'e girmedi
    assert not any(wts.rglob("gorev-*"))                                       # kopya klasörü bağlantıyla kalmadı


@needs_git
def test_paralel_sirasinda_durdurulunca_duraklar(tmp_path):
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")})
    orig = fake.run_task_in

    def stop_after(task, prompt, r):
        res = orig(task, prompt, r)
        fake.cancel = True
        return res
    fake.run_task_in = stop_after
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "duraklatildi" and fake.seq == []


@needs_git
def test_durdurulan_paralel_deneme_basarisiz_sayilmaz(tmp_path):
    """Kullanıcı durdurunca yarım kalan paralel görev 'takıldı/sırayla' olmaz: deneme hakkı geri verilir."""
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")})

    def cancelled_run(task, prompt, r):
        fake.cancel = True
        return pj.TaskRun(stopped="cancelled", summary="", model="m")
    fake.run_task_in = cancelled_run
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "duraklatildi"
    for t in out.tasks[:2]:
        assert t.status == "bekliyor" and t.attempts == 0 and not t.seq_only and not (t.note or "")
    assert "gorev-" not in _git(root, "branch")


@needs_git
def test_dogrulama_komutu_calisma_kopyasinda_kosar(tmp_path):
    """Paralel görevin doğrulama komutu ANA klasörde değil, görevin kendi kopyasında çalışmalı."""
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")})
    seen = []

    def check_in(command, r):
        seen.append(Path(r))
        name = command.split()[-1]
        return (0, "OK") if (Path(r) / name).is_file() else (1, f"{name} yok")
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    st.tasks[0].check, st.tasks[1].check = "dir a.py", "dir b.py"
    hooks = fake.hooks(wts)
    hooks.run_check_in = check_in
    hooks.run_check = lambda c: (1, "ANA KLASÖRDE ÇALIŞTI")
    out = pj.ProjectRunner(st, root, hooks).run()
    assert out.status == "bitti" and sorted(fake.par) == [1, 2] and fake.seq == [3]
    assert len(seen) == 2 and all(wts in p.parents for p in seen)


@needs_git
def test_son_gorev_bagimsiz_olsa_da_tek_basina(tmp_path):
    """Son görev (toparlama) bağımlılık yazılmasa da paralele alınmaz; sırayla denenen (seq_only) görev de."""
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n"), 4: ("d.py", "D\n")}, parallel=4)
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1], []))
    st.tasks[1].seq_only = True
    out = pj.ProjectRunner(st, root, fake.hooks(wts)).run()
    assert out.status == "bitti"
    assert 4 not in fake.par and 2 not in fake.par and 4 in fake.seq and 2 in fake.seq


def test_alt_ajan_otomatik_kip_ve_test_bekcisi(monkeypatch, tmp_path):
    """Paralel görevin arayüzsüz ajanı Otomatik kipte ve test koruma bekçisi AÇIK koşar; Derin'in alt ajanı
    (varsayılan) salt okunur Plan kipinde kalır."""
    from evren_studio.agent import deep

    seen: dict = {}

    class R:
        def __init__(self, *a, **kw):
            seen.update(kw)
            self.model = "m"

        def run(self, history):
            history.append({"role": "assistant", "content": "bitti"})
            return type("O", (), {"stopped": "done"})()
    monkeypatch.setattr(deep, "AgentRunner", R)
    res = deep.run_subagent(client=None, model="m", fallbacks=[], root=tmp_path, prompt="p", marker="",
                            mode="auto", test_check=True,
                            runner_kw={"install_mode": "manuel", "untrusted": ["gizli"], "route_role": "kod"})
    assert seen["mode"] == "auto" and seen["test_check"] is True and seen["final_marker"] is None
    assert seen["install_mode"] == "manuel" and seen["untrusted"] == ["gizli"] and seen["route_role"] == "kod"
    assert res.stopped == "done" and res.text == "bitti"
    deep.run_subagent(client=None, model="m", fallbacks=[], root=tmp_path, prompt="p", marker="<x>")
    assert seen["mode"] == "plan" and seen["test_check"] is False and seen["final_marker"] == "<x>"


def test_baglanti_kaldirma_hedefe_dokunmaz(tmp_path):
    """_unlink yalnız bağlantıyı kaldırır; hedef klasör ve içeriği yerinde kalır."""
    import os

    src, link = tmp_path / "hedef", tmp_path / "kopya" / ".venv"
    src.mkdir()
    (src / "py.txt").write_text("x", encoding="utf-8")
    link.parent.mkdir()
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(src)], check=True, capture_output=True)
        assert os.path.isjunction(link)
    else:
        os.symlink(src, link, target_is_directory=True)
    pj.ProjectRunner._unlink([link, tmp_path / "yok"])
    assert not link.exists() and not os.path.lexists(link)
    assert (src / "py.txt").read_text(encoding="utf-8") == "x"


@needs_git
def test_kota_penceresi_doluyken_sirayla_gunluk_kota_deneme_sayilmaz(tmp_path):
    """Kota kapısı 1 derse paralel yok (bir kez not); günlük kota yüzünden yarım kalan paralel deneme
    başarısız sayılmaz ve proje kota nedeniyle duraklar."""
    root, wts = tmp_path / "p", tmp_path / "wt"
    root.mkdir()
    _git_repo(root)
    fake = Fake(root, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n"), 4: ("d.py", "D\n")})
    st = pj.ProjectState(goal="hedef", tasks=tasks([], [], [], [1, 2, 3]))
    out = pj.ProjectRunner(st, root, fake.hooks(wts, parallel_limit=lambda: 1)).run()
    assert out.status == "bitti" and fake.par == [] and fake.seq == [1, 2, 3, 4]
    assert sum("kota penceresi dolmak üzere" in x for x in out.log) == 1

    root2 = tmp_path / "p2"
    root2.mkdir()
    _git_repo(root2)
    fake2 = Fake(root2, {1: ("a.py", "A\n"), 2: ("b.py", "B\n"), 3: ("c.py", "C\n")})
    calls = {"n": 0}

    def quota():
        calls["n"] += 1
        return (0.0, "") if calls["n"] == 1 else (-1.0, "EVREN günlük kotası doldu")
    fake2.run_task_in = lambda task, prompt, r: pj.TaskRun(stopped="quota_daily", model="m")
    st2 = pj.ProjectState(goal="hedef", tasks=tasks([], [], [1, 2]))
    out2 = pj.ProjectRunner(st2, root2, fake2.hooks(tmp_path / "wt2", quota_wait=quota)).run()
    assert out2.status == "duraklatildi" and "günlük" in out2.pause_reason
    assert all(t.attempts == 0 and not t.seq_only and t.status == "bekliyor" for t in out2.tasks)
