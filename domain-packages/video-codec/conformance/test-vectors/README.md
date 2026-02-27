# Conformance Test Vectors

This directory stores H.264/H.265 conformance test bitstreams.

## How to Populate

### H.264 (JVT Conformance Bitstreams)
Download from: https://www.itu.int/net/ITU-T/sigdb/gengravsigdb/gengravsigdb.aspx?val=10002502

Place extracted bitstreams here:
```
test-vectors/
├── h264/
│   ├── CVPCMNL1_SVA_C.264      # Baseline profile
│   ├── CVPCMNL2_SVA_C.264      # Main profile
│   └── ...
```

### H.265 (JVET Conformance Bitstreams)
Download from: https://www.itu.int/net/ITU-T/sigdb/gengravsigdb/gengravsigdb.aspx?val=10002504

Place extracted bitstreams here:
```
test-vectors/
├── h265/
│   ├── DBLK_A_SONY_3.bin       # Deblocking test
│   ├── SAO_A_MediaTek_4.bin    # SAO test
│   └── ...
```

## Usage with rtl-conformance-test Skill

The `rtl-conformance-test` skill expects test vectors in this directory.
Run: `/rtl-agent-team:rtl-conformance-test` to decode and compare against golden outputs.
