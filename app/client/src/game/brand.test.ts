import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { BRAND, BUILT_ON } from './brand';

describe('Powered by Databricks', () => {
  it('uses the official symbol that ships with the app, and links to Databricks', () => {
    expect(existsSync(resolve(__dirname, '../../public', BRAND.logo.slice(1)))).toBe(true);
    expect(BRAND.text).toBe('Powered by Databricks');
    expect(BRAND.href).toBe('https://www.databricks.com/');
  });

  it('names the Databricks pieces the player just saw', () => {
    expect(BUILT_ON).toEqual(['Agent Runtime', 'Lakebase', 'AI Search', 'Agent memory', 'MLflow', 'AI Gateway']);
  });
});
