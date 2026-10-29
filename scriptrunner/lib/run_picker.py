import queue
import subprocess
import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk, messagebox
import scriptrunner.lib.utilities as util


# ==============================================================================
#                           Tiled Run Picker
# ==============================================================================


class RunPickerWindow(tk.Toplevel):
    """
    Find a Bluesky run in a Tiled catalog and hand it to ``on_pick``.

    The search runs ``tiled_runs.py`` with ``interpreter`` (the one the
    selected script would run with), so Tiled only needs to be installed
    there. ``on_pick`` is called with the chosen run's dict
    (uid, scan_id, time, plan_name, data_session).
    """

    COLUMNS = ("time", "scan_id", "plan_name", "data_session", "uid")
    HEADINGS = ("Time", "Scan ID", "Plan", "Proposal", "UID")

    def __init__(self, parent, interpreter, on_pick, title="Pick a run"):
        super().__init__(parent)
        self.title(title)
        self.interpreter = interpreter
        self.on_pick = on_pick
        self.runs = []
        self.results = queue.Queue()
        self.searching = False

        config = util.load_config() or {}
        today = date.today().isoformat()
        self.uri = tk.StringVar(
            value=config.get("tiled_uri", util.TILED_URI_DEFAULT))
        self.catalog = tk.StringVar(value=config.get("tiled_catalog", ""))
        self.plan_name = tk.StringVar(value=config.get("tiled_plan_name", ""))
        self.data_session = tk.StringVar(
            value=config.get("tiled_data_session", ""))
        self.since = tk.StringVar(value=today)
        self.until = tk.StringVar(value=today)
        self.status = tk.StringVar(value=f"Interpreter: {interpreter}")

        form = ttk.Frame(self, padding=5)
        form.pack(side=tk.TOP, fill=tk.X)
        fields = [("Tiled URI:", self.uri, 40), ("Catalog:", self.catalog, 15),
                  ("Plan name:", self.plan_name, 15),
                  ("Proposal:", self.data_session, 15),
                  ("From (YYYY-MM-DD):", self.since, 12),
                  ("To:", self.until, 12)]
        for i, (label, var, width) in enumerate(fields):
            row, col = divmod(i, 2)
            ttk.Label(form, text=label).grid(row=row, column=2 * col,
                                             sticky="w", padx=2, pady=2)
            entry = ttk.Entry(form, textvariable=var, width=width)
            entry.grid(row=row, column=2 * col + 1, sticky="w", padx=2,
                       pady=2)
            entry.bind("<Return>", lambda e: self.search())
        self.btn_search = ttk.Button(form, text="Search", command=self.search)
        self.btn_search.grid(row=3, column=0, sticky="w", padx=2, pady=4)

        table = ttk.Frame(self, padding=5)
        table.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(table, columns=self.COLUMNS, show="headings",
                                 selectmode="browse", height=15)
        widths = (150, 70, 130, 110, 290)
        for col, heading, width in zip(self.COLUMNS, self.HEADINGS, widths):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor="w")
        vsb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda e: self.use_selected())

        bottom = ttk.Frame(self, padding=5)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(bottom, text="Use selected run",
                   command=self.use_selected).pack(side=tk.RIGHT, padx=2)
        ttk.Button(bottom, text="Cancel",
                   command=self.destroy).pack(side=tk.RIGHT, padx=2)
        ttk.Label(bottom, textvariable=self.status,
                  foreground="#555").pack(side=tk.LEFT, padx=2)

        self.transient(parent)
        self.after(100, self.poll_results)

    def search(self):
        if self.searching:
            return
        command = util.build_run_search_command(
            self.interpreter, self.uri.get().strip(),
            self.catalog.get().strip(), self.since.get().strip(),
            self.until.get().strip(), self.plan_name.get().strip(),
            self.data_session.get().strip())
        util.update_config(tiled_uri=self.uri.get().strip(),
                           tiled_catalog=self.catalog.get().strip(),
                           tiled_plan_name=self.plan_name.get().strip(),
                           tiled_data_session=self.data_session.get().strip())
        self.searching = True
        self.btn_search.config(state=tk.DISABLED)
        self.status.set("Searching...")
        threading.Thread(target=self._run_search, args=(command,),
                         daemon=True).start()

    def _run_search(self, command):
        # stdin is closed so a Tiled login prompt fails at once instead of
        # waiting for input nobody can type.
        try:
            proc = subprocess.run(command, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True,
                                  timeout=120)
            runs, error = util.parse_run_search_output(proc.stdout)
            if error and proc.stderr.strip():
                error += "\n\n" + proc.stderr.strip()[-2000:]
        except subprocess.TimeoutExpired:
            runs, error = [], "The run search took longer than 120 s."
        except Exception as e:
            runs, error = [], f"{type(e).__name__}: {e}"
        self.results.put((runs, error))

    def poll_results(self):
        if not self.winfo_exists():
            return
        try:
            runs, error = self.results.get_nowait()
        except queue.Empty:
            self.after(100, self.poll_results)
            return
        self.searching = False
        self.btn_search.config(state=tk.NORMAL)
        if error:
            self.status.set("Search failed")
            messagebox.showerror("Run search failed", error, parent=self)
        else:
            self.show_runs(runs)
        self.after(100, self.poll_results)

    def show_runs(self, runs):
        self.runs = runs
        self.tree.delete(*self.tree.get_children())
        for i, run in enumerate(runs):
            when = datetime.fromtimestamp(run.get("time") or 0)
            values = (when.strftime("%Y-%m-%d %H:%M:%S"),
                      "" if run.get("scan_id") is None else run["scan_id"],
                      run.get("plan_name") or "",
                      run.get("data_session") or "", run.get("uid") or "")
            self.tree.insert("", tk.END, iid=str(i), values=values)
        self.status.set(f"{len(runs)} run(s) found")

    def use_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No run selected",
                                   "Select a run in the list first.",
                                   parent=self)
            return
        self.on_pick(self.runs[int(selection[0])])
        self.destroy()
