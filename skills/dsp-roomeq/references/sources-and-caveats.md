# Source provenance and technical qualifications

### OCR-based decision-rule supplement

[Toole third-edition decision rules](toole-third-edition.md) adds a focused review
of the supplied `books/toole3rd/toole_ocr` text: sections 3.5.1.4–3.5.1.7,
8.2.4, 8.2.8–8.6, 12.2.3–12.3, 13.3 and 14.1–14.2.3. Its citations use OCR
file numbers, not printed pages. It supplements the existing full-book work;
this focused update does not assert a new cover-to-cover or visual-figure review.
Numerical plot values and damaged OCR equations are not treated as verified.
The correlated-input regression checks are engineering applications of the
book's shared-bass architecture, not quotations or book-specified test criteria.

This skill is a tool-independent synthesis of all four PDFs and both PPTX files directly in `books/keith`, plus the three DOCX guides and one PPTX in `books/toole3rd-extras`, read on 2026-09-19. All were converted with MarkItDown; the configured Headroom executable was absent, so a temporary installation of MarkItDown performed the conversion. Extracted text included document text and slide text/notes; image-only plots, screenshots, and equations were not independently visually verified. No numeric result was inferred from an unavailable image. Supporting equations in this skill are stated explicitly and checked independently of the source typography.

The original files remain in the sibling `books/keith` and `books/toole3rd-extras` directories. They are attribution and further-reading sources, not runtime dependencies. The Toole files are his own simplified guides and supplementary slides associated with *Sound Reproduction*, third edition. Since 2026-09-20 the full third-edition text has additionally been read via tesseract OCR of the owner's paper-copy scans (`books/toole3rd/1.png`–`474.png`, working copy in `books/Toole_Sound_Reproduction_3ed.md`, figure index in `books/Toole_Sound_Reproduction_3ed_figures.md`; both local-only, not for redistribution). Book chapter/section pointers below were verified against that OCR. The skill contains distilled guidance rather than copies of the documents. Software-specific recipes, menus, macros, product rankings, and device limitations have deliberately been omitted.

## Reading map

| Source file and author | Extent | Material used |
| --- | --- | --- |
| `1. MAC Talk Treble.pptx`, Keith Wong, *Loudspeakers in listening rooms Part 1* | 173 slides | Slides 14–19: frequency regimes; 22–83: response, ETC and decay; 85–94: noise; 99–170: placement, directivity, treatment and limits of EQ |
| `2. MAC Talk Bass.pptx`, Keith Wong, *Loudspeakers in listening rooms Part 2: Bass* | 201 slides | Slides 17–76: measurement views; 77–109: modes/SBIR; 110–137: geometry and placement; 138–161: DSP and arrays; 162–196: treatment and frequency-dependent strategy |
| `2. REW Full eBook.pdf`, Keith Wong, *REW Book 2: Taking and Interpreting Measurements* | 84 PDF pages; first published 2025-11-21, modified 2026-07-19 | §§1–3: capture validity; §4: magnitude, phase, distortion, timing, ETC and decay; addendum: phase and group delay |
| `100. Acourate for Multichannel Speakers.pdf`, Keith Wong, *Acourate for DSP Controlled Active Speakers with Subwoofers* | 74 pages | §§3–6: gain, crossover, driver correction and timing; §§7–8: target and verification principles; §9.1–9.2: spatial magnitude and partial correction; §§9.4–11: phase correction, bass integration and verification |
| `101. Acourate for Passive Speakers and One or More Subwoofers.pdf`, Keith Wong, *Acourate for Passive Speakers with Optional Subwoofers* | 36 pages | §§2–5: gain, crossover, limits of speaker correction and sub timing; §§6–7: targets and measured verification |
| `acoustic_measurement_standards.pdf`, Nyal Mellor and Jeff Hedback, *Acoustical Measurement Standards for Stereo Listening Rooms*, 2011 | 30 pages | Summary p.3; noise p.4; ETC pp.5–9; bass decay pp.10–12; midrange decay pp.13–16; magnitude pp.17–21; room design/context pp.22–25 |

## Deliberate departures from source claims

### Toole additions

| Source in `books/toole3rd-extras` | Author / edition | Material used |
| --- | --- | --- |
| `designing_a_home_theater_part_1.docx` | Floyd E. Toole, *Designing Home Theaters and Listening Rooms: Part 1—Acoustical Perspectives*, updated 2017-10-15 | §§4–5: modal control and limits of RT; §§6–8: directional/perceptual effects of reflections and treatment; §9: correction priorities |
| `designing_home_theaters_part_2.docx` | Floyd E. Toole, *Part 2—Loudspeaker Selection, Placement, and Calibration*, modified 2017-10-16 | §2: coverage and mounting; §3: multi-sub spatial consistency; §4: prime-seat level/delay; §5: speaker EQ versus room/program compensation; §6: screen/baffle effects |
| `designing_home_theaters_part_3.docx` | Floyd E. Toole, *Part 3—Power Amplifiers—How Much Power is Needed?*, updated 2017-10-17 | §§2–4: amplifier ratings, sensitivity, impedance; §§5–6: reference levels and output estimation; §7: directivity/output trade-offs |
| `sound_isolation_2017.pptx` | Floyd E. Toole, *Sound Isolation and Noise Control in Home Theaters*, 81 slides; identifies itself as a third-edition supplement | Slides 3–23: leakage, absorption and rating limitations; 33–46: isolation and flanking; 62–78: floors, openings and mechanical/HVAC noise |

### Full-book evidence (*Sound Reproduction*, 3rd ed.)

Verified against the OCR working copy (`books/Toole_Sound_Reproduction_3ed.md`):

- **The target is flat direct sound, not a flat room curve.** Listeners in double-blind comparisons routinely prefer loudspeakers with flattish, smooth on-axis/listening-window response, higher still with good off-axis behavior. Steady-state room curves tilt downward (rising bass) according to speaker directivity, room reflectivity, and high-frequency air attenuation over listening distance. A room curve without reasonably comprehensive anechoic loudspeaker data is unreliable evidence of performance (§13.3).
- **Resonances outrank interference.** Transducer resonances are minimum-phase phenomena that radiate widely, so their bumps appear in all spinorama curves (and may not show in the directivity index). Bump height and shape in the amplitude response is the most reliable audibility indicator; spectrally broad (low-Q) resonances are the most audible, and they can be attenuated by precise equalization (§4.6.2). Crossover-region and edge-diffraction interference changes with direction and tends to be less audible than resonances.
- **Three unequal views of frequency response.** Toole ranks (1) comprehensive anechoic spinorama data, (2) compromised in-situ direct-sound measurements, and (3) steady-state room curves. Room curves alone are not definitive: a single omnidirectional microphone cannot make the directional and temporal distinctions two ears and a brain make (Ch. 14 opening).
- **Do not import the cinema X-curve.** The cinema calibration target is in significant disagreement with practice in the rest of audio; early psychoacoustical work favored a flattish direct sound on the audience side of the screen instead (§13.2.6).

### Interpretation across the sources

- Toole's approximately 300–500 Hz transition guidance is a practical region, not a fixed value interchangeable with every Schroeder estimate.
- Toole's RT discussion and Mellor/Hedback's tighter spectral decay benchmark differ in emphasis. Neither a blanket −15 dB reflection limit nor a mandatory flat RT profile is adopted. Evaluate directional reflection spectra and the listening application.
- The guides emphasize modal peak attenuation and joint multi-sub control. Their broad statements that a single-sub EQ benefits “nowhere else” are qualified: it can help multiple seats with similar response errors, but a common filter cannot change their relative transfer functions.
- A multi-sub playback solution is not passive treatment of every acoustic source in the room. Do not assume adding subs automatically eliminates the room-center null in an arbitrary installation.
- The assertion in Part 3 that voltage sensitivity assumes 8 ohms is not adopted. Only the conversion from 2.83 V to approximately 1 W assumes an 8-ohm resistive load. Nominal impedance and real reactive loading remain separate.
- Part 3's roughly 3 dB per distance-doubling estimate applies to combined steady-state sound in the illustrated furnished-room context. It is not a universal point-source propagation law or guaranteed transient headroom.
- Calibration examples and SPL peak/RMS language require their signal/meter conventions. Cinema X-curve equalization and 2017 immersive-layout/product examples are not imported as present-day domestic requirements.
- Isolation slide 16 calls absorption the percentage reflected; that wording is reversed. Absorption refers to energy not returned as reflection under the measurement convention, and is distinct from transmission loss. Single-number NRC/STC/Rw/NC ratings do not settle bass performance or tonal noise.
- Broad claims about phase inaudibility, hearing status, treatment, amplifiers, and customer preference are not universal rules. Keep audible crossover summation effects distinct from claims about isolated phase distortion, and judge controlled comparisons in context.

Use these qualifications when applying the sources; do not reproduce their categorical claims as established facts.

1. **Source correction versus room correction.** The books sometimes say all speakers/drivers are minimum-phase. Multi-driver sums, ports, delays, reflections, and crossovers can create non-minimum-phase behavior. Nonlinearity and non-minimum-phase behavior are different properties. A room resonance can be linear, and a linear system can be non-minimum-phase.
2. **Phase terminology.** IIR is not synonymous with minimum-phase; FIR is not synonymous with linear-phase. Mixed-phase is not defined by having both an IIR and an FIR stage. Linear phase has constant group delay. A finite causal FIR can approximate phase compensation with added latency. It does not predict the future.
3. **Group-delay diagnosis.** The minus sign is required in `τg = −dφ/dω`. Do not equate peaks in ordinary group delay with excess phase, or treat a flat ordinary group-delay curve as the definition of minimum-phase. Phase wraps and noise at nulls can resemble discontinuities.
4. **Spatial averaging.** REW §2.1.2 recommends vector averaging moved-microphone sweeps, and Active §9.1 adds IRs. Coherent spatial averaging can create artificial cancellation. For listening-area tonal response, select a documented magnitude/power average and retain a separate timing-referenced point capture. Individual multi-position sweeps retain timing; their spatial magnitude average does not.
5. **Window geometry.** The books give inconsistent quasi-anechoic cutoff calculations. Usable time is the delay between direct arrival and first reflection, not the total reflected travel time. A 1 m horizontal separation with both source and mic 1 m above a flat floor gives about 3.60 ms of floor-reflection separation, an approximate one-cycle scale of 278 Hz. Distance/window details and other boundaries still matter.
6. **Modal and propagation arithmetic.** Treble slide 63's “1 m ≈ 0.3 ms” is wrong. In a rigid rectangular room, the first axial pressure mode has a pressure node at the room midpoint along that axis, not a peak as stated in REW §4.1. A room diagonal does not set the lowest mode. Correct simple SBIR at 0.3 m is about 286 Hz; the bass slides' accompanying denominator is mistyped.
7. **Level and correlation.** Free-field far-field point-source pressure falls as `1/r`, intensity as `1/r²`, and SPL by about 6 dB per distance doubling. DRR is `10 log10(Edirect/Ereverberant)`, not a ratio of already logarithmic SPL values. IACC is a normalized cross-correlation with specified windows and lag limits, not “percent identical.” Separate speaker captures at one microphone are not a binaural ear-pair measurement, and maximizing IACC is not a universal listening goal.
8. **Target authority.** The 2011 white paper is a proposal for domestic stereo. Keith's target examples differ across publications. The −15 dB early-reflection rule is not the white paper's complete ETC criterion. RC, NC and NR are different procedures. The guides mix EBU 3267/3276 references and contain inconsistent room-volume units/figures; do not claim formal compliance from those summaries.
9. **Gain, ringing, and decay.** Constant gain reduction does not create pre-ringing. Digital attenuation does not mechanically delete source-file bits in a floating-point chain. There is no guaranteed inaudible pre-ringing duration or universally safe all-pass Q. Cutting a peak can reduce delivered ringing without changing the physical room decay constant.
10. **Preferences and product claims.** FIR is not always the best choice; latency and resources matter. Existing subwoofer DSP may provide necessary protection and useful processing. Treatment, active traps, and bass arrays are not categorically useful or useless. No number of subwoofers, target tilt, or room ratio is mandatory for all systems.

## File identity

SHA-256 of the editions read:

```text
871932bfd9b1bf0f1cb5d5883ff19e375829aab9f018340e076438e5e60faf0e  1. MAC Talk Treble.pptx
dd2759ce716aa8ce493fb8ce563f4aa7807f8c06745a42c8af19bd470eb59978  2. MAC Talk Bass.pptx
f452bd6aab915f86211d41b61dfe3e15708dccb53af9bb3629a03ca47300c8c5  2. REW Full eBook.pdf
ffeacd180d224e19baf16fd1c74560ed847a766abc0cc9d28be4ea7674afd1a0  100. Acourate for Multichannel Speakers.pdf
a2501481808a807f0f698e56f9f0309aaaf12e12cbdbabf481815dd4f19cd0e5  101. Acourate for Passive Speakers and One or More Subwoofers.pdf
8f8c3852534fe811af31bf064f4ad67ec0c4efe1a4173908d5ba3a39a1e518b0  acoustic_measurement_standards.pdf
0406bbc436da9ee7d2bb5fb2a26f6c2292045872daf61aed3f846befbcbbf2df  designing_a_home_theater_part_1.docx
77e2c2519c5e58838991ee53b51917b790cf488f5df173bcb178e2e899b39f8e  designing_home_theaters_part_2.docx
085f9b0e6ef2a6ddcb221e99c1f88f11bfab4c9b4abf6aa702a98102abd4e47d  designing_home_theaters_part_3.docx
2b19f91ef108e55fab4de515d83981c818fa5e94de99adf5a8ed0ef21be48989  sound_isolation_2017.pptx
```
