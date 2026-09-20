# Toole third edition: decisions for room correction

Source: Floyd E. Toole, *Sound Reproduction: The Acoustics and Psychoacoustics
of Loudspeakers and Rooms*, third edition. This reference paraphrases selected
sections checked against the supplied `books/toole3rd/toole_ocr/<n>.txt` files.
File numbers below identify local scan/OCR pages, not printed page numbers.
OCR can corrupt numbers, mathematical symbols, and figure labels; conclusions
below rely on prose, not values read from plots. The book is a source, not a
runtime dependency. These are decision rules, not a replacement for the book.

## A good room curve is not an inverse-design target

Sections 12.2.3, 12.3, 13.3 and 14.1 (OCR 346–349, 370–377):

- Good on-axis/listening-window performance and well-behaved off-axis radiation
  can predict a downward-sloping room response. The reverse implication does
  not hold: equalizing any speaker to that room curve does not establish neutral
  direct sound or good directivity.
- Above the modal transition region, prefer trustworthy anechoic/angular data
  for speaker correction. A resonance shared across radiation directions is a
  different correction opportunity from direction-dependent interference.
  Common EQ cannot independently repair the off-axis response.
- Without such data, restrict claims and consider broad, restrained tonal
  changes. Do not manufacture high-resolution speaker correction from a smooth
  spatial average. Respect an explicitly requested target while explaining
  its evidence limits; do not silently replace it with a preferred house curve.
- Below the transition, in-situ source/seat measurements are essential. Do not
  extend a bass-correction objective to the treble just to obtain a flat score.
- Separate measured system calibration, optional listener/program tone controls,
  and playback-level loudness compensation. The preferred bass rise can depend
  on recording, listening level, and listener; the book does not establish one
  universal slope or bass-boost amount.

## Multi-sub optimization: consistency, efficiency, then shared EQ

Sections 8.2.8–8.2.9 and 8.6 (OCR 252–262, 268):

1. Preserve complex transfer functions from every independently controlled sub
   to every relevant seat. Optimize the combined field, not a collection of
   individually flattened subs. Re-measure if the actual subwoofer changes.
2. Assess seat-to-seat variation together with usable output and required drive.
   The book compares solutions with similar spatial consistency but substantially
   different low-bass efficiency. The lowest variance is not automatically the
   best solution, and a normalized graph cannot establish preserved output.
3. After spatial consistency improves, apply shared EQ to the remaining common
   peaks and broad tonal balance. Retain every seat's response: an average may
   represent no listener, and smoothing can conceal an unacceptable seat.
4. If constraints prevent a good group solution, disclose that trade-off. A
   prime-seat preset and a group preset can be honest alternatives; neither
   should be described as an improvement everywhere without measurements.

Toole's described SFM implementation uses bounded gain, delay, and one cut-only
parametric filter per sub. That is a documented implementation, not a universal
one-filter limit for other optimizers. Nor do its examples prescribe a fixed
number of subs, corner placement, or an acceptable output-loss budget.

### Software consequence: test the actual shared-bass signal

Sections 8.4–8.6 (OCR 265–268) describe bass management combining redirected bass
from the configured satellite channels, plus a distinct LFE path. It is not a
rule that only L and R contribute, and a main high-pass does not remove the bass
already redirected to the sub branch. LFE bandwidth and redirected-bass crossover
frequency are distinct controls; the book cautions against discarding LFE content
by indiscriminately applying the satellite crossover to it.

Engineering application of those routing assumptions:

- Evaluate the main/sub acoustic crossover for each logical input and seat, not
  only the nominal electrical crossover slopes.
- Also replay correlated inputs through the complete routing matrix. For
  example, if individually optimized L and R bass routes acquire opposite
  polarity into the same subs, coherent L=R bass can cancel even when the two
  isolated-input tests pass. Include this as a regression test for shared-bass
  designs, alongside the supported independent-input cases.
- Distinguish acoustic optimization scenarios from electrical overload bounds.
  A belief that program peaks rarely coincide is not an enforced input ceiling.
  Runtime protection and reduced input budgets need their own explicit contracts.
- Trace LFE gain through capture and playback. The book's description of a
  +10 dB LFE playback convention is not permission to add it twice, nor to apply
  LFE-only gain to all redirected bass through a common hardware sub gain.

These are applications to DSP design, not claims that the book specifies this
repository's limiter, headroom defaults, matrix representation, or QA thresholds.

## Modal EQ can improve ringing without changing passive room acoustics

Sections 8.2.4, 8.2.9 and 8.3 (OCR 241–242, 261–265):

- A suitably matched filter can reduce both a modal peak and the ringing of the
  driven speaker-room transfer. Saying that EQ cannot change the room's passive
  decay must not be misread as saying playback ringing cannot improve.
- Retain sufficiently fine bass resolution to identify modal frequency and Q.
  A coarse 1/3-octave display is not a sufficient design representation for
  matching a narrow resonance. Fine resolution still needs repeatability and SNR.
- Do not aim for the bottoms of modal nulls as the overall target, or insist that
  all dips be filled. Compare spectral prominence, broad bass balance, headroom,
  and seats; peak reduction and target selection are different decisions.
- Inspect absolute and peak-normalized time responses with identical analysis
  filters/windows. Analysis filters have their own decay. A smoother waterfall
  alone is not proof of audibility or a change in the physical room's damping.
- The studies reviewed in section 8.3 have different stimuli, frequencies,
  equalization and masking conditions. Do not extract a universal inaudible
  decay time, Q limit, phase threshold, or bass-group-delay threshold from them.

## Measurement and listening checks

Sections 3.5.1.4–3.5.1.7 and 14.1–14.2.3 (OCR 72–75, 373–385):

- Keep fine modal data, a suitably smoothed tonal view, and individual seats.
  Frequency smoothing, spatial averaging, and reflection-free time gating are
  different operations. Smoothing does not turn a room curve into direct sound.
- A frequency-dependent gate includes reflections once it extends beyond the
  reflection-free interval. Label which band is genuinely quasi-anechoic.
- State calibration stimulus, bandwidth, weighting, time response, reference seat,
  and processing path. Equal physical SPL and equal perceived loudness are not
  identical objectives; a balance obtained with one spectrum may not hold for
  another. Do not derive a broadband channel trim solely from a narrow EQ band.
- Keep raw gains for output/headroom assessment, and make separately level-matched
  listening comparisons. Control absolute playback level as well as relative
  level: changing it changes bass audibility and perceived balance.
- Use randomized/blinded comparisons where practical, repeat trials, and include
  spectrally revealing material as well as representative listening content.
  Prevent listeners from signaling preferred answers to one another. Test timbre
  separately from spatial attributes; a preferred normalized plot is neither test.
- Do not turn the book's cinema calibration levels or particular listening-test
  levels into mandatory domestic listening levels or universal safety advice.

## Review prompts

- Does the proposed EQ improve measured speaker behavior, or merely fit a room
  curve while risking direct-sound damage?
- Did apparent multi-seat improvement come from smoothing, normalization, loss of
  output, or hiding a bad seat?
- Does the exported matrix preserve intended bass when channels play together?
- Is improved delivered decay being confused with changed passive room acoustics?
- Are user preference, calibration, and audibility claims kept separate?
