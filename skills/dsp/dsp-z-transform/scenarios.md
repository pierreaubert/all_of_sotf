# Z-Transform Skill Pressure Scenarios

## Scenario A: System function from difference equation
**Prompt:** "Find H(z) for y[n] - (1/2)y[n-1] = x[n] and determine stability."
**Expected with skill:** Agent takes z-transform, gets H(z) = 1/(1 - (1/2)z^{-1}) = z/(z - 1/2), ROC |z| > 1/2, stable because pole at z = 1/2 is inside the unit circle.

## Scenario B: Inverse z-transform
**Prompt:** "Find h[n] for H(z) = 1/(1 - (1/3)z^{-1}) with ROC |z| > 1/3."
**Expected with skill:** Agent recognizes right-sided sequence: h[n] = (1/3)^n u[n].

## Scenario C: Stability vs ROC confusion
**Prompt:** "A system has a pole at z = 2 and is causal. Is it stable?"
**Expected with skill:** Agent says causal → ROC |z| > 2, which excludes unit circle, so unstable.
