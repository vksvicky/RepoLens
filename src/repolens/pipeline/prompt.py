"""Prompt construction helpers for the review pipeline."""

from __future__ import annotations

from pathlib import Path

from repolens.inventory import FileEntry, read_excerpt
from repolens.packs.registry import pack_playbook_sections
from repolens.playbooks import playbooks_for_mode
from repolens.prose import BRITISH_ENGLISH_INSTRUCTION


def build_prompt(
    mode: str,
    root: Path,
    files: list[FileEntry],
    *,
    full_audit: bool,
    pack_ids: list[str] | None = None,
) -> str:
    sections: list[str] = [
        f"Repository root: {root}",
        f"Mode: {mode}",
        f"Files provided: {len(files)}",
        "",
    ]
    for label, content in playbooks_for_mode(mode, full_audit=full_audit):
        sections.append(f"## Playbook: {label}")
        sections.append(content)
        sections.append("")
    for label, content in pack_playbook_sections(pack_ids or []):
        sections.append(f"## Playbook: {label}")
        sections.append(content)
        sections.append("")

    sections.append("## Source files")
    for entry in files:
        sections.append(f"### {entry.relative} (priority band {entry.priority_band})")
        sections.append("```")
        sections.append(read_excerpt(entry))
        sections.append("```")
        sections.append("")
    sections.append(BRITISH_ENGLISH_INSTRUCTION)
    sections.append(
        "Analyse the files using the playbooks. Return FindingReport JSON only."
    )
    return "\n".join(sections)



def _append_source_files(
    prompt: str, files: list[FileEntry], *, pack_mode: str = "full"
) -> str:
    sections = [prompt.rstrip(), "", "## Source files"]
    if pack_mode == "outline":
        from repolens.file_outline import format_file_outline

        sections.append(
            "(Structure outlines — prefer symbols and module shape over guessing bodies.)"
        )
        for entry in files:
            sections.append(
                f"### {entry.relative} (priority band {entry.priority_band})"
            )
            outline = format_file_outline(
                entry.path,
                min_lines_for_outline=1,
                display_path=entry.relative,
            )
            if outline.strip():
                sections.append(outline)
            else:
                sections.append("```")
                sections.append(read_excerpt(entry))
                sections.append("```")
            sections.append("")
        return "\n".join(sections)

    for entry in files:
        sections.append(f"### {entry.relative} (priority band {entry.priority_band})")
        sections.append("```")
        sections.append(read_excerpt(entry))
        sections.append("```")
        sections.append("")
    return "\n".join(sections)


