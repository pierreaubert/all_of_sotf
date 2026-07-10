# Acoustics Router Pressure Scenarios

## Scenario A: Speed of sound in a warm room
**Prompt:** "I need the speed of sound at 30 °C to set up a delay line in a room acoustics plugin."
**Expected:** Agent loads `acoustics-fundamentals` and computes c ≈ 349 m/s.

### Subagent Response
- **Loaded sub-skill:** `acoustics-fundamentals`
- **Why:** The scenario asks for the speed of sound at a given temperature to configure a delay line. Per the router skill, problems involving free-field waves, speed of sound, acoustic energy, or sound sources route to `acoustics-fundamentals`. Although the application is a room-acoustics plugin, the immediate physics question is a temperature-dependent speed-of-sound calculation, not duct wave behavior or radiation/resonator modeling.
- **Result:** ✅ Correct

## Scenario B: Reflection in a duct
**Prompt:** "A 1 kHz plane wave hits a closed end in a pipe. What is the pressure reflection coefficient?"
**Expected:** Agent loads `acoustics-waves-in-ducts` and states R = +1.

### Subagent Response
- **Loaded sub-skill:** `acoustics-waves-in-ducts`
- **Why:** The scenario involves a plane wave propagating inside a pipe and reflecting from a closed end — a 1D duct/waveguide reflection problem. Per the router rules, "pipes, ducts, plane waves, reflection/transmission, or 1D systems" route to `acoustics-waves-in-ducts`.
- **Result:** ✅ Correct

## Scenario C: Helmholtz resonator tuning
**Prompt:** "Design a Helmholtz resonator to absorb 200 Hz in a small control room."
**Expected:** Agent loads `acoustics-radiation-and-resonators` and gives the f₀ formula.

### Subagent Response
- **Loaded sub-skill:** `acoustics-radiation-and-resonators`
- **Why:** A Helmholtz resonator is explicitly a resonator/radiation system. The router skill maps resonators and Helmholtz resonators to this sub-skill, not to fundamentals or duct acoustics.
- **Result:** ✅ Correct
