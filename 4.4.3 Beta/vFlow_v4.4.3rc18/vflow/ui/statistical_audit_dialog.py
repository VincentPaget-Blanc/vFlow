"""Compact statistical audit dialogs with a cancellable worker and immutable results."""
import copy
import gc
import queue
import threading
import tkinter as tk
from tkinter import ttk,messagebox,filedialog,simpledialog
from vflow.statistics.models import AuditCancelled
from vflow.statistics.variable_eligibility import eligible_variables
from vflow.statistics.audit_runner import run_audit
from vflow.statistics.workspace_audit import prepare_samples,commit,decide_many,capture_population_inputs,materialize_population_inputs
from .audit_interpretation import show_interpretation
from vflow.statistics.audit_serialization import read_bundle,source_identity_warnings
from vflow.statistics.audit_export import export_xlsx,export_csv_package

class StatisticalAuditDialog(tk.Toplevel):
    def __init__(self,owner,app):
        super().__init__(app.root);self.owner=owner;self.app=app
        self.title('Statistical Audit')
        line=int(self.tk.call('font','metrics','VFlowBody','-linespace'))
        scale=max(1.,line/17)
        width=min(round(820*scale),max(1,self.winfo_screenwidth()-40))
        height=min(round(700*scale),max(1,self.winfo_screenheight()-80))
        self.geometry(f'{width}x{height}');self.minsize(min(width,round(680*scale)),min(height,round(580*scale)))
        self.cancel_event=threading.Event();self.messages=queue.Queue();self.worker=None;self.prepared=None;self._poll_id=None;self._closed=False;self._busy=False;self.excluded_variables=[]
        owner.capture(app);self.workspace_id=owner.document.workspace_id
        self.workspace_document=owner.document
        self._input_controls=[]
        self._variable_choices=None
        self.kind=tk.StringVar(self,value='qc');self.name=tk.StringVar(self,value='Within-group audit')
        self.population=tk.StringVar(self,value='Current population: '+(app.parent_label or 'All events'))
        top=ttk.Frame(self,padding=8);top.pack(fill='x')
        context_hint=ttk.Label(top,text='Compare samples from the same condition / procedure / population.',wraplength=width-24)
        context_hint.pack(anchor='w')
        population_hint=ttk.Label(top,textvariable=self.population,wraplength=width-24)
        population_hint.pack(anchor='w',pady=5)
        types=ttk.Frame(top);types.pack(fill='x')
        for text,value in [('Sample concordance / QC','qc'),('Hierarchical replication','hierarchy')]:
            button=ttk.Radiobutton(types,text=text,variable=self.kind,value=value,command=self.update_hierarchy)
            button.pack(side='left',padx=6);self._input_controls.append(button)
        name_entry=ttk.Entry(top,textvariable=self.name);name_entry.pack(fill='x',pady=6);self._input_controls.append(name_entry)
        sample_hint=ttk.Label(top,text='Click a sample to select or deselect it; other selections stay. Space toggles the focused row.\nDouble-click Biological replicate to edit its ID.',wraplength=770)
        sample_hint.pack(anchor='w')
        frame=ttk.Frame(self,padding=(12,0));frame.pack(fill='both',expand=True)
        self.samples=ttk.Treeview(frame,columns=('state','bio'),show='tree headings',selectmode='none',height=8)
        self.samples.heading('#0',text='Sample');self.samples.heading('state',text='Current state');self.samples.heading('bio',text='Biological replicate')
        self.samples.column('#0',width=300);self.samples.column('state',width=90);self.samples.column('bio',width=140)
        scroll=ttk.Scrollbar(frame,command=self.samples.yview);self.samples.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.samples.pack(fill='both',expand=True)
        self.mapping={}
        active=set(app._active())
        membership=owner.document.tabs.get(app._workspace_tab_id,{}).get('sample_ids') if app is not owner.main else None
        for sid,s in owner.document.samples.items():
            if membership is not None and sid not in membership:continue
            self.samples.insert('', 'end',iid=sid,text=s.display_name,values=('Excluded' if s.excluded else 'Included',''))
            if owner.path_for(sid) in active:self.samples.selection_add(sid)
        self.samples.bind('<Button-1>',self.toggle_sample_click)
        self.samples.bind('<Double-1>',self.sample_double_click)
        for key in ('<space>','<Return>'):
            self.samples.bind(key,self.toggle_focused_sample)
        controls=ttk.Frame(self,padding=8);controls.pack(fill='x')
        self.all_samples_button=ttk.Button(controls,text='Select all samples',command=lambda:self.samples.selection_set(self.samples.get_children()))
        self.all_samples_button.pack(side='left');self._input_controls.append(self.all_samples_button)
        self.no_samples_button=ttk.Button(controls,text='None',command=lambda:self.samples.selection_set(()))
        self.no_samples_button.pack(side='left',padx=6);self._input_controls.append(self.no_samples_button)
        self.prepare_button=ttk.Button(controls,text='Prepare populations / variables',command=self.prepare);self.prepare_button.pack(side='left',padx=8)
        variable_hint=ttk.Label(self,text='Variables — click to include or remove each one; no Ctrl/Command needed.',wraplength=770)
        variable_hint.pack(fill='x',padx=12,pady=(0,3))
        variable_frame=ttk.Frame(self);variable_frame.pack(fill='both',expand=True,padx=12)
        self._variable_frame=variable_frame;self._sample_frame=frame;self._row_resize_id=None
        self.variables=tk.Listbox(variable_frame,selectmode='multiple',exportselection=False,height=7,font='VFlowBody')
        self.style_variables()
        self.bind('<FocusIn>',lambda event:self.style_variables(),add='+')
        sy=ttk.Scrollbar(variable_frame,command=self.variables.yview)
        sx=ttk.Scrollbar(variable_frame,orient='horizontal',command=self.variables.xview)
        self.variables.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        variable_frame.columnconfigure(0,weight=1);variable_frame.rowconfigure(0,weight=1)
        self.variables.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        self.variables.bind('<Button-1>',self.variable_click_guard)
        self.variables.bind('<<ListboxSelect>>',lambda event:self.variable_selection_status())
        variable_controls=ttk.Frame(self,padding=6);variable_controls.pack(fill='x')
        self.all_variables_button=ttk.Button(variable_controls,text='All variables',command=lambda:self.set_variable_selection(True))
        self.all_variables_button.pack(side='left');self._input_controls.append(self.all_variables_button)
        self.no_variables_button=ttk.Button(variable_controls,text='None',command=lambda:self.set_variable_selection(False))
        self.no_variables_button.pack(side='left',padx=8);self._input_controls.append(self.no_variables_button)
        ttk.Button(variable_controls,text='Why variables were excluded',command=self.show_exclusions).pack(side='left',padx=8)
        self.status=tk.StringVar(self,value='Prepare populations to see eligible numeric variables.')
        status_label=ttk.Label(self,textvariable=self.status,wraplength=770);status_label.pack(fill='x',padx=12,pady=5)
        actions=ttk.Frame(self,padding=8);actions.pack(fill='x')
        ttk.Button(actions,text='How to interpret',command=lambda:show_interpretation(self)).pack(side='left')
        self.run_button=ttk.Button(actions,text='Run audit',command=self.run);self.run_button.pack(side='right')
        ttk.Button(actions,text='Cancel / Close',command=self.close).pack(side='right',padx=8)
        # Reserve fixed controls before assigning the remaining height to samples.
        for widget in (actions,status_label,variable_controls,variable_frame,variable_hint,controls):
            widget.pack_configure(side='bottom',before=frame,expand=False)
        def resize_hints(event):
            if event.widget is self:
                for label in (context_hint,population_hint,sample_hint,variable_hint,status_label):label.configure(wraplength=max(300,event.width-24))
            if event.widget in (self,top,controls,variable_frame,variable_hint,variable_controls,status_label,actions):
                if self._row_resize_id is None:self._row_resize_id=self.after_idle(self.resize_variable_rows)
        self.bind('<Configure>',resize_hints)
        self.protocol('WM_DELETE_WINDOW',self.close);self.update_hierarchy()
        self._row_resize_id=self.after_idle(self.resize_variable_rows)
    def resize_variable_rows(self):
        self._row_resize_id=None
        if self._closed:return
        # Reserve two sample rows before allocating a bounded variable list.
        # Measure on the normal event loop; never pump nested Tk events here.
        fixed=0
        for widget in self.winfo_children():
            if widget in (self._sample_frame,self._variable_frame) or widget.winfo_manager()!='pack':continue
            fixed+=widget.winfo_reqheight()
            padding=widget.pack_info().get('pady',0)
            parts=padding if isinstance(padding,(tuple,list)) else str(padding).split()
            values=[int(p) for p in parts]
            fixed+=sum(values) if len(values)>1 else 2*values[0] if values else 0
        line=max(1,int(self.tk.call('font','metrics',self.variables.cget('font'),'-linespace')))
        # The styled heading can be as tall as a data row at large scaling.
        sample_rows=3*int(ttk.Style(self).lookup('Treeview','rowheight') or 24)+8
        overhead=self._variable_frame.winfo_reqheight()-self.variables.winfo_reqheight()+4
        rows=max(1,min(7,(self.winfo_height()-fixed-overhead-sample_rows)//line))
        if int(self.variables.cget('height'))!=rows:self.variables.configure(height=rows)
    def toggle_sample(self,sid):
        if self._busy or not sid or not self.samples.exists(sid):return
        if sid in self.samples.selection():self.samples.selection_remove(sid)
        else:self.samples.selection_add(sid)
    def toggle_sample_click(self,event):
        if self._busy:return 'break'
        if self.samples.identify_region(event.x,event.y) not in ('tree','cell'):return
        sid=self.samples.identify_row(event.y)
        if not sid:return 'break'
        self._sample_click_before=(sid,sid in self.samples.selection())
        self.samples.focus_set();self.samples.focus(sid);self.toggle_sample(sid)
        return 'break'
    def toggle_focused_sample(self,event=None):
        self.toggle_sample(self.samples.focus());return 'break'
    def sample_double_click(self,event):
        if self._busy:return 'break'
        sid=self.samples.identify_row(event.y)
        if self.kind.get()=='hierarchy' and self.samples.identify_column(event.x)=='#2' and sid:
            # Editing a replicate ID should preserve membership from before the
            # first click of the double-click sequence.
            previous=getattr(self,'_sample_click_before',None)
            if previous and previous[0]==sid:
                if previous[1]:self.samples.selection_add(sid)
                else:self.samples.selection_remove(sid)
            self.edit_bio(event)
            return 'break'
        return self.toggle_sample_click(event)
    def variable_click_guard(self,event):
        if self._busy or not self.variables.size():return 'break'
        index=self.variables.nearest(event.y);box=self.variables.bbox(index)
        if not box or not box[1]<=event.y<box[1]+box[3]:return 'break'
    def style_variables(self):
        palette=self.app.T
        self.variables.configure(background=palette['field_bg'],foreground=palette['fg'],
            selectbackground=palette['sel_bg'],selectforeground='white',
            highlightbackground=palette['header_bg'],highlightcolor=palette['sel_bg'],disabledforeground=palette['fg_dim'])
    def variable_selection_status(self):
        if self._busy or not self.prepared:return
        self.status.set(f'{self.variables.size()} eligible variables; {len(self.variables.curselection())} selected; {len(self.excluded_variables)} excluded. All finite values in selected variables will be used.')
    def set_variable_selection(self,selected):
        if self._busy:return
        if selected:self.variables.select_set(0,'end')
        else:self.variables.selection_clear(0,'end')
        self.variable_selection_status()
    def workspace_is_current(self):
        return (self.owner.document is self.workspace_document and self.owner.document.workspace_id==self.workspace_id
                and self.owner.apps.get(self.app._workspace_tab_id) is self.app)
    def check_workspace(self):
        if self.workspace_is_current():return True
        messagebox.showerror('Audit','Workspace or population tab changed; reopen Statistical Audit.',parent=self)
        return False
    def set_busy(self,busy):
        self._busy=busy
        state='disabled' if busy else 'normal'
        for widget in self._input_controls+[self.run_button,self.prepare_button]:widget.configure(state=state)
        self.samples.state(['disabled'] if busy else ['!disabled'])
        self.variables.configure(state=state)
    def update_hierarchy(self):
        self.samples.configure(displaycolumns=('state','bio') if self.kind.get()=='hierarchy' else ('state',))
    def edit_bio(self,event):
        if self._busy or self.kind.get()!='hierarchy' or self.samples.identify_column(event.x)!='#2':return
        sid=self.samples.identify_row(event.y)
        if not sid:return
        value=simpledialog.askstring('Biological replicate','Biological replicate ID:',initialvalue=self.mapping.get(sid,''),parent=self)
        if value is not None and not self._closed and self.workspace_is_current() and sid in self.owner.document.samples:
            self.mapping[sid]=value.strip();self.samples.set(sid,'bio',value.strip())
    def prepare(self):
        if self._closed or self._busy or (self.worker and self.worker.is_alive()):return
        if not self.check_workspace():return
        ids=list(self.samples.selection())
        if not ids:messagebox.showerror('Audit','Select at least one sample.',parent=self);return
        try:inputs=capture_population_inputs(self.owner,self.app,ids)
        except (ValueError,KeyError) as exc:messagebox.showerror('Audit',str(exc),parent=self);return
        self.prepared_ids=ids;self.prepared_tab=self.app._workspace_tab_id
        if self.variables.size():
            self._variable_choices={self.variables.get(i) for i in self.variables.curselection()}
        self.prepared=None;self.excluded_variables=[];self.variables.delete(0,'end')
        # Workers own only immutable inputs, a queue and cancellation state.
        # Retaining this Tk dialog can finalize its interpreter on a worker.
        messages,cancel=self.messages,self.cancel_event
        def work():
            try:
                prepared=materialize_population_inputs(inputs,cancel)
                eligible,excluded,_=eligible_variables(prepared)
                messages.put(('variables',(eligible,excluded,prepared)))
            except AuditCancelled as exc:messages.put(('cancelled',str(exc)))
            except Exception as exc:messages.put(('error',str(exc)))
        self.start(work)
    def start(self,target):
        if self._closed or self._busy or (self.worker and self.worker.is_alive()):return
        if self._poll_id:self.after_cancel(self._poll_id);self._poll_id=None
        self.cancel_event.clear();self.set_busy(True)
        gc.collect()  # Finalize retired GUI objects here, before worker allocations.
        self.worker=threading.Thread(target=target,daemon=True);self.worker.start();self._poll_id=self.after(80,self.poll)
    def run(self):
        if self._closed or self._busy or (self.worker and self.worker.is_alive()):return
        if not self.check_workspace():return
        if not self.prepared or set(self.samples.selection())!=set(self.prepared_ids):
            messagebox.showerror('Audit','Prepare the currently selected populations first.',parent=self);return
        selected=[self.variables.get(i) for i in self.variables.curselection()]
        kind=self.kind.get();mapping={s.sample_id:self.mapping.get(s.sample_id,'') for s in self.prepared}
        if not selected:messagebox.showerror('Audit','Select at least one variable.',parent=self);return
        if kind=='hierarchy' and any(not b for b in mapping.values()):
            messagebox.showerror('Audit','Assign a biological replicate ID to every selected sample.',parent=self);return
        name=self.name.get().strip() or 'Within-group audit';population=self.population.get()
        try:inputs=capture_population_inputs(self.owner,self.app,self.prepared_ids)
        except (ValueError,KeyError) as exc:messagebox.showerror('Audit',str(exc),parent=self);return
        messages,cancel=self.messages,self.cancel_event
        def work():
            try:
                prepared=materialize_population_inputs(inputs,cancel,lambda stage:messages.put(('progress',stage)))
                bundle=run_audit(prepared,selected,kind,name,population,mapping if kind=='hierarchy' else None,
                    cancel=cancel,progress=lambda stage:messages.put(('progress',stage)))
                messages.put(('result',bundle))
            except AuditCancelled as exc:messages.put(('cancelled',str(exc)))
            except Exception as exc:messages.put(('error',str(exc)))
        self.start(work)
    def poll(self):
        if self._closed:return
        if self._poll_id:self.after_cancel(self._poll_id);self._poll_id=None
        last_progress=None
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='progress':last_progress=value
                elif kind=='variables':
                    if not self.workspace_is_current():
                        self.prepared=None;self.status.set('Workspace or population tab changed; reopen Statistical Audit.');continue
                    if len(value)>2:self.prepared=value[2]
                    self.excluded_variables=value[1]
                    self.variables.configure(state='normal')
                    for v in value[0]:self.variables.insert('end',v)
                    if self._variable_choices is None:self.variables.select_set(0,'end')
                    else:
                        for index,name in enumerate(value[0]):
                            if name in self._variable_choices:self.variables.select_set(index)
                    self.status.set(f'{len(value[0])} eligible variables; {len(self.variables.curselection())} selected; {len(value[1])} excluded. All finite values in selected variables will be used.')
                elif kind in ('error','cancelled'):
                    last_progress=None
                    self.status.set(value)
                    if kind=='error':messagebox.showerror('Audit',value,parent=self)
                elif kind=='result':
                    last_progress=None
                    if self.cancel_event.is_set():self.status.set('Cancelled; no audit committed.');continue
                    try:
                        if not self.workspace_is_current():raise ValueError('Workspace or population tab changed; audit was not committed.')
                        ref=commit(self.owner,value);AuditResultsDialog(self.owner,ref,value);self.status.set('Audit saved: '+ref.name)
                    except (OSError,ValueError) as exc:
                        self.status.set(str(exc));messagebox.showerror('Audit',str(exc),parent=self)
        except queue.Empty:pass
        if last_progress:self.status.set(last_progress)
        if (self.worker and self.worker.is_alive()) or not self.messages.empty():
            if self._busy:self.variables.configure(state='disabled')
            self._poll_id=self.after(80,self.poll)
        else:self._poll_id=None;self.set_busy(False)
    def close(self):
        self.destroy()
    def destroy(self):
        # Tk also calls destroy directly when closing the parent window.
        if self._closed:return
        self._closed=True
        self.cancel_event.set()
        for attr in ('_poll_id','_row_resize_id'):
            token=getattr(self,attr,None);setattr(self,attr,None)
            if token:
                try:self.after_cancel(token)
                except tk.TclError:pass
        super().destroy()
    def show_exclusions(self):
        reasons={'missing_in_sample':'Not present in every selected sample','non_numeric':'Not a real numeric measurement',
            'integer_precision_exceeds_float64':'Integer values exceed the exact float64 range','insufficient_finite_values':'Fewer than three finite values in at least one sample',
            'constant_or_zero_scale':'Constant in a selected sample or no pooled spread','numeric_range_exceeds_float64':'Pooled spread exceeds the supported numeric range'}
        dialog=tk.Toplevel(self);dialog.title('Variable eligibility');dialog.geometry('640x340')
        text=tk.Text(dialog,wrap='word',padx=12,pady=12);text.pack(fill='both',expand=True)
        text.insert('end','Variables must be shared, numeric and nonconstant, with at least three finite values in every selected sample.\n\n')
        for row in self.excluded_variables:text.insert('end',str(row['variable'])+': '+reasons.get(row['reason'],row['reason'])+'\n')
        if not self.excluded_variables:text.insert('end','No excluded variables recorded. Prepare populations to refresh this list.')
        text.configure(state='disabled')

class AuditResultsDialog(tk.Toplevel):
    def __init__(self,owner,reference,bundle=None):
        super().__init__(owner.main.root);self.owner=owner;self.reference=reference;self.workspace_id=owner.document.workspace_id
        try:self.bundle=bundle or read_bundle(reference,owner.path)
        except (ValueError,OSError) as exc:self.destroy();messagebox.showerror('Audit',str(exc),parent=owner.main.root);return
        self.title(reference.name)
        line=int(self.tk.call('font','metrics','VFlowBody','-linespace'));scale=max(1.,line/17)
        width=min(round(1000*scale),max(1,self.winfo_screenwidth()-40))
        height=min(round(760*scale),max(1,self.winfo_screenheight()-80))
        self.geometry(f'{width}x{height}');self.minsize(min(width,round(720*scale)),min(height,round(580*scale)))
        warnings=source_identity_warnings(self.bundle,owner.document,owner.path)
        explanation=ttk.Label(self,text='\n'.join(warnings+[self.bundle['interpretation']]),wraplength=960);explanation.pack(fill='x',padx=12,pady=10)
        definitions=ttk.Label(self,text='Saved snapshot: scores use the data and gates at audit creation. Later edits do not recalculate them; run a new audit to compare. Current state shows inclusion now.\nGlobal discordance measures joint distribution differences; isolation compares separation from peers. Flags ask for review. Zero is a computed score; Unavailable means no eligible joint comparison. See Details and How to interpret.',wraplength=width-24);definitions.pack(fill='x',padx=12,pady=(0,8))
        def resize_explanations(event):
            if event.widget is self:
                for label in (explanation,definitions):label.configure(wraplength=max(300,event.width-24))
        self.bind('<Configure>',resize_explanations)
        frame=ttk.Frame(self);frame.pack(fill='both',expand=True,padx=12)
        self.tree=ttk.Treeview(frame,columns=('status','score','isolation','contributors','state'),show='tree headings',height=12)
        for key,label in [('#0','Sample'),('status','Status'),('score','Global discordance'),('isolation','Isolation'),('contributors','Top contributors'),('state','Current state')]:
            self.tree.heading(key,text=label);self.tree.column(key,width=150,minwidth=80)
        sy=ttk.Scrollbar(frame,command=self.tree.yview);sx=ttk.Scrollbar(frame,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        sy.pack(side='right',fill='y');sx.pack(side='bottom',fill='x');self.tree.pack(fill='both',expand=True)
        bar=ttk.Frame(self,padding=12);bar.pack(side='bottom',fill='x',before=frame)
        for i,(label,fn) in enumerate([('Details',self.details),('How to interpret',lambda:show_interpretation(self,self.bundle)),('Keep / Reviewed',lambda:self.action('keep')),('Exclude',lambda:self.action('exclude')),
            ('Restore',lambda:self.action('restore')),('Add note',lambda:self.action('note')),('Rename',self.rename),('Export…',self.export)]):
            ttk.Button(bar,text=label,command=fn).grid(row=i//4,column=i%4,padx=4,pady=3,sticky='ew')
        for i in range(4):bar.columnconfigure(i,weight=1)
        self.refresh()
        self._state_poll_id=self.after(250,self.poll_current_state)
        self.bind('<Destroy>',self.cancel_state_poll,add='+')
    def state_signature(self):
        return (self.is_current(),tuple((r['sample_id'],r['sample_id'] in self.owner.document.samples,
            getattr(self.owner.document.samples.get(r['sample_id']),'excluded',None)) for r in self.bundle['sample_qc']))
    def poll_current_state(self):
        self._state_poll_id=None
        if self.state_signature()!=self._state_signature:self.refresh()
        self._state_poll_id=self.after(250,self.poll_current_state)
    def cancel_state_poll(self,event):
        if event.widget is self and getattr(self,'_state_poll_id',None):
            self.after_cancel(self._state_poll_id);self._state_poll_id=None
    def refresh(self):
        self._state_signature=self.state_signature()
        selected=self.tree.selection();self.tree.delete(*self.tree.get_children())
        for row in self.bundle['sample_qc']:
            sid=row['sample_id'];sample=self.owner.document.samples.get(sid) if self.is_current() else None
            self.tree.insert('','end',iid=sid,text=row['sample_name'],values=(row['status'].replace('_',' '),
                'Unavailable' if row['global_peer_distance'] is None else f"{row['global_peer_distance']:.5g}",
                '—' if row['global_isolation_ratio'] is None else f"{row['global_isolation_ratio']:.4g}",
                ', '.join(r['variable'] for r in row['contributors'][:3]),('Unknown (workspace changed)' if not self.is_current() else 'Removed') if sample is None else ('Excluded' if sample.excluded else 'Included')))
        for sid in selected:
            if self.tree.exists(sid):self.tree.selection_add(sid)
    def action(self,action):
        ids=self.tree.selection()
        if not ids:return
        note=simpledialog.askstring('Review '+action,'Optional reason / note:',parent=self)
        if note is None:return
        try:
            decide_many(self.owner,self.reference,ids,action,'other' if note else 'no_reason_supplied',note)
        except ValueError as exc:messagebox.showerror('Review',str(exc),parent=self)
        self.refresh()
    def rename(self):
        if not self.is_current():messagebox.showerror('Audit','Workspace changed; reopen this audit from the current workspace.',parent=self);return
        name=simpledialog.askstring('Rename audit','Display name:',initialvalue=self.reference.name,parent=self)
        if not self.is_current() or not self.winfo_exists():return
        if name and name.strip():self.reference.name=name.strip();self.title(name.strip());self.owner.mark_dirty()
    def is_current(self):
        return self.owner.document.workspace_id==self.workspace_id and self.owner.document.audits.get(self.reference.audit_id) is self.reference
    def details(self):
        ids=self.tree.selection()
        if not ids:return
        sid=ids[0];dialog=tk.Toplevel(self);dialog.title('Audit details');dialog.geometry('1000x620')
        row=next(r for r in self.bundle['sample_qc'] if r['sample_id']==sid)
        ttk.Label(dialog,text=f"{row['sample_name']} — {row['status'].replace('_',' ')}",font=('TkDefaultFont',12,'bold')).pack(anchor='w',padx=12,pady=10)
        ttk.Label(dialog,text=f"{row['event_count']:,} events; {row['multivariate_complete_count']:,} complete rows for joint distances. Finite univariate values are retained.",wraplength=940).pack(anchor='w',padx=12)
        ttk.Label(dialog,text=f"Joint comparison: {row.get('multivariate_sample_count','Unknown')} available samples; {row.get('global_peer_count','Unknown')} peers. Isolation condition: {row['isolation_condition'].replace('_',' ')}. Robust z condition: {row.get('robust_z_condition','not recorded')}.\nRobust z: {row['robust_z'] if row['robust_z'] is not None else 'Unavailable'}; projection review repeated: {row['projection_stability'] if row['projection_stability'] is not None else 'Not applicable'}.",wraplength=940).pack(anchor='w',padx=12,pady=5)
        ttk.Button(dialog,text='How to interpret',command=lambda:show_interpretation(dialog,self.bundle)).pack(anchor='w',padx=12)
        notebook=ttk.Notebook(dialog);notebook.pack(fill='both',expand=True,padx=12,pady=12)
        def table(title,rows,fields):
            frame=ttk.Frame(notebook);notebook.add(frame,text=title)
            tree=ttk.Treeview(frame,columns=[k for k,_ in fields],show='headings')
            for k,label in fields:tree.heading(k,text=label);tree.column(k,width=155,minwidth=90)
            sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
            tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
            sy.pack(side='right',fill='y');sx.pack(side='bottom',fill='x');tree.pack(fill='both',expand=True)
            def display(value):
                if value is None:return 'Unavailable'
                if isinstance(value,float):return f'{value:.6g}'
                if isinstance(value,bool):return 'Yes' if value else 'No'
                return str(value)
            for r in rows:tree.insert('','end',values=[display(r.get(k)) for k,_ in fields])
            return tree
        table('Variables',[r for r in self.bundle['variable_qc'] if r['sample_id']==sid],[(k,label) for k,label in [('variable','Variable'),('count','Finite values'),('missing_count','Nonfinite values'),('mean','Mean'),('median','Median'),('std','SD'),('iqr','IQR'),('raw_peer_distance','Raw peer W1'),('peer_distance','Normalized peer W1'),('isolation_ratio','Isolation'),('isolation_condition','Isolation condition'),('scale_method','Scale method')]])
        if self.bundle['audit_type']=='hierarchy':
            table('Variance components',self.bundle['variance_components'],[('variable','Variable'),('model_status','Model status'),('n_biological','Biological units'),('n_nested','Nested samples'),('n_particles','Events'),('sigma2_bio','Biological variance'),('sigma2_nested_sample','Nested variance'),('sigma2_particle','Particle variance'),('icc_bio','Biological ICC'),('icc_same_nested_sample','Within sample ICC'),('reason','Model reason')])
            table('Biological influence',self.bundle['influence'],[('variable','Variable'),('omitted_bio','Omitted biological ID'),('full_equal_bio_center','Full center'),('loo_equal_bio_center','Leave-one-out center'),('delta','Signed change'),('absolute_change','Absolute change'),('relative_change','Relative change'),('standardized_change','Standardized change'),('influence_status','Status'),('low_biological_n','Low biological N')])
            table('Leave-one-out models',[{'variable':r['variable'],'omitted_bio':r['omitted_bio'],**r['loo_variance_components']} for r in self.bundle['influence']],[('variable','Variable'),('omitted_bio','Omitted biological ID'),('model_status','Model status'),('sigma2_bio','Biological variance'),('sigma2_nested_sample','Nested variance'),('sigma2_particle','Particle variance'),('icc_bio','Biological ICC'),('icc_same_nested_sample','Within sample ICC'),('reason','Model reason')])
        table('Review history',[r for r in self.reference.decision_history if r['sample_id']==sid],[('action','Action'),('timestamp','Date'),('reason_code','Reason'),('note','Note')])
        provenance=ttk.Frame(notebook);notebook.add(provenance,text='Provenance')
        snapshot=next(r for r in self.bundle['samples'] if r['sample_id']==sid)
        text=tk.Text(provenance,wrap='word');text.pack(fill='both',expand=True)
        text.insert('1.0',f"Audit: {self.reference.audit_id}\nCreated: {self.bundle['created_at']}\nPopulation: {self.bundle['population_label']}\nSource: {row['original_source']}\nPopulation snapshot SHA-256: {snapshot['population_sha256']}\n\n{self.bundle['interpretation']}\n\nComplete gate snapshots, source fingerprints, policies and matrices are included in the export.")
        text.configure(state='disabled')
    def export(self):
        dialog=tk.Toplevel(self);dialog.title('Export audit');kind=tk.StringVar(dialog,value='xlsx')
        ttk.Radiobutton(dialog,text='Excel workbook (.xlsx) — Recommended',variable=kind,value='xlsx').pack(padx=15,pady=10)
        ttk.Radiobutton(dialog,text='CSV package (.zip)',variable=kind,value='csv').pack(padx=15,pady=10)
        def save():
            mode=kind.get();ext='.xlsx' if mode=='xlsx' else '.zip'
            path=filedialog.asksaveasfilename(parent=dialog,initialfile=self.reference.audit_id+ext,defaultextension=ext,
                filetypes=[('Excel workbook' if mode=='xlsx' else 'CSV package','*'+ext)])
            if not path:return
            protected=[self.owner.path,*self.owner.main.loaded_files,*self.owner.main.excluded_files,
                *(ref.absolute_path for _,ref in self.owner.document.references())]
            try:(export_xlsx if mode=='xlsx' else export_csv_package)(self.bundle,path,self.reference,self.owner.document if self.is_current() else None,protected_paths=protected)
            except (OSError,ValueError) as exc:messagebox.showerror('Export',str(exc),parent=dialog);return
            dialog.destroy()
        ttk.Button(dialog,text='Save export',command=save).pack(pady=12)

class AuditListDialog(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner.main.root);self.title('Statistical audits');self.geometry('700x360');self.owner=owner;self.document=owner.document
        table=ttk.Frame(self);table.pack(fill='both',expand=True,padx=10,pady=10)
        table.columnconfigure(0,weight=1);table.rowconfigure(0,weight=1)
        tree=ttk.Treeview(table,columns=('type','created'),show='tree headings');tree.heading('#0',text='Audit');tree.heading('type',text='Type');tree.heading('created',text='Created')
        tree.grid(row=0,column=0,sticky='nsew')
        sy=ttk.Scrollbar(table,orient='vertical',command=tree.yview);sy.grid(row=0,column=1,sticky='ns')
        sx=ttk.Scrollbar(table,orient='horizontal',command=tree.xview);sx.grid(row=1,column=0,sticky='ew')
        tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        for aid,ref in owner.document.audits.items():tree.insert('','end',iid=aid,text=ref.name,values=(ref.audit_type,ref.created_at[:19]))
        def open_selected():
            if owner.document is not self.document:
                messagebox.showinfo('Statistical audits','Workspace changed. Reopen the saved-audit list for the current workspace.',parent=self);return
            if tree.selection():
                ref=owner.document.audits.get(tree.selection()[0])
                if ref:AuditResultsDialog(owner,ref)
        self.tree=tree;self.open_selected=open_selected
        actions=ttk.Frame(self);actions.pack(side='bottom',fill='x',padx=10,pady=8,before=table)
        ttk.Button(actions,text='Open audit',command=open_selected).pack(side='right')
        ttk.Button(actions,text='Close',command=self.destroy).pack(side='right',padx=6)
        tree.bind('<Double-1>',lambda e:open_selected())
