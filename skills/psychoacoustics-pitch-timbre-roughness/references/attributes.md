# Pitch, Timbre, and Modulation Attributes

## Separate the perceptual target

| Attribute | Primary cues | Typical confound |
|---|---|---|
| Pitch | periodicity, resolved harmonics, temporal fine structure | strongest spectral peak |
| Pitch strength | salience/clarity of pitch | pitch value itself |
| Timbre | spectral envelope, attack/decay, temporal/spectral variation | loudness and pitch mismatch |
| Sharpness | high-frequency share of specific loudness | spectral centroid without level model |
| Fluctuation strength | slow envelope/frequency modulation | roughness |
| Roughness | faster modulation and within-channel beating | broadband noisiness |
| Subjective duration | onset/offset and level-dependent temporal perception | physical duration |

## Workflow

1. Level-match and, where the experiment requires it, pitch-match stimuli before attributing a difference to timbre.
2. Choose a named model and its calibrated input representation.
3. Resolve partials or auditory-channel envelopes at a resolution appropriate to the model.
4. Preserve time variation; a long-term average spectrum erases attack, modulation, and intermittency cues.
5. Compute the attribute and its temporal statistic, then check stimulus-domain validity.
6. Validate with controlled perceptual data when making a listener claim.

Missing-fundamental sounds require virtual/periodicity pitch reasoning. Closely spaced components may shift from separable pitches to beating/roughness depending on auditory-filter interaction. The boundary between fluctuation strength and roughness is gradual and model-dependent, so avoid presenting fixed modulation ranges as universal cutoffs.

Timbre is multidimensional. Report interpretable features (spectral shape, attack time, modulation, inharmonicity) or a task-specific embedding; do not collapse it to one unexplained scalar.

## Spatial playback caution

Room correction that changes DRR or early/late energy can alter apparent distance and spatial impression alongside timbre. Evaluate these attributes separately and level-match (`books/2604.12439.md`, `books/2503.12948.md`).

## Primary source

Read `books/Psycho_Acoustics-Zwicker_Fastl.md`, Chapters 5 and 9–12 for pitch, sharpness, sensory pleasantness, fluctuation strength, roughness, and subjective duration.
