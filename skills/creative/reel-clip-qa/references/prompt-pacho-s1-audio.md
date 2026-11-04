# Prompt Pacho S1 (aprobado) — referencia del formato AUDIO REQUIREMENT

Bloque final usado en la regeneración que SÍ habló (run 01M1ZJ4E4RPEVJZ312WCJA0CAW, $0.91).
Estructura: hook AUDIO REQUIREMENT al frente → DIALOGUE → lock de composición → GOLDIE
CONTINUITY → SCENE → CAMERA → GOLDIE ACTION → ENVIRONMENT → LIGHTING → MOOD → IMPORTANT →
NEG (sin texto/números/logos).

```
Animate the provided approved Scene 1 keyframe as a premium cinematic 3D commercial shot in vertical 9:16.

AUDIO REQUIREMENT (MANDATORY):
The final video's audio track MUST contain a single warm adult narrator voice speaking the ENTIRE DIALOGUE text below, in Spanish, starting within the first second of the clip. A silent video or a video with only ambient sound is an INCOMPLETE and REJECTED result. No music. No extra voices. No background noise. Numbers are written out so the voice pronounces them correctly.

DIALOGUE (Spanish. Native generated voice-over narration — the friendly local attendant. Unhurried, warm, prideful small-town tone):

"¿Qué significa Pacho? «Padre bueno». El pueblo lleva el nombre de Diego Pacho, el último cacique que cuidó esta frontera. Dicen que nadie cuidaba mejor a los suyos."

The narrator voice carries the dialogue as voice-over synced to the scene's mood. The character's mouth does NOT need to move in detail; if it moves, keep it subtle and natural.

Treat the provided image as a LOCKED visual composition and preserve it exactly.

GOLDIE CONTINUITY:
Use the exact approved Goldie character from the reference image. Preserve identical anatomy, proportions, yellow screen-face, eyes, eyebrows, smile, gold and chrome mechanical body, arms, hands, legs, joints and materials. Do not redesign, morph, simplify, cartoonize or reinterpret Goldie.

SCENE:
Pacho, Cundinamarca, Colombia, at warm early sunrise. Goldie is walking slowly along a rural path surrounded by lush orange groves, Colombian Andean mountains, soft vegetation and delicate morning mist. He holds a small irregular ochre-colored iron ore stone in one mechanical hand.

CAMERA:
Begin with a calm wide establishing composition.
At approximately 2 seconds, initiate a very slow cinematic dolly forward.
Create subtle foreground-to-background parallax between vegetation, Goldie and the distant mountains.
Around 8 seconds, introduce a very subtle camera arc toward Goldie's frontal three-quarter view.
Finish with a restrained cinematic push-in.

GOLDIE ACTION:
Goldie walks with extremely subtle physically plausible mechanical movement.
He gently raises the iron ore stone.
He looks at the stone with quiet curiosity and pride.
Make only a small head inclination.
His facial expression remains warm and stable.
His mechanical joints move naturally and minimally.

ENVIRONMENT:
Very subtle movement of orange-tree leaves.
Gentle movement of nearby vegetation.
Soft drifting morning mist.
Subtle atmospheric depth.
Warm sunrise rays gradually illuminate Goldie's gold and chrome surfaces.
Realistic reflections and physically plausible light interaction.

LIGHTING:
Warm low-angle sunrise.
Soft volumetric golden light.
Natural shadows.
Subtle rim light around Goldie's silhouette.
No dramatic artificial lighting.

MOOD:
Quiet discovery.
Pride in the town.
Heritage.
Warmth.
Beginning of a journey.

IMPORTANT:
The scene must feel like a sophisticated cinematic commercial, not an animated cartoon.
Goldie must feel physically present inside the environment, not pasted onto it.

No introduce new objects. No text. No numbers. No logos. No signs. No banners. No typography. No altering the composition. No morphing. No character redesign. No proportions change. No extra limbs or fingers. No camera shake. No sudden movement. No fast camera movement. No scene transformation.
```

## QA STT de referencia (whisper small, es, beam 5)

| Toma | Transcripción |
|---|---|
| toma1 (01M1ZG4X...) | (muda — hallucination de whisper: "Subtítulos realizados por la comunidad de Amara.org") |
| toma2/dup (01M1ZG38...) | "¿Qué significa? Padre bueno. El pueblo lleva el nombre de una persona, el último casista que cuidó esta frontera. Dicen que nadie cuidaba mejor a los suyos." |
| regen (01M1ZJ4E...) | "¿Qué significa Pacho? ¡Padre bueno! El pueblo lleva el nombre de Diego Pacho, el último casita que cuidó esta frontera. Dicen que nadie cuidaba mejor a los suyos." |

Nota: whisper transcribe «cacique» como «casista»/«casita» — variante de STT, no del audio.
Los defectos de marca viven en el VIDEO (marquee «GOLDY» en regen; «GOLDIE» correcto en toma2).
