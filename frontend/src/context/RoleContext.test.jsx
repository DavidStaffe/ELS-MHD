import * as React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { RoleProvider, useRole, canRole } from './RoleContext';
import { api } from '@/lib/api';
jest.mock('@/lib/api',()=>({API_BASE:'/api',api:{get:jest.fn(),post:jest.fn(),defaults:{headers:{common:{}}},interceptors:{response:{use:jest.fn(),eject:jest.fn()}}}}));
const data={user:{id:'u',display_name:'Person',permissions:[],must_change_password:false},csrf:'csrf',assignments:{},locked:false,access_version:'v1'};
function Child(){const auth=useRole();return <section><p>Geschützte Patientendetails</p><p data-testid="role">{auth.role||'keine Rolle'}</p><button onClick={auth.lock}>Sperren</button><button onClick={auth.refresh}>Prüfen</button></section>;}
let container,root;
beforeEach(async()=>{
 global.IS_REACT_ACT_ENVIRONMENT=true;
 global.EventSource=class{addEventListener(){}close(){}};
 jest.useFakeTimers();jest.clearAllMocks();localStorage.clear();sessionStorage.clear();
 localStorage.setItem('els-role','einsatzleiter');localStorage.setItem('els-user-name','Gefälschter Name');
 api.get.mockResolvedValue({data});api.post.mockResolvedValue({data:{ok:true}});
 container=document.createElement('div');document.body.appendChild(container);root=createRoot(container);
 await act(async()=>root.render(<RoleProvider><Child/></RoleProvider>));
});
afterEach(async()=>{await act(async()=>root.unmount());container.remove();jest.useRealTimers();});
test('local role and name cannot establish identity; unknown actions deny',()=>{
 expect(container.querySelector('[data-testid="role"]').textContent).toBe('keine Rolle');
 expect(localStorage.getItem('els-role')).toBeNull();expect(localStorage.getItem('els-user-name')).toBeNull();
 expect(canRole('einsatzleiter','unknown.action')).toBe(false);
});
test('manual lock removes the complete protected tree and rejects late identity responses',async()=>{
 let resolve;api.get.mockImplementationOnce(()=>new Promise(r=>{resolve=r;}));
 await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Prüfen').click());
 await act(async()=>[...container.querySelectorAll('button')].find(b=>b.textContent==='Sperren').click());
 expect(container.textContent).not.toContain('Geschützte Patientendetails');
 await act(async()=>resolve({data}));
 expect(container.textContent).toContain('Arbeitsplatz gesperrt');expect(container.textContent).not.toContain('Geschützte Patientendetails');
});
test('background polling never prevents the ten minute inactivity lock',async()=>{
 await act(async()=>jest.advanceTimersByTime(600001));
 expect(container.textContent).toContain('Arbeitsplatz gesperrt');
 expect(container.textContent).not.toContain('Geschützte Patientendetails');
 expect(api.post).toHaveBeenCalledWith('/auth/lock');
});
