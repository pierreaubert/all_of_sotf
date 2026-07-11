---
name: dsp-problem-solving
description: Use when analyzing or implementing signals and systems code and need to choose a DSP method or transform.
---

# DSP Problem Solving

## Overview
Classify the signal/system task and load the focused sub-skill that teaches the right technique.

## When to Use
- The task involves continuous-time or discrete-time signals or LTI systems.
- You need to choose between time-domain, Fourier, Laplace, or z-domain analysis.
- You are reviewing or writing DSP code and want to avoid transform misuse.

## Decision Flowchart

```dot
digraph dsp_router {
  "Signal/system task?" [shape=diamond];
  "Discrete-time?" [shape=diamond];
  "Need z-domain transform?" [shape=diamond];
  "dsp-z-transform" [shape=box];
  "dsp-fourier-analysis" [shape=box];

  "Signal/system task?" -> "Discrete-time?" [label="yes"];
  "Discrete-time?" -> "Need z-domain transform?" [label="yes"];
  "Need z-domain transform?" -> "dsp-z-transform" [label="yes"];
  "Need z-domain transform?" -> "dsp-fourier-analysis" [label="no / frequency / unclear"];
  "Discrete-time?" -> "dsp-fourier-analysis" [label="no (time domain / other)"];
  "Signal/system task?" -> "dsp-fourier-analysis" [label="CT / sampling / other"];
}
```

## Routing Rules

1. If the system/signal is discrete-time and you need the z-transform (difference equation, H(z), ROC, stability) → load `dsp-z-transform`.
2. For all other signal/system tasks — including continuous-time transforms, Fourier analysis, sampling, Laplace, time-domain-only analysis, or unclear/mixed CT-DT problems — load `dsp-fourier-analysis`.

## Available Sub-Skills (This Cycle)

The following sub-skills are implemented and ready to load:
- `dsp-fourier-analysis`
- `dsp-z-transform`

The following sub-skills are planned for future cycles:
- `dsp-continuous-time-lti`
- `dsp-discrete-time-lti`
- `dsp-laplace-transform`
- `dsp-sampling`

## Common Mistakes
- Picking Laplace for a discrete-time problem or z-transform for a continuous-time problem.
- Skipping the region of convergence / stability check.
- Trying to solve a sampling problem entirely in one domain without checking the Nyquist condition.
