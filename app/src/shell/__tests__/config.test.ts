import { DEFAULT_PROJECT, readConfig } from '../config';

describe("a build's configuration", () => {
  it('reads the client ID, status URL, project and environment', () => {
    expect(
      readConfig({
        EXPO_PUBLIC_GITHUB_CLIENT_ID: 'Iv23liExample',
        EXPO_PUBLIC_STATUS_URL: 'https://status-123456789012.us-east1.run.app',
        EXPO_PUBLIC_PROJECT: 'jugonzal/architect-loop',
        EXPO_PUBLIC_ENVIRONMENT: 'staging/app',
      }),
    ).toEqual({
      githubClientId: 'Iv23liExample',
      statusUrl: 'https://status-123456789012.us-east1.run.app',
      project: 'jugonzal/architect-loop',
      environment: 'staging/app',
    });
  });

  it("treats the owner's TODO placeholders as missing, so the app never sends one to GitHub", () => {
    const config = readConfig({
      EXPO_PUBLIC_GITHUB_CLIENT_ID: "TODO(owner): the OAuth app's client ID",
      EXPO_PUBLIC_STATUS_URL: 'TODO(owner)',
    });
    expect(config.githubClientId).toBeNull();
    expect(config.statusUrl).toBeNull();
  });

  it('serves the one phase 1 project by default (command-center/D18)', () => {
    expect(readConfig({}).project).toBe(DEFAULT_PROJECT);
    expect(DEFAULT_PROJECT).toBe('jugonzal/architect-loop');
    expect(readConfig({}).environment).toBe('development');
  });

  it('refuses a project that is not owner/repo', () => {
    expect(() => readConfig({ EXPO_PUBLIC_PROJECT: 'architect-loop' })).toThrow(/owner\/repo/);
  });
});
