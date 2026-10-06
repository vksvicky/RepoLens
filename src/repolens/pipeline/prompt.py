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



def _append_outline_entry(sections: list[str], entry: FileEntry) -> None:
    from repolens.file_outline import format_file_outline

    sections.append(f"#### {entry.relative} (priority band {entry.priority_band})")
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


def _append_full_entry(sections: list[str], entry: FileEntry, *, heading: str) -> None:
    sections.append(f"{heading} {entry.relative} (priority band {entry.priority_band})")
    sections.append("```")
    sections.append(read_excerpt(entry))
    sections.append("```")
    sections.append("")


def _append_source_files(
    prompt: str,
    files: list[FileEntry],
    *,
    pack_mode: str = "full",
    file_pack_modes: dict[str, str] | None = None,
) -> str:
    sections = [prompt.rstrip(), "", "## Source files"]
    modes = file_pack_modes or {}
    if pack_mode == "hybrid":
        full_files = [e for e in files if modes.get(e.relative, "outline") == "full"]
        outline_files = [e for e in files if e not in full_files]
        if not full_files:
            pack_mode = "outline"
            files = outline_files or files
        else:
            sections.append(
                "### Active cycle modules (full bodies for refactoring context)"
            )
            for entry in full_files:
                _append_full_entry(sections, entry, heading="####")
            if outline_files:
                sections.append("### Architectural context (structure outlines)")
                sections.append(
                    "(Structure outlines — prefer symbols and module shape "
                    "over guessing bodies.)"
                )
                for entry in outline_files:
                    _append_outline_entry(sections, entry)
            return "\n".join(sections)

    if pack_mode == "outline":
        sections.append(
            "(Structure outlines — prefer symbols and module shape over guessing bodies.)"
        )
        for entry in files:
            sections.append(
                f"### {entry.relative} (priority band {entry.priority_band})"
            )
            from repolens.file_outline import format_file_outline

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
        _append_full_entry(sections, entry, heading="###")
    return "\n".join(sections)


