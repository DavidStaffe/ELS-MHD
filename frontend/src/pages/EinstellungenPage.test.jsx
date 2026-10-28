import * as React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import EinstellungenPage from './EinstellungenPage';
import { api } from '@/lib/api';
jest.mock('@/lib/api', () => ({api:{get:jest.fn(),post:jest.fn(),put:jest.fn()}}));
let mockAllowed=true;
const mockCan=()=>mockAllowed;
jest.mock('@/context/RoleContext',()=>({useRole:()=>({can:mockCan})}));
let container,root;
const button=label=>[...container.querySelectorAll('button')].find(n=>n.textContent===label);
const fill=async(node,value)=>act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(node,value);node.dispatchEvent(new Event('input',{bubbles:true}));});
beforeEach(async()=>{global.IS_REACT_ACT_ENVIRONMENT=true;mockAllowed=true;jest.clearAllMocks();api.get.mockResolvedValue({data:{configured:true,poll_interval_seconds:30}});api.post.mockResolvedValue({data:{ok:true}});api.put.mockResolvedValue({data:{ok:true}});container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);await act(async()=>root.render(<MemoryRouter><EinstellungenPage/></MemoryRouter>));});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();});
test('personal settings permission enables configuration without shared admin password',async()=>{
 expect(container.textContent).not.toContain('Administratorpasswort');
 expect(container.querySelector('option[value="5"]').disabled).toBe(true);
 expect(button('Key speichern').disabled).toBe(true);
 expect(localStorage.length).toBe(0);
});
test('changed key requires a fresh successful test',async()=>{
 const input=container.querySelector('input[type="password"]');await fill(input,'candidate-one');
 await act(async()=>button('Verbindung testen').click());expect(button('Key speichern').disabled).toBe(false);
 await fill(input,'candidate-two');expect(button('Key speichern').disabled).toBe(true);
 await act(async()=>button('Verbindung testen').click());await act(async()=>button('Key speichern').click());
 expect(api.put).toHaveBeenCalledWith('/divera/settings/key',{api_key:'candidate-two'});
 expect(input.value).toBe('');
});
test('failed verification never enables save',async()=>{
 await fill(container.querySelector('input[type="password"]'),'candidate');api.post.mockRejectedValueOnce({response:{status:502,data:{detail:'DIVERA nicht erreichbar.'}}});
 await act(async()=>button('Verbindung testen').click());expect(button('Key speichern').disabled).toBe(true);expect(api.put).not.toHaveBeenCalled();
});
