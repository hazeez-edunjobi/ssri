import next from "eslint-config-next";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

/**
 * Flat ESLint config (ESLint 9). `eslint-config-next` v16 ships flat presets,
 * so the legacy `.eslintrc.json` cannot be loaded any more.
 *
 * @type {import("eslint").Linter.Config[]}
 */
const config = [
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
  },
  ...next,
  ...nextCoreWebVitals,
  ...nextTypescript,
];

export default config;
