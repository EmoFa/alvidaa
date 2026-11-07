#!/usr/bin/env python3
"""Build local Cobalt fonts and monochrome raster symbols from the pinned package.

Build-only dependencies: fonttools, Pillow, rsvg-convert. Nothing is downloaded.
Output must be a new directory; publish it only after assets.json exists.
"""
import argparse
import concurrent.futures
import hashlib
import importlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "third-party/free-my-tv/upstream"


def dependency(name):
    # Optional, build-only dependencies: even --help must work without them.
    try:
        return importlib.import_module(name)
    except ImportError as error:
        raise RuntimeError("Install requirements-web-assets.txt in a dedicated build virtualenv") from error


def font_instance(args):
    source, target, optical, weight = args
    font = dependency("fontTools.ttLib").TTFont(source, recalcTimestamp=False)
    font = dependency("fontTools.varLib.instancer").instantiateVariableFont(
        font, {"opsz": optical, "wght": weight}, inplace=True)
    font.recalcTimestamp = False
    # Instancing updates weight class, but leaves the variable font's Regular
    # style bits. Prevent renderers synthesizing bold over an already-bold face.
    font["OS/2"].fsSelection = (font["OS/2"].fsSelection & ~96) | (32 if weight >= 700 else 64)
    font["head"].macStyle = (font["head"].macStyle & ~1) | (1 if weight >= 700 else 0)
    family = "FMTVWeb" + str(optical)
    style = {200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}[weight]
    names = {1: family, 2: style, 3: family + "-" + style, 4: family + " " + style,
             6: family + "-" + style, 16: family, 17: style, 21: family, 22: style, 25: family}
    for record in font["name"].names:
        if record.nameID in names:
            record.string = names[record.nameID].encode(record.getEncoding())
    font.save(target)
    return str(Path(target).name)


def build(output):
    if output.exists():
        raise ValueError("Refusing to overwrite an existing asset directory")
    image_module = dependency("PIL.Image")
    dependency("fontTools.varLib.instancer")
    try:
        manifest = json.loads((SOURCE / "MANIFEST.json").read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Cannot read pinned upstream manifest") from error
    for name, expected in manifest["files"].items():
        if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Upstream integrity check failed: " + name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fmtv-assets-", dir=output.parent) as temporary:
        stage = Path(temporary) / "assets"
        stage.mkdir()
        (stage / "fonts").mkdir()
        (stage / "symbols").mkdir()
        css = (SOURCE / "home.css").read_text()
        js = (SOURCE / "home.js").read_text()
        colors = set()
        for color in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])", css + js):
            colors.add((color if len(color) == 6 else "".join(c * 2 for c in color)).lower())
        for rgb in re.findall(r"rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)", css + js):
            colors.add("".join(f"{int(channel):02x}" for channel in rgb))
        colors = sorted(colors)
        try:
            coins_text = (SOURCE / "coins.js").read_text()
            coins = json.loads(coins_text.split("window.COINS = ", 1)[1].strip().removesuffix(";"))
        except (OSError, IndexError, json.JSONDecodeError) as error:
            raise ValueError("Cannot read upstream coin shapes") from error
        sources = {p.stem: p for p in (SOURCE / "symbols").glob("*.png")}
        for i, paths in enumerate(coins):
            svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            svg += "".join('<path fill="white" fill-rule="evenodd" d="' + p + '"/>' for p in paths) + "</svg>"
            target = Path(temporary) / ("coin-" + str(i) + ".png")
            subprocess.run(["rsvg-convert", "-w", "128", "-h", "128", "-o", str(target)],
                           input=svg.encode(), check=True, capture_output=True)
            sources["coin-" + str(i)] = target
        for name, source in sources.items():
            with image_module.open(source) as image:
                alpha = image.convert("RGBA").getchannel("A")
                for color in colors:
                    rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
                    tinted = image_module.new("RGBA", alpha.size, rgb + (255,))
                    tinted.putalpha(alpha)
                    tinted.save(stage / "symbols" / (name + "-" + color + ".png"))
        jobs = []
        faces = []
        for optical in range(14, 33):
            for weight in (200, 300, 400, 500, 600, 700):
                name = f"o{optical}-w{weight}.ttf"
                jobs.append((str(SOURCE / "fonts/InterVariable.ttf"), str(stage / "fonts" / name), optical, weight))
                faces.append(f"@font-face{{font-family:FMTVWeb{optical};font-weight:{weight};src:url(fonts/{name});}}")
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            list(pool.map(font_instance, jobs))
        (stage / "fonts.css").write_text("\n".join(faces) + "\n")
        (stage / "OFL.txt").write_bytes((SOURCE / "fonts/OFL.txt").read_bytes())
        (stage / "LICENSE-material-symbols.txt").write_bytes((SOURCE / "symbols/LICENSE-material-symbols.txt").read_bytes())
        data = {"upstream": manifest["revision"], "colors": colors, "symbols": sorted(sources),
                "opticalSizes": list(range(14, 33)), "weights": [200, 300, 400, 500, 600, 700],
                "files": {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(stage.rglob("*")) if p.is_file()}}
        (stage / "assets.json").write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        if output.exists():
            raise ValueError("Asset directory appeared concurrently; refusing replacement")
        stage.rename(output)
    print("Built verified native assets:", len(data["files"]), "files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
