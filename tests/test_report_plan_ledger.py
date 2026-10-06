"""Plan-to-fix, audit ledger, and change-set report sections."""

from __future__ import annotations

from repolens.report import (
    format_collapsed_duplicates,
    render_markdown,
)
from repolens.schema import (
    ComplexityBlock,
    ComplexityHotspot,
    FindingReport,
    Issue,
    ProvenanceBlock,
    Severity,
    Summary,
    SuppressedIssue,
)


def test_plan_to_fix_names_high_complexity_when_nothing_is_immediate() -> None:
    report = FindingReport(
        confidence=95,
        summary=Summary(),
        complexity=ComplexityBlock(
            functionsAnalysed=10,
            issueCount=2,
            hotspots=[
                ComplexityHotspot(
                    file="src/repolens/report.py",
                    function="_render_issue",
                    line=429,
                    cyclomatic=21,
                    cognitive=23,
                ),
                ComplexityHotspot(
                    file="src/repolens/cli/app.py",
                    function="init_cmd",
                    line=85,
                    cyclomatic=11,
                    cognitive=8,
                ),
            ],
        ),
    )
    text = render_markdown(report, mode="review", commit_go="n/a", push_go="n/a")
    plan = text.split("## Plan to fix", 1)[1].split("##", 1)[0]
    assert "_render_issue" in plan
    assert "src/repolens/report.py:429" in plan
    assert "init_cmd" not in plan
    assert "_No immediate-priority findings._" not in plan


def _high(title: str, *, package: str, advisory: str) -> Issue:
    return Issue(
        severity=Severity.HIGH,
        priority="P1",
        category="sec.deps_cve",
        file="Cargo.lock",
        line=1,
        title=title,
        explanation="A known advisory.",
        impact="The dependency is vulnerable.",
        recommendedFix="Upgrade the crate.",
        codeExample=f'{package} = "0.1"',
        packageName=package,
        advisoryId=advisory,
        source="scanner",
    )


def test_package_echo_requires_the_whole_name() -> None:
    from repolens.report_checklist import _echoes_suppressed

    suppressed = _high(
        "RUSTSEC-2026-0192 in ttf-parser",
        package="ttf-parser",
        advisory="RUSTSEC-2026-0192",
    )

    def issue(title: str) -> Issue:
        return Issue(
            severity=Severity.MEDIUM,
            priority="P2",
            category="Security",
            file="Cargo.lock",
            line=1,
            title=title,
            explanation="Lockfile note.",
            recommendedFix="Edit the lockfile.",
            fixTiming="immediately",
            source="llm",
        )

    report = FindingReport(
        confidence=40,
        summary=Summary(),
        issues=[],
        suppressedIssues=[
            SuppressedIssue(issue=suppressed, reason="accepted risk", mechanism="ignore_file")
        ],
    )
    assert _echoes_suppressed(issue("Update ttf-parser"), report) is True
    assert _echoes_suppressed(issue("Update ttf-parser-sys"), report) is False
    assert _echoes_suppressed(issue("Parser helper is too long"), report) is False


def test_plan_to_fix_omits_a_suppressed_advisory() -> None:
    suppressed = _high(
        "RUSTSEC-2026-0192 in ttf-parser",
        package="ttf-parser",
        advisory="RUSTSEC-2026-0192",
    )
    echo = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="Security",
        file="Cargo.lock",
        line=12,
        title="Vulnerable dependency in Cargo.lock",
        explanation="The model restated a scanner row.",
        recommendedFix="Update the crate.",
        fixTiming="immediately",
        source="llm",
        advisoryId="RUSTSEC-2026-0192",
    )
    package_echo = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="Security",
        file="package.json",
        line=2,
        title="Vulnerable dependency left-pad",
        explanation="The model restated a suppressed package.",
        recommendedFix="Remove left-pad.",
        fixTiming="immediately",
        source="llm",
    )
    kept = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="Reliability",
        file="src/app.py",
        line=3,
        title="Bare except",
        explanation="Errors disappear.",
        recommendedFix="Catch OSError.",
        fixTiming="immediately",
        source="heuristic",
    )
    report = FindingReport(
        confidence=40,
        summary=Summary(medium=1),
        issues=[echo, package_echo, kept],
        suppressedIssues=[
            SuppressedIssue(
                issue=suppressed, reason="accepted risk", mechanism="ignore_file"
            ),
            SuppressedIssue(
                issue=_high("left-pad", package="left-pad", advisory=""),
                reason="false positive",
                mechanism="ignore_file",
            ),
        ],
        securityAuditConfidence=40,
    )
    text = render_markdown(report, mode="review", commit_go="n/a", push_go="n/a")
    plan = text.split("## Plan to fix", 1)[1].split("##", 1)[0]
    assert "ttf-parser" not in plan
    assert "left-pad" not in plan
    assert "Bare except" in plan
    assert "Suppressed: 1" not in plan
    assert "Suppressed 2 (via .repolens-ignore)" in text
    assert "### Audit Ledger" in text


def test_scanner_math_names_suppressed_and_dropped_rows() -> None:
    suppressed = [
        _high(f"advisory {index}", package=f"crate{index}", advisory=f"RUSTSEC-{index}")
        for index in range(10)
    ]
    report = FindingReport(
        confidence=90,
        summary=Summary(),
        rawCriticalHighCount=14,
        suppressedIssues=[
            SuppressedIssue(issue=issue, reason="accepted risk", mechanism="ignore_file")
            for issue in suppressed
        ],
        securityAuditConfidence=90,
    )
    assert format_collapsed_duplicates(report) == (
        "14 tool rows evaluated → 0 Critical/High retained (10 suppressed, 4 not retained)"
    )


def test_audit_ledger_does_not_call_a_cloud_run_air_gapped() -> None:
    local = FindingReport(
        confidence=80,
        summary=Summary(),
        securityAuditConfidence=80,
        provenance=ProvenanceBlock(
            repoLensVersion="0.1.0a1",
            gitSha="abc1234",
            model="qwen2.5-coder:32b",
            provider="ollama",
            fastBrainSeconds=12,
            llmSeconds=1122,
        ),
    )
    local_md = render_markdown(local, mode="review", commit_go="n/a", push_go="n/a")
    assert "RepoLens 0.1.0a1" in local_md
    assert "qwen2.5-coder:32b" in local_md
    assert "not sent to a cloud model API" in local_md
    assert "commit `abc1234`" in local_md
    assert "0 external network" not in local_md
    assert "pipx" not in local_md

    cloud = FindingReport(
        confidence=80,
        summary=Summary(),
        securityAuditConfidence=80,
        provenance=ProvenanceBlock(provider="openai", model="gpt-4.1"),
    )
    cloud_md = render_markdown(cloud, mode="review", commit_go="n/a", push_go="n/a")
    assert "was not air-gapped" in cloud_md
    assert "not sent to a cloud model API" not in cloud_md

    from repolens.report_metrics import _data_boundary

    assert "on this machine" in _data_boundary("openai_compatible")
    assert "not recorded" in _data_boundary(None)
    assert "Confirm that endpoint" in _data_boundary("custom-gateway")

    from repolens.report_metrics import suppression_suffix

    noise = Issue(
        severity=Severity.LOW,
        priority="P3",
        category="General",
        file="a.py",
        line=1,
        title="Noise",
        explanation="Ignored.",
        recommendedFix="Leave it.",
    )
    inline = FindingReport(
        confidence=1,
        summary=Summary(),
        suppressedIssues=[
            SuppressedIssue(issue=noise, reason="noise", mechanism="disable_comment")
        ],
    )
    assert suppression_suffix(inline) == " (via inline disable comments)"
    mixed = FindingReport(
        confidence=1,
        summary=Summary(),
        suppressedIssues=[
            SuppressedIssue(issue=noise, reason="noise", mechanism="disable_comment"),
            SuppressedIssue(issue=noise, reason="risk", mechanism="ignore_file"),
        ],
    )
    assert "or inline disable comments" in suppression_suffix(mixed)
    assert suppression_suffix(FindingReport(confidence=1, summary=Summary())) == ""


def test_plan_to_fix_splits_quick_wins_from_structural_work() -> None:
    from repolens.report_checklist import plan_to_fix_lines

    secret = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="sec.repo_hygiene_secrets",
        file=".gitignore",
        line=1,
        title="Gitignore is missing secret patterns",
        explanation="A .env file can be committed.",
        recommendedFix="Add .env",
        fixTiming="immediately",
        source="heuristic",
    )
    mega = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.mega_file",
        file="src/legacy.py",
        line=1,
        title="Mega file src/legacy.py",
        explanation="The file is over the line cap.",
        recommendedFix="Split by responsibility.",
        fixTiming="immediately",
        source="heuristic",
    )
    report = FindingReport(
        confidence=40,
        summary=Summary(medium=2),
        issues=[secret, mega],
    )
    text = "\n".join(plan_to_fix_lines(report))
    assert text.index("Quick wins:") < text.index("Gitignore is missing")
    assert text.index("Structural:") < text.index("Mega file")
    assert text.index("Quick wins:") < text.index("Structural:")
    assert "< 1 hour" not in text
    assert "1–3 days" not in text


def test_change_set_tags_touched_files_only() -> None:
    from repolens.changeset import tag_findings_for_changeset

    touched = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="Reliability",
        file="src/app.py",
        line=3,
        title="Bare except",
        explanation="Errors disappear.",
        recommendedFix="Catch OSError.",
    )
    old = Issue(
        severity=Severity.MEDIUM,
        priority="P2",
        category="heuristic.mega_file",
        file="src/legacy.py",
        line=1,
        title="Mega file",
        explanation="The file is long.",
        recommendedFix="Split it.",
    )
    tag_findings_for_changeset([touched, old], ["src/app.py"])
    assert touched.introducedInDiff is True
    assert old.introducedInDiff is False

    report = FindingReport(
        confidence=40,
        summary=Summary(medium=2),
        issues=[touched, old],
        securityAuditConfidence=40,
    )
    text = render_markdown(report, mode="review", commit_go="n/a", push_go="n/a")
    assert "Bare except — New / touched in this diff" in text
    assert "Mega file — Pre-existing baseline" in text

    plain = Issue(
        severity=Severity.LOW,
        priority="P3",
        category="General",
        file="src/app.py",
        line=1,
        title="Untagged note",
        explanation="Whole-tree review.",
        recommendedFix="Leave it.",
    )
    plain_md = render_markdown(
        FindingReport(
            confidence=40,
            summary=Summary(low=1),
            issues=[plain],
            securityAuditConfidence=40,
        ),
        mode="review",
        commit_go="n/a",
        push_go="n/a",
    )
    assert "New / touched in this diff" not in plain_md
    assert "Pre-existing baseline" not in plain_md


def test_ledger_splits_queue_wait_from_generation() -> None:
    queued = FindingReport(
        confidence=80,
        summary=Summary(),
        securityAuditConfidence=80,
        provenance=ProvenanceBlock(
            repoLensVersion="0.1.0a1",
            model="qwen2.5-coder:32b",
            provider="ollama",
            llmSeconds=21900,
            queueWaitSeconds=15600,
        ),
    )
    text = render_markdown(queued, mode="review", commit_go="n/a", push_go="n/a")
    assert "queued" in text
    assert "generating" in text
    assert "0 external network" not in text

    quiet = FindingReport(
        confidence=80,
        summary=Summary(),
        securityAuditConfidence=80,
        provenance=ProvenanceBlock(
            model="qwen2.5-coder:32b",
            provider="ollama",
            llmSeconds=100,
            queueWaitSeconds=0,
        ),
    )
    quiet_md = render_markdown(quiet, mode="review", commit_go="n/a", push_go="n/a")
    assert "queued" not in quiet_md
