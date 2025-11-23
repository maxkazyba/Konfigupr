import os
import sys
import argparse

def exp(a: str) -> str:
    """Простое раскрытие переменных окружения вида $VAR."""
    for k, v in os.environ.items():
        a = a.replace(f"${k}", v)
    return a


def run_repl(vfs_name: str, params: dict):
    """Интерактивный REPL."""
    while True:
        try:
            a = input(f"{vfs_name}$ ")
        except EOFError:
            print()
            break

        if not a.strip():
            continue

        b = a.split()
        cmd = b[0]

        if cmd == "exit":
            break

        elif cmd == "ls":
            print("ls called with args:", b[1:])

        elif cmd == "cd":
            print("cd called with args:", b[1:])

        elif cmd == "echo":
            expanded = exp(" ".join(b[1:])) if len(b) > 1 else ""
            print(expanded)

        elif cmd == "conf-dump":
            for k, v in params.items():
                print(f"{k}={v}")

        else:
            print("CommandNotFoundException")


def run_start_script(script_path: str, vfs_name: str, params: dict):
    """Выполнить стартовый скрипт построчно."""
    if not os.path.exists(script_path):
        print(f"[ERROR] Start script not found: {script_path}")
        return

    print(f"[INFO] Executing start script: {script_path}")
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[ERROR] Cannot read script: {e}")
        return

    for idx, line in enumerate(lines, start=1):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if line.strip().startswith("#"):
            print(f"{vfs_name}$ {line}")  # показываем комментарий как ввод
            continue

        print(f"{vfs_name}$ {line}")  # имитация пользовательского ввода
        try:
            b = line.split()
            cmd = b[0]

            if cmd == "exit":
                print("exit")
                return

            elif cmd == "ls":
                print("ls called with args:", b[1:])

            elif cmd == "cd":
                print("cd called with args:", b[1:])

            elif cmd == "echo":
                expanded = exp(" ".join(b[1:])) if len(b) > 1 else ""
                print(expanded)

            elif cmd == "conf-dump":
                for k, v in params.items():
                    print(f"{k}={v}")

            else:
                print("CommandNotFoundException")

        except Exception as e:
            print(f"[ERROR] Exception at line {idx}: {e}")
            break


def main():
    parser = argparse.ArgumentParser(description="VFS Shell Emulator (Stage 2)")
    parser.add_argument("--vfs", required=True, help="Path to virtual filesystem root")
    parser.add_argument("--start-script", required=False, help="Path to start script file")
    args = parser.parse_args()

    vfs_name = os.path.basename(os.path.abspath(args.vfs)) or "VFS"
    params = {
        "vfs_path": os.path.abspath(args.vfs),
        "start_script": args.start_script or "",
        "vfs_name": vfs_name,
    }

    # Отладочный вывод всех параметров
    print("[DEBUG] Emulator parameters:")
    for k, v in params.items():
        print(f"{k}={v}")

    # Выполнение стартового скрипта, если указан
    if args.start_script:
        run_start_script(args.start_script, vfs_name, params)

    print("[INFO] Entering interactive mode. Type 'exit' to quit.")
    run_repl(vfs_name, params)


if __name__ == "__main__":
    main()