"""下載 Ultima IV DOS 原始資料檔（freeware）並解壓成本工具鏈可用的目錄結構。

**來源**（沿用 xu4 upstream `Makefile` 的 `download:` 目標）：

- `ultima4.zip` → `http://ultima.thatfleminggent.com/ultima4.zip`
  - 由 Origin Systems 於 1990 宣布 freeware，含 `.TLK` × 16 + `title.exe` + `avatar.exe`
    + 地圖/tile/字型/MIDI 等完整 DOS 遊戲檔
- `u4upgrad.zip` → `http://sourceforge.net/projects/xu4/files/.../u4upgrad.zip`
  - VGA 圖磚升級包（1.3），可選；本專案 Phase 1 工具鏈**不需要**

**輸出結構**（預設 `--out data/`）::

    data/
    ├── downloads/
    │   ├── ultima4.zip
    │   └── u4upgrad.zip   (若指定 --with-upgrade)
    ├── dos/               ← 給 extract-strings 用
    │   ├── title.exe
    │   └── avatar.exe
    └── tlk/               ← 給 extract-tlk 用
        └── *.TLK (16 檔)

用完可直接：

    u4cht extract-tlk     --tlk-dir data/tlk   --out out/talk.json
    u4cht extract-strings --data-dir data/dos  --out out/strings.json
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

# ── 常數 ────────────────────────────────────────────────────────────────────

ULTIMA4_URL = "http://ultima.thatfleminggent.com/ultima4.zip"
U4UPGRADE_URL = (
    "http://sourceforge.net/projects/xu4/files/"
    "Ultima%204%20VGA%20Upgrade/1.3/u4upgrad.zip"
)
XU4_TARBALL_URL = "https://github.com/xu4-engine/u4/archive/refs/heads/master.tar.gz"

TLK_NAMES: tuple[str, ...] = (
    "BRITAIN.TLK", "COVE.TLK", "DEN.TLK", "EMPATH.TLK",
    "JHELOM.TLK", "LCB.TLK", "LYCAEUM.TLK", "MAGINCIA.TLK",
    "MINOC.TLK", "MOONGLOW.TLK", "PAWS.TLK", "SERPENT.TLK",
    "SKARA.TLK", "TRINSIC.TLK", "VESPER.TLK", "YEW.TLK",
)

DOS_EXE_NAMES: tuple[str, ...] = ("title.exe", "avatar.exe")


# ── 資料模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class FetchResult:
    """單次 fetch-data 執行的統計結果。"""

    downloaded: tuple[str, ...]     # 本次實際下載的檔（未 hit cache 者）
    tlk_files: tuple[str, ...]      # 已解壓的 .TLK 檔名
    dos_files: tuple[str, ...]      # 已解壓的 .exe 檔名
    xu4_src_files: int              # 已解壓的 xu4 .cpp/.c/.h 數 (0 表未取)
    vendors_b_path: Path | None     # 已解壓的 vendors.b 路徑 (None 表未取)
    ultima4_zip_sha256: str
    u4upgrade_zip_sha256: str | None
    xu4_tarball_sha256: str | None


# ── 純函式 ──────────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    """算檔案 SHA-256 hex。"""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, out: Path, log: TextIO | None = None) -> bool:
    """把 `url` 下載到 `out`；已存在則跳過（回傳 False）。

    以 `.part` 檔暫存，成功後 rename，避免部分寫入殘留。
    """
    if out.exists() and out.stat().st_size > 0:
        if log is not None:
            print(f"  [skip] {out.name} 已存在 ({out.stat().st_size:,} bytes)", file=log)
        return False

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    if log is not None:
        print(f"  [get ] {url}", file=log)

    req = urllib.request.Request(url, headers={"User-Agent": "u4cht/fetch-data"})
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as ofh:
        shutil.copyfileobj(resp, ofh, length=65536)
    tmp.replace(out)

    if log is not None:
        print(f"  [done] {out.name} ({out.stat().st_size:,} bytes)", file=log)
    return True


def _extract_from_zip(
    zip_path: Path,
    dest: Path,
    wanted_names: tuple[str, ...],
    case_insensitive: bool = True,
    uppercase_output: bool = False,
) -> list[str]:
    """從 zip 內取出 `wanted_names` 檔案到 `dest`。

    - `case_insensitive=True`: zip 內名字大小寫不敏感比對
    - `uppercase_output=True`: 輸出檔名一律轉大寫（`.TLK` 語意）
    - 找不到的檔案會被略過（不報錯，回傳的清單反映實際解出的檔）
    """
    dest.mkdir(parents=True, exist_ok=True)
    wanted_lower = {n.lower() for n in wanted_names}
    extracted: list[str] = []

    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            base = Path(info.filename).name  # 去掉 zip 內可能的路徑
            key = base.lower() if case_insensitive else base
            if key not in wanted_lower:
                continue
            out_name = base.upper() if uppercase_output else base.lower()
            out_path = dest / out_name
            with zf.open(info) as src, out_path.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=65536)
            extracted.append(out_name)

    extracted.sort()
    return extracted


# ── xu4 tarball 解壓 ────────────────────────────────────────────────────────

def _extract_xu4_tarball(
    tar_path: Path,
    dest: Path,
    log: TextIO | None = None,
) -> tuple[int, Path | None]:
    """把 xu4 tarball 解壓到 `dest`，剝掉 tar 內最外一層 `u4-master/` 目錄。

    採 **deny-list** 策略：跳過已知大型 binary 副檔名（module 資產 / 圖磚 /
    音樂），其餘全部解壓。這讓 A1/A2 emscripten build 能拿到全部原始碼、
    build 系統檔（Makefile.common / .sh / .glsl 等）而不用每次追加白名單。

    回傳 `(src 檔案數, vendors.b 絕對路徑或 None)`；
    `src 檔案數` 只算 `src/*.cpp`, `src/*.c`, `src/*.h`（不遞迴）。
    """
    dest.mkdir(parents=True, exist_ok=True)

    # 明確跳過的 binary 副檔名：module assets、rich media
    skip_suffixes = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".icns",
        ".wav", ".mp3", ".mid", ".ogg", ".flac",
        ".pak", ".zip", ".tar", ".gz", ".7z",
        ".rfx",           # xu4 音效格式（binary）
        ".ttf", ".woff", ".woff2", ".otf",
        ".jar", ".apk", ".class",
    }
    src_count = 0
    vendors_b: Path | None = None

    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            # 剝最外層資料夾（github tarball 一律 u4-master/*）
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            rel = Path(*parts[1:])
            # 過濾：拒絕已知 binary 副檔名，其餘全留
            if rel.suffix.lower() in skip_suffixes:
                continue

            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            with extracted, target.open("wb") as ofh:
                shutil.copyfileobj(extracted, ofh, length=65536)

            if (
                rel.suffix.lower() in {".cpp", ".c", ".h", ".hpp", ".cc"}
                and parts[1] == "src"
            ):
                src_count += 1
            if rel.name == "vendors.b" and "Ultima-IV" in rel.parts:
                vendors_b = target

    if log is not None:
        print(f"  [ok  ] xu4 src: {src_count} 個 .cpp/.c/.h 檔", file=log)
        if vendors_b is not None:
            print(f"  [ok  ] vendors.b @ {vendors_b.relative_to(dest.parent)}", file=log)
        else:
            print("  [warn] 找不到 vendors.b（xu4 upstream 結構變更？）", file=log)

    return src_count, vendors_b


# ── 主入口 ──────────────────────────────────────────────────────────────────

def fetch_data(
    out_dir: Path,
    with_upgrade: bool = False,
    with_xu4_src: bool = False,
    force: bool = False,
    log: TextIO | None = None,
) -> FetchResult:
    """下載 + 解壓完整流程。

    Args:
        out_dir: 頂層輸出資料夾（將建立 `downloads/`、`dos/`、`tlk/`、`xu4/` 子資料夾）
        with_upgrade: 是否額外下載 `u4upgrad.zip`（VGA 升級包，Phase 1 不需要）
        with_xu4_src: 是否額外下載 xu4 upstream 全樹（給 extract-hardcoded / extract-vendor 用）
        force: 重下（刪掉舊 zip / tarball 快取）
        log: 進度輸出（例如 sys.stdout）；None 則靜默

    Returns:
        `FetchResult` 統計摘要
    """
    downloads_dir = out_dir / "downloads"
    dos_dir = out_dir / "dos"
    tlk_dir = out_dir / "tlk"
    xu4_dir = out_dir / "xu4"

    ultima4_zip = downloads_dir / "ultima4.zip"
    u4upgrade_zip = downloads_dir / "u4upgrad.zip"
    xu4_tarball = downloads_dir / "xu4-master.tar.gz"

    if force:
        for p in (ultima4_zip, u4upgrade_zip, xu4_tarball):
            if p.exists():
                if log is not None:
                    print(f"  [wipe] {p.name}", file=log)
                p.unlink()

    downloaded: list[str] = []
    total_steps = 3 + (1 if with_xu4_src else 0)

    if log is not None:
        print(f"== Step 1/{total_steps}: 下載 freeware zip ==", file=log)
    if _download(ULTIMA4_URL, ultima4_zip, log=log):
        downloaded.append("ultima4.zip")

    u4up_sha: str | None = None
    if with_upgrade:
        if _download(U4UPGRADE_URL, u4upgrade_zip, log=log):
            downloaded.append("u4upgrad.zip")
        u4up_sha = _sha256_file(u4upgrade_zip)

    if log is not None:
        print(f"\n== Step 2/{total_steps}: 解壓 .TLK → tlk/ ==", file=log)
    tlk_files = tuple(_extract_from_zip(
        ultima4_zip, tlk_dir, TLK_NAMES,
        case_insensitive=True, uppercase_output=True,
    ))
    if log is not None:
        print(f"  [ok  ] {len(tlk_files)} 個 .TLK 解壓完成", file=log)
        missing = set(TLK_NAMES) - set(tlk_files)
        if missing:
            print(f"  [warn] 缺 {len(missing)} 個 .TLK: {sorted(missing)}", file=log)

    if log is not None:
        print(f"\n== Step 3/{total_steps}: 解壓 title.exe / avatar.exe → dos/ ==", file=log)
    dos_files = tuple(_extract_from_zip(
        ultima4_zip, dos_dir, DOS_EXE_NAMES,
        case_insensitive=True, uppercase_output=False,
    ))
    if log is not None:
        print(f"  [ok  ] {len(dos_files)} 個 exe 解壓完成", file=log)
        missing = set(DOS_EXE_NAMES) - set(dos_files)
        if missing:
            print(f"  [warn] 缺: {sorted(missing)}", file=log)

    src_count = 0
    vendors_b: Path | None = None
    xu4_tarball_sha: str | None = None
    if with_xu4_src:
        if log is not None:
            print(f"\n== Step 4/{total_steps}: 下載 xu4 upstream tarball ==", file=log)
        if _download(XU4_TARBALL_URL, xu4_tarball, log=log):
            downloaded.append("xu4-master.tar.gz")
        xu4_tarball_sha = _sha256_file(xu4_tarball)
        if log is not None:
            print("  [.. ] 解壓 xu4 全樹（原始碼 + build 系統，跳過大 binary）", file=log)
        src_count, vendors_b = _extract_xu4_tarball(xu4_tarball, xu4_dir, log=log)

    return FetchResult(
        downloaded=tuple(downloaded),
        tlk_files=tlk_files,
        dos_files=dos_files,
        xu4_src_files=src_count,
        vendors_b_path=vendors_b,
        ultima4_zip_sha256=_sha256_file(ultima4_zip),
        u4upgrade_zip_sha256=u4up_sha,
        xu4_tarball_sha256=xu4_tarball_sha,
    )
