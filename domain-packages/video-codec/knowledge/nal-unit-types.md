# NAL Unit Types — H.264 & H.265

> References: H.264 §7.3.1, Table 7-1; H.265 §7.3.1.2, Table 7-1

## H.264 NAL Unit Structure (§7.3.1)

### Header Format (1 byte)

```
+---+---+---+---+---+---+---+---+
| 0 | NRI |     nal_unit_type     |
+---+---+---+---+---+---+---+---+
  1   2       5 bits
```

| Field | Bits | Description |
|-------|------|-------------|
| forbidden_zero_bit | 1 | Must be 0 (error detection) |
| nal_ref_idc (NRI) | 2 | Reference importance (0=disposable, 3=highest) |
| nal_unit_type | 5 | NAL unit content type (0-31) |

### H.264 NAL Unit Types (Table 7-1)

| Type | Name | Content | NRI |
|------|------|---------|-----|
| 0 | Unspecified | — | — |
| 1 | Coded slice (non-IDR) | Slice data | 0-3 |
| 2 | Coded slice data partition A | Category 2 syntax | 2-3 |
| 3 | Coded slice data partition B | Category 3 syntax | 0-3 |
| 4 | Coded slice data partition C | Category 4 syntax | 0-3 |
| 5 | Coded slice (IDR) | IDR picture slice | 3 |
| 6 | SEI | Supplemental Enhancement Info | 0 |
| 7 | SPS | Sequence Parameter Set | 3 |
| 8 | PPS | Picture Parameter Set | 3 |
| 9 | Access Unit Delimiter | Picture type indicator | 0 |
| 10 | End of Sequence | Sequence boundary | 0 |
| 11 | End of Stream | Bitstream end | 0 |
| 12 | Filler Data | Padding bytes (0xFF) | 0 |
| 13 | SPS Extension | Sequence parameter extension | 3 |
| 14 | Prefix NAL unit | SVC/MVC prefix | 0-3 |
| 15 | Subset SPS | SVC/MVC SPS | 3 |
| 16-18 | Reserved | — | — |
| 19 | Coded slice (auxiliary) | Auxiliary coded picture | 0-3 |
| 20 | Coded slice extension | SVC/MVC slice | 0-3 |
| 21-23 | Reserved | — | — |
| 24-31 | Unspecified | RTP packetization (RFC 6184) | — |

**IDR (Instantaneous Decoder Refresh)**: Type 5 resets all reference pictures. Guarantees random access point.

## H.265 NAL Unit Structure (§7.3.1.2)

### Header Format (2 bytes)

```
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
| 0 |   nal_unit_type   | nuh_layer_id      | nuh_temporal_id_plus1 |
+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+---+
  1       6 bits             6 bits               3 bits
```

| Field | Bits | Description |
|-------|------|-------------|
| forbidden_zero_bit | 1 | Must be 0 |
| nal_unit_type | 6 | NAL unit type (0-63) |
| nuh_layer_id | 6 | Layer ID (0 for base layer) |
| nuh_temporal_id_plus1 | 3 | Temporal sub-layer + 1 (1-7; 0 forbidden) |

### H.265 NAL Unit Types (Table 7-1)

**VCL NAL units** (Video Coding Layer — contain slice data):

| Type | Name | Description |
|------|------|-------------|
| 0-1 | TRAIL_N, TRAIL_R | Trailing picture (non-ref / ref) |
| 2-3 | TSA_N, TSA_R | Temporal Sub-layer Access |
| 4-5 | STSA_N, STSA_R | Step-wise TSA |
| 6-7 | RADL_N, RADL_R | Random Access Decodable Leading |
| 8-9 | RASL_N, RASL_R | Random Access Skipped Leading |
| 10-15 | RSV_VCL_N/R | Reserved VCL |
| 16-17 | BLA_W_LP, BLA_W_RADL | Broken Link Access |
| 18 | BLA_N_LP | BLA without leading pictures |
| 19-20 | IDR_W_RADL, IDR_N_LP | IDR (with RADL / no leading) |
| 21 | CRA_NUT | Clean Random Access |
| 22-31 | RSV_IRAP/VCL | Reserved |

**Non-VCL NAL units** (parameter sets, SEI, etc.):

| Type | Name | Description |
|------|------|-------------|
| 32 | VPS_NUT | Video Parameter Set |
| 33 | SPS_NUT | Sequence Parameter Set |
| 34 | PPS_NUT | Picture Parameter Set |
| 35 | AUD_NUT | Access Unit Delimiter |
| 36 | EOS_NUT | End of Sequence |
| 37 | EOB_NUT | End of Bitstream |
| 38 | FD_NUT | Filler Data |
| 39-40 | PREFIX_SEI, SUFFIX_SEI | SEI messages |
| 41-47 | RSV_NVCL | Reserved non-VCL |
| 48-63 | UNSPEC | Unspecified |

### H.265 Random Access Points

| Type | DPB Flush | Leading Pics | Use Case |
|------|-----------|-------------|----------|
| IDR | Yes | RADL only (IDR_W_RADL) or none | Clean start, channel switch |
| CRA | No | RADL + RASL | Frequent random access |
| BLA | Yes | RADL (BLA_W_RADL) or none | Broken link (splicing) |

## Start Code Emulation Prevention (§7.4.1 / §7.4.2.1)

### Start Code Prefix

NAL units in byte-stream format are preceded by start codes:

| Pattern | Usage |
|---------|-------|
| `0x00 0x00 0x01` | 3-byte start code (standard) |
| `0x00 0x00 0x00 0x01` | 4-byte start code (access unit boundary) |

### Emulation Prevention Byte (§7.4.1)

Within NAL unit payload, the byte sequence `0x00 0x00 0x0X` (where X = 0, 1, 2, 3) is prevented by inserting `0x03`:

| Before Prevention | After Prevention | Reason |
|-------------------|------------------|--------|
| `00 00 00` | `00 00 03 00` | Prevents false start code `00 00 00 01` |
| `00 00 01` | `00 00 03 01` | Prevents false start code `00 00 01` |
| `00 00 02` | `00 00 03 02` | Prevents false start code alternative |
| `00 00 03` | `00 00 03 03` | Prevents ambiguity with prevention byte itself |

**Decoder must**: Strip `0x03` bytes at positions following `0x00 0x00` before RBSP parsing.

### RBSP Trailing Bits (§7.4.1.1)

```
rbsp_stop_one_bit = 1      (1 bit)
rbsp_alignment_zero_bit = 0 (0-7 bits to byte-align)
```

## Hardware Implementation Notes

### Start Code Detector

| Component | Description | Latency |
|-----------|-------------|---------|
| 3-byte shift register | Detect `00 00 01` pattern | Combinational |
| 4-byte shift register | Detect `00 00 00 01` pattern | Combinational |
| Emulation prevention FSM | Track `00 00 03` and strip `03` | 1 cycle |
| Byte counter | Track NAL unit size | — |

**FSM states** (emulation prevention removal):

| State | Input | Next State | Action |
|-------|-------|------------|--------|
| IDLE | 0x00 | ZERO1 | Output byte |
| IDLE | other | IDLE | Output byte |
| ZERO1 | 0x00 | ZERO2 | Output byte |
| ZERO1 | other | IDLE | Output byte |
| ZERO2 | 0x03 | IDLE | **Skip byte** (emulation prevention) |
| ZERO2 | 0x00 | ZERO2 | Output byte (could be start code prefix) |
| ZERO2 | 0x01 | START_CODE | Start code detected |
| ZERO2 | other | IDLE | Output byte |

### NAL Header Parser

| Codec | Parse Width | Cycle Count | Output |
|-------|-------------|-------------|--------|
| H.264 | 8 bits | 1 cycle | nal_unit_type[4:0], nal_ref_idc[1:0] |
| H.265 | 16 bits | 1 cycle | nal_unit_type[5:0], nuh_layer_id[5:0], nuh_temporal_id_plus1[2:0] |

### NAL Type Classification Logic

```
// H.264: Is this a reference picture?
is_reference = (nal_ref_idc != 0);
is_idr = (nal_unit_type == 5);
is_vcl = (nal_unit_type >= 1 && nal_unit_type <= 5);

// H.265: IRAP detection
is_irap = (nal_unit_type >= 16 && nal_unit_type <= 23);
is_idr = (nal_unit_type == 19 || nal_unit_type == 20);
is_cra = (nal_unit_type == 21);
is_vcl = (nal_unit_type <= 31);
is_reference = (nal_unit_type % 2 == 1) && is_vcl;  // odd types are reference
```

### Bitstream Buffer Sizing

| Parameter | H.264 | H.265 |
|-----------|-------|-------|
| Max NAL unit size (Level 5.1) | ~12 MB (cpbSize) | ~25 MB |
| Typical slice NAL (1080p) | 10-100 KB | 10-100 KB |
| Parameter set NAL (SPS/PPS) | 20-100 bytes | 50-200 bytes (VPS+SPS+PPS) |
| Input buffer (typical HW) | 4-16 KB FIFO | 4-16 KB FIFO |
