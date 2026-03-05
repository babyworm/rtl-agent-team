---
name: domain-consult
description: "This skill should be used when consulting domain experts for codec standards, video processing, or fixed-point math questions."
user-invocable: true
---

<Purpose>
Analyze the user's question and route it to the most appropriate domain expert agent.
Returns the expert's answer without modification.
</Purpose>

<Use_When>
- User has a domain-specific question (codec algorithms, video processing, signal processing, hardware protocols)
- Choosing the wrong expert would give a shallow answer
- Multiple domains may be relevant and the best expert needs to be selected
</Use_When>

<Do_Not_Use_When>
- Question is about RTL coding style (ask rtl-coder directly)
- Question is about synthesis or timing (use rtl-synth-check or timing-advisor directly)
- Implementation work is needed, not consultation
</Do_Not_Use_When>

<Why_This_Exists>
The project has multiple domain experts (4 codec sub-domain specialists, a codec chief,
video processing, and protocol experts). Routing to the wrong expert wastes tokens and
produces shallow answers. This skill reads the query and selects the best match before delegating.
</Why_This_Exists>

<Execution_Policy>
- Classify the query into a domain based on keywords and topic
- Delegate to exactly one primary expert (Opus for deep analysis, Sonnet for lookups)
- If multiple domains apply, delegate to both in parallel and merge answers
- For cross-domain codec questions, delegate to vcodec-chief-standard-expert (or relevant 2 sub-domain experts in parallel)
- Return expert answer verbatim, do not summarize or filter
</Execution_Policy>

<Routing_Table>
| Domain Keywords | Expert Agent | Notes |
|---|---|---|
| NAL, slice header, CABAC, CAVLC, entropy coding, DPB, bitstream, binarization, context model, Exp-Golomb | vcodec-syntax-entropy-expert | HLS parsing, entropy engine, DPB management |
| intra prediction, motion estimation, motion compensation, ME, MC, motion vector, MV prediction, sub-pel, reference frame, merge mode, AMVP, bi-prediction | vcodec-prediction-expert | Intra modes, ME search, MC interpolation, MV prediction |
| DCT, DST, quantization, RDOQ, fixed-point, scaling matrix, QP, transform, inverse transform, butterfly, dequantization, coefficient, scaling list | vcodec-transform-quant-expert | Transform, quantization, fixed-point arithmetic |
| deblocking, SAO, in-loop filter, boundary strength, reconstruction, filter decision, edge offset, band offset, sample adaptive offset | vcodec-filter-recon-expert | Deblocking filter, SAO, reconstruction path |
| cross-block, cross-block dependency, pipeline dependency, architecture-ready, architecture-ready assessment, codec domain coordination, codec overview, block interaction, data flow between blocks | vcodec-chief-standard-expert | Cross-block coordination, multi-block dependency analysis |
| codec pipeline, encoder/decoder architecture, datapath, throughput, latency, SRAM organization | vcodec-architecture-expert | Architecture-level codec design decisions |
| throughput, memory bandwidth, cycles per block, macroblock rate, CTU rate, DPB sizing, line buffer sizing, pipeline depth, parallelism degree, performance budget, frames per second, resolution target | video-processing-expert | Codec HW performance analysis (throughput, bandwidth, pipeline) |
| color space conversion, RGB to YUV, YUV to RGB, BT.601, BT.709, BT.2020, chroma subsampling, chroma upsampling, 4:2:0, 4:2:2, 4:4:4, bit depth conversion, 8-bit to 10-bit, Bayer demosaic, color format, limited range, full range, V4L2, fourcc, pixelformat, bytesperline, sizeimage, single-planar, multi-planar, NV12M, tiled format, storage layout | vproc-color-format-expert | Color format conversion + V4L2 storage semantics (FOURCC/plane/stride/sizeimage) |
| denoise, noise reduction, bilateral filter, NLM, temporal noise reduction, 3DNR, motion adaptive, spatial filter, Gaussian filter, noise model, AWGN, shot noise | vproc-denoise-expert | Spatial/temporal noise reduction for video HW |
| HDR, tone mapping, PQ curve, HLG, gamma correction, OETF, EOTF, sRGB, image scaling, resampling, bilinear, bicubic, Lanczos, edge enhancement, sharpening, unsharp mask, ISP pipeline, image signal processing | vproc-image-processing-expert | HDR, gamma, scaling, sharpening, ISP pipeline |
| AXI, AHB, APB, PCIe, USB, Ethernet, bus protocol, handshake, transaction | protocol-checker | Bus protocol rules and timing |
</Routing_Table>

<Steps>
0. Domain expert agents have `<Knowledge_Base>` or `<Domain_Knowledge>` sections with domain-specific knowledge.
   Video-codec experts reference `domain-packages/video-codec/knowledge/`; video-processing experts reference `domain-packages/video-processing/knowledge/`.
   They will read relevant knowledge files autonomously before answering. No manual loading required.
1. Read the user's query and identify domain keywords
2. Select primary expert from routing table
3. Delegate to selected expert:
   `Task(subagent_type="rtl-agent-team:{expert}", prompt="{user query}")`
4. If query spans two codec sub-domains, run both sub-domain experts in parallel
5. If query spans multiple codec sub-domains (3+) or asks about block interactions, route to vcodec-chief-standard-expert
6. Return expert response(s) to user
</Steps>

<Tool_Usage>
```
# Syntax/entropy question (NAL, CABAC, DPB)
Task(subagent_type="rtl-agent-team:vcodec-syntax-entropy-expert",
     prompt="Explain the CABAC context initialization process for H.264 Main profile slice_type=P. Cite spec section numbers.")

# Prediction question (intra/inter)
Task(subagent_type="rtl-agent-team:vcodec-prediction-expert",
     prompt="Describe H.265 AMVP candidate derivation for a 16x16 PU. Specify the spatial neighbor scan order and pruning rules.")

# Transform/quantization question
Task(subagent_type="rtl-agent-team:vcodec-transform-quant-expert",
     prompt="What is the required accumulator width for H.265 32x32 IDCT at 10-bit input? Show overflow analysis per butterfly stage.")

# Filter/reconstruction question
Task(subagent_type="rtl-agent-team:vcodec-filter-recon-expert",
     prompt="Describe H.265 SAO edge offset category derivation for class 1 (vertical). Specify the sign comparison logic.")

# Cross-domain codec question
Task(subagent_type="rtl-agent-team:vcodec-chief-standard-expert",
     prompt="What are the data dependencies between the CABAC entropy engine and the inverse transform block? Specify the interface data format and timing constraints.")

# Codec architecture question (design-level)
Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="What is the optimal pipeline depth for a CABAC encoder targeting 4K@60fps with a 500MHz sys_clk? Consider throughput vs latency tradeoffs.")

# Codec performance question
Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="What are the throughput requirements for a 4K@60fps H.265 decoder at 500 MHz? Include cycles-per-CTU budget and memory bandwidth breakdown.")

# Color format conversion question
Task(subagent_type="rtl-agent-team:vproc-color-format-expert",
     prompt="What are the exact BT.709 YCbCr-to-RGB conversion coefficients for 10-bit limited range? Include fixed-point Q-format suitable for RTL implementation.")

# Denoise question
Task(subagent_type="rtl-agent-team:vproc-denoise-expert",
     prompt="What are the line buffer requirements and DRAM bandwidth for a motion-adaptive 3DNR engine targeting 4K@60fps 10-bit 4:2:0?")

# Image processing / HDR question
Task(subagent_type="rtl-agent-team:vproc-image-processing-expert",
     prompt="Design a PQ EOTF LUT for 12-bit input to 16-bit output. Specify entry count, interpolation method, and maximum error vs floating-point reference.")

# Protocol question
Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="What is the correct AXI4 handshake behavior when ARVALID is asserted but ARREADY is low? Should the master hold ARVALID stable?")
```
</Tool_Usage>

<Examples>
<Good>
User asks about CABAC bin string encoding → routes to vcodec-syntax-entropy-expert(Opus) → returns
precise answer citing H.264 spec section 9.3.2.
</Good>
<Good>
User asks about H.265 intra prediction angular modes → routes to vcodec-prediction-expert(Opus) → returns
complete mode table with reference sample dependencies and boundary handling.
</Good>
<Good>
User asks about interaction between RDOQ and CABAC bit estimation → routes to vcodec-chief-standard-expert
because it spans transform-quant and syntax-entropy domains → returns cross-block analysis.
</Good>
<Bad>
Routing a deblocking filter question to vcodec-transform-quant-expert because it mentions "filter" and
"coefficient" — deblocking is vcodec-filter-recon-expert's domain. Always match the primary domain
(in-loop filtering → vcodec-filter-recon-expert), not incidental keywords.
</Bad>
<Bad>
Routing a cross-block pipeline dependency question to a single sub-domain expert — this should
go to vcodec-chief-standard-expert who understands all block interfaces.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Query does not match any domain → answer from general knowledge, note no specialist matched
- Expert returns "I don't know" → try secondary expert from adjacent domain
- Query spans codec standards + architecture → run relevant sub-domain expert and vcodec-architecture-expert in parallel, merge answers
- Query spans 3+ codec sub-domains → route to vcodec-chief-standard-expert for coordinated analysis
- RTL coding convention question → redirect to rtl-coder or rtl-critic (not a domain consult)
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Domain correctly identified from query keywords
- [ ] Correct expert agent selected from routing table
- [ ] Expert response returned without filtering
- [ ] Multi-domain queries ran experts in parallel (or routed to chief)
- [ ] Cross-block questions routed to vcodec-chief-standard-expert
</Final_Checklist>
