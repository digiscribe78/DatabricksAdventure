import { INTRO, UNDER_THE_HOOD } from './intro';
import { PoweredBy } from './PoweredBy';
import { TITLE_IMAGE } from './scene';

export function IntroScreen({ onStart, onGuide }: { onStart: () => void; onGuide: (page?: string) => void }) {
  return (
    <div className="b title-screen intro">
      <div className="frame title-card">
        <img src={TITLE_IMAGE} alt="An adventurer looks out over the Kingdom of Sparkia at dusk"
             onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
      </div>
      <h1 className="title8">✦ The Kingdom of Sparkia ✦</h1>
      <p className="subtitle">A Databricks Adventure</p>
      <p className="brand-row"><PoweredBy /></p>
      <p className="begin">
        <button className="bbtn inline" onClick={onStart}>Get started ▸</button>
        <button className="bbtn inline" onClick={() => onGuide()}>📖 Guide</button>
      </p>
      <div className="frame panel">
        {INTRO.map((s) => (
          <p key={s.title}><strong>{s.title}.</strong> {s.text}</p>
        ))}
        <p className="hood"><strong>Under the hood.</strong> {UNDER_THE_HOOD.join(' · ')}</p>
      </div>
    </div>
  );
}
