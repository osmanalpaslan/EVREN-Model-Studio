"""Proje haritası çok dilli (Madde 20 C1, 2026-11-12): tree-sitter ile Go, Rust, Java, C#, TS, PHP, C/C++, Ruby,
Kotlin sembolleri; en çok başvurulan dosyalar bütçe darken önce; çözümleyici yoksa eski yönteme düşer."""
from __future__ import annotations

import pytest

from evren_studio.agent import projectmap, tsmap

SAMPLES = {
    "main.go": ("package main\n\ntype Kasa struct{ Para int }\n\nfunc (k *Kasa) Topla(x int) int { return k.Para + x }\n"
                "\nfunc Baslat() {}\n\ntype Deger interface { Oku() int }\n",
                ["type Kasa", "Topla", "Baslat", "type Deger"]),
    "lib.rs": ("pub struct Kasa { para: i32 }\nimpl Kasa {\n    pub fn topla(&self) -> i32 { self.para }\n}\n"
               "pub fn baslat() {}\nenum Renk { Kirmizi }\ntrait Oku { fn oku(&self); }\n",
               ["struct Kasa", "impl Kasa(topla)", "baslat", "enum Renk", "trait Oku"]),
    "Kasa.java": ("package a;\npublic class Kasa {\n  public int topla(int x) { return x; }\n  void sil() {}\n}\n"
                  "interface Deger { int oku(); }\n",
                  ["class Kasa(topla, sil)", "interface Deger"]),
    "Kasa.cs": ("namespace Uygulama {\n  public class Kasa {\n    public int Topla(int x) { return x; }\n  }\n"
                "  public interface IDeger { int Oku(); }\n}\n",
                ["class Kasa(Topla)", "interface IDeger"]),
    "app.ts": ("export interface Kullanici { ad: string }\nexport class Servis {\n  getir(): void {}\n"
               "  _gizli(): void {}\n}\n"
               "export function baslat(): void {}\nconst durdur = () => 1;\n",
               ["interface Kullanici", "class Servis(getir)", "baslat", "durdur"]),
    "index.php": ("<?php\nclass Kasa {\n  public function topla($x) { return $x; }\n}\nfunction baslat() {}\n",
                  ["class Kasa(topla)", "baslat"]),
    "kasa.c": ("struct Kasa { int para; };\nint topla(int a, int b) { return a + b; }\nstatic void _gizli(void) {}\n",
               ["struct Kasa", "topla"]),
    "kasa.cpp": ("namespace hesap {\nclass Kasa {\npublic:\n  int topla(int x) { return x; }\n};\n}\n"
                 "int baslat() { return 0; }\n",
                 ["namespace hesap", "class Kasa", "baslat"]),
    "kasa.rb": ("module Hesap\n  class Kasa\n    def topla(x)\n      x\n    end\n  end\nend\ndef baslat\nend\n",
                ["module Hesap", "class Kasa(topla)", "baslat"]),
    "Kasa.kt": ("class Kasa {\n    fun topla(x: Int): Int = x\n}\nfun baslat() {}\nobject Ayar\n",
                ["class Kasa(topla)", "baslat", "object Ayar"]),
}


def test_dil_paketleri_kurulu():
    mods = tsmap.available()
    for m in ("tree_sitter_go", "tree_sitter_rust", "tree_sitter_java", "tree_sitter_c_sharp", "tree_sitter_typescript",
              "tree_sitter_javascript", "tree_sitter_php", "tree_sitter_c", "tree_sitter_cpp", "tree_sitter_ruby",
              "tree_sitter_kotlin"):
        assert m in mods, m


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_dillerde_semboller(tmp_path, name):
    text, expected = SAMPLES[name]
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    got = projectmap.symbols(f)
    for e in expected:
        assert any(g == e or g.startswith(e) for g in got), (name, e, got)
    assert not any("_gizli" in g for g in got)


def test_haritada_go_ve_csharp_projesi(tmp_path):
    for name in ("main.go", "Kasa.cs", "lib.rs"):
        (tmp_path / name).write_text(SAMPLES[name][0], encoding="utf-8")
    m = projectmap.build(tmp_path)
    assert "main.go: type Kasa" in m and "Baslat" in m
    assert "Kasa.cs: class Kasa(Topla), interface IDeger" in m


def test_cozumleyici_yoksa_eski_yonteme_duser(tmp_path, monkeypatch):
    monkeypatch.setattr(tsmap, "definitions", lambda text, suf: None)
    f = tmp_path / "app.js"
    f.write_text("export function baslat() {}\nconst durdur = () => 1\n", encoding="utf-8")
    assert projectmap.symbols(f) == ["baslat", "durdur"]
    g = tmp_path / "main.go"
    g.write_text(SAMPLES["main.go"][0], encoding="utf-8")
    assert projectmap.symbols(g) == []                                     # Go için eski yöntem yok: sembolsüz


def test_bozuk_kaynak_haritayi_bozmaz(tmp_path):
    f = tmp_path / "bozuk.go"
    f.write_text("package main\nfunc ((( {{{ \x00 type", encoding="utf-8")
    assert isinstance(projectmap.symbols(f), list)


def test_butce_darken_en_cok_basvurulan_dosyanin_sembolleri_kalir(tmp_path):
    projectmap._cache.clear()
    (tmp_path / "zcekirdek.go").write_text("package a\nfunc HesaplaVergi() {}\nfunc YuvarlaTutar() {}\n", encoding="utf-8")
    for i in range(30):
        (tmp_path / f"kullanan_{i:02d}.go").write_text(
            f"package a\nfunc Islem{i:02d}Uzun() {{ HesaplaVergi(); YuvarlaTutar() }}\n", encoding="utf-8")
    full = projectmap.build(tmp_path, max_chars=100_000)
    projectmap._cache.clear()
    paths_only = sum(len(ln.split(":")[0]) + 1 for ln in full.splitlines())
    m = projectmap.build(tmp_path, max_chars=paths_only + 200)
    assert "zcekirdek.go: HesaplaVergi, YuvarlaTutar" in m        # 30 dosya kullanıyor → adı sonda olsa da önce
    assert "en çok kullanılan" in m
    assert sum(1 for ln in m.splitlines() if ln.startswith("kullanan_") and ":" in ln) < 30


def test_uyumsuz_dil_paketi_haritayi_bozmaz(monkeypatch):
    """Dil paketi yüklenir ama dil nesnesi hata verirse (ör. ABI uyumsuzluğu) eski yönteme düşülür."""
    import sys
    import types

    mod = types.ModuleType("tree_sitter_bozuk")

    def language():
        raise ValueError("Incompatible Language version 99")
    mod.language = language
    monkeypatch.setitem(sys.modules, "tree_sitter_bozuk", mod)
    monkeypatch.setitem(tsmap.GRAMMARS, ".bozuk", ("tree_sitter_bozuk", "language"))
    assert tsmap.definitions("func X() {}", ".bozuk") is None


def test_basvuru_puani_kendi_dosyasini_saymaz(tmp_path):
    a, b = tmp_path / "a.go", tmp_path / "b.go"
    texts = {a: "func Ortak() {}\nfunc X() { Ortak() }", b: "func Y() { Ortak() }"}
    defs = {a: [("Ortak", "Ortak"), ("X", "X")], b: [("Y", "Y")]}
    s = projectmap.rank(texts, defs)
    assert s[a] == 1 and s[b] == 0
