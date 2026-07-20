"""u4cht 統一 CLI 入口。

實作進度追蹤於 docs/ai_planning/PLAN.md。
"""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .bootstrap import fetch_data as fetch_data_mod
from .extract import hardcoded as hardcoded_extract
from .extract import strings as strings_extract
from .extract import tlk as tlk_extract
from .extract import vendor as vendor_extract


@click.group(help="Ultima IV 繁中在地化 — Python 工具鏈")
@click.version_option(__version__, prog_name="u4cht")
def main() -> None:
    """CLI 入口。"""


@main.command("info")
def info() -> None:
    """列出目前實作進度。"""
    click.echo(f"u4cht {__version__}")
    click.echo("Phase 0 骨架 ✅")
    click.echo(
        "Phase 1 完成：extract-tlk ✅  extract-strings ✅  "
        "extract-hardcoded ✅  extract-vendor ✅"
    )
    click.echo("Bootstrap：fetch-data ✅")
    click.echo("實作進度：docs/ai_planning/PLAN.md")


@main.command("fetch-data")
@click.option(
    "--out",
    "out_dir",
    default=Path("data"),
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="頂層輸出資料夾（將建立 downloads/ dos/ tlk/ xu4/ 子資料夾）。",
)
@click.option(
    "--with-upgrade",
    is_flag=True,
    default=False,
    help="額外下載 u4upgrad.zip（VGA 升級包，Phase 1 不需要）。",
)
@click.option(
    "--with-xu4-src",
    is_flag=True,
    default=False,
    help="額外下載 xu4 upstream 全樹（給 extract-hardcoded / extract-vendor 用）。",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="重下（刪掉舊 zip / tarball 快取）。",
)
def fetch_data_cmd(
    out_dir: Path,
    with_upgrade: bool,
    with_xu4_src: bool,
    force: bool,
) -> None:
    """下載 freeware Ultima IV DOS 資料檔到本地（供後續 extract-* 使用）。"""
    import sys

    result = fetch_data_mod.fetch_data(
        out_dir=out_dir,
        with_upgrade=with_upgrade,
        with_xu4_src=with_xu4_src,
        force=force,
        log=sys.stdout,
    )
    click.echo("")
    click.echo("== 完成 ==")
    click.echo(f".TLK 解壓：{len(result.tlk_files)} / 16")
    click.echo(f"DOS exe：{len(result.dos_files)} / 2 ({', '.join(result.dos_files)})")
    if with_xu4_src:
        click.echo(f"xu4 src：{result.xu4_src_files} 個 .cpp/.c/.h")
        click.echo(f"vendors.b：{result.vendors_b_path if result.vendors_b_path else '（未找到）'}")
    click.echo(f"ultima4.zip SHA-256: {result.ultima4_zip_sha256}")
    click.echo("")
    click.echo("下一步：")
    click.echo(f"  u4cht extract-tlk     --tlk-dir  {out_dir / 'tlk'} --out out/talk.json")
    click.echo(f"  u4cht extract-strings --data-dir {out_dir / 'dos'} --out out/strings.json")
    if with_xu4_src and result.xu4_src_files > 0:
        click.echo(
            f"  u4cht extract-hardcoded --src-dir {out_dir / 'xu4' / 'src'} "
            f"--out out/hardcoded.json"
        )
    if with_xu4_src and result.vendors_b_path is not None:
        click.echo(
            f"  u4cht extract-vendor  --file {result.vendors_b_path} "
            f"--out out/vendor.json"
        )


@main.command("extract-tlk")
@click.option(
    "--tlk-dir",
    "tlk_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="包含 16 個 DOS `.TLK` 檔的資料夾。",
)
@click.option(
    "--out",
    "out_bilingual",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="輸出雙語 JSON 路徑。",
)
@click.option(
    "--report",
    "out_report",
    type=click.Path(dir_okay=False, path_type=Path),
    help="（選填）Markdown 對齊報告輸出路徑。",
)
@click.option(
    "--talk-json",
    "talk_json_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="（選填）u4remastered `talk.json` 作為對齊參考。",
)
def extract_tlk(
    tlk_dir: Path,
    out_bilingual: Path,
    out_report: Path | None,
    talk_json_path: Path | None,
) -> None:
    """抽 DOS `.TLK` NPC 對話為雙語 JSON（zh 待填）。"""
    stats = tlk_extract.run_extract(
        tlk_dir=tlk_dir,
        out_bilingual=out_bilingual,
        out_report=out_report,
        talk_json_path=talk_json_path,
    )
    click.echo(
        f"NPC 抽出：{stats['npc_count']}"
        f"  對齊成功：{stats['matched']}"
        f"  無對應：{stats['no_match']}"
        f"  有英文差異：{stats['text_diffs']}"
    )
    click.echo(f"→ {out_bilingual}")
    if out_report is not None:
        click.echo(f"→ {out_report}")


@main.command("extract-strings")
@click.option(
    "--data-dir",
    "data_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="包含 `title.exe` 與 `avatar.exe` 的 DOS U4 資料夾。",
)
@click.option(
    "--out",
    "out_bilingual",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="輸出雙語 JSON 路徑。",
)
@click.option(
    "--report",
    "out_report",
    type=click.Path(dir_okay=False, path_type=Path),
    help="（選填）Markdown 報告輸出路徑。",
)
def extract_strings(
    data_dir: Path,
    out_bilingual: Path,
    out_report: Path | None,
) -> None:
    """抽 `title.exe` / `avatar.exe` stringtable（intro / codex / shrine）為雙語 JSON。"""
    stats = strings_extract.run_extract(
        data_dir=data_dir,
        out_bilingual=out_bilingual,
        out_report=out_report,
    )
    click.echo(f"抽出字串總數：{stats['total']}")
    for k, v in stats.items():
        if k == "total":
            continue
        click.echo(f"  {k}: {v}")
    click.echo(f"→ {out_bilingual}")
    if out_report is not None:
        click.echo(f"→ {out_report}")


@main.command("extract-hardcoded")
@click.option(
    "--src-dir",
    "src_dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="xu4 C/C++ 原始碼資料夾（會遞迴掃 .cpp/.c/.h）。",
)
@click.option(
    "--out",
    "out_json",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="輸出雙語 JSON 路徑。",
)
@click.option(
    "--report",
    "out_report",
    type=click.Path(dir_okay=False, path_type=Path),
    help="（選填）Markdown 報告輸出路徑。",
)
def extract_hardcoded(
    src_dir: Path,
    out_json: Path,
    out_report: Path | None,
) -> None:
    """靜態抽取 xu4 原始碼中 `screenMessage()` 系列字面字串為雙語 JSON。"""
    payload = hardcoded_extract.run_extract(
        src_dir=src_dir,
        out_json=out_json,
        report=out_report,
    )
    meta = payload["_meta"]
    click.echo(
        f"call site(字面): {meta['total_call_sites_with_literal']}  "
        f"唯一: {meta['unique_strings']}  "
        f"含 format: {meta['with_format_specifier']}  "
        f"dynamic: {meta['dynamic_first_arg']}"
    )
    click.echo(f"→ {out_json}")
    if out_report is not None:
        click.echo(f"→ {out_report}")


@main.command("extract-vendor")
@click.option(
    "--file",
    "files",
    required=True,
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Boron 模組檔案（如 `vendors.b`）；可指定多次。",
)
@click.option(
    "--out",
    "out_json",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="輸出雙語 JSON 路徑。",
)
@click.option(
    "--report",
    "out_report",
    type=click.Path(dir_okay=False, path_type=Path),
    help="（選填）Markdown 報告輸出路徑。",
)
def extract_vendor(
    files: tuple[Path, ...],
    out_json: Path,
    out_report: Path | None,
) -> None:
    """文字抽取 xu4 Boron 腳本（如 `vendors.b`）字面為雙語 JSON。"""
    payload = vendor_extract.run_extract(
        files=list(files),
        out_json=out_json,
        report=out_report,
    )
    meta = payload["_meta"]
    click.echo(
        f"raw 字面: {meta['raw_literals']}  "
        f"control: {meta['control_skipped']}  "
        f"唯一真文字: {meta['unique_text_strings']}  "
        f"含佔位: {meta['with_placeholder']}"
    )
    click.echo(f"→ {out_json}")
    if out_report is not None:
        click.echo(f"→ {out_report}")


# 尚未實作的子指令（僅列於此供追蹤，見 PLAN §3 對照表）：
# 共用（Phase 2–3）:
#   build-font / build-lookup
#   platform fmtowns|msx2|amiga|x68000|sms
# 軌 A（Phase A1+）:
#   build-web / deploy-hf
# 軌 B（Phase B0 gated）:
#   game poc / game build-pygbag


if __name__ == "__main__":
    main()
