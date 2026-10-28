import * as React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useRole } from '@/context/RoleContext';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
export function RoleSelectorDialog() {
 const { pickerOpen, setPickerOpen, displayName, lock, logout, refresh } = useRole();
 const [currentPassword, setCurrentPassword] = React.useState('');
 const [newPassword, setNewPassword] = React.useState('');
 const [message, setMessage] = React.useState('');
 React.useEffect(() => { setCurrentPassword(''); setNewPassword(''); setMessage(''); }, [pickerOpen]);
 return <Dialog open={pickerOpen} onOpenChange={setPickerOpen}><DialogContent>
 <DialogHeader><DialogTitle>{displayName}</DialogTitle><DialogDescription>Die Einsatzrolle wird serverseitig zugewiesen.</DialogDescription></DialogHeader>
 <Button onClick={lock}>Arbeitsplatz sperren</Button><Button variant="outline" onClick={logout}>Abmelden / Benutzer wechseln</Button>
 <form className="space-y-3 border-t pt-3" onSubmit={async e => {e.preventDefault();try{await api.post('/auth/password',{current_password:currentPassword,password:newPassword});await refresh();setMessage('Passwort geändert; andere Sessions wurden widerrufen.');}catch{setMessage('Passwortänderung fehlgeschlagen. Aktuelles Passwort und Verbindung prüfen.');}finally{setCurrentPassword('');setNewPassword('');}}}>
 <h3>Eigenes Passwort ändern</h3><label className="block">Aktuelles Passwort<Input type="password" required autoComplete="current-password" value={currentPassword} onChange={e=>setCurrentPassword(e.target.value)}/></label><label className="block">Neues Passwort<Input type="password" required minLength={12} autoComplete="new-password" value={newPassword} onChange={e=>setNewPassword(e.target.value)}/></label><Button>Passwort ändern</Button>{message&&<p role="status">{message}</p>}
 </form>
 </DialogContent></Dialog>;
}
