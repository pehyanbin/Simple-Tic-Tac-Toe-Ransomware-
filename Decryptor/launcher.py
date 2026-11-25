#!/usr/bin/env python3
"""
Interactive CLI wrapper for crypt_tool.py.

Lets you pick an operation (encrypt / decrypt / encrypt-folder / decrypt-folder),
enter a path and password, then runs the underlying crypt_tool.py for you.

Place this script in the SAME directory as crypt_tool.py, or pass
--tool /path/to/crypt_tool.py when running it.
"""

import argparse
import getpass
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Locate the underlying tool
# ---------------------------------------------------------------------------
def find_tool(explicit: str | None = None) -> Path:
    """Return the Path to crypt_tool.py, or exit with a helpful error."""
    if explicit:
        tool = Path(explicit).expanduser().resolve()
        if tool.is_file():
            return tool
        sys.exit(f"ERROR: tool not found at {tool}")

    # Look next to this script first, then in the current directory.
    for candidate in (
        Path(__file__).resolve().parent / "crypt_tool.py",
        Path.cwd() / "crypt_tool.py",
    ):
        if candidate.is_file():
            return candidate

    sys.exit(
        "ERROR: could not find 'crypt_tool.py'.\n"
        "       Put this script in the same folder as crypt_tool.py, "
        "or run with --tool /path/to/crypt_tool.py"
    )


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def ask_path(label: str, must_exist: bool) -> Path:
    """Prompt for a path until a valid one is supplied."""
    while True:
        raw = input(f"{label}: ").strip().strip('"').strip("'")
        if not raw:
            print("  [x] path cannot be empty, try again.")
            continue

        path = Path(raw).expanduser()

        if must_exist and not path.exists():
            print(f"  [x] not found: {path}")
            continue

        return path


def ask_password() -> str:
    """Prompt for a password twice and confirm they match (hidden input)."""
    while True:
        pw1 = getpass.getpass("Password: ")
        if not pw1:
            print("  [x] password cannot be empty.")
            continue
        pw2 = getpass.getpass("Confirm password: ")
        if pw1 != pw2:
            print("  [x] passwords do not match, try again.")
            continue
        return pw1


def ask_yes_no(question: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer."""
    suffix = " [Y/n] " if default else " [y/N] "
    answer = input(question + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------
COMMANDS = {
    "1": ("encrypt",        "file",   "Encrypt a single file"),
    "2": ("decrypt",        "file",   "Decrypt a single .enc file"),
    "3": ("encrypt-folder", "folder", "Encrypt every file in a folder (recursive)"),
    "4": ("decrypt-folder", "folder", "Decrypt every .enc file in a folder (recursive)"),
}


def choose_command() -> str:
    """Show the menu and return the chosen command name."""
    print("\n=== Encryption Tool ===")
    for key, (_, _, desc) in COMMANDS.items():
        print(f"  {key}) {desc}")
    print("  q) Quit")

    while True:
        choice = input("\nChoose an option: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            sys.exit(0)
        if choice in COMMANDS:
            return COMMANDS[choice][0]
        print("  [x] invalid choice, try again.")


def run(tool: Path, command: str, target: Path, password: str, delete: bool) -> int:
    """Invoke crypt_tool.py with the chosen arguments and return its exit code."""
    # Build the argument list. Pass the password via env-var-free approach:
    # crypt_tool.py currently takes the password as a positional arg,
    # so we must put it on the command line. (See notes below.)
    cmd = [
        sys.executable,     # use the same Python interpreter
        str(tool),
        command,
        str(target),
        password,
    ]
    if delete:
        cmd.append("--delete")

    print("\nRunning:")
    # Never print the real password; mask it in the display.
    display = " ".join(
        "********" if part == password else part for part in cmd
    )
    print("  " + display + "\n")

    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive wrapper around crypt_tool.py"
    )
    parser.add_argument(
        "--tool",
        help="Path to crypt_tool.py (default: look next to this script)",
        default=None,
    )
    parser.add_argument(
        "--command",
        choices=[c[0] for c in COMMANDS.values()],
        help="Skip the menu and run this command directly",
    )
    parser.add_argument("--path", help="Target file or folder (with --command)")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Pass --delete to crypt_tool.py (delete source after success)",
    )
    args = parser.parse_args()

    tool = find_tool(args.tool)

    # If a command was supplied non-interactively, run it.
    if args.command:
        if not args.path:
            sys.exit("ERROR: --path is required with --command")
        target = Path(args.path).expanduser().resolve()
        if not target.exists():
            sys.exit(f"ERROR: not found: {target}")
        password = getpass.getpass("Password: ")
        if not password:
            sys.exit("ERROR: empty password")
        rc = run(tool, args.command, target, password, args.delete)
        sys.exit(rc)

    # Interactive flow.
    command = choose_command()
    is_file = COMMANDS_BY_NAME(command) == "file"

    label = "File path" if is_file else "Folder path"
    target = ask_path(label, must_exist=True)

    # For decryption, sanity-check the extension.
    if command == "decrypt" and target.suffix != ".enc":
        if not ask_yes_no(
            f"  [!] '{target.name}' does not end in .enc — continue anyway?"
        ):
            sys.exit(0)

    # Optionally delete source files after success.
    delete = False
    if is_file or command.endswith("-folder"):
        delete = ask_yes_no(
            "Delete source file(s) after successful operation?", default=False
        )

    password = ask_password()

    print("\nSummary")
    print(f"  command : {command}")
    print(f"  target  : {target}")
    print(f"  delete  : {delete}")

    if not ask_yes_no("Proceed?", default=True):
        print("Cancelled.")
        sys.exit(0)

    rc = run(tool, command, target, password, delete)
    if rc == 0:
        print("\n✔ Done.")
    else:
        print(f"\n✘ crypt_tool.py exited with code {rc}.")
    sys.exit(rc)


def COMMANDS_BY_NAME(name: str) -> str:
    """Return the target type ('file' or 'folder') for a given command name."""
    for cmd_name, target_type, _ in COMMANDS.values():
        if cmd_name == name:
            return target_type
    raise KeyError(name)


if __name__ == "__main__":
    main()