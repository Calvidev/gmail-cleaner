#!/usr/bin/env python3
"""Relee el project.pbxproj generado y comprueba que se sostiene.

No sustituye a abrirlo en Xcode, pero pilla lo que más duele: un paréntesis
sin cerrar, una referencia a un objeto que no existe o un archivo declarado
que no está en el disco.

Uso:  python3 tools/check_pbxproj.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PBXPROJ = ROOT / "SleeperScore.xcodeproj" / "project.pbxproj"

TOKEN = re.compile(r'''
      (?P<comment>/\*.*?\*/)
    | (?P<string>"(?:[^"\\]|\\.)*")
    | (?P<symbol>[{}()=;,])
    | (?P<bare>[A-Za-z0-9_./$()@\-]+)
    | (?P<space>\s+)
''', re.VERBOSE | re.DOTALL)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    position = 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            raise SyntaxError(f"carácter inesperado en {position}: {text[position:position+40]!r}")
        position = match.end()
        if match.lastgroup in ("comment", "space"):
            continue
        tokens.append(match.group())
    return tokens


class Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.index = 0

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def next(self) -> str:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, token: str) -> None:
        actual = self.next()
        if actual != token:
            raise SyntaxError(f"se esperaba {token!r} y llegó {actual!r}")

    def value(self):
        token = self.peek()
        if token == "{":
            return self.dictionary()
        if token == "(":
            return self.array()
        raw = self.next()
        if raw.startswith('"'):
            return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return raw

    def dictionary(self) -> dict:
        self.expect("{")
        result = {}
        while self.peek() != "}":
            key = self.value()
            self.expect("=")
            result[key] = self.value()
            self.expect(";")
        self.expect("}")
        return result

    def array(self) -> list:
        self.expect("(")
        items = []
        while self.peek() != ")":
            items.append(self.value())
            if self.peek() == ",":
                self.next()
        self.expect(")")
        return items


UUID = re.compile(r"^[0-9A-F]{24}$")


def walk(value, found: list[str]) -> None:
    if isinstance(value, dict):
        for item in value.values():
            walk(item, found)
    elif isinstance(value, list):
        for item in value:
            walk(item, found)
    elif isinstance(value, str) and UUID.match(value):
        found.append(value)


def main() -> int:
    text = PBXPROJ.read_text(encoding="utf-8")
    if not text.startswith("// !$*UTF8*$!"):
        print("✗ falta la cabecera // !$*UTF8*$!")
        return 1

    parser = Parser(tokenize(text.split("\n", 1)[1]))
    document = parser.dictionary()
    if parser.peek() is not None:
        print(f"✗ sobra contenido tras el objeto raíz: {parser.peek()!r}")
        return 1

    problems: list[str] = []
    objects = document["objects"]
    root = document["rootObject"]
    if root not in objects:
        problems.append(f"rootObject {root} no existe")

    referenced: list[str] = []
    walk(objects, referenced)
    for uuid in set(referenced):
        if uuid not in objects:
            problems.append(f"referencia colgada: {uuid}")

    # Todos los archivos declarados tienen que existir en el disco.
    group_paths = {}
    for uuid, body in objects.items():
        if body.get("isa") == "PBXGroup" and "path" in body:
            for child in body.get("children", []):
                group_paths[child] = body["path"]

    for uuid, body in objects.items():
        if body.get("isa") != "PBXFileReference":
            continue
        if body.get("sourceTree") != "<group>":
            continue
        folder = group_paths.get(uuid, "")
        path = ROOT / folder / body["path"]
        if not path.exists():
            problems.append(f"declarado pero no está en el disco: {folder}/{body['path']}")

    # Cada objetivo tiene sus fases y su lista de configuraciones.
    targets = [b for b in objects.values() if b.get("isa") == "PBXNativeTarget"]
    if len(targets) != 2:
        problems.append(f"se esperaban 2 objetivos y hay {len(targets)}")
    for target in targets:
        if not target.get("buildPhases"):
            problems.append(f"{target.get('name')} sin fases de compilación")
        if target.get("buildConfigurationList") not in objects:
            problems.append(f"{target.get('name')} sin configuraciones")

    if problems:
        print("✗ problemas encontrados:")
        for problem in problems:
            print(f"   · {problem}")
        return 1

    counts: dict[str, int] = {}
    for body in objects.values():
        counts[body.get("isa", "?")] = counts.get(body.get("isa", "?"), 0) + 1
    print(f"✓ project.pbxproj correcto: {len(objects)} objetos")
    for isa in sorted(counts):
        print(f"   {isa}: {counts[isa]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
