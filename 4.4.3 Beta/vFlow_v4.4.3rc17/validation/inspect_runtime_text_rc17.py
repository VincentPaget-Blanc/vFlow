import tkinter as tk,json
from tkinter import ttk
r=tk.Tk();b=ttk.Button(r,text='Actions…');b.pack();r.update()
print(json.dumps({'tcl':r.tk.call('info','patchlevel'),'system_encoding':r.tk.call('encoding','system'),'widget_text':b.cget('text'),'matches':b.cget('text')=='Actions…'},ensure_ascii=True))
r.destroy()
