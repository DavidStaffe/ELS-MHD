import * as React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import SystemUpdatesPage from './SystemUpdatesPage';
import { api } from '@/lib/api';
jest.mock('@/lib/api', () => ({ api: { get: jest.fn(), post: jest.fn() } }));
let container, root;
const button = label => [...container.querySelectorAll('button')].find(node => node.textContent === label);
const fill = async (node, value) => act(async () => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(node, value);
  node.dispatchEvent(new Event('input', { bubbles: true }));
});
beforeEach(async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { configured: true, state: 'idle', running_version: 'v1', can_install: true, can_rollback: true, rollback_version: 'v0' } });
  api.post.mockImplementation(path => Promise.resolve({ data: path === '/admin/login' ? { token: 'test-token' } : { configured: true, state: 'queued' } }));
  container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
  await act(async () => root.render(<MemoryRouter><SystemUpdatesPage /></MemoryRouter>));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
test('installation needs release check, both passwords and explicit confirmation', async () => {
  expect(button('Update installieren').disabled).toBe(true);
  api.get.mockResolvedValueOnce({ data: { configured: true, can_install: true, update_available: true, available_version: 'v2', release_id: 'a'.repeat(64) } });
  await act(async () => button('Auf Updates prüfen').click());
  await act(async () => button('Update installieren').click());
  expect(button('Jetzt installieren').disabled).toBe(true);
  const inputs = container.querySelectorAll('input[type="password"]');
  await fill(inputs[0], 'test-admin'); await fill(inputs[1], 'test-update');
  await act(async () => container.querySelector('input[type="checkbox"]').click());
  await act(async () => container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
  expect(api.post).toHaveBeenCalledWith('/system/updates/apply', { password: 'test-update', version: 'v2', release_id: 'a'.repeat(64) }, { headers: { Authorization: 'Bearer test-token' } });
  expect(container.querySelector('form')).toBeNull();
  expect(localStorage.length).toBe(0);
});
test('cancel clears rollback secrets and never starts an operation', async () => {
  await act(async () => button('Rollback').click());
  await fill(container.querySelector('input[type="password"]'), 'test-admin');
  await act(async () => button('Abbrechen').click());
  await act(async () => button('Rollback').click());
  expect(container.querySelector('input[type="password"]').value).toBe('');
  expect(button('Jetzt zurücksetzen').disabled).toBe(true);
  expect(api.post).not.toHaveBeenCalled();
});
