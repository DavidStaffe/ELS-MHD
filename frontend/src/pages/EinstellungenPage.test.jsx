import * as React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import EinstellungenPage from './EinstellungenPage';
import { api } from '@/lib/api';

jest.mock('@/lib/api', () => ({ api: { get: jest.fn(), post: jest.fn(), put: jest.fn() } }));
// Keep form behavior under test without relying on portal animation timing.
jest.mock('@/components/ui/dialog', () => ({
  Dialog: ({ open, children }) => open ? <div role="dialog">{children}</div> : null,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogDescription: ({ children }) => <p>{children}</p>,
}));

let container, root;
const button = (label) => [...container.querySelectorAll('button')].find((node) => node.textContent === label);
const fill = async (node, value) => act(async () => {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(node, value);
  node.dispatchEvent(new Event('input', { bubbles: true }));
});
const click = async (node) => act(async () => { node.click(); });

beforeEach(async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  jest.clearAllMocks();
  api.get.mockResolvedValue({ data: { configured: true, poll_interval_seconds: 30 } });
  api.post.mockImplementation((path) => Promise.resolve({ data: path === '/admin/login' ? { token: 'opaque-session' } : { ok: true, vehicles_total: 2 } }));
  api.put.mockResolvedValue({ data: { configured: true, poll_interval_seconds: 30 } });
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => { root.render(<MemoryRouter><EinstellungenPage /></MemoryRouter>); });
});

afterEach(async () => {
  await act(async () => { root.unmount(); });
  container.remove();
});

async function login() {
  await fill(container.querySelector('input[type="password"]'), 'test-password');
  await act(async () => { container.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); });
}

test('configuration changes need login; five seconds stay disabled', async () => {
  expect(button('API-Key ändern').disabled).toBe(true);
  expect(container.querySelector('select').disabled).toBe(true);
  await login();
  expect(button('API-Key ändern').disabled).toBe(false);
  expect(container.querySelector('option[value="5"]').disabled).toBe(true);
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
  expect(container.textContent).not.toContain('test-password');
});

test('changed candidate needs a fresh test and save uses explicit admin authorization', async () => {
  await login();
  await click(button('API-Key ändern'));
  const input = container.querySelector('#divera-key');
  await fill(input, 'candidate-one');
  expect(button('Speichern und übernehmen').disabled).toBe(true);
  await click(button('Verbindung testen'));
  expect(button('Speichern und übernehmen').disabled).toBe(false);
  await fill(input, 'candidate-two');
  expect(button('Speichern und übernehmen').disabled).toBe(true);
  await click(button('Verbindung testen'));
  await click(button('Speichern und übernehmen'));
  expect(api.put).toHaveBeenCalledWith('/divera/settings/key', { api_key: 'candidate-two' }, expect.objectContaining({ headers: { Authorization: 'Bearer opaque-session' } }));
  expect(container.querySelector('[role="dialog"]')).toBeNull();
  expect(container.innerHTML).not.toContain('candidate-two');
});

test('failed key verification does not offer saving; session expiry relocks controls', async () => {
  await login();
  await click(button('API-Key ändern'));
  await fill(container.querySelector('#divera-key'), 'candidate');
  api.post.mockRejectedValueOnce({ response: { status: 502, data: { detail: 'DIVERA derzeit nicht erreichbar.' } } });
  await click(button('Verbindung testen'));
  expect(button('Speichern und übernehmen').disabled).toBe(true);
  expect(api.put).not.toHaveBeenCalled();
  api.post.mockRejectedValueOnce({ response: { status: 401, data: { detail: 'Administratoranmeldung abgelaufen.' } } });
  await click(button('Verbindung testen'));
  expect(button('API-Key ändern').disabled).toBe(true);
  expect(container.querySelector('[role="dialog"]')).toBeNull();
});
