"""Workspace presentation, gate transfer, and semantic interface scaling."""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import sys
from vflow.workspace.controller import WorkspaceController
from vflow.ui.fonts import semantic_fonts
from vflow.ui.tooltips import tooltip
from vflow.ui.task_sidebar import SECTION_TITLES
from vflow.ui.adaptive_samples import AdaptiveSamplesMixin

class WorkspaceUIMixin(AdaptiveSamplesMixin):
    def _workspace_initialize(self):
        owner = getattr(self.manager, '_workspace_controller', None) if self.manager else None
        if owner is None:
            owner = WorkspaceController(self)
            if self.manager: self.manager._workspace_controller = owner
        self._workspace = owner; owner.register(self)
        if not hasattr(owner, '_fonts'):
            owner._fonts = semantic_fonts(self.root)
        self.gate_scope_var = tk.StringVar(self.root, value='All samples (default)')
        self.interface_size_var = tk.StringVar(self.root, value='Automatic')
        self.auto_gate_input_var = tk.StringVar(self.root, value='Active samples (pooled)')
        self._workspace_applying_view = self._workspace_rendering = False
        self._sections = {}
        self._workspace_sample_icons = {}
        self._sample_panel_fraction = None
        self.sample_panel_mode_var = tk.StringVar(self.root, value='Automatic')

    def _build_workspace_panel(self, parent):
        panel = ttk.Frame(parent, style='TFrame'); panel.pack(fill='both', expand=True)
        self._workspace_panel = panel
        self._workspace_name_var = tk.StringVar(self.root, value=self._workspace.workspace_name())
        header = ttk.Frame(panel); header.pack(fill='x', padx=8, pady=(6, 3))
        self._build_sidebar_settings(header)
        self._workspace_name_entry = ttk.Entry(header, textvariable=self._workspace_name_var, width=15)
        self._workspace_name_entry.pack(side='left', fill='x', expand=True)
        tooltip(self._workspace_name_entry, 'Click to rename this workspace. Enter or leaving the field applies the name; Escape cancels. Rename changes the display name; Save As chooses another file.')
        self._workspace_name_entry.bind('<FocusIn>', self._workspace_name_focus)
        self._workspace_name_entry.bind('<Return>', self._workspace_name_commit)
        self._workspace_name_entry.bind('<FocusOut>', self._workspace_name_commit)
        self._workspace_name_entry.bind('<Escape>', self._workspace_name_cancel)
        buttons = ttk.Frame(panel); buttons.pack(fill='x', padx=8)
        self._workspace_summary_var = tk.StringVar(self.root)
        summary = ttk.Label(buttons, textvariable=self._workspace_summary_var, style='Dim.TLabel', wraplength=230)
        summary.pack(side='left', fill='x', expand=True)
        from vflow.ui.layout_helpers import wrap_on_resize, reserve_footer
        wrap_on_resize(summary)
        source_button = ttk.Button(buttons, text='Sources', command=lambda: self._select_sidebar_task('Data'))
        source_button.pack(side='right')
        summary.pack_configure(after=source_button)
        f = ttk.Frame(panel); f.pack(fill='both', expand=True, padx=8, pady=4)
        tree = ttk.Treeview(f, columns=('active','state'), show='tree headings', height=8, selectmode='none')
        tree.heading('#0', text='Samples'); tree.heading('active',text='Active'); tree.heading('state', text='State')
        tree.column('#0', width=140, minwidth=100); tree.column('active',width=48,minwidth=40,stretch=False)
        tree.column('state', width=100, minwidth=75,stretch=False)
        tree.bind('<Button-1>', self._workspace_sample_click)
        # Rapid clicks are selection gestures; Show sample is explicit.
        tree.bind('<Double-1>', self._workspace_sample_click)
        for key in ('<space>', '<Return>'):
            tree.bind(key, self._workspace_sample_key)
        scroll = ttk.Scrollbar(f, orient='vertical', command=tree.yview)
        horizontal = ttk.Scrollbar(f, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        f.columnconfigure(0, weight=1); f.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky='nsew'); scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        events = ('<Button-3>', '<Control-Button-1>') if sys.platform == 'darwin' else ('<Button-3>',)
        for event in events: tree.bind(event, lambda e: self._workspace.sample_menu(self, e))
        self._workspace_tree = tree
        self._workspace_hover_sample = None
        tree.bind('<Motion>', lambda event: setattr(self, '_workspace_hover_sample', tree.identify_row(event.y)), add='+')
        tooltip(tree, lambda: self._workspace.sample_hover_text(self, self._workspace_hover_sample))
        self._workspace_resize_binding = self.root.bind('<Configure>',lambda event:self._workspace_fit_rows() if event.widget is self.root else None,add='+')
        tools = ttk.Frame(panel); tools.pack(fill='x', padx=8, pady=(1,4))
        tools.columnconfigure((0,1,2),weight=1,uniform='samples')
        for column,(text,callback,help_text) in enumerate([
            ('All active',self._select_all,'Activate every loaded sample without changing row selection.'),
            ('None active',self._unselect_all,'Deactivate every loaded sample; keep files and saved gates.'),
            ('Actions…',self._selected_sample_actions,'Source location, details, sample gates and workspace actions for the selected row.')]):
            tooltip(ttk.Button(tools,text=text,command=callback),help_text).grid(row=0,column=column,sticky='ew',padx=2,pady=2)
        self._sample_exclude_button = ttk.Button(tools,text='Exclude',command=lambda:self._sample_inclusion_action(False))
        self._sample_restore_button = ttk.Button(tools,text='Restore',command=lambda:self._sample_inclusion_action(True))
        self._sample_exclude_button.grid(row=1,column=0,sticky='ew',padx=2,pady=2)
        self._sample_restore_button.grid(row=1,column=1,sticky='ew',padx=2,pady=2)
        tooltip(self._sample_exclude_button,'Exclude one selected sample from analysis; retain its workspace reference and allow Restore.')
        tooltip(self._sample_restore_button,'Restore one selected excluded sample to analysis.')
        self._sample_show_button = ttk.Button(tools,text='Show sample',command=self._show_selected_sample)
        self._sample_show_button.grid(row=1,column=2,sticky='ew',padx=2,pady=2)
        tooltip(self._sample_show_button,'Select one loaded sample to display it in Cycle view.')
        tree.bind('<<TreeviewSelect>>',lambda e:self._update_sample_action_buttons())
        view = ttk.Frame(panel); view.pack(fill='x', padx=8)
        ttk.Label(view,text='View:').pack(side='left',padx=(0,3))
        for value, text in [('overlay','Overlay'),('cycle','Cycle')]:
            ttk.Radiobutton(view, text=text, variable=self.view_mode_var, value=value, command=self._on_view_mode_change).pack(side='left')
        self._btn_prev = ttk.Button(view, text='Prev', width=4, command=self._cycle_prev, state='disabled')
        self._btn_prev.pack(side='left')
        self._btn_next = ttk.Button(view, text='Next', width=4, command=self._cycle_next, state='disabled')
        self._btn_next.pack(side='left')
        self.cycle_label_var = tk.StringVar(self.root, value='')
        self._workspace_scope_label=tk.StringVar(self.root, value='Overlay · All samples')
        scope = ttk.Label(panel,textvariable=self._workspace_scope_label,style='Dim.TLabel',wraplength=310)
        scope.pack(fill='x',padx=8,pady=(0,5)); wrap_on_resize(scope)
        reserve_footer(f,[tools,view,scope])
        self._update_sample_action_buttons()

    def _workspace_sample_click(self, event):
        tree = self._workspace_tree
        if tree.identify_region(event.x, event.y) not in ('tree', 'cell'):
            return
        sid = tree.identify_row(event.y)
        if not sid: return 'break'
        tree.focus_set(); tree.focus(sid)
        if tree.identify_column(event.x) == '#1':
            self._workspace.toggle_sample(sid, self)
        else:
            self._workspace_toggle_row(sid)
        return 'break'

    def _workspace_toggle_row(self, sid):
        tree = self._workspace_tree
        if not sid or not tree.exists(sid): return
        if sid in tree.selection(): tree.selection_remove(sid)
        else: tree.selection_add(sid)
        self._update_sample_action_buttons()

    def _workspace_sample_key(self, event):
        self._workspace_toggle_row(self._workspace_tree.focus())
        return 'break'

    def _workspace_name_focus(self, event=None):
        self._workspace_name_entry.selection_range(0, 'end')

    def _workspace_name_commit(self, event=None):
        self._workspace.rename(self._workspace_name_var.get())
        self._workspace_name_var.set(self._workspace.workspace_name())
        return 'break' if event is not None and event.type == tk.EventType.KeyPress else None

    def _workspace_name_cancel(self, event=None):
        self._workspace_name_var.set(self._workspace.workspace_name())
        return 'break'

    def _build_workspace_actions(self):
        self._section('WORKSPACE')
        parent = self._control_parent
        self._workspace_action_buttons = {}
        row = ttk.Frame(parent); row.pack(fill='x', padx=8, pady=3)
        row.columnconfigure((0, 1), weight=1, uniform='workspace')
        actions = [
            ('New', self._workspace.new, 'Start a new workspace. Unsaved changes prompt you to save first.'),
            ('Open…', self._workspace.open_dialog, 'Open a saved .vflow workspace with its samples, gates and views.'),
            ('Save', self._workspace.save, 'Save this workspace, including sample decisions and gate changes.'),
            ('Save As…', lambda: self._workspace.save(True), 'Save this workspace under another filename.'),
            ('Close', self._workspace.new, 'Close this workspace and start an empty one. Unsaved changes prompt you to save first.'),
        ]
        for index, (text, command, help_text) in enumerate(actions):
            button = tooltip(ttk.Button(row, text=text, command=command), help_text)
            button.grid(row=index//2, column=index%2, sticky='ew', padx=2, pady=2)
            self._workspace_action_buttons[text] = button
        recent = ttk.Menubutton(row, text='Open Recent…')
        menu = tk.Menu(recent, tearoff=False, postcommand=lambda: self._workspace.populate_recent_menu(menu))
        recent.configure(menu=menu); recent.grid(row=2, column=1, sticky='ew', padx=2, pady=2)
        self._workspace_recent_menu = menu
        self._workspace_recent_button = recent
        self._workspace.populate_recent_menu(menu)
        self._workspace_save_state_var = tk.StringVar(self.root)
        status = tooltip(ttk.Label(parent, textvariable=self._workspace_save_state_var, style='Dim.TLabel'),
                         lambda: str(self._workspace.path or 'Choose Save to create a .vflow workspace file.'))
        status.pack(fill='x', padx=8, pady=(0, 3))
        hint = ttk.Label(parent, text='Click the workspace name above the sample list to rename it.', style='Dim.TLabel', wraplength=280)
        hint.pack(fill='x', padx=8, pady=(0, 3))
        from vflow.ui.layout_helpers import wrap_on_resize
        wrap_on_resize(hint)
        self._workspace.title()

    def _update_sample_action_buttons(self):
        selected = self._workspace_tree.selection()
        path = self._workspace.path_for(selected[0]) if len(selected)==1 else None
        for button, enabled in [(self._sample_exclude_button,path in self.loaded_files),
                                (self._sample_restore_button,path in self.excluded_files),
                                (self._sample_show_button,path in self.loaded_files)]:
            button.configure(state='normal' if enabled else 'disabled')

    def _sample_inclusion_action(self, restore):
        selected = self._workspace_tree.selection()
        if len(selected)!=1: return
        path = self._workspace.path_for(selected[0])
        if restore and path in self.excluded_files: self._restore_file(path)
        elif not restore and path in self.loaded_files: self._exclude_file(path)
        self._update_sample_action_buttons()

    def _show_selected_sample(self):
        selected = self._workspace_tree.selection()
        if len(selected)==1: self._workspace.show_sample(self,selected[0])

    def _disclose_section(self, name):
        var,_ = self._sections[name]; var.set(not var.get()); self._toggle_section(name)

    def _workspace_fit_rows(self):
        if not self._workspace_tree.winfo_exists(): return
        ratio=max(.75,float(self.root.tk.call('tk','scaling'))/(96/72))
        columns=('active','state') if self._side_outer.winfo_width()>=480*ratio else ('active',)
        if tuple(self._workspace_tree.cget('displaycolumns')) != columns:
            self._workspace_tree.configure(displaycolumns=columns)
            self._workspace.update_tree(self)

    def _apply_interface_size(self):
        points,width,padding={'Compact':(10,285,3),'Comfortable':(12,340,5),'Large':(14,410,7),'Automatic':(11,330,4)}[self.interface_size_var.get()]
        family=tkfont.nametofont('TkDefaultFont').actual('family')
        for role,size,weight in [('VFlowBody',points,'normal'),('VFlowSmall',max(10,points-1),'normal'),('VFlowSection',points+1,'bold'),('VFlowControl',points,'normal'),('VFlowStatus',max(10,points-1),'normal')]:
            font = self._workspace._fonts[role]
            font.configure(family=family,size=size,weight=weight)
        ratio = max(0.75, float(self.root.tk.call('tk', 'scaling')) / (96/72))
        width = round(width * ratio); padding = round(padding * ratio)
        style=ttk.Style(self.root)
        for name in ('TLabel','TCheckbutton','TRadiobutton','TCombobox','TEntry','TSpinbox','Treeview','Sidebar.TNotebook.Tab'): style.configure(name,font='VFlowBody')
        style.configure('Dim.TLabel',font='VFlowSmall');style.configure('Section.TLabel',font='VFlowSection')
        for name in ('TButton','TMenubutton','Accent.TButton','Gray.TButton','Red.TButton','Green.TButton','Blue2.TButton','Purple.TButton','Teal.TButton','Orange.TButton','DarkBlue.TButton','Cyan.TButton','Olive.TButton'): style.configure(name,font='VFlowControl',padding=padding)
        style.configure('Treeview',rowheight=round((points*2+4)*ratio))
        if hasattr(self, '_workspace_tree'):
            self._workspace_tree.column('state',width=self._workspace._fonts['VFlowBody'].measure('Gate unavailable')+12)
            self._workspace_tree.column('active',width=self._workspace._fonts['VFlowSection'].measure('Active')+20)
            self._workspace_tree.column('#0',minwidth=self._workspace._fonts['VFlowBody'].measure('Sample_01')+8)
        def walk(widget):
            for child in widget.winfo_children():
                try:
                    if 'font' in child.keys(): child.configure(font='VFlowBody')
                except tk.TclError: pass
                walk(child)
        walk(self._side_outer);self._status_lbl.configure(font='VFlowStatus')
        style.configure('SidebarSection.TButton',font='VFlowSection',padding=(7,padding),anchor='w')
        control_width = max(self._workspace._fonts['VFlowControl'].measure(text) for text in ('Show sample','Info / thresholds'))
        outer_bar = self._sidebar_outer_scrollbar.winfo_reqwidth()
        width = max(width,3*(control_width+2*padding+14)+24+outer_bar)
        self._main_pane.paneconfigure(self._side_outer,minsize=width,width=width);self._ui_plot_fontsize=points*ratio
        def resize_labels(widget):
            for child in widget.winfo_children():
                if getattr(child, '_vflow_tab_header', False): child.configure(height=self._workspace._fonts['VFlowBody'].metrics('linespace')+12)
                try:
                    if 'wraplength' in child.keys() and int(child.cget('wraplength')) > 0 and child.winfo_width() < width:
                        child.configure(wraplength=max(160,width-32))
                except (tk.TclError,ValueError): pass
                resize_labels(child)
        resize_labels(self.root)
        self._workspace_fit_rows()
        self._sample_pane_configured()

    def _toggle_section(self,name):
        var,frame=self._sections[name]
        frame._section_header.configure(text=('▾ ' if var.get() else '▸ ')+SECTION_TITLES[name])
        if var.get():
            frame.pack(fill='x',after=frame._section_header)
            if hasattr(self, '_task_notebook') and not self._sidebar_restoring and not self._workspace.restoring:
                self._show_sidebar_section(name)
        else: frame.pack_forget()
        if hasattr(self, '_gate_tools_notebook'): self._sidebar_gate_height()
        if hasattr(self,'_workspace') and not self._workspace.restoring and not getattr(self, '_sidebar_restoring', False):
            self._workspace.mark_dirty()

    def _set_all_sections(self,value):
        restoring = self._sidebar_restoring
        self._sidebar_restoring = True
        try:
            for name,(var,frame) in self._sections.items():var.set(value);self._toggle_section(name)
        finally: self._sidebar_restoring = restoring

    def _workspace_gate_row(self,row,label,gate):
        gid=gate['id'];store=self._workspace.stores[self._workspace_tab_id];sid=self._workspace.current_sid(self)
        badge='This sample' if self.gate_scope_var.get()=='Current sample' and gid in store.sample_overrides.get(sid,{}) else 'All samples'
        if self.gate_scope_var.get() == 'Selected samples': badge = 'Selected samples'
        if self.view_mode_var.get()=='overlay':
            n=sum(gid in m for m in store.sample_overrides.values())
            if n:badge+=f' + {n} overrides'
        elif self.gate_scope_var.get()=='All samples (default)' and gid in store.sample_overrides.get(sid,{}):
            badge += ' (sample override in use)'
        compact = badge.replace('All samples', 'ALL').replace('This sample', 'SAMPLE').replace('Selected samples', 'SELECTED').replace(' overrides', '').replace(' (sample override in use)', ' *')
        tooltip(ttk.Label(row,text=compact,style='Dim.TLabel'), badge).pack(side='right',padx=4)
        def menu(event=None):
            previous = getattr(self,'_workspace_gate_menu',None)
            if previous is not None: previous.destroy()
            m=tk.Menu(self.root,tearoff=False)
            self._workspace_gate_menu = m
            m.add_command(label='Rename…',command=lambda:self._rename_gate(gid))
            m.add_command(label='Copy gate to sample…',command=lambda:self._workspace.copy_dialog(self,gid))
            m.add_command(label='Apply to selected samples…',command=lambda:self._workspace.gate_action(self,'copy',gid,list(self._workspace_tree.selection())))
            m.add_command(label='Apply gate to entire workspace (replace overrides)', command=lambda:self._workspace.gate_action(self,'workspace',gid))
            for text,action in [('Reset this sample to all-samples gate','reset'),("Use this sample's gate for all samples",'promote')]:
                m.add_command(label=text,command=lambda a=action:self._workspace.gate_action(self,a,gid),state='normal' if sid and self.view_mode_var.get()=='cycle' else 'disabled')
            m.add_separator();m.add_command(label='Delete gate',command=lambda:self._del_gate(gid))
            x = event.x_root if event is not None else actions.winfo_rootx()
            y = event.y_root if event is not None else actions.winfo_rooty()+actions.winfo_height()
            try: m.tk_popup(x,y)
            finally: m.grab_release()
        events = ('<Button-3>','<Control-Button-1>') if sys.platform=='darwin' else ('<Button-3>',)
        for event in events:label.bind(event,menu)
        actions = ttk.Button(row,text='Actions…',command=menu)
        actions.pack(side='right',padx=3)
        def start(event):
            self._workspace_drag=(gid,event.x_root,event.y_root)
            self._workspace_drag_selection = self._workspace_tree.selection()
            self._workspace_drag_target = None
        def motion(event):
            drag=getattr(self,'_workspace_drag',None)
            if not drag or abs(event.x_root-drag[1])+abs(event.y_root-drag[2])<5:return
            tree=self._workspace_tree;target=tree.identify_row(event.y_root-tree.winfo_rooty())
            previous=getattr(self,'_workspace_drag_target',None)
            if previous and tree.exists(previous): tree.item(previous,tags=())
            self._workspace_drag_target = None
            if tree.winfo_rootx()<=event.x_root<=tree.winfo_rootx()+tree.winfo_width() and target:
                source=store.resolve_gate(self._workspace.current_sid(self) if self.view_mode_var.get()=='cycle' else None,gid)
                try:
                    if source is None: raise ValueError('Source gate unavailable.')
                    self._workspace.validate_gate_target(self,source,target)
                    valid=True
                except ValueError as exc: valid=False; reason=str(exc)
                if valid:
                    tree.tag_configure('drop_target',background=self.T['select_bg'] if 'select_bg' in self.T else '#3178a8',foreground='white')
                    tree.item(target,tags=('drop_target',));self._workspace_drag_target=target
                    self.status_var.set('Copy '+gate['name']+' to '+self._workspace.document.samples[target].display_name)
                else:self.status_var.set('Cannot copy: '+reason)
                tree.configure(cursor='hand2' if valid else 'X_cursor')
            else: tree.configure(cursor='')
        def drop(event):
            drag=getattr(self,'_workspace_drag',None);self._workspace_drag=None;tree=self._workspace_tree;tree.configure(cursor='')
            previous=getattr(self,'_workspace_drag_target',None)
            if previous and tree.exists(previous): tree.item(previous,tags=())
            self._workspace_drag_target=None
            if not drag or abs(event.x_root-drag[1])+abs(event.y_root-drag[2])<5:return
            if tree.winfo_rootx()<=event.x_root<=tree.winfo_rootx()+tree.winfo_width():
                target=tree.identify_row(event.y_root-tree.winfo_rooty())
                if target:self._workspace.gate_action(self,'copy',gid,[target])
        handle = ttk.Label(row, text='Drag', style='Dim.TLabel', cursor='hand2')
        handle.pack(side='left', padx=4)
        handle.bind('<ButtonPress-1>',start);handle.bind('<B1-Motion>',motion);handle.bind('<ButtonRelease-1>',drop)
        handle._vflow_drag_gate_id = gid
