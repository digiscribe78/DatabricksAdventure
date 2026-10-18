import { BRAND } from './brand';

/** A small, quiet "Powered by Databricks" mark: on the intro and title screens, and in the game's corner. */
export function PoweredBy({ corner = false }: { corner?: boolean }) {
  return (
    <a className={`powered-by${corner ? ' corner' : ''}`} href={BRAND.href} target="_blank" rel="noreferrer"
       title="This game runs on Databricks">
      <img src={BRAND.logo} alt="" aria-hidden="true" />
      <span>{BRAND.text}</span>
    </a>
  );
}
