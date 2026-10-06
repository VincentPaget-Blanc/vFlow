"""Keep secondary analysis windows attached to their originating workspace/tab."""
def session_is_current(window):
    app=window.app;owner=getattr(app,'_workspace',None)
    if owner is None:return True
    return (not owner._disposed and owner.document is getattr(window,'_workspace_document',owner.document)
        and owner.apps.get(app._workspace_tab_id) is app)

def check_session(window):
    if session_is_current(window):return True
    from tkinter import messagebox
    messagebox.showerror('Analysis window','Workspace or population tab changed; reopen this analysis window.',parent=window)
    return False
