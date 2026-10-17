export interface Explainer {
  title: string;
  text: string;
  docs: string;
}

const AGENTS = 'https://docs.databricks.com/aws/en/agents/';

export const EXPLAINERS: Record<string, Explainer> = {
  roll: { title: 'Tool call', text: 'The model asked a function to roll the dice instead of making up the result. The numbers come from code and the character sheet, never from the model.', docs: `${AGENTS}mcp-tools/` },
  attack: { title: 'Tool call', text: 'Combat is resolved by a tool against real defence and HP. The model narrates; code does the maths.', docs: `${AGENTS}mcp-tools/` },
  lore: { title: 'Retrieval (RAG)', text: 'The DM searched the lorebooks in AI Search, filtered to where you stand and nearby, and grounded its narration in what came back.', docs: 'https://docs.databricks.com/aws/en/ai-search/ai-search' },
  memory: { title: 'Long-term memory', text: 'Facts about you that outlive a single adventure, stored in a managed memory store and recalled when a new adventure begins.', docs: `${AGENTS}custom-agents/stateful-agents` },
  state: { title: 'State commit', text: 'Tools staged changes during the turn; they were written to Lakebase in a single transaction at the end, so the world never half-updates.', docs: 'https://docs.databricks.com/aws/en/oltp/' },
  guardrail: { title: 'Guardrail', text: 'A Unity AI Gateway service policy screened the model call and blocked it. The DM refused in-world and never saw the blocked words again; no game state from the turn was saved.', docs: 'https://docs.databricks.com/aws/en/data-governance/unity-catalog/service-policies' },
  hint: { title: 'Hint', text: 'Hints are worked out by code from the campaign state (the next unfinished story beat), not by the model: always right, free, and they never use a turn.', docs: 'https://docs.databricks.com/aws/en/oltp/' },
  load_state: { title: 'load_state', text: 'Load your save from Lakebase and recall memories before the DM thinks.', docs: 'https://docs.databricks.com/aws/en/oltp/' },
  dm_reason: { title: 'dm_reason', text: 'The model reasons about your action and decides which tools to call.', docs: AGENTS },
  tools: { title: 'tools', text: 'The requested tools run: dice, lore search, state changes.', docs: `${AGENTS}mcp-tools/` },
  commit_state: { title: 'commit_state', text: 'All staged changes are committed in one transaction.', docs: 'https://docs.databricks.com/aws/en/oltp/' },
  compose: { title: 'compose', text: 'The model writes the narration and choices as structured output, validated before you see it.', docs: AGENTS },
};

export const GRAPH = ['load_state', 'dm_reason', 'tools', 'commit_state', 'compose'];
export const GLYPHS: Record<string, string> = { roll: '🎲', attack: '⚔️', lore: '📚', memory: '🧠', state: '💾', guardrail: '🛡', hint: '💡' };
