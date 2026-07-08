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
  "Need transform domain?" [shape=diamond];
  "dsp-discrete-time-lti" [shape=box];
  "dsp-continuous-time-lti" [shape=box];
  "dsp-z-transform" [shape=box];
  "dsp-laplace-transform" [shape=box];
  "dsp-fourier-analysis" [shape=box];
  "dsp-sampling" [shape=box];

  "Signal/system task?" -> "Discrete-time?" [label="yes"];
  "Discrete-time?" -> "Need transform domain?" [label="yes"];
  "Need transform domain?" -> "dsp-z-transform" [label="z-domain"];
  "Need transform domain?" -> "dsp-fourier-analysis" [label="frequency"];
  "Discrete-time?" -> "dsp-discrete-time-lti" [label="no (time domain)"];
  "Signal/system task?" -> "Need transform domain?" [label="CT"];
  "Need transform domain?" -> "dsp-laplace-transform" [label="s-domain"];
  "Need transform domain?" -> "dsp-fourier-analysis" [label="frequency"];
  "Signal/system task?" -> "dsp-sampling" [label="sampling/reconstruction"];
}
```

## Routing Rules

1. If the problem explicitly mentions sampling, aliasing, reconstruction, or the Nyquist rate → load `dsp-sampling`.
2. If the system/signal is discrete-time and you need a transform → load `dsp-z-transform`.
3. If the system/signal is continuous-time and you need a transform → load `dsp-laplace-transform`.
4. If the task is frequency-domain analysis (Fourier series/transform, spectra, filtering) → load `dsp-fourier-analysis`.
5. If the task is time-domain analysis only → load `dsp-continuous-time-lti` or `dsp-discrete-time-lti`.
6. If unclear or the problem mixes CT and DT → load `dsp-fourier-analysis` first.

## Available Sub-Skills (This Cycle)

The following sub-skills are implemented and ready to load:
- `dsp-fourier-analysis`
- `dsp-z-transform`

The following sub-skills are planned but not yet implemented; fall back to `dsp-fourier-analysis` if one of these would be the natural choice:
- `dsp-continuous-time-lti`
- `dsp-discrete-time-lti`
- `dsp-laplace-transform`
- `dsp-sampling`

## Common Mistakes
- Picking Laplace for a discrete-time problem or z-transform for a continuous-time problem.
- Skipping the region of convergence / stability check.
- Trying to solve a sampling problem entirely in one domain without checking the Nyquist condition.
