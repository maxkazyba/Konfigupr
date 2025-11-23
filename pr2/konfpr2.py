#!/usr/bin/env python3
"""
maven_deps_cli.py

Минимальный CLI для:
- Получения параметров от пользователя (этап 1)
- Загрузки POM из Maven-репозитория или локального файла и извлечения прямых зависимостей (этап 2)
- Генерации Graphviz DOT и попытки рендеринга графа (этап 5)

Не требует сторонних библиотек (только stdlib).
"""

import argparse
import sys
import os
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import subprocess
from typing import List, Tuple, Optional

# -------------------------
# Утилиты и ошибки
# -------------------------
class CLIError(Exception):
    pass

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# -------------------------
# Парсинг и валидация аргументов (Этап 1)
# -------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Maven direct-dependency inspector + Graphviz exporter")
    parser.add_argument("--package", "-p", required=True,
                        help="Имя пакета в формате groupId:artifactId (например org.apache.commons:commons-lang3)")
    parser.add_argument("--version", "-v", required=True,
                        help="Версия пакета (например 3.12.0)")
    parser.add_argument("--repo", "-r", required=True,
                        help="URL репозитория (например https://repo1.maven.org/maven2) или путь к локальной директории")
    parser.add_argument("--mode", "-m", choices=["remote", "local"], default="remote",
                        help="remote — загружать по HTTP из репозитория; local — искать файл в локальном репозитории (filesystem)")
    parser.add_argument("--render", action="store_true",
                        help="Попытаться отрендерить граф с помощью `dot` (если установлен). Сохранит PNG рядом с программой.")
    parser.add_argument("--out-dot", default=None,
                        help="Путь для сохранения DOT-файла (если не указан — <artifact>-<version>.dot)")
    return parser.parse_args()

def print_config_and_validate(args):
    # вывод ключ-значение (этап 1.3)
    config = {
        "package": args.package,
        "version": args.version,
        "repo": args.repo,
        "mode": args.mode,
        "render": str(args.render),
        "out_dot": args.out_dot or "(auto)"
    }
    print("=== Конфигурация (ключ=значение) ===")
    for k, v in config.items():
        print(f"{k}={v}")
    print("====================================")

    # валидация package формата
    if ":" not in args.package:
        raise CLIError("Неверный формат --package. Ожидается groupId:artifactId (например org.apache.commons:commons-lang3).")
    group_id, artifact_id = args.package.split(":", 1)
    if not group_id or not artifact_id:
        raise CLIError("groupId и artifactId не могут быть пустыми.")
    if args.mode == "remote" and not (args.repo.startswith("http://") or args.repo.startswith("https://")):
        raise CLIError("Для режима remote --repo должен быть URL (начинаться с http:// или https://).")
    if args.mode == "local" and not os.path.isdir(args.repo):
        raise CLIError(f"Локальный репозиторий не найден: {args.repo}")
    return group_id, artifact_id

# -------------------------
# Получение POM (Этап 2)
# -------------------------
def build_pom_path_remote(repo_url: str, group_id: str, artifact_id: str, version: str) -> str:
    group_path = group_id.replace(".", "/")
    pom_name = f"{artifact_id}-{version}.pom"
    if repo_url.endswith("/"):
        return f"{repo_url}{group_path}/{artifact_id}/{version}/{pom_name}"
    else:
        return f"{repo_url}/{group_path}/{artifact_id}/{version}/{pom_name}"

def get_pom_remote(url: str) -> str:
    try:
        with urllib.request.urlopen(url) as resp:
            if resp.status != 200:
                raise CLIError(f"HTTP {resp.status} при попытке получить POM по {url}")
            data = resp.read()
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("latin1")
            return text
    except urllib.error.HTTPError as he:
        raise CLIError(f"HTTPError: {he.code} {he.reason} for {url}")
    except urllib.error.URLError as ue:
        raise CLIError(f"URLError: {ue.reason} for {url}")
    except Exception as ex:
        raise CLIError(f"Ошибка при загрузке POM: {ex}")

def get_pom_local(repo_dir: str, group_id: str, artifact_id: str, version: str) -> str:
    group_path = group_id.replace(".", "/")
    pom_path = os.path.join(repo_dir, group_path, artifact_id, version, f"{artifact_id}-{version}.pom")
    if not os.path.isfile(pom_path):
        raise CLIError(f"POM-файл не найден по пути: {pom_path}")
    try:
        with open(pom_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as ex:
        raise CLIError(f"Ошибка чтения локального POM: {ex}")

# -------------------------
# Разбор POM и извлечение прямых зависимостей (Этап 2.2-4)
# -------------------------
def extract_direct_dependencies(pom_xml: str) -> List[Tuple[str,str,str]]:
    """
    Возвращает список прямых зависимостей в формате [(groupId, artifactId, version_or_none), ...]
    Не выполняется резолвинг переменных POM (<${...}>) и не обрабатывает профили/parent inheritance полноценно.
    Это простая, но рабочая реализация для большинства POM.
    """
    try:
        root = ET.fromstring(pom_xml)
    except ET.ParseError as pe:
        raise CLIError(f"XML Parse Error в POM: {pe}")

    # Обычно POM использует namespace: http://maven.apache.org/POM/4.0.0
    ns = {}
    if root.tag.startswith("{"):
        uri = root.tag.split("}")[0].strip("{")
        ns["m"] = uri
        dep_xpath = ".//m:dependencies/m:dependency"
    else:
        dep_xpath = ".//dependencies/dependency"

    deps = []
    for dep in root.findall(dep_xpath, ns):
        gid = dep.findtext("m:groupId" if ns else "groupId", default=None, namespaces=ns)
        aid = dep.findtext("m:artifactId" if ns else "artifactId", default=None, namespaces=ns)
        ver = dep.findtext("m:version" if ns else "version", default=None, namespaces=ns)
        scope = dep.findtext("m:scope" if ns else "scope", default=None, namespaces=ns)
        optional = dep.findtext("m:optional" if ns else "optional", default=None, namespaces=ns)
        # Игнорируем зависимости с scope 'test' или optional='true' — это можно изменить при необходимости
        if gid and aid:
            deps.append((gid.strip(), aid.strip(), (ver.strip() if ver and ver.strip() else None), (scope.strip() if scope else None), (optional.strip() if optional else None)))
    return deps

# -------------------------
# Graphviz DOT генерация (Этап 5.1)
# -------------------------
def generate_dot(root_pkg: str, root_ver: str, dependencies: List[Tuple[str,str,Optional[str],Optional[str],Optional[str]]]) -> str:
    lines = []
    lines.append('digraph dependencies {')
    lines.append('  rankdir=LR;')
    # root node
    root_node = f"\"{root_pkg}:{root_ver}\""
    lines.append(f"  {root_node} [shape=box, style=filled, fillcolor=lightgrey];")
    # deps
    for gid, aid, ver, scope, optional in dependencies:
        label = f"{gid}:{aid}"
        if ver:
            label += f":{ver}"
        node = f"\"{label}\""
        lines.append(f"  {node} [shape=ellipse];")
        # maybe annotate label with scope
        edge_attrs = []
        if scope:
            edge_attrs.append(f"label=\"{scope}\"")
        if optional and optional.lower() == "true":
            edge_attrs.append("style=dashed")
        attrs = f" [{', '.join(edge_attrs)}]" if edge_attrs else ""
        lines.append(f"  {root_node} -> {node}{attrs};")
    lines.append("}")
    return "\n".join(lines)

def try_render_dot(dot_text: str, out_dot_path: str, out_png_path: str) -> None:
    # Сохраняем DOT
    with open(out_dot_path, "w", encoding="utf-8") as f:
        f.write(dot_text)
    # пытаемся запустить dot
    try:
        subprocess.run(["dot", "-Tpng", out_dot_path, "-o", out_png_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Graphviz PNG сгенерирован: {out_png_path}")
    except FileNotFoundError:
        eprint("Команда `dot` не найдена. Установите Graphviz, чтобы отрендерить PNG, или используйте сохранённый .dot файл.")
    except subprocess.CalledProcessError as cpe:
        eprint(f"Ошибка при рендеринге dot: {cpe}; stderr: {cpe.stderr.decode() if cpe.stderr else '<no stderr>'}")

# -------------------------
# Основной рабочий поток
# -------------------------
def run():
    try:
        args = parse_args()
        group_id, artifact_id = print_config_and_validate(args)
        version = args.version

        # получить POM
        print("\n=== Получаем POM ===")
        if args.mode == "remote":
            pom_url = build_pom_path_remote(args.repo, group_id, artifact_id, version)
            print(f"Загружаем POM по URL: {pom_url}")
            pom_xml = get_pom_remote(pom_url)
        else:
            print(f"Ищем POM в локальном репозитории: {args.repo}")
            pom_xml = get_pom_local(args.repo, group_id, artifact_id, version)

        # извлечь прямые зависимости (Этап 2.3-4)
        print("\n=== Прямые зависимости ===")
        deps = extract_direct_dependencies(pom_xml)
        if not deps:
            print("Прямых зависимостей не найдено.")
        else:
            for (gid, aid, ver, scope, optional) in deps:
                s = f"{gid}:{aid}"
                if ver:
                    s += f":{ver}"
                if scope:
                    s += f" [scope={scope}]"
                if optional:
                    s += f" [optional={optional}]"
                print(s)

        # Graphviz (Этап 5)
        print("\n=== Генерация Graphviz (DOT) ===")
        root_pkg = f"{group_id}:{artifact_id}"
        dot_text = generate_dot(root_pkg, version, deps)
        out_dot_path = args.out_dot if args.out_dot else f"{artifact_id}-{version}.dot"
        out_png_path = out_dot_path.rsplit(".",1)[0] + ".png"
        with open(out_dot_path, "w", encoding="utf-8") as f:
            f.write(dot_text)
        print(f"DOT файл сохранён: {out_dot_path}")
        if args.render:
            try_render_dot(dot_text, out_dot_path, out_png_path)
        else:
            print("Рендеринг не запрошен (--render), .dot можно открыть в Graphviz или онлайн-рендерерах.")

        print("\n=== Готово ===")
        # дополнительные объяснения про ограничения
        print("\n[Примечание] Этот инструмент извлекает только прямые зависимости из POM (section <dependencies>).")
        print("Он не выполняет резолвинг переменных вида ${...}, не учитывает parent/dependencyManagement/профили/байнд-плагины.")
        print("Поэтому результаты могут отличаться от вывода `mvn dependency:tree`, который резолвит транзитивные зависимости, свойства и плагины.")
    except CLIError as e:
        eprint(f"Ошибка: {e}")
        sys.exit(2)
    except Exception as exc:
        eprint(f"Непредвиденная ошибка: {exc}")
        sys.exit(3)

if __name__ == "__main__":
    run()
