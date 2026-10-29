import * as React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { LifecycleDialog } from './LifecycleDialog';
import { api } from '@/lib/api';

jest.mock('@/lib/api', () => ({ api: { get: jest.fn(), post: jest.fn() } }));
let root, container;
const pending = { id: 'i', action: 'close' };
const onDone = jest.fn();
const preview = { patients: [{ id: 'p' }], resources: [], transports: [], dispositions: [] };
const button = () => [...document.querySelectorAll('button')].find(b => b.textContent === 'Begründet bestätigen');
async function reason(value) {
  const input = document.querySelector('input:not([type="checkbox"])');
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, value);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: preview });
  api.post.mockResolvedValue({ data: { closed: true } });
  container = document.createElement('div'); document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

test('open work requires a reason and explicit confirmation before posting', async () => {
  await act(async () => root.render(<LifecycleDialog pending={pending} onDone={onDone} />));
  expect(button().disabled).toBe(true);
  await reason('Einsatzende');
  expect(button().disabled).toBe(true);
  await act(async () => document.querySelector('input[type="checkbox"]').click());
  expect(button().disabled).toBe(false);
  await act(async () => button().click());
  expect(api.post).toHaveBeenCalledWith('/incidents/i/close', { reason: 'Einsatzende', confirm_open: true });
  expect(onDone).toHaveBeenCalledWith(true);
});

test('a late preview from a previous incident cannot enable closure of the next incident', async () => {
  let resolveOld;
  api.get.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
  api.get.mockImplementationOnce(() => new Promise(() => {}));
  await act(async () => root.render(<LifecycleDialog pending={pending} onDone={onDone} />));
  await act(async () => root.render(<LifecycleDialog pending={{ id: 'next', action: 'close' }} onDone={onDone} />));
  await reason('Einsatzende');
  await act(async () => resolveOld({ data: { patients: [], resources: [], transports: [], dispositions: [] } }));
  expect(button().disabled).toBe(true);
  expect(api.post).not.toHaveBeenCalled();
});

test('a rejected close clears confirmation and requires reviewing open work again', async () => {
  api.post.mockRejectedValue({ response: { data: { detail: 'Bitte erneut prüfen.' } } });
  await act(async () => root.render(<LifecycleDialog pending={pending} onDone={onDone} />));
  await reason('Einsatzende');
  await act(async () => document.querySelector('input[type="checkbox"]').click());
  await act(async () => button().click());
  expect(document.querySelector('[role="alert"]').textContent).toContain('Bitte erneut prüfen');
  expect(document.querySelector('input[type="checkbox"]').checked).toBe(false);
  expect(button().disabled).toBe(true);
  expect(onDone).not.toHaveBeenCalled();
});
