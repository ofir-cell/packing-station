# LiveOpsHub — Higgsfield Production Pack

Higgsfield is **camera-first, image-to-video**. That changes the whole workflow, so this
pack replaces the generic one:

| | Generic text-to-video | **Higgsfield** |
|---|---|---|
| Input | one long prose prompt | **a start image** |
| Camera move | described in words | **chosen from a preset** |
| Prompt job | describe everything | describe **only what moves** |

So every shot below has three parts: **① a start-frame image prompt → ② a Higgsfield
camera preset → ③ a short motion prompt.**

---

## Workflow

1. **Generate the 15 start frames first.** Use Higgsfield's own image model, or Midjourney / GPT Image. Do this as one batch — it is far easier to keep a consistent look across stills than across videos, and the stills are what lock your film together.
2. **Lock the host's face once.** Generate one good frame of the presenter, then use **Character Consistency** (upload that image as the reference) on every shot she appears in — Shots 2 and 12. Without it she'll be a different person in each clip.
3. **Upload frame → pick preset → paste motion prompt → generate.**
4. **Take 2–3 runs on the hero shots** (7, 8, 10, 11). Those carry the film.
5. Assemble in your editor, add text overlays and sound there.

**Style suffix — append to every *image* prompt:**
```
cinematic still, anamorphic lens, shallow depth of field, warm amber highlights with
cool teal shadows, soft key light with practical LEDs in frame, subtle film grain,
photorealistic, no text, no logos, no watermark
```

---

## The 15 shots

### 1 · Drone arrival
- **Image:** `Exterior of a large modern warehouse in an industrial park at golden hour, wide open roller door, aerial view from 30 metres up looking down at the entrance`
- **Preset:** `FPV Drone` *(fallback: Dolly In)*
- **Motion:** `Camera flies forward and descends toward the open door, continuous smooth motion into the building`

### 2 · The live show  ← use Character Consistency
- **Image:** `A confident woman in her late twenties presenting to a smartphone on a ring-light tripod inside a warehouse, holding a cosmetics product, mid-gesture, smiling. Tall shelves packed with colourful beauty products behind her. Two more cameras on tripods at the edges of frame`
- **Preset:** `360 Orbit` *(or Arc Left)*
- **Motion:** `She talks and gestures with the product, camera orbits slowly around her`

### 3 · The chaos
- **Image:** `A long folding table buried in disorganised stock — cosmetics boxes, bubble wrap, loose printed order sheets, rolls of stickers, marker pens. Two workers leaning over it looking overwhelmed`
- **Preset:** `Dolly In` *(slow)*
- **Motion:** `Camera pushes slowly across the cluttered table, workers shuffle papers and search`

### 4 · Drowning in paper
- **Image:** `Extreme close-up of hands shuffling a thick stack of printed order sheets and peeling sticker labels, papers slipping loose, shallow focus`
- **Preset:** `Static` *(or Handheld)*
- **Motion:** `Hands fumble through the papers, one sheet slips and falls out of frame, slow motion`

> **THE TURN.** In your edit: hard cut to 4 frames of black after Shot 4, music out. This is the pivot from chaos to order — the whole film hinges on it.

### 5 · Order arrives
- **Image:** `The same warehouse, now spotless and calm. Clear tables, soft daylight through high windows. Four workers each holding a tablet, moving with quiet purpose down a central aisle`
- **Preset:** `Dolly In`
- **Motion:** `Camera glides forward down the aisle, workers move calmly through frame`

### 6 · The team, equipped
- **Image:** `Rear view of a worker walking between tall warehouse shelves holding a tablet at chest height, shelves receding on both sides`
- **Preset:** `Tracking / Follow`
- **Motion:** `Camera follows behind her as she walks, shelves rush past on both sides`

### 7 · Picking  ⭐ hero
- **Image:** `Over-the-shoulder close-up: a woman holds a tablet angled away from camera so the screen reads as a soft glow, her other hand lifting a cosmetics product from a shelf toward a plastic picking basket`
- **Preset:** `Dolly In` *(subtle)*
- **Motion:** `She places the product into the basket, a soft green light pulses on the tablet`

### 8 · The scan  ⭐ hero
- **Image:** `Macro shot of a handheld barcode scanner projecting a thin red laser line across a product barcode, dust motes drifting through the beam, background dissolved into warm bokeh`
- **Preset:** `Crash Zoom In` *(fallback: Dolly In)*
- **Motion:** `The red scan line sweeps across the barcode and holds, a soft green glow blooms`

### 9 · Basket to bench
- **Image:** `A full picking basket of neatly arranged cosmetics products being carried through a warehouse toward a clean packing bench, low angle`
- **Preset:** `Tracking / Follow`
- **Motion:** `Camera follows the basket low and smooth, then settles as it lands on the bench`

### 10 · The packing station  ⭐ hero
- **Image:** `A clean, well-lit packing bench. A worker scanning a shipping label. Above the bench a small camera on an arm points down at the surface with a tiny red recording light`
- **Preset:** `Arc / Orbit` *(slow)*
- **Motion:** `She scans the label then places products into the open box one by one, camera arcs slowly around the bench`

### 11 · Filmed from above  ⭐ hero
- **Image:** `Top-down overhead view of a packing bench, hands placing three cosmetics products into an open shipping box, everything centred and perfectly framed, beautifully lit`
- **Preset:** `Static` *(or Boom Down)*
- **Motion:** `Hands place each product into the box, add packing paper, then fold the flaps closed`

### 12 · The complaint  ← Character Consistency (different person to Shot 2)
- **Image:** `A woman sitting at a kitchen table at home holding a smartphone, frowning slightly, an unopened parcel beside her, soft window light`
- **Preset:** `Dolly In` *(slow)*
- **Motion:** `She types on her phone and glances at the parcel, camera eases in`

### 13 · The proof
- **Image:** `An office desk, three-quarter angle on an open laptop, the screen showing a soft glowing rectangle of video, a hand resting on the trackpad`
- **Preset:** `Dolly In`
- **Motion:** `The video plays on the screen, the person leans back relaxed, camera pushes in on the screen glow`

### 14 · The numbers
- **Image:** `Abstract data visualisation as physical light in a dark space — glowing coloured bar charts rising from a dark surface, a climbing line graph, drifting light particles, deep teal and violet with amber accents, no readable text`
- **Preset:** `Crane Up` *(or Boom Up)*
- **Motion:** `The bars grow upward and light particles drift up as the camera rises`

### 15 · Closing wide
- **Image:** `Wide view of a calm, organised warehouse at end of day, neat rows of sealed labelled boxes ready to ship, warm low sunlight through high windows, dust glittering in the air`
- **Preset:** `Static`
- **Motion:** `Two workers walk out of frame together, dust drifts in the light`

---

## Higgsfield-specific notes

**Keep motion prompts short.** The preset is doing the camera work. If you also describe the camera in the prompt, the two fight each other and you get drifting, unstable shots. Describe only what moves *inside* the frame.

**If a preset overshoots**, most moves have an intensity/duration control — pull it down. Shots 3, 8 and 12 look better understated; a crash zoom at full strength will feel like a meme rather than a commercial.

**Screens stay abstract.** Every shot with a tablet or laptop is framed at an angle or in shallow focus on purpose. Do not add prompts like "the screen shows an order list" — you'll get scrambled text. Real numbers go in your editor as overlays.

**Character Consistency is not optional** for Shots 2 and 12. Generate the reference frame once, save it, reuse it. It's the single biggest difference between a film that feels made and one that feels assembled.

**Aspect ratio:** generate the 15 start frames twice — 16:9 for the site film, 9:16 for the social cut. Do not crop; the compositions won't survive it. The vertical cut uses shots 2, 4, 7, 8, 11, 13, 14, 15.

---

## Voiceover and assembly

The VO script, timing table, on-screen text and the 30-second vertical cutdown are
unchanged — see **VIDEO_PROMPTS.md**, sections *"Film A — voiceover script"*,
*"Film B"* and *"Assembly checklist"*. Only the generation method differs.

---

## Connecting me to Higgsfield

There's no Higgsfield connector in the MCP directory, so I can't call it as a tool.
Two ways forward:

**Option A — I drive it in your browser.** With the Claude in Chrome extension I can
open higgsfield.ai, upload each start frame, select the preset, paste the motion
prompt and queue the generations, working through the shot list with you. You stay
logged in and in control; I do the repetitive part. Install it here:
https://code.claude.com/docs/en/chrome

**Option B — you paste, I direct.** You run the generations; send me the results and
I'll tell you which takes work, what to change, and how to cut them together.

Option A is much faster for 15 shots × 2 aspect ratios. Tell me which you'd like.
