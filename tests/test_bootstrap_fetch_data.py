"""Unit tests for :mod:`u4cht.bootstrap.fetch_data`.

網路完全被 mock 掉；用合成 zip / tarball 驗證解壓語意。
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from u4cht.bootstrap.fetch_data import (
    DOS_EXE_NAMES,
    TLK_NAMES,
    _extract_from_zip,
    _extract_xu4_tarball,
    _sha256_file,
    fetch_data,
)
from u4cht.cli import main

# ── helpers ─────────────────────────────────────────────────────────────────

def _make_synthetic_ultima4_zip(dst: Path) -> None:
    """組一個假的 ultima4.zip：含 16 個 .TLK + 2 個 .exe + 額外雜檔。

    - TLK 內容：符合 tlk.py 語意的 288 bytes（讓 extract-tlk 可能解得動）
    - exe 內容：任意小 payload（只驗解壓）
    - 檔名故意混用大小寫，驗 case_insensitive
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w") as zf:
        # 16 個 .TLK — 一半小寫、一半大寫，驗 case-insensitive
        for i, name in enumerate(TLK_NAMES):
            written = name.lower() if i % 2 == 0 else name.upper()
            # 288 bytes: 1 (questionFlag) + 3 (idx) + 剩下 null-terminated 12 段
            data = b"\x03\x00\x01\x01" + b"question?\x00" + b"\x00" * (288 - 14)
            zf.writestr(f"u4/{written}", data[:288])
        # exe 一律小寫
        for name in DOS_EXE_NAMES:
            zf.writestr(name, b"fake-exe-payload")
        # 一些垃圾檔應被忽略
        zf.writestr("README.txt", b"noise")
        zf.writestr("subdir/", b"")


class _FakeUrlOpen:
    """替換 urllib.request.urlopen，回傳預先組好的 bytes。"""

    def __init__(self, url_to_bytes: dict[str, bytes]):
        self.url_to_bytes = url_to_bytes
        self.calls: list[str] = []

    def __call__(self, req, timeout: float = 60):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        self.calls.append(url)
        try:
            payload = self.url_to_bytes[url]
        except KeyError as exc:
            raise RuntimeError(f"unexpected URL: {url!r}") from exc
        # context manager 模擬
        buf = io.BytesIO(payload)
        buf.__enter__ = lambda: buf  # type: ignore[method-assign]
        buf.__exit__ = lambda *_: None  # type: ignore[method-assign]
        return buf


# ── _extract_from_zip ───────────────────────────────────────────────────────

def test_extract_from_zip_case_insensitive_and_uppercase(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("britain.tlk", b"payload-A")
        zf.writestr("path/COVE.TLK", b"payload-B")
        zf.writestr("noise.dat", b"skip")

    out = tmp_path / "out"
    got = _extract_from_zip(
        zip_path, out, ("BRITAIN.TLK", "COVE.TLK"),
        case_insensitive=True, uppercase_output=True,
    )
    assert got == ["BRITAIN.TLK", "COVE.TLK"]
    assert (out / "BRITAIN.TLK").read_bytes() == b"payload-A"
    assert (out / "COVE.TLK").read_bytes() == b"payload-B"
    assert not (out / "noise.dat").exists()


def test_extract_from_zip_lowercase_output(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("TITLE.EXE", b"exe")
        zf.writestr("AVATAR.EXE", b"exe2")

    out = tmp_path / "out"
    got = _extract_from_zip(
        zip_path, out, ("title.exe", "avatar.exe"),
        case_insensitive=True, uppercase_output=False,
    )
    assert got == ["avatar.exe", "title.exe"]
    assert (out / "title.exe").exists()


def test_extract_from_zip_missing_is_silent(tmp_path: Path) -> None:
    zip_path = tmp_path / "src.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("only.txt", b"x")
    got = _extract_from_zip(zip_path, tmp_path / "out", ("MISSING.TLK",))
    assert got == []


# ── _sha256_file ────────────────────────────────────────────────────────────

def test_sha256_of_known_content(tmp_path: Path) -> None:
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello")
    # sha256 of "hello"
    assert _sha256_file(p) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


# ── fetch_data 端到端（mock 網路）──────────────────────────────────────────

@pytest.fixture()
def fake_zip_bytes(tmp_path: Path) -> bytes:
    p = tmp_path / "_seed.zip"
    _make_synthetic_ultima4_zip(p)
    return p.read_bytes()


def test_fetch_data_end_to_end(
    tmp_path: Path,
    fake_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from u4cht.bootstrap import fetch_data as mod

    fake = _FakeUrlOpen({
        "http://ultima.thatfleminggent.com/ultima4.zip": fake_zip_bytes,
    })
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)

    out_dir = tmp_path / "data"
    result = fetch_data(out_dir=out_dir, with_upgrade=False, force=False, log=None)

    assert set(result.tlk_files) == set(TLK_NAMES)
    assert set(result.dos_files) == set(DOS_EXE_NAMES)
    assert "ultima4.zip" in result.downloaded
    assert result.u4upgrade_zip_sha256 is None
    # 檔案實際落地
    for name in TLK_NAMES:
        assert (out_dir / "tlk" / name).exists()
    for name in DOS_EXE_NAMES:
        assert (out_dir / "dos" / name).exists()
    # SHA-256 非空
    assert len(result.ultima4_zip_sha256) == 64
    # 只打了一個 URL
    assert fake.calls == ["http://ultima.thatfleminggent.com/ultima4.zip"]


def test_fetch_data_skips_when_zip_cached(
    tmp_path: Path,
    fake_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from u4cht.bootstrap import fetch_data as mod

    out_dir = tmp_path / "data"
    downloads = out_dir / "downloads"
    downloads.mkdir(parents=True)
    (downloads / "ultima4.zip").write_bytes(fake_zip_bytes)

    fake = _FakeUrlOpen({})  # 任何 URL 都會 raise
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)

    result = fetch_data(out_dir=out_dir, with_upgrade=False, force=False, log=None)
    assert result.downloaded == ()  # 沒下載
    assert fake.calls == []
    assert set(result.tlk_files) == set(TLK_NAMES)


def test_fetch_data_force_redownloads(
    tmp_path: Path,
    fake_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from u4cht.bootstrap import fetch_data as mod

    out_dir = tmp_path / "data"
    downloads = out_dir / "downloads"
    downloads.mkdir(parents=True)
    (downloads / "ultima4.zip").write_bytes(b"stale")

    fake = _FakeUrlOpen({
        "http://ultima.thatfleminggent.com/ultima4.zip": fake_zip_bytes,
    })
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)

    result = fetch_data(out_dir=out_dir, with_upgrade=False, force=True, log=None)
    assert "ultima4.zip" in result.downloaded
    # 舊的假 zip 已被覆蓋成真的
    assert (downloads / "ultima4.zip").read_bytes() == fake_zip_bytes


def test_fetch_data_with_upgrade_fetches_both(
    tmp_path: Path,
    fake_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from u4cht.bootstrap import fetch_data as mod

    fake_upgrade = b"fake-upgrade-zip-bytes"
    fake = _FakeUrlOpen({
        "http://ultima.thatfleminggent.com/ultima4.zip": fake_zip_bytes,
        "http://sourceforge.net/projects/xu4/files/"
        "Ultima%204%20VGA%20Upgrade/1.3/u4upgrad.zip": fake_upgrade,
    })
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)

    result = fetch_data(out_dir=tmp_path / "data", with_upgrade=True, force=False, log=None)
    assert set(result.downloaded) == {"ultima4.zip", "u4upgrad.zip"}
    assert result.u4upgrade_zip_sha256 is not None
    assert len(result.u4upgrade_zip_sha256) == 64


# ── xu4 tarball ─────────────────────────────────────────────────────────────

def _make_synthetic_xu4_tarball(dst: Path) -> None:
    """組一個假的 xu4 tarball。GitHub 的 tarball 一律以 `u4-master/` 為最外層。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    entries: dict[str, bytes] = {
        "u4-master/src/game.cpp": b'screenMessage("hi");\n',
        "u4-master/src/combat.cpp": b'screenMessage("\\n");\n',
        "u4-master/src/screen.h": b"int screen_x;\n",
        "u4-master/module/Ultima-IV/vendors.b": b'"welcome to shop"\n',
        "u4-master/module/Ultima-IV/README.txt": b"Ultima IV module\n",
        # Build 系統檔（A1 emscripten build 需要）
        "u4-master/Makefile": b"all:\n\techo top-level\n",
        "u4-master/configure": b"#!/bin/sh\necho configuring\n",
        "u4-master/src/Makefile": b"xu4:\n\techo build\n",
        "u4-master/android/Android.mk": b"LOCAL_MODULE := xu4\n",
        # 應被過濾掉：非文字類
        "u4-master/module/Ultima-IV/tiles.png": b"\x89PNG binary",
        "u4-master/render.pak": b"binary blob",
    }
    with tarfile.open(dst, "w:gz") as tf:
        for name, payload in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = 0
            tf.addfile(info, io.BytesIO(payload))


def test_extract_xu4_tarball_filters_binary(tmp_path: Path) -> None:
    tar_path = tmp_path / "xu4.tar.gz"
    _make_synthetic_xu4_tarball(tar_path)

    dest = tmp_path / "xu4"
    src_count, vendors_b = _extract_xu4_tarball(tar_path, dest, log=None)

    # game.cpp + combat.cpp + screen.h = 3（src_count 只算 src/ 下的 .cpp/.c/.h）
    assert src_count == 3
    assert vendors_b is not None
    assert vendors_b == dest / "module" / "Ultima-IV" / "vendors.b"
    assert vendors_b.exists()

    # 檔案已剝去 u4-master/ 最外層
    assert (dest / "src" / "game.cpp").exists()
    assert (dest / "src" / "screen.h").exists()
    assert (dest / "module" / "Ultima-IV" / "README.txt").exists()
    # Build 系統檔（A1 需要）
    assert (dest / "Makefile").exists()
    assert (dest / "configure").exists()
    assert (dest / "src" / "Makefile").exists()
    assert (dest / "android" / "Android.mk").exists()
    # 非文字類被過濾
    assert not (dest / "module" / "Ultima-IV" / "tiles.png").exists()
    assert not (dest / "render.pak").exists()


def test_extract_xu4_tarball_missing_vendors_b(tmp_path: Path) -> None:
    tar_path = tmp_path / "xu4.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        payload = b"x"
        info = tarfile.TarInfo("u4-master/src/only.cpp")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))

    src_count, vendors_b = _extract_xu4_tarball(tar_path, tmp_path / "out", log=None)
    assert src_count == 1
    assert vendors_b is None


def test_fetch_data_with_xu4_src(
    tmp_path: Path,
    fake_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from u4cht.bootstrap import fetch_data as mod

    tar_path = tmp_path / "_seed.tar.gz"
    _make_synthetic_xu4_tarball(tar_path)
    tar_bytes = tar_path.read_bytes()

    fake = _FakeUrlOpen({
        "http://ultima.thatfleminggent.com/ultima4.zip": fake_zip_bytes,
        "https://github.com/xu4-engine/u4/archive/refs/heads/master.tar.gz": tar_bytes,
    })
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)

    out_dir = tmp_path / "data"
    result = fetch_data(
        out_dir=out_dir, with_upgrade=False, with_xu4_src=True, force=False, log=None,
    )
    assert result.xu4_src_files == 3
    assert result.vendors_b_path is not None
    assert result.vendors_b_path == out_dir / "xu4" / "module" / "Ultima-IV" / "vendors.b"
    assert result.xu4_tarball_sha256 is not None
    assert "xu4-master.tar.gz" in result.downloaded


# ── CLI ─────────────────────────────────────────────────────────────────────

def test_cli_fetch_data(
    tmp_path: Path,
    fake_zip_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from u4cht.bootstrap import fetch_data as mod

    fake = _FakeUrlOpen({
        "http://ultima.thatfleminggent.com/ultima4.zip": fake_zip_bytes,
    })
    monkeypatch.setattr(mod.urllib.request, "urlopen", fake)

    out_dir = tmp_path / "data"
    runner = CliRunner()
    result = runner.invoke(main, ["fetch-data", "--out", str(out_dir)])

    assert result.exit_code == 0, result.output
    assert ".TLK 解壓：16 / 16" in result.output
    assert "DOS exe：2 / 2" in result.output
    assert (out_dir / "tlk" / "BRITAIN.TLK").exists()
    assert (out_dir / "dos" / "title.exe").exists()
