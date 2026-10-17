# Music

The tracks in `app/client/public/music/` were generated with ElevenLabs Music (instrumental, 75 seconds each) from the prompts below, then loudness-normalised to about −16 LUFS and re-encoded at 128 kbps. Each prompt is the track line followed by the shared style tail.

In the game, each location plays its own track. The battle theme takes over on any turn with an attack, and the title theme plays on the title screen and once an adventure ends. Tracks crossfade over two seconds, and each crossfades into its own restart near the end, so tracks that fade out still loop cleanly. Music stays off until the player switches it on (browsers block sound before a click).

To re-roll a track, generate it from its prompt and save it as `<id>.mp3` in that folder.

**Style tail:** retro 16-bit Amiga MOD tracker music, chiptune and sampled instruments, fantasy RPG soundtrack, seamless loop with no fade-in or fade-out, instrumental, no vocals

| id | Track |
|---|---|
| `title` | Heroic, adventurous main theme, bold brass-like lead melody over marching drums and arpeggios, sense of a journey beginning, uplifting and grand |
| `medallion-inn` | Warm, cosy tavern folk tune, jaunty lute and flute melody, gentle hand drum, 6/8 lilt, friendly and welcoming like a fire-lit inn |
| `delta-crossing` | Eerie flowing river music, rippling arpeggios like moving water, slow haunting lead, soft pads, mysterious twilight mood |
| `unity-archive` | Hushed, reverent library theme, soft choir-like pads, slow organ chords, sparse bell tones, ancient and solemn |
| `spark-forge` | Percussive, industrious forge theme, anvil-like metallic hits on the beat, driving bassline, fiery energetic melody, busy workshop |
| `streaming-falls` | Shimmering ambient waterfall theme, cascading bell arpeggios, airy pads, dreamy and reflective, misty and magical |
| `photon-mines` | Tense, echoing mine theme, low pulsing bass, dripping-water plinks, distant metallic taps, uneasy minor-key melody, claustrophobic |
| `data-swamp` | Murky, ominous swamp theme, slow wobbling bass, croaking low tones, eerie detuned lead, creeping dread |
| `silos-keep` | Grand, melancholic fortress theme, slow heavy drums, mournful organ and string-like lead, tragic and imposing, final dungeon |
| `combat` | Driving battle theme, fast drums, urgent bass arpeggios, aggressive heroic lead, high tension, fight music |
