import * as fs from 'fs';
import * as path from 'path';

import { serviceUrlVariable } from '../../api/service';
import { DEFAULT_PROJECT, readConfig, SERVICE_URLS } from '../config';

const EAS = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../../eas.json'), 'utf8'));

describe("a build's configuration", () => {
  it('reads the client ID, each service URL, the project and the environment', () => {
    expect(
      readConfig({
        EXPO_PUBLIC_GITHUB_CLIENT_ID: 'Iv23liExample',
        EXPO_PUBLIC_STATUS_URL: 'https://status-123456789012.us-east1.run.app',
        EXPO_PUBLIC_RUNNER_URL: 'https://runner-123456789012.us-east1.run.app',
        EXPO_PUBLIC_THREADS_URL: 'https://threads-123456789012.us-east1.run.app',
        EXPO_PUBLIC_NOTIFY_URL: 'https://notify-123456789012.us-east1.run.app',
        EXPO_PUBLIC_PROJECT: 'jugonzal/architect-loop',
        EXPO_PUBLIC_ENVIRONMENT: 'staging/app',
      }),
    ).toEqual({
      githubClientId: 'Iv23liExample',
      statusUrl: 'https://status-123456789012.us-east1.run.app',
      runnerUrl: 'https://runner-123456789012.us-east1.run.app',
      threadsUrl: 'https://threads-123456789012.us-east1.run.app',
      notifyUrl: 'https://notify-123456789012.us-east1.run.app',
      project: 'jugonzal/architect-loop',
      environment: 'staging/app',
    });
  });

  it("treats the owner's TODO placeholders as missing, so the app never sends one to GitHub or calls one", () => {
    const config = readConfig({
      EXPO_PUBLIC_GITHUB_CLIENT_ID: "TODO(owner): the OAuth app's client ID",
      EXPO_PUBLIC_STATUS_URL: 'TODO(owner)',
      EXPO_PUBLIC_RUNNER_URL: "TODO(owner): production's runner service",
      EXPO_PUBLIC_THREADS_URL: ' ',
    });
    expect(config.githubClientId).toBeNull();
    expect(config.statusUrl).toBeNull();
    expect(config.runnerUrl).toBeNull();
    expect(config.threadsUrl).toBeNull();
    expect(config.notifyUrl).toBeNull();
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

describe("each service's URL (app-clients C2)", () => {
  it.each(Object.entries(SERVICE_URLS))(
    "reads the %s service's URL from the variable a missing one's message names",
    (service, field) => {
      const url = `https://${service}-123456789012.us-east1.run.app`;
      expect(readConfig({ [serviceUrlVariable(service)]: url })[field]).toBe(url);
    },
  );

  it('knows the status, runner, threads and notify services (command-center/D55)', () => {
    expect(Object.keys(SERVICE_URLS)).toEqual(['status', 'runner', 'threads', 'notify']);
  });

  it("names staging's status service in the staging build profile (project number 665570365697)", () => {
    expect(readConfig(EAS.build.staging.env).statusUrl).toBe('https://status-665570365697.us-east1.run.app');
  });

  it('leaves every production URL to the owner until production has a project (command-center/D54)', () => {
    const production = readConfig(EAS.build.production.env);
    for (const field of Object.values(SERVICE_URLS)) expect(production[field]).toBeNull();
  });
});
