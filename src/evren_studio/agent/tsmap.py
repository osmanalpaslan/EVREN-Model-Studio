"""Madde 20 C1 (2026-11-12): tree-sitter ile çok dilli sembol çıkarma (Aider repo haritası fikri).

Neden: proje haritası Python'da `ast`, JS'de basit düzenli ifade kullanıyordu; Go, Rust, Java, C#, PHP, C/C++, Ruby,
Kotlin, TypeScript projelerinde sembol YOKTU → ajan bu dillerde keşif için birkaç adım (her biri tüm bağlamla bir
model çağrısı) harcıyordu. Dil başına küçük, ÇEVRİMDIŞI çözümleyici paketleri (tree-sitter-<dil>, MIT, toplam ~2 MB)
kullanılır; `tree-sitter-language-pack` yeni sürümlerde çözümleyiciyi ilk kullanımda internetten indirdiği için seçilmedi.
Paket yoksa / çözümleme hata verirse None döner → harita eski yönteme (düzenli ifade) düşer; harita asla bozulmaz.
"""
from __future__ import annotations

import importlib
from typing import Any

# uzantı → (modül, dil fonksiyonu)
GRAMMARS: dict[str, tuple[str, str]] = {
    ".go": ("tree_sitter_go", "language"),
    ".rs": ("tree_sitter_rust", "language"),
    ".java": ("tree_sitter_java", "language"),
    ".cs": ("tree_sitter_c_sharp", "language"),
    ".js": ("tree_sitter_javascript", "language"), ".jsx": ("tree_sitter_javascript", "language"),
    ".mjs": ("tree_sitter_javascript", "language"), ".cjs": ("tree_sitter_javascript", "language"),
    ".ts": ("tree_sitter_typescript", "language_typescript"),
    ".tsx": ("tree_sitter_typescript", "language_tsx"),
    ".php": ("tree_sitter_php", "language_php"),
    ".c": ("tree_sitter_c", "language"), ".h": ("tree_sitter_c", "language"),
    ".cpp": ("tree_sitter_cpp", "language"), ".cc": ("tree_sitter_cpp", "language"),
    ".cxx": ("tree_sitter_cpp", "language"), ".hpp": ("tree_sitter_cpp", "language"),
    ".rb": ("tree_sitter_ruby", "language"),
    ".kt": ("tree_sitter_kotlin", "language"), ".kts": ("tree_sitter_kotlin", "language"),
}

# Tür (sınıf benzeri; üyeleri listelenir) ve fonksiyon düğümleri — dillerin dilbilgisi adları
TYPES = {
    "class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "struct_declaration",
    "trait_declaration", "object_declaration", "class_specifier", "struct_specifier", "class", "module",
    "struct_item", "enum_item", "trait_item", "impl_item", "mod_item", "type_spec", "type_alias_declaration",
    "abstract_class_declaration", "namespace_definition",
}
FUNCS = {
    "function_declaration", "function_definition", "method_declaration", "method_definition", "function_item",
    "method", "singleton_method", "constructor_declaration", "generator_function_declaration",
}
# İçine girilen sarmalayıcılar (dosya kökü, ad alanı, dışa aktarma, gövde)
WRAPPERS = {
    "program", "source_file", "translation_unit", "compilation_unit", "namespace_declaration",
    "file_scoped_namespace_declaration", "declaration_list", "export_statement", "type_declaration", "php_tag",
    "body_statement", "linkage_specification", "template_declaration",
}
BODIES = {"class_body", "declaration_list", "field_declaration_list", "interface_body", "enum_body", "body",
          "body_statement", "enum_class_body", "object_type", "compound_statement"}
NAME_TYPES = {"identifier", "type_identifier", "simple_identifier", "constant", "name", "field_identifier",
              "property_identifier", "scope_resolution", "namespace_identifier"}
KIND_LABEL = {"interface_declaration": "interface", "trait_item": "trait", "trait_declaration": "trait",
              "enum_declaration": "enum", "enum_item": "enum", "impl_item": "impl", "module": "module",
              "mod_item": "mod", "namespace_definition": "namespace", "type_alias_declaration": "type",
              "type_spec": "type", "struct_item": "struct", "struct_specifier": "struct", "struct_declaration": "struct",
              "record_declaration": "record", "object_declaration": "object"}
MAX_MEMBERS = 6

_parsers: dict[str, Any] = {}
_missing: set[str] = set()


def available() -> list[str]:
    """Kurulu (yüklenebilen) dil modülleri — duman raporu ve testler için."""
    return sorted({mod for mod, _fn in GRAMMARS.values() if _language(mod, GRAMMARS_FN[mod]) is not None})


GRAMMARS_FN = {}
for _suf, (_mod, _fn) in GRAMMARS.items():
    GRAMMARS_FN.setdefault(_mod, _fn)


def _language(mod: str, fn: str):
    key = f"{mod}.{fn}"
    if key in _missing:
        return None
    try:
        from tree_sitter import Language

        return Language(getattr(importlib.import_module(mod), fn)())
    except Exception:                         # paket yok / ABI uyumsuz → eski yöntem
        _missing.add(key)
        return None


def _parser(suffix: str):
    spec = GRAMMARS.get(suffix)
    if spec is None:
        return None
    key = f"{spec[0]}.{spec[1]}"
    if key not in _parsers:
        lang = _language(*spec)
        if lang is None:
            return None
        from tree_sitter import Parser

        _parsers[key] = Parser(lang)
    return _parsers[key]


def _name(node) -> str:
    n = node.child_by_field_name("name")
    if n is None and node.type in ("function_definition",):          # C/C++: declarator zinciri
        d = node.child_by_field_name("declarator")
        while d is not None and d.type not in ("identifier", "field_identifier", "qualified_identifier",
                                               "operator_name", "destructor_name"):
            d = d.child_by_field_name("declarator") or next(
                (c for c in d.named_children if c.type in ("identifier", "field_identifier", "qualified_identifier")),
                None)
        n = d
    if n is None and node.type == "impl_item":
        n = node.child_by_field_name("type")
    if n is None:
        n = next((c for c in node.named_children if c.type in NAME_TYPES), None)
    if n is None:
        return ""
    return n.text.decode("utf-8", "replace").strip()[:60]


def _public(name: str, suffix: str) -> bool:
    return bool(name) and not name.startswith("_")


def _members(node, suffix: str) -> list[str]:
    body = node.child_by_field_name("body")
    if body is None:
        body = next((c for c in node.named_children if c.type in BODIES), None)
    if body is None:
        return []
    out = []
    for c in body.named_children:
        if c.type in FUNCS or c.type in ("function_signature_item", "method_signature", "constructor_declaration"):
            nm = _name(c)
            if nm and not nm.startswith("_") and nm not in out:
                out.append(nm)
    return out


def _walk(node, suffix: str, out: list[tuple[str, str]], depth: int = 0) -> None:
    for c in node.named_children:
        t = c.type
        if t in TYPES:
            nm = _name(c)
            if nm and _public(nm, suffix):
                mem = _members(c, suffix)
                label = KIND_LABEL.get(t, "class")
                shown = f"{label} {nm}" + (f"({', '.join(mem[:MAX_MEMBERS])}{'…' if len(mem) > MAX_MEMBERS else ''})"
                                           if mem else "")
                out.append((shown, nm))
                for m in mem:
                    out.append(("", m))                 # yalnız başvuru sayımı için ad
            if t in ("namespace_definition", "module", "mod_item") and depth < 3:
                body = c.child_by_field_name("body") or next((x for x in c.named_children if x.type in BODIES), None)
                if body is not None:
                    _walk(body, suffix, out, depth + 1)
        elif t in FUNCS:
            nm = _name(c)
            if nm and _public(nm, suffix):
                out.append((nm, nm))
        elif t in ("lexical_declaration", "variable_declaration"):          # JS/TS: const f = () => …
            for d in c.named_children:
                if d.type == "variable_declarator":
                    v = d.child_by_field_name("value")
                    if v is not None and v.type in ("arrow_function", "function_expression", "function"):
                        nm = _name(d)
                        if nm and _public(nm, suffix):
                            out.append((nm, nm))
        elif (t in WRAPPERS or t == "declaration") and depth < 4:
            _walk(c, suffix, out, depth + 1)


def definitions(text: str, suffix: str) -> list[tuple[str, str]] | None:
    """[(gösterim, ad)] — gösterimi boş olanlar yalnız sayım içindir. Çözümleyici yoksa None (eski yönteme düş)."""
    parser = _parser(suffix)
    if parser is None:
        return None
    try:
        tree = parser.parse(text.encode("utf-8", "replace"))
    except Exception:
        return None
    out: list[tuple[str, str]] = []
    _walk(tree.root_node, suffix, out)
    return out
