"""Tests for build_encoder.sh and build_decoder.sh — C source build scripts."""

from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script

BUILD_ENCODER = SKILLS_DIR / "codec-rd-eval" / "scripts" / "build_encoder.sh"
BUILD_DECODER = SKILLS_DIR / "codec-conformance-eval" / "scripts" / "build_decoder.sh"


class TestBuildEncoder:
    """Tests for build_encoder.sh argument validation."""

    def test_missing_args_exits_nonzero(self):
        result = run_script(BUILD_ENCODER)
        assert result.returncode != 0
        assert "ERROR" in result.stdout or "Usage" in result.stdout

    def test_help_flag(self):
        result = run_script(BUILD_ENCODER, "--help")
        assert result.returncode == 0
        assert "Usage" in result.stdout
        assert "src_dir" in result.stdout

    def test_nonexistent_src_dir(self, tmp_path):
        result = run_script(BUILD_ENCODER, "/nonexistent/dir", str(tmp_path / "out"))
        assert result.returncode != 0
        assert "does not exist" in result.stdout

    def test_no_c_files_exits_nonzero(self, tmp_path):
        src = tmp_path / "empty_src"
        src.mkdir()
        result = run_script(BUILD_ENCODER, str(src), str(tmp_path / "out"))
        assert result.returncode != 0
        assert "No .c files" in result.stdout

    def test_output_dir_created(self, tmp_path):
        """Output directory should be created even if compilation fails."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text("invalid c code }{}{")
        out = tmp_path / "deep" / "nested" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out), timeout=30)
        # Compilation will fail, but output dir should exist
        assert (tmp_path / "deep" / "nested").exists()

    def test_valid_c_compiles(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text(
            '#include <stdio.h>\n'
            'int main(void) { printf("hello\\n"); return 0; }\n'
        )
        out = tmp_path / "build" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out), timeout=30)
        assert result.returncode == 0
        assert "Build successful" in result.stdout
        assert out.exists()

    def test_extra_cflags_passed(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text(
            '#include <stdio.h>\n'
            'int main(void) {\n'
            '#ifdef MY_FLAG\n'
            '  printf("flag found\\n");\n'
            '#endif\n'
            '  return 0;\n'
            '}\n'
        )
        out = tmp_path / "build" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out), "-DMY_FLAG", timeout=30)
        assert result.returncode == 0

    def test_h_flag_shows_help(self):
        result = run_script(BUILD_ENCODER, "-h")
        assert result.returncode == 0
        assert "Usage" in result.stdout


class TestBuildDecoder:
    """Tests for build_decoder.sh — mirrors encoder but for decoder."""

    def test_missing_args_exits_nonzero(self):
        result = run_script(BUILD_DECODER)
        assert result.returncode != 0

    def test_help_flag(self):
        result = run_script(BUILD_DECODER, "--help")
        assert result.returncode == 0
        assert "Usage" in result.stdout
        assert "decoder" in result.stdout.lower()

    def test_nonexistent_src_dir(self, tmp_path):
        result = run_script(BUILD_DECODER, "/nonexistent/dir", str(tmp_path / "out"))
        assert result.returncode != 0
        assert "does not exist" in result.stdout

    def test_valid_c_compiles(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text(
            '#include <stdio.h>\n'
            'int main(void) { printf("decoder\\n"); return 0; }\n'
        )
        out = tmp_path / "build" / "decoder"
        result = run_script(BUILD_DECODER, str(src), str(out), timeout=30)
        assert result.returncode == 0
        assert "Build successful" in result.stdout
