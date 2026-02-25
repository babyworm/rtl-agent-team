/**
 * RTL Agent Team - Reference Model Template
 * Domain: Video Codec (H.264/H.265)
 *
 * Usage: Copy this template and implement the algorithm-specific functions.
 *        The reference model must produce bit-exact output matching JM/HM.
 *
 * Build: g++ -std=c++17 -O2 -o ref_model ref_model.cpp
 * Test:  ./ref_model --selftest
 * Conformance: ./ref_model --compare jm_output.bin
 */

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <fstream>
#include <cassert>

// =============================================================================
// Type Definitions
// =============================================================================

using pixel_t = uint8_t;  // 8-bit pixel value
using coeff_t = int16_t;  // Transform coefficient
using qcoeff_t = int16_t; // Quantized coefficient

struct Block4x4 {
    pixel_t data[4][4];

    pixel_t& operator()(int row, int col) { return data[row][col]; }
    const pixel_t& operator()(int row, int col) const { return data[row][col]; }

    bool operator==(const Block4x4& other) const {
        return memcmp(data, other.data, sizeof(data)) == 0;
    }
};

struct CoeffBlock4x4 {
    coeff_t data[4][4];

    coeff_t& operator()(int row, int col) { return data[row][col]; }
    const coeff_t& operator()(int row, int col) const { return data[row][col]; }
};

// =============================================================================
// Algorithm Implementation (TODO: Implement per spec)
// =============================================================================

/**
 * TODO: Implement the core algorithm here.
 *
 * Example for intra prediction:
 *   void intra_predict_4x4(
 *       int mode,
 *       const pixel_t* above,     // 8 pixels above (+ above-left)
 *       const pixel_t* left,      // 4 pixels left
 *       Block4x4& predicted
 *   );
 *
 * Requirements:
 *   - Must be bit-exact with JM/HM reference software
 *   - All intermediate calculations must use correct fixed-point precision
 *   - Edge cases (unavailable neighbors) must follow spec exactly
 */

// =============================================================================
// Test Vector I/O
// =============================================================================

bool load_vectors(const std::string& path, std::vector<Block4x4>& blocks) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) return false;

    Block4x4 block;
    while (f.read(reinterpret_cast<char*>(&block), sizeof(block))) {
        blocks.push_back(block);
    }
    return !blocks.empty();
}

bool save_vectors(const std::string& path, const std::vector<Block4x4>& blocks) {
    std::ofstream f(path, std::ios::binary);
    if (!f.is_open()) return false;

    for (const auto& block : blocks) {
        f.write(reinterpret_cast<const char*>(&block), sizeof(block));
    }
    return true;
}

// =============================================================================
// Self-Test
// =============================================================================

bool run_selftest() {
    printf("Running self-test...\n");

    // TODO: Add self-test vectors here
    // These should be hand-verified against the standard
    //
    // Example:
    //   Block4x4 input = {...};
    //   Block4x4 expected = {...};
    //   Block4x4 result;
    //   intra_predict_4x4(MODE_DC, above, left, result);
    //   assert(result == expected);

    printf("Self-test PASSED\n");
    return true;
}

// =============================================================================
// Conformance Check (vs JM/HM output)
// =============================================================================

int run_conformance(const std::string& reference_path, const std::string& model_path) {
    std::vector<Block4x4> reference, model;

    if (!load_vectors(reference_path, reference)) {
        fprintf(stderr, "ERROR: Cannot load reference vectors: %s\n", reference_path.c_str());
        return 1;
    }
    if (!load_vectors(model_path, model)) {
        fprintf(stderr, "ERROR: Cannot load model vectors: %s\n", model_path.c_str());
        return 1;
    }

    if (reference.size() != model.size()) {
        fprintf(stderr, "ERROR: Vector count mismatch: ref=%zu, model=%zu\n",
                reference.size(), model.size());
        return 1;
    }

    int mismatches = 0;
    for (size_t i = 0; i < reference.size(); i++) {
        if (!(reference[i] == model[i])) {
            mismatches++;
            if (mismatches <= 10) {
                fprintf(stderr, "MISMATCH at vector %zu\n", i);
                // Print first differing pixel
                for (int r = 0; r < 4 && mismatches <= 10; r++) {
                    for (int c = 0; c < 4; c++) {
                        if (reference[i](r, c) != model[i](r, c)) {
                            fprintf(stderr, "  [%d][%d]: ref=%d, model=%d\n",
                                    r, c, reference[i](r, c), model[i](r, c));
                        }
                    }
                }
            }
        }
    }

    printf("Conformance: %zu vectors, %d mismatches (%.2f%% match)\n",
           reference.size(), mismatches,
           100.0 * (reference.size() - mismatches) / reference.size());

    return mismatches > 0 ? 1 : 0;
}

// =============================================================================
// Main
// =============================================================================

int main(int argc, char* argv[]) {
    if (argc < 2) {
        printf("Usage:\n");
        printf("  %s --selftest              Run self-test\n", argv[0]);
        printf("  %s --compare <ref> <model> Compare with reference\n", argv[0]);
        printf("  %s --generate <input> <output> Generate vectors\n", argv[0]);
        return 1;
    }

    std::string cmd = argv[1];

    if (cmd == "--selftest") {
        return run_selftest() ? 0 : 1;
    }
    else if (cmd == "--compare" && argc >= 4) {
        return run_conformance(argv[2], argv[3]);
    }
    else {
        fprintf(stderr, "Unknown command: %s\n", cmd.c_str());
        return 1;
    }
}
