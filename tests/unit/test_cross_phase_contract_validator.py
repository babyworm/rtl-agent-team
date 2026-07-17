from tests.conftest import REPO_ROOT


def test_cross_phase_validator_uses_phase1_io_definition():
    # Given: the cross-phase validator skill consumed at P3/P4 boundaries.
    validator_path = REPO_ROOT / "skills" / "cross-phase-contract-validator" / "SKILL.md"

    # When: its machine-consumed I/O definition paths are inspected.
    validator = validator_path.read_text()

    # Then: both references use the canonical Phase-1 producer artifact.
    assert validator.count("docs/phase-1-research/io_definition.json") == 2
    assert "docs/phase-2-architecture/io_definition.json" not in validator
