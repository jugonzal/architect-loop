// command-center/app-environments C1, the screen: against the status fixtures, a known environment shows the
// commit it serves, when that was read, and what is merged but not served, with a link to its ship card; an
// unknown one says unknown with the failure. A failed read shows the failure and nothing from an earlier read.

import { act, fireEvent, render, screen } from '@testing-library/react-native';

import { StatusError, type StatusClient, type StatusDocument } from '../../../api/status';
import { loadStatusFixture } from '../../../api/statusFixtures';
import { EnvironmentsScreen } from '../EnvironmentsScreen';

/** Three days, five hours after the board fixture's facts were gathered (2026-10-20T15:00:00Z). */
const NOW = Date.parse('2026-10-23T20:00:00Z');

/** A status client that answers each call with the next of its answers: a document, or an error to throw. */
function scriptedClient(...answers: (StatusDocument | Error)[]) {
  const calls: number[] = [];
  const client: StatusClient = {
    project: 'example/reports',
    async getStatus() {
      calls.push(calls.length);
      const answer = answers[Math.min(calls.length - 1, answers.length - 1)];
      if (!answer) throw new Error('no answer scripted');
      if (answer instanceof Error) throw answer;
      return structuredClone(answer);
    },
  };
  return { client, calls };
}

async function shown(client: StatusClient | null, onOpenShipCard = jest.fn(), now = () => NOW) {
  render(<EnvironmentsScreen status={client} now={now} onOpenShipCard={onOpenShipCard} />);
  await act(async () => {});
  return onOpenShipCard;
}

const card = (name: string) => screen.getByTestId(`environment-${name}`);
const textOf = (name: string) =>
  screen
    .getByTestId(`environment-${name}`)
    .findAll((node) => typeof node.props.children === 'string' || typeof node.props.children === 'number')
    .map((node) => String(node.props.children))
    .join(' | ');

async function pullToRefresh() {
  const list = screen.getByTestId('environments-list');
  await act(async () => {
    list.props.refreshControl.props.onRefresh();
  });
}

describe('the Environments screen', () => {
  it('shows one card for each environment, in the order the document lists them', async () => {
    const doc = loadStatusFixture('board');
    await shown(scriptedClient(doc).client);
    const cards = screen.getAllByTestId(/^environment-/).map((node) => node.props.testID);
    expect(cards).toEqual(doc.environments.map((e) => `environment-${e.name}`));
    expect(screen.getByText('Environments')).toBeTruthy();
  });

  it('shows what a known environment serves, when that was read, and what is merged but not served', async () => {
    await shown(scriptedClient(loadStatusFixture('board')).client);
    const production = textOf('production');
    expect(production).toContain('production');
    expect(production).toContain('serves @d1b62ed');
    expect(production).toContain('read 3 days ago');
    expect(production).toContain('Merged, not served');
    expect(production).toContain('report-pipeline/scheduler');
    expect(production).not.toContain('UNKNOWN');

    const staging = textOf('staging');
    expect(staging).toContain('serves @780d0c5');
    expect(staging).toContain('Nothing merged is waiting for it');
    expect(staging).not.toContain('Merged, not served');
  });

  it("links to the ship card in Needs you for an environment with something to ship, and only for it", async () => {
    const onOpen = await shown(scriptedClient(loadStatusFixture('board')).client);
    expect(screen.getAllByRole('button', { name: 'Read the ship brief' })).toHaveLength(1);
    const button = screen.getByRole('button', { name: 'Read the ship brief' });
    expect(card('production').findAll((n) => n === button)).toHaveLength(1);
    fireEvent.press(button);
    expect(onOpen).toHaveBeenCalledWith('ship/production');
  });

  it('says unknown, with the failure, for an environment whose read failed, and fills nothing in', async () => {
    await shown(scriptedClient(loadStatusFixture('unknown')).client);
    const staging = textOf('staging');
    expect(staging).toContain('UNKNOWN');
    expect(staging).toContain('GET https://staging.example.com/version timed out after 10 s');
    expect(staging).toContain('nothing is filled in from memory');
    expect(staging).toContain('Tried 3 days ago.');
    expect(staging).not.toContain('serves @');
    expect(staging).not.toContain('Nothing merged is waiting');
    expect(staging).not.toContain('Merged, not served');
    // What it cannot tell is named, from the document: queue's work is on main.
    expect(staging).toContain('report-pipeline/queue');

    const production = textOf('production');
    expect(production).toContain('UNKNOWN');
    expect(production).toContain('LOOP.md §3 has no served-commit command for production');
    expect(production).not.toContain('serves @');

    // main was read, and is known.
    expect(textOf('main')).toContain('serves @db5da19');
    expect(textOf('main')).not.toContain('UNKNOWN');
    expect(screen.queryByRole('button', { name: 'Read the ship brief' })).toBeNull();
  });

  it('says it is reading until the status service answers', async () => {
    let answer: (doc: StatusDocument) => void = () => {};
    const client: StatusClient = {
      project: 'example/reports',
      getStatus: () => new Promise((resolve) => (answer = resolve)),
    };
    await shown(client);
    expect(screen.getByText('Reading the status service…')).toBeTruthy();
    expect(screen.queryAllByTestId(/^environment-/)).toHaveLength(0);
    await act(async () => answer(loadStatusFixture('board')));
    expect(screen.queryByText('Reading the status service…')).toBeNull();
    expect(screen.getAllByTestId(/^environment-/)).toHaveLength(3);
  });

  it('shows the failure, and no environment, when the status service cannot be read', async () => {
    await shown(scriptedClient(new StatusError('http', 'GET https://status.example/x answered 503', 503)).client);
    expect(screen.getByText(/The status service could not be read/)).toBeTruthy();
    expect(screen.getByText('GET https://status.example/x answered 503')).toBeTruthy();
    expect(screen.queryAllByTestId(/^environment-/)).toHaveLength(0);
  });

  it('reads again on Try again', async () => {
    const { client, calls } = scriptedClient(new Error('network down'), loadStatusFixture('board'));
    await shown(client);
    expect(screen.getByText('network down')).toBeTruthy();
    await act(async () => {
      fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
    });
    expect(calls).toHaveLength(2);
    expect(screen.getAllByTestId(/^environment-/)).toHaveLength(3);
  });

  it('drops what an earlier read showed when a later one fails, so nothing is filled in from memory', async () => {
    const { client, calls } = scriptedClient(loadStatusFixture('board'), new Error('network down'));
    await shown(client);
    expect(textOf('staging')).toContain('serves @780d0c5');
    await pullToRefresh();
    expect(calls).toHaveLength(2);
    expect(screen.queryAllByTestId(/^environment-/)).toHaveLength(0);
    expect(screen.queryByText(/780d0c5/)).toBeNull();
    expect(screen.getByText('network down')).toBeTruthy();
  });

  it('shows a later read that finds an environment unknown as unknown, not as the commit it served before', async () => {
    const known = loadStatusFixture('board');
    const later = loadStatusFixture('board');
    const staging = later.environments.find((e) => e.name === 'staging')!;
    staging.served = null;
    staging.error = 'GET https://staging.example.com/version answered 503';
    await shown(scriptedClient(known, later).client);
    expect(textOf('staging')).toContain('serves @780d0c5');
    await pullToRefresh();
    expect(textOf('staging')).toContain('UNKNOWN');
    expect(textOf('staging')).toContain('answered 503');
    expect(screen.queryByText(/780d0c5/)).toBeNull();
  });

  it('says so, and shows no environment, when the build has no status service', async () => {
    await shown(null);
    expect(screen.getByText(/This build has no status service yet/)).toBeTruthy();
    expect(screen.queryAllByTestId(/^environment-/)).toHaveLength(0);
  });

  it('keeps when a row was read true while the screen stays open', async () => {
    jest.useFakeTimers();
    try {
      let now = Date.parse('2026-10-20T15:00:40Z');
      render(<EnvironmentsScreen status={scriptedClient(loadStatusFixture('board')).client} now={() => now} onOpenShipCard={jest.fn()} />);
      await act(async () => {
        await jest.advanceTimersByTimeAsync(0);
      });
      expect(textOf('main')).toContain('read 40 s ago');
      now += 2 * 60 * 1000;
      await act(async () => {
        await jest.advanceTimersByTimeAsync(30 * 1000);
      });
      expect(textOf('main')).toContain('read 2 min ago');
    } finally {
      jest.useRealTimers();
    }
  });
});
