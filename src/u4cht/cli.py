"""u4cht 統一 CLI 入口。

實作進度追蹤於 docs/ai_planning/PLAN.md。
"""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .extract import tlk as tlk_extract


@click.group(help="Ultima IV 繁中在地化 — Python 工具鏈")
@click.version_option(__version__, prog_name="u4cht")
def main() -> None:
    """CLI 入口。"""


@main.command("info")
def info() -> None:
    """列出目前實作進度。"""
    click.echo(f"u4cht {__version__}")
    click.echo("Phase 0 骨架 ✅")
    click.echo("Phase 1 進行中：extract-tlk ✅")
    click.echo("實作進度：docs/ai_planning/PLAN.md")


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


# 尚未實作的子指令（僅列於此供追蹤，見 PLAN §3 對照表）：
# 共用（Phase 1–3）:
#   extract-strings / extract-hardcoded / extract-vendor
#   build-font / build-lookup
#   platform fmtowns|msx2|amiga|x68000|sms
# 軌 A（Phase A1+）:
#   build-web / deploy-hf
# 軌 B（Phase B0 gated）:
#   game poc / game build-pygbag


if __name__ == "__main__":
    main()
