# Simple-Tic-Tac-Toe-Ransomware
# Ransomware Simulation Tool - Red Team Project

## ⚠️ CRITICAL WARNING ⚠️

**THIS IS AN EDUCATIONAL/RESEARCH TOOL ONLY**

This software is a ransomware simulation created **strictly for authorized red team exercises, malware analysis training, and security research** in controlled environments. 

**DO NOT RUN THIS CODE ON ANY SYSTEM YOU DO NOT OWN OR HAVE EXPLICIT WRITTEN AUTHORIZATION TO TEST.**

Unauthorized use of this software may violate:
- Computer Fraud and Abuse Act (CFAA) and similar laws worldwide
- Data protection regulations (GDPR, etc.)
- University/organizational acceptable use policies
- Criminal statutes regarding computer intrusion and data destruction

The authors assume **no liability** for misuse, data loss, or legal consequences resulting from improper use of this code.

---

## Overview

This project demonstrates ransomware behavior for defensive research and red team training. It consists of two components:

| File | Purpose |
|------|---------|
| `encryptor.py` | AES-256-GCM file encryption engine with multi-threaded/process worker support |
| `tic_tac_toe.py` | Social engineering wrapper that disguises the encryptor as a benign game |

The tool encrypts files in common user directories, optionally deletes originals, and leaves a ransom note. It is designed to help security teams understand ransomware TTPs (Tactics, Techniques, and Procedures) in a safe, contained manner.

---

## Features

### Encryption Engine (`encryptor.py`)
- **AES-256-GCM** authenticated encryption via `cryptography` library
- **PBKDF2-HMAC-SHA256** key derivation with 480,000 iterations
- Per-file random **salt (16 bytes)** and **nonce (12 bytes)**
- Custom file header format: `MAGIC (4B) | VERSION (1B) | SALT (16B) | NONCE (12B) | CIPHERTEXT`
- Recursive directory traversal with `rglob`
- **Multi-threaded** (default) or **multi-process** execution modes
- Automatic dependency installation (attempts `pip install cryptography`)
- Console hiding on Windows (no visible window when launched)
- Optional original file deletion after successful encryption
- Skips already-encrypted files (`.enc` extension)
- Graceful `KeyboardInterrupt` handling with task cancellation

### Social Engineering Wrapper (`tic_tac_toe.py`)
- Fully functional Tic-Tac-Toe game
- Silently launches `encryptor.py` in the background on startup
- Captures encryptor output (no visible console popup)
- Creates a plausible cover story for the encryption activity

### Ransom Note
After encrypting each folder, a `README.txt` is written containing a simulated ransom demand.

---

## Technical Details

### File Format

```
Offset  Size    Field
------  ----    -----
0       4       Magic bytes: "ENCF"
4       1       Version: 0x01
5       16      Salt (random per file)
21      12      Nonce (random per file)
33      var     AES-256-GCM ciphertext + 16-byte auth tag
```

### Key Derivation

```
key = PBKDF2-HMAC-SHA256(
    password = "G24k34932_^&@jd",
    salt     = random_16_bytes,
    iterations = 480000,
    length   = 32
)
```

### Default Targets

The hardcoded mode targets:
- `~/Downloads`
- `~/Documents`
- `~/Desktop`
- `~/OneDrive`
- `~/Pictures`
- `~/Videos`

### Execution Modes

| Mode | Flag | Description |
|------|------|-------------|
| Thread | `--mode thread` | Default; uses `ThreadPoolExecutor` |
| Process | `--mode process` | Uses `ProcessPoolExecutor` for CPU-bound parallelism |

Worker count defaults to `os.cpu_count()`. Files are processed in batches of 32.

---

## Usage

### Prerequisites
- Python 3.8+
- `cryptography` package (auto-installed if missing)

### Interactive Mode (Disguised)
```bash
python tic_tac_toe.py
```
Launches the game and silently executes the encryptor with hardcoded settings.

### Direct CLI Mode
```bash
# Encrypt a specific folder
python encryptor.py /path/to/folder "password"

# Encrypt and delete originals
python encryptor.py /path/to/folder "password" --delete

# Specify worker count and backend
python encryptor.py /path/to/folder "password" --workers 8 --mode process

# No arguments = hardcoded targets + hidden console (Windows)
python encryptor.py
```

### CLI Arguments

| Argument | Description |
|----------|-------------|
| `folder` | Target directory (optional; defaults to hardcoded list) |
| `password` | Encryption passphrase (optional; defaults to hardcoded value) |
| `--delete` | Delete original files after encryption |
| `--workers N` | Number of worker threads/processes (default: CPU count) |
| `--mode {thread,process}` | Worker backend (default: thread) |

---

## Configuration

Edit the constants at the top of `encryptor.py`:

```python
TARGET_FOLDERS  = [...]           # Directories to encrypt
PASSWORD        = "..."           # Encryption password
DELETE_ORIGINAL = True            # Remove originals after encryption
WORKERS         = None            # None = auto (CPU count)
EXECUTION_MODE  = "thread"        # "thread" or "process"
CHUNK_SIZE      = 32              # Files per batch
KDF_ITERATIONS  = 480_000         # PBKDF2 iterations
```

---

## Detection & Defense Considerations

This project is useful for testing the following defensive controls:

- **EDR/AV signatures** — AES-GCM encryption patterns, high-entropy file writes
- **Behavioral detection** — mass file modification, rapid extension changes
- **Honeypot files** — files in monitored directories triggering alerts
- **Backup/restore validation** — recovery from encrypted state
- **User awareness training** — recognizing disguised executables
- **Application allowlisting** — blocking unauthorized Python execution
- **File integrity monitoring (FIM)** — detecting mass `.enc` file creation

### Indicators of Compromise (IOCs)
- Files with `.enc` extension appended to original names
- `README.txt` ransom notes in user directories
- High-volume PBKDF2 CPU usage (480k iterations per file)
- Python processes reading from `~/Documents`, `~/Pictures`, etc.
- Unusual `pip install cryptography` activity

---

## Legal & Ethical Notice

This code is provided **solely for**:
- Authorized penetration testing engagements
- Red team exercises with signed rules of engagement
- Malware analysis and reverse engineering education
- Defensive security research in isolated lab environments

**You must:**
1. Obtain **written authorization** before running on any system
2. Use **isolated VMs or dedicated test machines** — never production systems
3. Maintain **offline backups** of all test data
4. Comply with all applicable laws and organizational policies
5. Never deploy this against systems you do not own

The hardcoded Bitcoin address (`ctf{lazarus_bitcoin_wallet}`) is a **CTF-style placeholder** and not a real wallet.

---

## Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

**Use at your own risk. You are solely responsible for your actions.**

---

## References

- [MITRE ATT&CK — Data Encrypted for Impact (T1486)](https://attack.mitre.org/techniques/T1486/)
- [NIST SP 800-38D — GCM Mode](https://csrc.nist.gov/publications/detail/sp/800-38d/final)
- [RFC 8018 — PBKDF2](https://datatracker.ietf.org/doc/html/rfc8018)
- [cryptography.io Documentation](https://cryptography.io/)

---

## License

This project is released for **educational and authorized security testing purposes only**. Redistribution for malicious use is strictly prohibited.
