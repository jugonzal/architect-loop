// What a build is configured with. EAS sets these per build profile (app/eas.json, `env`); for `expo start`,
// set them in the shell. Expo inlines EXPO_PUBLIC_ variables into the bundle, so none of them may be a secret,
// and none is: the device flow needs only the OAuth app's client ID, which is public (app-shell D1).

import type { ProjectKey } from '../api/status';

/** Phase 1 serves this one project (command-center/D18). */
export const DEFAULT_PROJECT: ProjectKey = 'jugonzal/architect-loop';

export type AppConfig = {
  /** The GitHub OAuth app's client ID, or null when the build has none yet. */
  githubClientId: string | null;
  /** The status service's URL for this build's environment, or null when the build has none yet. */
  statusUrl: string | null;
  project: ProjectKey;
  /** The LOOP.md §3 environment the build serves: staging/app, production/app, or development. */
  environment: string;
};

type Env = Record<string, string | undefined>;

/** A value the owner has not filled in yet reads as missing, so the app says so instead of using it. */
function present(raw: string | undefined): string | null {
  const value = raw?.trim();
  return value && !value.startsWith('TODO') ? value : null;
}

export function readConfig(env: Env): AppConfig {
  const project = present(env.EXPO_PUBLIC_PROJECT) ?? DEFAULT_PROJECT;
  if (!/^[^/\s]+\/[^/\s]+$/.test(project)) throw new Error(`EXPO_PUBLIC_PROJECT must be owner/repo, not ${project}`);
  return {
    githubClientId: present(env.EXPO_PUBLIC_GITHUB_CLIENT_ID),
    statusUrl: present(env.EXPO_PUBLIC_STATUS_URL),
    project: project as ProjectKey,
    environment: present(env.EXPO_PUBLIC_ENVIRONMENT) ?? 'development',
  };
}

export const NOT_CONFIGURED_MESSAGE =
  'This build has no GitHub client ID yet. The owner sets EXPO_PUBLIC_GITHUB_CLIENT_ID in app/eas.json once ' +
  'the OAuth app exists.';

// Each variable is named in full: Expo inlines only `process.env.EXPO_PUBLIC_<NAME>` written out like this.
export const config: AppConfig = readConfig({
  EXPO_PUBLIC_GITHUB_CLIENT_ID: process.env.EXPO_PUBLIC_GITHUB_CLIENT_ID,
  EXPO_PUBLIC_STATUS_URL: process.env.EXPO_PUBLIC_STATUS_URL,
  EXPO_PUBLIC_PROJECT: process.env.EXPO_PUBLIC_PROJECT,
  EXPO_PUBLIC_ENVIRONMENT: process.env.EXPO_PUBLIC_ENVIRONMENT,
});
