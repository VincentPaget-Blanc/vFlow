"""Capture the real task sidebar with untouched frozen benchmark data."""
import json, os, sys, tempfile
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager

OUTPUT = ROOT.parent / 'vFlow_v4.4.3rc5_Task_Tabs_Screenshots'
OUTPUT.mkdir(exist_ok=True)
errors = []
messagebox.showerror = lambda *a, **k: errors.append(str(a))
messagebox.showinfo = messagebox.showwarning = lambda *a, **k: None
root = tk.Tk()
tkfont.nametofont('TkDefaultFont').configure(family='DejaVu Sans')
root.report_callback_exception = lambda *a: errors.append(str(a))
manager = FlowTabManager(root)
root.geometry('1440x1100+0+0')
app = manager._apps[0]
owner = app._workspace
with tempfile.TemporaryDirectory() as td:
    owner.state_dir = Path(td) / 'state'
    owner.recent_path = Path(td) / 'recent.json'
    files = [ROOT / 'benchmark_extensions/frozen_v1/cytometry' / (name + '.csv')
             for name in ('Control_01', 'Control_02', 'Treatment_01', 'Treatment_02')]
    app._load_paths([str(p) for p in files])
    app.interface_size_var.set('Comfortable')
    app._apply_interface_size()
    if app._theme_name != 'light': app.toggle_theme()
    app._main_pane.sash_place(0, 570, 0)
    app.x_var.set('FSC-A'); app.y_var.set('SSC-A'); app.apply_axes()
    app.x_scale_var.set('linear'); app.y_scale_var.set('linear')
    app.plot_type_var.set('Dot Plot'); app.refresh_plot(); root.update()
    app._add_gate(auto_type='rectangle')
    gate = app._sel_gate()
    definition = json.loads((ROOT / 'benchmark_extensions/frozen_v1/references/benchmark_gate_definitions.json').read_text())['gates'][0]
    gate.update({k: definition[k] for k in ('x0', 'x1', 'y0', 'y1')})
    gate['name'] = definition['id']; gate['applied'] = True
    app._bind_gate_context(gate); app._rebuild_gate_manager(); app._rebuild_thresh_panel()
    app._recompute_all_gate_stats(); app.refresh_plot(); root.update()
    expected = {'Control_01.csv': 7273, 'Control_02.csv': 7020,
                'Treatment_01.csv': 7081, 'Treatment_02.csv': 7058}
    counts = {Path(p).name: int(((df['FSC-A'] >= gate['x0']) & (df['FSC-A'] <= gate['x1']) &
                               (df['SSC-A'] >= gate['y0']) & (df['SSC-A'] <= gate['y1'])).sum())
              for p, df in app.loaded_files.items()}
    assert counts == expected, counts
    assert {Path(p).name: item['stats']['IN']['count']
            for p, item in app.gate_stats[gate['id']].items()} == expected
    assert len(owner.document.samples) == 4
    assert owner.save(path=str(Path(td) / 'Benchmark.vflow'))
    records = []
    views = [('01_Data', 'Data', None), ('02_Plot', 'Plot', None),
             ('03_Gates_Manual', 'Gates', 'GATING'),
             ('04_Gates_Automatic', 'Gates', 'AUTO-GATE'),
             ('05_Analysis', 'Analysis', None)]
    for name, task, tool in views:
        app._select_sidebar_task(task)
        if tool: app._gate_tools_notebook.select(app._gate_tool_pages[tool])
        page = app._task_pages[task]
        page['canvas'].yview_moveto(0); root.update()
        x, y = app._side_outer.winfo_rootx(), app._side_outer.winfo_rooty()
        w, h = app._side_outer.winfo_width(), app._side_outer.winfo_height()
        path = OUTPUT / (name + '.png')
        ImageGrab.grab(bbox=(x, y, x+w, y+h), xdisplay=os.environ['DISPLAY']).save(path)
        records.append({'file': path.name, 'task': task, 'gate_tool': tool,
                        'pixels': [w, h], 'viewport_height': page['canvas'].winfo_height(),
                        'content_height': page['content'].winfo_reqheight(),
                        'scroll_pixels': max(0, page['content'].winfo_reqheight()-page['canvas'].winfo_height()),
                        'yview': page['canvas'].yview()})
    app._select_sidebar_task('Plot'); root.update()
    ImageGrab.grab(bbox=(root.winfo_rootx(), root.winfo_rooty(),
                        root.winfo_rootx()+root.winfo_width(), root.winfo_rooty()+root.winfo_height()),
                   xdisplay=os.environ['DISPLAY']).save(OUTPUT / '06_Full_App.png')
    metadata = {'sources': [p.name for p in files],
                'events': {Path(p).name: len(df) for p, df in app.loaded_files.items()},
                'gate_counts': counts, 'gate_total': sum(counts.values()),
                'screenshots': records, 'capture_font': tkfont.nametofont('TkDefaultFont').actual(),
                'errors': errors}
    (ROOT / 'validation/sidebar_capture_rc5.json').write_text(json.dumps(metadata, indent=2)+'\n')
    (OUTPUT / 'README.md').write_text(
        '# vFlow 4.4.3rc5 — benchmark-loaded task tabs\n\n'
        'Unaltered native Linux/Tk screenshots of the implemented Data, Plot, Gates (Manual and Automatic), '
        'and Analysis tabs, plus the full app. Four frozen cytometry CSVs are loaded and active: Control_01, '
        'Control_02, Treatment_01 and Treatment_02; 12,000 events each, 48,000 total. The benchmark '
        'G_LYMPH_RECT gate contains 28,432 events. The mixed-condition screenshot session does not run a '
        'within-condition statistical audit.\n\n'
        'Light theme, Comfortable interface size and a 570-pixel sidebar; the ordinary default sections '
        'are used. Advanced settings remain available in their collapsible sections and Settings menu. '
        'The pinned samples, single View Mode selector and gate-target status remain visible on every '
        'task. macOS/Windows appearance may differ. The native X11 capture uses DejaVu Sans glyphs; '
        'the resolved font and viewport measurements are recorded in validation/sidebar_capture_rc5.json '
        'in the app bundle. Automatic gates require a small 38-pixel scroll in this session; the other '
        'ordinary task views fit within the viewport.\n')
    assert not errors, errors
owner.dispose(); root.destroy()
print(json.dumps(metadata, indent=2))
