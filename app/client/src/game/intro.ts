/** The "Get started" screen's words: what this is and why, before anyone makes a character. */
export const INTRO: { title: string; text: string }[] = [
  { title: 'What this is',
    text: 'A retro text adventure whose Dungeon Master is an AI agent running on Databricks. You play; it narrates, rolls the dice, keeps the story straight and remembers you.' },
  { title: 'The aim',
    text: 'Learn how agents are built by playing one. Every turn shows its workings in the ✦ Scrying Glass: the steps the agent took, the dice and other tools it called, the lore it looked up, what it remembered and what it saved.' },
  { title: 'How to play',
    text: 'Pick one of the suggested choices or type what you do. Press 💡 Hint if you are not sure what to do next, and open the 📖 Guide (start with 🧭 Things to try) to see how each part of the game is built.' },
  { title: 'The quest',
    text: 'Find Keeper Aldric of the sealed Unity Archive, win the three seals of the Kingdom of Sparkia, and face Lord Silo in his fortress of walled-up books. A full tale takes about an hour.' },
  { title: 'A note on memory',
    text: 'The Dungeon Master remembers things about you between adventures: promises you made, the characters you played. That is one of the things this game shows off.' },
];

export const UNDER_THE_HOOD = ['LangGraph on Agent Runtime', 'AI Search', 'Lakebase', 'Agent memory',
  'MLflow tracing and evals', 'AI Gateway guardrails'];
