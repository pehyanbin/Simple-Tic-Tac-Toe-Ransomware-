#!/usr/bin/env python3
"""
File & Folder Encryption Tool
Uses AES-256-GCM with PBKDF2-HMAC-SHA256 key derivation.

pip install cryptography

Usage:
    python crypt_tool.py encrypt <path> <password>
    python crypt_tool.py decrypt <path> <password>
    python crypt_tool.py encrypt-folder <folder> <password>
    python crypt_tool.py decrypt-folder <folder> <password>

The .enc extension marks encrypted files.
Encrypted files keep the original filename + '.enc'.
"""

import os
import sys
import base64
import argparse
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Constants
SALT_SIZE = 16          # bytes
NONCE_SIZE = 12         # bytes (GCM standard)
KEY_SIZE = 32           # 256-bit key
KDF_ITERATIONS = 480_000
MAGIC = b"ENCF"         # File header magic
VERSION = b"\x01"       # File format version
ENC_EXT = ".enc"


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------
def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from password + salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


# ---------------------------------------------------------------------------
# File encryption / decryption
# ---------------------------------------------------------------------------
def encrypt_file(file_path: Path, password: str, delete_original: bool = False) -> Path:
    """Encrypt a single file. Returns the path of the encrypted file."""
    if file_path.suffix == ENC_EXT:
        print(f"  [skip] already encrypted: {file_path}")
        return file_path

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    plaintext = file_path.read_bytes()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    out_path = file_path.with_suffix(file_path.suffix + ENC_EXT)
    with open(out_path, "wb") as f:
        # Layout: MAGIC | VERSION | SALT | NONCE | CIPHERTEXT
        f.write(MAGIC)
        f.write(VERSION)
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

    if delete_original:
        file_path.unlink()

    print(f"  [enc] {file_path} -> {out_path.name}")
    return out_path


def decrypt_file(file_path: Path, password: str, delete_original: bool = False) -> Path:
    """Decrypt a single .enc file. Returns the path of the decrypted file."""
    if file_path.suffix != ENC_EXT:
        raise ValueError(f"Not an encrypted file (missing {ENC_EXT}): {file_path}")

    data = file_path.read_bytes()
    header_len = len(MAGIC) + len(VERSION) + SALT_SIZE + NONCE_SIZE
    if len(data) < header_len:
        raise ValueError(f"File too short / corrupt: {file_path}")

    if data[:len(MAGIC)] != MAGIC:
        raise ValueError(f"Bad magic header (not our format): {file_path}")
    pos = len(MAGIC)
    version = data[pos:pos + len(VERSION)]
    pos += len(VERSION)
    if version != VERSION:
        raise ValueError(f"Unsupported version: {version!r}")

    salt = data[pos:pos + SALT_SIZE]
    pos += SALT_SIZE
    nonce = data[pos:pos + NONCE_SIZE]
    pos += NONCE_SIZE
    ciphertext = data[pos:]

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError(
            f"Decryption failed (wrong password or corrupted file): {file_path}"
        ) from exc

    # Strip .enc
    out_path = file_path.with_suffix("")
    out_path.write_bytes(plaintext)

    if delete_original:
        file_path.unlink()

    print(f"  [dec] {file_path.name} -> {out_path.name}")
    return out_path


# ---------------------------------------------------------------------------
# Folder encryption / decryption
# ---------------------------------------------------------------------------
def encrypt_folder(folder: Path, password: str, delete_originals: bool = False) -> None:
    """Recursively encrypt all files in a folder."""
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix != ENC_EXT]
    print(f"Encrypting {len(files)} file(s) under {folder} ...")
    for f in files:
        try:
            encrypt_file(f, password, delete_original=delete_originals)
        except Exception as exc:
            print(f"  [error] {f}: {exc}")


def decrypt_folder(folder: Path, password: str, delete_originals: bool = False) -> None:
    """Recursively decrypt all .enc files in a folder."""
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    files = [p for p in folder.rglob(f"*{ENC_EXT}") if p.is_file()]
    print(f"Decrypting {len(files)} file(s) under {folder} ...")
    for f in files:
        try:
            decrypt_file(f, password, delete_original=delete_originals)
        except Exception as exc:
            print(f"  [error] {f}: {exc}")


# ---------------------------------------------------------------------------
# Optional: package a whole folder into a single encrypted archive
# ---------------------------------------------------------------------------
def encrypt_folder_as_archive(folder: Path, password: str) -> Path:
    """Tar + gzip the folder in memory, then encrypt into <folder>.tar.gz.enc"""
    import tarfile
    import io

    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(folder, arcname=folder.name)
    plaintext = buf.getvalue()

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    out_path = folder.with_name(folder.name + ".tar.gz" + ENC_EXT)
    with open(out_path, "wb") as f:
        f.write(MAGIC)
        f.write(VERSION)
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

    print(f"[enc-archive] {folder} -> {out_path.name}")
    return out_path


def decrypt_archive(archive: Path, password: str, out_dir: Path = None) -> Path:
    """Decrypt an archive created by encrypt_folder_as_archive and extract it."""
    import tarfile
    import io

    data = archive.read_bytes()
    pos = len(MAGIC) + len(VERSION)
    salt = data[pos:pos + SALT_SIZE]; pos += SALT_SIZE
    nonce = data[pos:pos + NONCE_SIZE]; pos += NONCE_SIZE
    ciphertext = data[pos:]

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception as exc:
        raise ValueError("Decryption failed (wrong password or corrupted archive)") from exc

    out_dir = out_dir or archive.parent
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tar:
        tar.extractall(path=out_dir)
    print(f"[dec-archive] extracted to {out_dir}")
    return out_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AES-256-GCM file/folder encryption tool")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("encrypt", "decrypt"):
        p = sub.add_parser(name)
        p.add_argument("path", type=Path)
        p.add_argument("password")
        p.add_argument("--delete", action="store_true", help="Delete original file")

    for name in ("encrypt-folder", "decrypt-folder"):
        p = sub.add_parser(name)
        p.add_argument("folder", type=Path)
        p.add_argument("password")
        p.add_argument("--delete", action="store_true", help="Delete original files")

    p_ea = sub.add_parser("encrypt-archive", help="Tar folder then encrypt into one file")
    p_ea.add_argument("folder", type=Path)
    p_ea.add_argument("password")

    p_da = sub.add_parser("decrypt-archive", help="Decrypt + extract an archive")
    p_da.add_argument("archive", type=Path)
    p_da.add_argument("password")
    p_da.add_argument("--out", type=Path, default=None)

    args = parser.parse_args()

    try:
        if args.command == "encrypt":
            encrypt_file(args.path, args.password, args.delete)
        elif args.command == "decrypt":
            decrypt_file(args.path, args.password, args.delete)
        elif args.command == "encrypt-folder":
            encrypt_folder(args.folder, args.password, args.delete)
        elif args.command == "decrypt-folder":
            decrypt_folder(args.folder, args.password, args.delete)
        elif args.command == "encrypt-archive":
            encrypt_folder_as_archive(args.folder, args.password)
        elif args.command == "decrypt-archive":
            decrypt_archive(args.archive, args.password, args.out)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()



"""
# Encrypt a single file
python crypt_tool.py encrypt secret.pdf "MyStr0ngPass!"
python crypt_tool.py encrypt secret.pdf "MyStr0ngPass!" --delete

# Decrypt it
python crypt_tool.py decrypt secret.pdf.enc "MyStr0ngPass!"
python crypt_tool.py decrypt secret.pdf.enc "MyStr0ngPass!" --delete

# Encrypt every file inside a folder (recursively, in-place)
python crypt_tool.py encrypt-folder ./myfolder "password123" --delete

# Decrypt them all back
python crypt_tool.py decrypt-folder ./myfolder "password123"

# Or pack an entire folder into ONE encrypted archive (recommended)
python crypt_tool.py encrypt-archive ./project "password123"
#  -> project.tar.gz.enc

python crypt_tool.py decrypt-archive project.tar.gz.enc "password123" --out ./restored
"""