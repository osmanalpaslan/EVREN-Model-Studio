"""Blender İÇİNDE çalışan dönüştürme betiği (uygulama içe aktarmaz; convert_model aracı çalıştırır).

    blender --background --factory-startup --disable-autoexec -noaudio --python blender_donustur.py -- \\
        <girdi> <çıktı.glb> <poligon_oranı 0.05-1> <en_büyük_doku_px>

--disable-autoexec: .blend içindeki gömülü Python betikleri ÇALIŞMAZ (güvenilmeyen mod dosyası olabilir).
Sonuç tek satır: `SONUC {json}` (yüz sayısı önce/sonra, nesne, malzeme, doku, uyarılar).
"""
import json
import os
import sys


def main():
    import bpy

    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        print("SONUC " + json.dumps({"hata": "kullanım: <girdi> <çıktı> [oran] [doku_px]"}))
        return 2
    src, dst = argv[0], argv[1]
    ratio = max(0.01, min(1.0, float(argv[2]) if len(argv) > 2 else 1.0))
    max_tex = int(argv[3]) if len(argv) > 3 else 0
    warn = []
    ext = os.path.splitext(src)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=src, load_ui=False)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ops = {".fbx": ("import_scene", "fbx"), ".obj": ("wm", "obj_import"), ".gltf": ("import_scene", "gltf"),
               ".glb": ("import_scene", "gltf"), ".stl": ("wm", "stl_import"), ".ply": ("wm", "ply_import"),
               ".dae": ("wm", "collada_import")}
        if ext not in ops:
            print("SONUC " + json.dumps({"hata": f"desteklenmeyen biçim: {ext}"}, ensure_ascii=False))
            return 3
        mod, name = ops[ext]
        op = getattr(getattr(bpy.ops, mod), name, None)
        if op is None or not hasattr(op, "poll"):
            print("SONUC " + json.dumps({"hata": f"{ext} bu Blender sürümünde içe aktarılamıyor "
                                                 "(ör. Collada/DAE Blender 5'te kaldırıldı)"}, ensure_ascii=False))
            return 3
        op(filepath=src)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        warn.append("sahnede mesh yok")
    before = sum(len(o.data.polygons) for o in meshes)
    if ratio < 1.0:
        for o in meshes:
            m = o.modifiers.new("evren_azalt", "DECIMATE")
            m.ratio = ratio
    resized = 0
    if max_tex > 0:
        for img in bpy.data.images:
            w, h = img.size[0], img.size[1]
            if w and h and max(w, h) > max_tex:
                k = max_tex / float(max(w, h))
                img.scale(max(1, int(w * k)), max(1, int(h * k)))
                img.pack()
                resized += 1
    dg = bpy.context.evaluated_depsgraph_get()
    after = 0
    for o in meshes:
        ev = o.evaluated_get(dg)
        after += len(ev.to_mesh().polygons)
        ev.to_mesh_clear()
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_apply=True)
    info = {"girdi": os.path.basename(src), "cikti": dst, "nesne": len(meshes), "yuz_once": before,
            "yuz_sonra": after, "malzeme": len(bpy.data.materials), "doku": len(bpy.data.images),
            "kucultulen_doku": resized, "boyut_kb": os.path.getsize(dst) // 1024, "uyarilar": warn}
    print("SONUC " + json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:  # Blender içinde: hatayı tek satırda raporla
        print("SONUC " + json.dumps({"hata": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        code = 1
    sys.exit(code)
