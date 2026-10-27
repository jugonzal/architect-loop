// A loop's or a concern's own file, read from GitHub at the main commit the status document was gathered on
// (app-documents C1, command-center/D72), so the text a page shows and the state it derives come from the same commit.
// It goes through the signed-in fetch, so GitHub reads it as the person: this project is public, and the sign-in token
// asks for no repository access (app-shell D1), which is enough to read a public repository's contents.

import { useEffect, useState } from 'react';

import type { Fetch } from '../../api/fetch';
import type { ProjectKey } from '../../api/status';

export const GITHUB_API = 'https://api.github.com';

export type DocumentRead =
  | { kind: 'loading' }
  | { kind: 'read'; text: string }
  | { kind: 'failed'; message: string };

/** GitHub's contents API for one file at one commit. */
export function documentUrl(project: ProjectKey, path: string, sha: string): string {
  const [owner, repo] = project.split('/');
  if (!owner || !repo) throw new Error(`A project is owner/repo, not ${project}`);
  const file = path.split('/').map(encodeURIComponent).join('/');
  return `${GITHUB_API}/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${file}?ref=${encodeURIComponent(sha)}`;
}

/** The file's text, as GitHub's raw media type answers it. */
export async function readDocument(fetch: Fetch, project: ProjectKey, path: string, sha: string): Promise<string> {
  const url = documentUrl(project, path, sha);
  const response = await fetch(url, { headers: { Accept: 'application/vnd.github.raw+json' } });
  if (!response.ok) {
    let said = '';
    try {
      const message = ((await response.json()) as { message?: unknown } | null)?.message;
      if (typeof message === 'string' && message) said = `: ${message}`;
    } catch {
      // GitHub said nothing more than its status.
    }
    throw new Error(`GitHub answered ${response.status}${said}`);
  }
  return response.text();
}

/** The file at that commit, read again whenever the path or the commit changes. */
export function useDocument(fetch: Fetch, project: ProjectKey, path: string, sha: string): DocumentRead {
  const [read, setRead] = useState<DocumentRead>({ kind: 'loading' });
  useEffect(() => {
    let live = true;
    setRead({ kind: 'loading' });
    readDocument(fetch, project, path, sha).then(
      (text) => live && setRead({ kind: 'read', text }),
      (error: unknown) => live && setRead({ kind: 'failed', message: error instanceof Error ? error.message : String(error) }),
    );
    return () => {
      // A read that answers after the page has moved on changes nothing.
      live = false;
    };
  }, [fetch, project, path, sha]);
  return read;
}
