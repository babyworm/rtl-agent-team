"""Tests for build_encoder.sh and build_decoder.sh — C11 build scripts."""

import os
from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script

BUILD_ENCODER = SKILLS_DIR / "codec-rd-eval" / "scripts" / "build_encoder.sh"
BUILD_DECODER = SKILLS_DIR / "codec-conformance-eval" / "scripts" / "build_decoder.sh"


class TestBuildEncoderValidation:
    """Tests for build_encoder.sh argument validation."""

    def test_missing_args(self):
        result = run_script(BUILD_ENCODER)
        assert result.returncode == 1
        assert "src_dir and output_binary are required" in result.stdout

    def test_help_flag(self):
        result = run_script(BUILD_ENCODER, "--help")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_nonexistent_src_dir(self, tmp_path):
        result = run_script(BUILD_ENCODER, "/nonexistent/dir", str(tmp_path / "enc"))
        assert result.returncode == 1
        assert "does not exist" in result.stdout

    def test_no_c_files(self, tmp_path):
        src = tmp_path / "empty_src"
        src.mkdir()
        result = run_script(BUILD_ENCODER, str(src), str(tmp_path / "enc"))
        assert result.returncode == 1
        assert "No .c files" in result.stdout

    def test_output_dir_created(self, tmp_path):
        """Output directory should be created even if build fails."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text("invalid c code{{{")
        out = tmp_path / "deep" / "dir" / "encoder"
        run_script(BUILD_ENCODER, str(src), str(out))
        assert (tmp_path / "deep" / "dir").exists()

    def test_include_dir_detection(self, tmp_path):
        """Include directory should be auto-detected."""
        src = tmp_path / "src"
        src.mkdir()
        inc = tmp_path / "include"
        inc.mkdir()
        (inc / "header.h").write_text("#define FOO 1\n")
        (src / "main.c").write_text('#include "header.h"\nint main() { return FOO - 1; }\n')
        out = tmp_path / "build" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out))
        # Should find include dir and attempt compilation
        assert "Building encoder" in result.stdout


class TestBuildDecoderValidation:
    """Tests for build_decoder.sh argument validation."""

    def test_missing_args(self):
        result = run_script(BUILD_DECODER)
        assert result.returncode == 1
        assert "src_dir and output_binary are required" in result.stdout

    def test_help_flag(self):
        result = run_script(BUILD_DECODER, "--help")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_nonexistent_src_dir(self, tmp_path):
        result = run_script(BUILD_DECODER, "/nonexistent/dir", str(tmp_path / "dec"))
        assert result.returncode == 1
        assert "does not exist" in result.stdout

    def test_no_c_files(self, tmp_path):
        src = tmp_path / "empty_src"
        src.mkdir()
        result = run_script(BUILD_DECODER, str(src), str(tmp_path / "dec"))
        assert result.returncode == 1
        assert "No .c files" in result.stdout


class TestBuildWithGcc:
    """Integration-style tests that actually compile C code (requires gcc)."""

    @pytest.fixture
    def gcc_available(self):
        import shutil
        if not shutil.which("gcc"):
            pytest.skip("gcc not installed")

    def test_encoder_builds_hello_world(self, tmp_path, gcc_available):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text(
            '#include <stdio.h>\nint main() { printf("hello"); return 0; }\n'
        )
        out = tmp_path / "build" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out))
        assert result.returncode == 0
        assert "Build successful" in result.stdout
        assert out.exists()
        assert os.access(str(out), os.X_OK)

    def test_decoder_builds_hello_world(self, tmp_path, gcc_available):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text(
            '#include <stdio.h>\nint main() { printf("hello"); return 0; }\n'
        )
        out = tmp_path / "build" / "decoder"
        result = run_script(BUILD_DECODER, str(src), str(out))
        assert result.returncode == 0
        assert "Build successful" in result.stdout

    def test_encoder_with_extra_cflags(self, tmp_path, gcc_available):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text(
            '#include <stdio.h>\n'
            'int main() {\n'
            '#ifdef MY_FLAG\n'
            '  printf("flag set");\n'
            '#endif\n'
            '  return 0;\n'
            '}\n'
        )
        out = tmp_path / "build" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out), "-DMY_FLAG")
        assert result.returncode == 0

    def test_encoder_with_makefile(self, tmp_path, gcc_available):
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.c").write_text('int main() { return 0; }\n')
        (src / "Makefile").write_text(
            'all:\n'
            '\t$(CC) $(CFLAGS) main.c -o $(OUTPUT)\n'
        )
        out = tmp_path / "build" / "encoder"
        result = run_script(BUILD_ENCODER, str(src), str(out))
        assert result.returncode == 0
        assert "make" in result.stdout.lower()
