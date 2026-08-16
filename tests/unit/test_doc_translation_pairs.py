"""Structural parity between the English canonical docs and their _kr translations.

Convention: the plain filename is the English canonical document; the Korean
translation carries a `_kr` suffix. Both are shipped, so a change applied to one
and not the other leaves half the readership with stale instructions.

Content cannot be compared directly across languages, but structure can: the
heading skeleton, the table shape, and the language-neutral cells (paths,
commands, counts) must match. That is exactly what drifts when someone edits one
side only.

v0.14.2: CONTRIBUTING.md, tests/README.md and tests/TEST-GUIDE.md were
Korean-only while README.md had an English/Korean pair, so a contributor arriving
from the English README could not read how to contribute.
"""

import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

PAIRS = [
    (REPO_ROOT / "README.md", REPO_ROOT / "README_kr.md"),
    (REPO_ROOT / "CONTRIBUTING.md", REPO_ROOT / "CONTRIBUTING_kr.md"),
    (REPO_ROOT / "tests" / "README.md", REPO_ROOT / "tests" / "README_kr.md"),
    (REPO_ROOT / "tests" / "TEST-GUIDE.md", REPO_ROOT / "tests" / "TEST-GUIDE_kr.md"),
]

_HANGUL = re.compile(r"[가-힣]")
_IDS = [f"{en.parent.name}/{en.name}" for en, _ in PAIRS]


def _hangul_ratio(text: str) -> float:
    hangul = len(_HANGUL.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return hangul / max(hangul + latin, 1)


@pytest.mark.parametrize(("en_path", "kr_path"), PAIRS, ids=_IDS)
def test_both_documents_exist(en_path: Path, kr_path: Path) -> None:
    assert en_path.exists(), f"Missing English canonical document: {en_path}"
    assert kr_path.exists(), f"Missing Korean translation: {kr_path}"


@pytest.mark.parametrize(("en_path", "kr_path"), PAIRS, ids=_IDS)
def test_canonical_document_is_english(en_path: Path, kr_path: Path) -> None:
    """The unsuffixed file must be the English one, not the Korean one."""
    en_ratio = _hangul_ratio(en_path.read_text())
    kr_ratio = _hangul_ratio(kr_path.read_text())
    assert en_ratio < 0.05, (
        f"{en_path.name} is {en_ratio:.0%} Hangul — the unsuffixed filename is the "
        "English canonical document; Korean belongs in the _kr file"
    )
    assert kr_ratio > 0.10, (
        f"{kr_path.name} is only {kr_ratio:.0%} Hangul — it should be the Korean translation"
    )


@pytest.mark.parametrize(("en_path", "kr_path"), PAIRS, ids=_IDS)
def test_pair_cross_links(en_path: Path, kr_path: Path) -> None:
    assert kr_path.name in en_path.read_text(), (
        f"{en_path.name} must link to its Korean translation ({kr_path.name})"
    )
    assert en_path.name in kr_path.read_text(), (
        f"{kr_path.name} must link back to {en_path.name}"
    )


@pytest.mark.parametrize(("en_path", "kr_path"), PAIRS, ids=_IDS)
def test_heading_skeleton_matches(en_path: Path, kr_path: Path) -> None:
    """Heading levels, in order, must be identical — headings are the document's shape."""

    def levels(path: Path):
        return [
            len(m.group(1))
            for m in (
                re.match(r"^(#{1,6}) ", line)
                for line in path.read_text().splitlines()
            )
            if m
        ]

    en_levels, kr_levels = levels(en_path), levels(kr_path)
    assert en_levels == kr_levels, (
        f"{en_path.name} and {kr_path.name} have diverged: "
        f"{len(en_levels)} vs {len(kr_levels)} headings "
        f"(level sequences differ)"
    )


@pytest.mark.parametrize(("en_path", "kr_path"), PAIRS, ids=_IDS)
def test_table_shape_matches(en_path: Path, kr_path: Path) -> None:
    """Same number of table rows, and each row has the same column count."""

    def rows(path: Path):
        return [line for line in path.read_text().splitlines() if line.startswith("|")]

    en_rows, kr_rows = rows(en_path), rows(kr_path)
    assert len(en_rows) == len(kr_rows), (
        f"table rows differ: {en_path.name}={len(en_rows)} {kr_path.name}={len(kr_rows)}"
    )
    mismatched = [
        i
        for i, (a, b) in enumerate(zip(en_rows, kr_rows))
        if len(a.strip("|").split("|")) != len(b.strip("|").split("|"))
    ]
    assert mismatched == [], (
        f"{en_path.name}/{kr_path.name} table rows with differing column counts: {mismatched}"
    )


@pytest.mark.parametrize(("en_path", "kr_path"), PAIRS, ids=_IDS)
def test_code_blocks_match(en_path: Path, kr_path: Path) -> None:
    """Commands are not translated, so the fenced-block count must agree."""

    def blocks(path: Path):
        return re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", path.read_text(), re.S)

    en_blocks, kr_blocks = blocks(en_path), blocks(kr_path)
    assert len(en_blocks) == len(kr_blocks), (
        f"fenced blocks differ: {en_path.name}={len(en_blocks)} "
        f"{kr_path.name}={len(kr_blocks)}"
    )
