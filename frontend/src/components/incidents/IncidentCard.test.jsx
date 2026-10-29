import * as React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { IncidentCard } from './IncidentCard';
let root, container;
beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div'); document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
test('restricted global closer can close without opening incident details', async () => {
  const close = jest.fn();
  await act(async () => root.render(<IncidentCard incident={{id:'i',name:'Einsatz',status:'operativ',restricted:true,can_close:true}} onClose={close} />));
  await act(async () => container.querySelector('[data-testid="incident-close-i"]').click());
  expect(close).toHaveBeenCalledWith(expect.objectContaining({ id: 'i' }));
});
test('closure and reopening actions require server capabilities', async () => {
  await act(async () => root.render(<IncidentCard incident={{id:'i',status:'operativ'}} />));
  expect(container.querySelector('[data-testid="incident-close-i"]')).toBeNull();
  await act(async () => root.render(<IncidentCard incident={{id:'i',status:'abgeschlossen',can_reopen:false}} />));
  expect(container.querySelector('[data-testid="incident-reopen-i"]')).toBeNull();
  await act(async () => root.render(<IncidentCard incident={{id:'i',status:'abgeschlossen',can_reopen:true}} />));
  expect(container.querySelector('[data-testid="incident-reopen-i"]')).not.toBeNull();
});
