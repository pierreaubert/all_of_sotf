---
name: acoustics-problem-solving
description: Use when analyzing or implementing physical acoustics problems and need to choose the right acoustics sub-skill.
---

# Acoustics Problem Solving

## Overview
Classify the physical acoustics task by scale and phenomenon, then load the focused sub-skill that covers it.

## When to Use
- The task involves sound propagation, sources, reflection, radiation, or resonators.
- You need to choose between free-field fundamentals, duct/waveguide behavior, or radiation/resonator models.
- You are writing audio, room-acoustics, or transducer-related code.

## Decision Flowchart

```dot
digraph acoustics_router {
  "Acoustics task?" [shape=diamond];
  "Free field / sources / energy?" [shape=diamond];
  "Ducts / 1D waves / reflection?" [shape=diamond];
  "acoustics-fundamentals" [shape=box];
  "acoustics-waves-in-ducts" [shape=box];
  "acoustics-radiation-and-resonators" [shape=box];

  "Acoustics task?" -> "Free field / sources / energy?" [label="yes"];
  "Free field / sources / energy?" -> "acoustics-fundamentals" [label="yes"];
  "Free field / sources / energy?" -> "Ducts / 1D waves / reflection?" [label="no"];
  "Ducts / 1D waves / reflection?" -> "acoustics-waves-in-ducts" [label="yes"];
  "Ducts / 1D waves / reflection?" -> "acoustics-radiation-and-resonators" [label="no / radiation / resonator"];
}
```

## Routing Rules

1. If the problem is about free-field waves, speed of sound, acoustic energy, or sound sources → load `acoustics-fundamentals`.
2. If the problem is about pipes, ducts, plane waves, reflection/transmission, or 1D systems → load `acoustics-waves-in-ducts`.
3. If the problem is about radiation, resonators, Helmholtz resonators, or self-sustained oscillations → load `acoustics-radiation-and-resonators`.
4. If the problem mixes scales or is unclear, start with `acoustics-fundamentals`.

## Implemented Sub-Skills

- `acoustics-fundamentals`
- `acoustics-waves-in-ducts`
- `acoustics-radiation-and-resonators`

## Common Mistakes
- Applying 1D duct formulas to free-field spherical radiation.
- Ignoring temperature dependence of the speed of sound.
- Treating a resonator as a simple mass-spring without checking radiation damping.
