---
name: domain-consult
description: Domain expert consultation dispatcher. Routes query to the appropriate domain expert based on content.
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
- Question is about synthesis or timing (use synth-check or timing-advisor directly)
- Implementation work is needed, not consultation
</Do_Not_Use_When>

<Why_This_Exists>
The project has multiple domain experts (codec, video, signal, protocol). Routing to
the wrong expert wastes tokens and produces shallow answers. This skill reads the query
and selects the best match before delegating.
</Why_This_Exists>

<Execution_Policy>
- Classify the query into a domain based on keywords and topic
- Delegate to exactly one primary expert (Opus for deep analysis, Sonnet for lookups)
- If multiple domains apply, delegate to both in parallel and merge answers
- Return expert answer verbatim, do not summarize or filter
</Execution_Policy>

<Routing_Table>
| Domain Keywords | Expert Agent | Notes |
|---|---|---|
| H.264, H.265, HEVC, AVC, CABAC, CAVLC, entropy coding, NAL, spec compliance | codec-standards-expert | Standards interpretation, spec section references |
| codec pipeline, encoder/decoder architecture, datapath, throughput, latency | codec-architecture-expert | Architecture-level codec design decisions |
| DCT, quantization, FFT, filter, convolution, DSP, fixed-point, overflow, numerical precision | codec-standards-expert | Numerical/algorithmic questions route here |
| chroma subsampling, color space, YUV, frame rate, resolution, HDR, tone mapping | video-processing-expert | Video signal processing chain |
| AXI, AHB, APB, PCIe, USB, Ethernet, bus protocol, handshake, transaction | protocol-checker | Bus protocol rules and timing |
</Routing_Table>

<Steps>
1. Read the user's query and identify domain keywords
2. Select primary expert from routing table
3. Delegate to selected expert:
   `Task(subagent_type="rtl-agent-team:{expert}", prompt="{user query}")`
4. If query spans two domains, run two experts in parallel
5. Return expert response(s) to user
</Steps>

<Tool_Usage>
```
# Codec standards question (spec interpretation)
Task(subagent_type="rtl-agent-team:codec-standards-expert",
     prompt="Explain the CABAC context initialization process for H.264 Main profile slice_type=P. Cite spec section numbers.")

# Codec architecture question (design-level)
Task(subagent_type="rtl-agent-team:codec-architecture-expert",
     prompt="What is the optimal pipeline depth for a CABAC encoder targeting 4K@60fps with a 500MHz sys_clk? Consider throughput vs latency tradeoffs.")

# Video processing question
Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="What are the correct coefficients for BT.709 YCbCr to RGB conversion? Include fixed-point representation suitable for RTL implementation.")

# Protocol question
Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="What is the correct AXI4 handshake behavior when ARVALID is asserted but ARREADY is low? Should the master hold ARVALID stable?")
```
</Tool_Usage>

<Examples>
<Good>
User asks about CABAC bin string encoding → routes to codec-standards-expert(Opus) → returns
precise answer citing H.264 spec section 9.3.2.
</Good>
<Bad>
Routing a CABAC arithmetic coding question to video-processing-expert because it mentions "arithmetic" —
misses the standards-specific context that codec-standards-expert provides. Always match the primary
domain (entropy coding → codec-standards-expert), not incidental keywords.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Query does not match any domain → answer from general knowledge, note no specialist matched
- Expert returns "I don't know" → try secondary expert from adjacent domain
- Query spans codec standards + architecture → run codec-standards-expert and codec-architecture-expert in parallel, merge answers
- RTL coding convention question → redirect to rtl-coder or rtl-critic (not a domain consult)
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Domain correctly identified from query keywords
- [ ] Correct expert agent selected
- [ ] Expert response returned without filtering
- [ ] Multi-domain queries ran experts in parallel
</Final_Checklist>
