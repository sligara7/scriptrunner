import os
import time
import queue
import threading
import tkinter as tk
from pathlib import Path
import importlib.resources
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkFont
import scriptrunner.lib.utilities as util

try:
    from idlelib.colorizer import ColorDelegator
    from idlelib.percolator import Percolator
except ImportError:
    ColorDelegator = None
    Percolator = None


# ==============================================================================
#                           Editor Panel
# ==============================================================================


def get_icon_path():
    with importlib.resources.path("scriptrunner.assets",
                                  "ScriptRunner_icon.png") as icon:
        return str(icon)


class EditorPanel(ttk.Frame):

    def __init__(self, parent, file_path, refresh_callback, close_callback):
        super().__init__(parent)
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.directory = os.path.dirname(file_path)
        self.refresh_callback = refresh_callback
        self.close_callback = close_callback
        # Toolbar
        toolbar = ttk.Frame(self, padding=2)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        self.btn_edit = ttk.Button(toolbar, text="Edit",
                                   command=self.enable_editing,
                                   style="Small.TButton")
        self.btn_edit.pack(side=tk.LEFT, padx=2)
        self.btn_save = ttk.Button(toolbar, text="Save (Ctrl+S)",
                                   command=self.save_file, state=tk.DISABLED,
                                   style="Small.TButton")
        self.btn_save.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y,
                                                       padx=5)

        ttk.Label(toolbar, text="Name:",
                  font=(util.FONT_FAMILY, 8)).pack(side=tk.LEFT, padx=2)
        self.entry_new_name = ttk.Entry(toolbar,
                                        width=12, font=(util.FONT_FAMILY, 9))
        self.entry_new_name.pack(side=tk.LEFT, padx=2)

        self.btn_copy = ttk.Button(toolbar, text="Copy", command=self.copy_file,
                                   style="Small.TButton")
        self.btn_copy.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y,
                                                       padx=5)

        self.btn_delete = ttk.Button(toolbar, text="Delete",
                                     command=self.delete_file,
                                     style="Small.TButton")
        self.btn_delete.pack(side=tk.LEFT, padx=2)
        # Close "X" Button
        self.btn_close = ttk.Button(toolbar, text="X", width=2,
                                    command=lambda: self.close_callback(self),
                                    style="Small.TButton")
        self.btn_close.pack(side=tk.RIGHT, padx=2)
        self.lbl_info = ttk.Label(toolbar, text=self.filename,
                                  foreground="blue",
                                  font=(util.FONT_FAMILY, 9, "bold"))
        self.lbl_info.pack(side=tk.RIGHT, padx=5)
        # Main Content
        content_frame = ttk.Frame(self)
        content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.vsb = ttk.Scrollbar(content_frame, orient="vertical")
        self.hsb = ttk.Scrollbar(content_frame, orient="horizontal")
        # Line Numbers
        self.line_numbers = tk.Text(content_frame, width=4, padx=4, takefocus=0,
                                    border=0, background=util.LINE_NUM_BG,
                                    foreground=util.LINE_NUM_FG,
                                    state='disabled',
                                    font=("Consolas", util.CODE_FONT_SIZE))
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        # Text Area
        self.text_area = tk.Text(content_frame, wrap="none",
                                 font=("Consolas", util.CODE_FONT_SIZE),
                                 undo=True, yscrollcommand=self.vsb.set,
                                 xscrollcommand=self.hsb.set)
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Configure Scrollbars
        self.vsb.config(command=self._on_vsb_scroll)
        self.hsb.config(command=self.text_area.xview)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.hsb.pack(side=tk.BOTTOM, fill=tk.X)
        # Events
        self.text_area.bind("<Configure>", lambda e: self.after_idle(
            self._update_line_numbers))
        self.text_area.bind("<KeyPress>", lambda e: self.after_idle(
            self._update_line_numbers))
        self.text_area.bind("<Button-1>", lambda e: self.after_idle(
            self._update_line_numbers))
        self.text_area.bind("<MouseWheel>", lambda e: self.after_idle(
            self._update_line_numbers))
        self.text_area.bind("<Control-s>", self.save_file)
        self.text_area.bind("<Tab>", self._insert_spaces)
        self.text_area.bind("<Shift-Tab>", self._remove_indent)
        # Syntax Highlighting
        if ColorDelegator and Percolator:
            self.percolator = Percolator(self.text_area)
            self.color_delegator = ColorDelegator()
            self.percolator.insertfilter(self.color_delegator)

        self.load_content()

    def _on_vsb_scroll(self, *args):
        self.text_area.yview(*args)
        self.line_numbers.yview(*args)

    def _update_line_numbers(self, event=None):
        lines = int(self.text_area.index('end-1c').split('.')[0])
        line_content = "\n".join(str(i) for i in range(1, lines + 1))
        self.line_numbers.config(state='normal')
        self.line_numbers.delete('1.0', tk.END)
        self.line_numbers.insert('1.0', line_content)
        self.line_numbers.config(state='disabled')
        self.line_numbers.yview_moveto(self.text_area.yview()[0])

    def _insert_spaces(self, event):
        """Replace Tab key with 4 spaces"""
        self.text_area.insert("insert", " " * 4)
        return "break"

    def _remove_indent(self, event):
        """Handle Shift+Tab to remove 4 spaces"""
        line_start = self.text_area.index("insert linestart")
        line_end = self.text_area.index("insert lineend")
        line = self.text_area.get(line_start, line_end)

        if line.startswith(" " * 4):
            self.text_area.delete(line_start, f"{line_start}+4c")

        return "break"

    def load_content(self):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.delete('1.0', tk.END)
        try:
            with open(self.file_path, 'r') as f:
                content = f.read().replace("\t", " " * 4)
            self.text_area.insert('1.0', content)
        except Exception as e:
            self.text_area.insert('1.0', f"# Error: {e}")

        self.after_idle(self._update_line_numbers)
        self.text_area.config(state=tk.DISABLED)
        self.reset_buttons()

    def reset_buttons(self):
        self.btn_edit.config(state=tk.NORMAL)
        self.btn_save.config(state=tk.DISABLED)
        self.btn_copy.config(state=tk.NORMAL)
        self.btn_delete.config(state=tk.NORMAL)

    def enable_editing(self):
        self.text_area.config(state=tk.NORMAL)
        self.btn_edit.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.NORMAL)
        self.text_area.focus_set()

    def save_file(self, event=None):
        if str(self.btn_save['state']) == 'disabled':
            return
        content = self.text_area.get('1.0', 'end-1c')
        try:
            with open(self.file_path, 'w') as f:
                f.write(content)
            messagebox.showinfo("Success", "File saved.", parent=self)
            if self.refresh_callback:
                self.refresh_callback()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def copy_file(self):
        new_name = self.entry_new_name.get().strip()
        if not new_name:
            base, ext = os.path.splitext(self.filename)
            c = 1
            while True:
                cand = f"{base}_copy_{c}{ext}"
                if not os.path.exists(os.path.join(self.directory, cand)):
                    new_name = cand
                    break
                c += 1
        else:
            if not new_name.endswith(".py"):
                new_name += ".py"
        new_path = os.path.join(self.directory, new_name)
        if os.path.exists(new_path):
            messagebox.showerror("Error", "File exists.", parent=self)
            return
        try:
            content = self.text_area.get('1.0', 'end-1c')
            with open(new_path, 'w') as f:
                f.write(content)
            if self.refresh_callback:
                self.refresh_callback()
            # Reload this pane
            self.file_path = new_path
            self.filename = new_name
            self.directory = os.path.dirname(new_path)
            self.lbl_info.config(text=self.filename)
            self.entry_new_name.delete(0, tk.END)
            messagebox.showinfo("Success", f"Copied to {new_name}", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def delete_file(self):
        if messagebox.askyesno("Confirm", f"Delete '{self.filename}'?",
                               parent=self):
            try:
                os.remove(self.file_path)
                if self.refresh_callback:
                    self.refresh_callback()
                self.close_callback(self)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)


# ==============================================================================
#                          Code Editor Manager Window
# ==============================================================================

class CodeEditorWindow(tk.Toplevel):
    def __init__(self, parent, refresh_callback):
        super().__init__(parent)
        self.refresh_callback = refresh_callback
        self.title("Script Editor")

        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        width = int(self.screen_width * util.TEXT_WIN_RATIO)
        height = int(self.screen_height * util.TEXT_WIN_RATIO)
        x = (self.screen_width - width) // 2
        y = (self.screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        self.panes = []
        self.lift_window()

    def add_file(self, file_path):
        # Check existing
        for pane in self.panes:
            if pane.file_path == file_path:
                return
        # Split View Logic
        if len(self.panes) >= 2:
            old_pane = self.panes.pop()
            old_pane.destroy()
        new_pane = EditorPanel(self.paned, file_path, self.refresh_callback,
                               self.close_pane)
        self.paned.add(new_pane, weight=1)
        self.panes.append(new_pane)
        self.lift_window()

    def close_pane(self, pane_obj):
        if pane_obj in self.panes:
            self.panes.remove(pane_obj)
            pane_obj.destroy()

        if not self.panes:
            self.destroy()

    def lift_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()


# ==============================================================================
#                          Main GUI rendering (View)
# ==============================================================================


class ScriptRunnerRendering(tk.Tk):
    def __init__(self, initial_folder):
        super().__init__()

        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.dpi = self.winfo_fpixels("1i")
        try:
            icon_path = get_icon_path()
            if icon_path and Path(icon_path).exists():
                icon = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, icon)
        except (tk.TclError, TypeError):
            pass

        self.current_folder = tk.StringVar(
            value=os.path.abspath(initial_folder))
        self.interpreter_path = tk.StringVar(value="")

        self.log_to_file_var = tk.BooleanVar(value=False)
        self.log_file_path_var = tk.StringVar(value="")
        self.show_all_var = tk.BooleanVar(value=False)

        self.process = None
        self.msg_queue = queue.Queue()
        self.shutdown_flag = False

        self.script_inputs = {}
        self.current_script = None
        self.entries = {}
        self.entry_sched_index = None
        self.entry_sched_iter = None

        self.scheduled_tasks = []
        self.scheduler_entries = {}
        self.scheduler_running = False
        self.scheduler_paused = False
        self.scheduler_visible = False

        self.sleep_duration_var = tk.StringVar(value="5.0")
        self.sleep_position_var = tk.StringVar(value="-1")
        self.task_output_complete = threading.Event()

        self.editor_window = None
        self.setup_window()
        self.setup_styles()
        self.create_layout()

    def setup_window(self):
        width, height, x_offset, y_offset = self.define_window_geometry(
            util.MAIN_WIN_RATIO)
        self.geometry(f"{width}x{height}+{x_offset}+{y_offset}")
        self.title("Script Runner")
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=6)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=0)
        self.grid_rowconfigure(5, weight=1)
        self.grid_rowconfigure(6, weight=0)
        self.grid_columnconfigure(0, weight=1)

    def define_window_geometry(self, ratio):
        width = int(self.screen_width * ratio)
        height = int(self.screen_height * ratio)
        x_offset = (self.screen_width - width) // 2
        y_offset = (self.screen_height - height) // 2
        return width, height, x_offset, y_offset

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use(util.TTK_THEME)
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(family=util.FONT_FAMILY, size=util.FONT_SIZE,
                               weight=util.FONT_WEIGHT)
        self.option_add("*Font", default_font)
        self.style.configure("TButton", padding=5)
        self.style.configure("TEntry", padding=5)
        self.style.configure("TLabelframe", padding=5)
        self.style.configure("TLabelframe.Label",
                             font=(util.FONT_FAMILY, util.FONT_SIZE),
                             foreground="#333")
        self.style.configure("Path.TLabel", foreground=util.PATH_COLOR,
                             font=(util.FONT_FAMILY, util.FONT_SIZE, "italic"))
        self.style.configure("Treeview", rowheight=25)
        self.style.configure("Toggle.TButton",
                             font=(util.FONT_FAMILY, 11))
        self.style.configure("Small.TButton", padding=2,
                             font=(util.FONT_FAMILY, 9))

    def _setup_canvas_scroll(self, canvas):

        def _on_mousewheel(event):
            if self.tk.call('tk', 'windowingsystem') == 'win32':
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif self.tk.call('tk', 'windowingsystem') == 'x11':
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * event.delta), "units")

        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)

    def create_layout(self):
        self.create_folder_bar()
        self.create_interpreter_bar()
        self.create_middle_panel()
        self.create_scheduler_toggle()
        self.create_scheduler_panel()
        self.create_output_panel()
        self.create_status_bar()
        self.sched_frame.grid_remove()

    def create_folder_bar(self):
        frame = ttk.Frame(self, padding=0, relief="groove", borderwidth=1)
        frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        frame.grid_columnconfigure(1, weight=1)

        ttk.Label(frame, text="Base folder path:",
                  font=(util.FONT_FAMILY, util.FONT_SIZE)).grid(row=0, column=0,
                                                                padx=5, pady=0)
        ttk.Label(frame, textvariable=self.current_folder, style="Path.TLabel",
                  anchor="w").grid(row=0, column=1, sticky="ew", padx=5, pady=0)

        self.chk_show_all = ttk.Checkbutton(frame, text="Show all .py",
                                            variable=self.show_all_var)
        self.chk_show_all.grid(row=0, column=2, padx=5, pady=5)

        self.btn_select_base = ttk.Button(frame, text="Select base")
        self.btn_select_base.grid(row=0, column=3, padx=5, pady=5)

        self.btn_refresh_scripts = ttk.Button(frame, text="Refresh")
        self.btn_refresh_scripts.grid(row=0, column=4, padx=(0, 5), pady=5)

    def create_interpreter_bar(self):
        frame = ttk.Frame(self, padding=0, relief="groove", borderwidth=1)
        frame.grid(row=1, column=0, sticky="ew", padx=5, pady=0)
        frame.grid_columnconfigure(1, weight=1)

        ttk.Label(frame, text="Python environment path:",
                  font=(util.FONT_FAMILY, util.FONT_SIZE)).grid(row=0, column=0,
                                                                padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.interpreter_path).grid(row=0,
                                                                  column=1,
                                                                  sticky="ew",
                                                                  padx=5,
                                                                  pady=5)
        self.btn_browse_interpreter = ttk.Button(frame, text="Select")
        self.btn_browse_interpreter.grid(row=0, column=2, padx=0, pady=5)

        self.btn_check_interpreter = ttk.Button(frame, text="Check")
        self.btn_check_interpreter.grid(row=0, column=3, padx=5, pady=5)

    def create_middle_panel(self):
        mid_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        mid_pane.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        left_frame = ttk.LabelFrame(mid_pane, text="   Available scripts",
                                    padding=0)
        mid_pane.add(left_frame, weight=1)

        self.script_list = tk.Listbox(left_frame, selectmode=tk.SINGLE, bd=0,
                                      highlightthickness=1, relief="solid",
                                      selectbackground=util.LISTBOX_SELECT_BG,
                                      selectforeground=util.LISTBOX_SELECT_FG,
                                      activestyle="none",
                                      font=(util.FONT_FAMILY, util.FONT_SIZE))
        self.script_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5,
                              pady=5)

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical",
                                  command=self.script_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        self.script_list.config(yscrollcommand=scrollbar.set)

        right_frame = ttk.LabelFrame(mid_pane, text="   Script parameters",
                                     padding=0)
        mid_pane.add(right_frame, weight=3)

        bg_color = self.style.lookup("TFrame", "background")

        self.canvas = tk.Canvas(right_frame, highlightthickness=0, bg=bg_color)
        self.scrollbar_args = ttk.Scrollbar(right_frame, orient="vertical",
                                            command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, padding=0)

        self.scrollable_frame.bind("<Configure>",
                                   lambda e: self.canvas.configure(
                                       scrollregion=self.canvas.bbox("all")))
        self.canvas_window = \
            self.canvas.create_window((0, 0),
                                      window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar_args.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5,
                         pady=5)
        self.scrollbar_args.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self.canvas_window,
                                                          width=e.width))
        self._setup_canvas_scroll(self.canvas)

    def create_scheduler_toggle(self):
        toggle_frame = ttk.Frame(self, padding=0)
        toggle_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=0)

        ttk.Separator(toggle_frame, orient="horizontal").pack(side=tk.LEFT,
                                                              fill=tk.X,
                                                              expand=True)
        self.btn_toggle_sched = ttk.Button(toggle_frame,
                                           text="▼ Show scheduler",
                                           style="Toggle.TButton",
                                           command=self.toggle_scheduler,
                                           width=20)
        self.btn_toggle_sched.pack(side=tk.LEFT, padx=10)
        ttk.Separator(toggle_frame, orient="horizontal").pack(side=tk.LEFT,
                                                              fill=tk.X,
                                                              expand=True)

    def toggle_scheduler(self):
        if self.scheduler_visible:
            self.sched_frame.grid_remove()
            self.btn_toggle_sched.config(text="▼ Show scheduler")
            self.scheduler_visible = False
            self.grid_rowconfigure(4, weight=0)
            self.grid_rowconfigure(5, weight=2)
        else:
            self.sched_frame.grid()
            self.btn_toggle_sched.config(text="▲ Hide scheduler")
            self.scheduler_visible = True
            self.grid_rowconfigure(4, weight=1)
            self.grid_rowconfigure(5, weight=1)

    def create_scheduler_panel(self):
        self.sched_frame = ttk.LabelFrame(self, text="Scheduler", padding=0)
        self.sched_frame.grid(row=4, column=0, sticky="nsew", padx=5,
                              pady=(5, 0))

        control_frame = ttk.Frame(self.sched_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        col_queue = ttk.Frame(control_frame)
        col_queue.pack(side=tk.LEFT)
        # Global queue iteration input
        ttk.Label(col_queue, text="Iteration:").pack(side=tk.LEFT, padx=(0, 2),
                                                     pady=5)
        self.entry_queue_iter = ttk.Entry(col_queue, width=3)
        self.entry_queue_iter.insert(0, "1")
        self.entry_queue_iter.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.btn_sched_run = ttk.Button(col_queue, text="Run queue")
        self.btn_sched_run.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.btn_sched_pause = ttk.Button(col_queue, text="Pause",
                                          state=tk.DISABLED)
        self.btn_sched_pause.pack(side=tk.LEFT, padx=0, pady=5)

        self.btn_sched_resume = ttk.Button(col_queue, text="Resume",
                                           state=tk.DISABLED)
        self.btn_sched_resume.pack(side=tk.LEFT, padx=5, pady=5)

        self.btn_sched_stop = ttk.Button(col_queue, text="Stop",
                                         state=tk.DISABLED)
        self.btn_sched_stop.pack(side=tk.LEFT, padx=0, pady=5)

        self.btn_sched_clear = ttk.Button(col_queue, text="Clear")
        self.btn_sched_clear.pack(side=tk.LEFT, padx=(15, 5), pady=5)

        ttk.Separator(control_frame, orient='vertical').pack(side=tk.LEFT,
                                                             fill=tk.Y, padx=10,
                                                             pady=5)

        col_sleep = ttk.Frame(control_frame)
        col_sleep.pack(side=tk.LEFT)

        ttk.Label(col_sleep, text="Sleep(s):").pack(side=tk.LEFT, padx=2,
                                                    pady=5)
        ttk.Entry(col_sleep, textvariable=self.sleep_duration_var,
                  width=6).pack(side=tk.LEFT, padx=2, pady=5)

        ttk.Label(col_sleep, text="Position:").pack(side=tk.LEFT, padx=(10, 2),
                                                    pady=5)
        ttk.Entry(col_sleep, textvariable=self.sleep_position_var,
                  width=4).pack(side=tk.LEFT, padx=2, pady=5)

        self.btn_add_sleep = ttk.Button(col_sleep, text="Add sleep")
        self.btn_add_sleep.pack(side=tk.LEFT, padx=5, pady=5)

        sched_pane = ttk.PanedWindow(self.sched_frame, orient=tk.HORIZONTAL)
        sched_pane.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        table_frame = ttk.Frame(sched_pane)
        sched_pane.add(table_frame, weight=2)
        cols = ("ID", "Iter", "Name/Details", "Status")
        self.sched_tree = ttk.Treeview(table_frame, columns=cols,
                                       show="headings", selectmode="browse",
                                       height=5)
        for c in cols:
            self.sched_tree.heading(c, text=c)

        self.sched_tree.column("ID", width=30, stretch=False)
        self.sched_tree.column("Iter", width=40, stretch=False)
        self.sched_tree.column("Name/Details", width=250)
        self.sched_tree.column("Status", width=70)

        sb_sched = ttk.Scrollbar(table_frame, orient="vertical",
                                 command=self.sched_tree.yview)
        self.sched_tree.configure(yscroll=sb_sched.set)

        self.sched_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_sched.pack(side=tk.RIGHT, fill=tk.Y)

        self.sched_details_frame = ttk.Frame(sched_pane, padding=0)
        sched_pane.add(self.sched_details_frame, weight=3)

        self.sched_btn_container = ttk.Frame(self.sched_details_frame,
                                             padding=0)
        self.sched_btn_container.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_sched_edit = ttk.Button(self.sched_btn_container, text="Edit",
                                         state=tk.DISABLED)
        self.btn_sched_edit.pack(side=tk.LEFT, fill=tk.X, expand=True,
                                 padx=(0, 5), pady=(5, 0))

        self.btn_sched_save = ttk.Button(self.sched_btn_container, text="Save",
                                         state=tk.DISABLED)
        self.btn_sched_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=0,
                                 pady=(5, 0))

        self.btn_sched_del = ttk.Button(self.sched_btn_container, text="Delete",
                                        state=tk.DISABLED)
        self.btn_sched_del.pack(side=tk.LEFT, fill=tk.X, expand=True,
                                padx=(5, 0), pady=(5, 0))

        self.sched_param_container = ttk.LabelFrame(self.sched_details_frame,
                                                    text="Task Details",
                                                    padding=0)
        self.sched_param_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        bg_color = self.style.lookup("TFrame", "background")
        self.sched_canvas = tk.Canvas(self.sched_param_container,
                                      highlightthickness=0, height=100,
                                      bg=bg_color)
        self.sched_sb = ttk.Scrollbar(self.sched_param_container,
                                      orient="vertical",
                                      command=self.sched_canvas.yview)
        self.sched_scroll_frame = ttk.Frame(self.sched_canvas)

        self.sched_scroll_frame.bind("<Configure>",
                                     lambda e: self.sched_canvas.configure(
                                         scrollregion=self.sched_canvas.bbox(
                                             "all")))
        self.sched_win_id = (
            self.sched_canvas.create_window((0, 0),
                                            window=self.sched_scroll_frame,
                                            anchor="nw"))
        self.sched_canvas.configure(yscrollcommand=self.sched_sb.set)

        self.sched_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.sched_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sched_canvas.bind("<Configure>",
                               lambda e: self.sched_canvas.itemconfig(
                                   self.sched_win_id, width=e.width))
        self._setup_canvas_scroll(self.sched_canvas)

    def update_log_widgets_state(self):
        """Updates the state/visibility of log widgets based on the checkbox."""
        is_checked = self.log_to_file_var.get()
        state = tk.NORMAL if is_checked else tk.DISABLED
        self.btn_browse_log.config(state=state)
        path_text = self.log_file_path_var.get()
        if not is_checked and not path_text:
            self.lbl_log_path.config(text="", style="TLabel")
        elif not is_checked:
            self.lbl_log_path.config(style="TLabel", foreground="#888")
        else:
            self.lbl_log_path.config(style="Path.TLabel",
                                     foreground=util.PATH_COLOR)

    def toggle_log_path_prompt(self):
        """Called when the log checkbox is toggled."""
        self.update_log_widgets_state()
        if self.log_to_file_var.get():
            if not self.log_file_path_var.get():
                self.browse_log_file()

    def browse_log_file(self):
        """Opens a file dialog to select the log file path."""
        initial_file = self.log_file_path_var.get()
        initial_dir = os.path.dirname(
            initial_file) if initial_file else os.path.expanduser("~")
        initial_name = os.path.basename(
            initial_file) if initial_file else "script_runner_log.txt"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialdir=initial_dir,
            initialfile=initial_name,
            title="Select log file to save console output",
            filetypes=(("Text files", "*.txt"), ("All files", "*.*")))

        if filepath:
            self.log_file_path_var.set(os.path.abspath(filepath))
            if not self.log_to_file_var.get():
                self.log_to_file_var.set(True)
            self.update_log_widgets_state()
            self.log_to_console(f">>> Console logging enabled to: "
                                f"{self.log_file_path_var.get()}", "info")
        elif self.log_to_file_var.get() and not self.log_file_path_var.get():
            self.log_to_file_var.set(False)
            self.update_log_widgets_state()

    def log_to_console(self, text, tag="stdout"):
        """
        Logs text to the GUI console and optionally saves it to a log file.
        """
        if tag == "STATUS_BAR":
            return

        if not text.endswith("\n"):
            text += "\n"
        # 1. Log to GUI Console
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text, tag)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
        # 2. Optionally Log to File
        if self.log_to_file_var.get():
            log_path = self.log_file_path_var.get()
            if log_path:
                try:
                    # Write in append mode
                    with open(log_path, 'a') as f:
                        # Prepend timestamp for file logging
                        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S] ")
                        f.write(timestamp + text)
                except Exception as e:
                    print(f"ERROR writing to log file {log_path}: {e}")
                    # Disable logging to file if it fails
                    self.log_to_file_var.set(False)
                    self.update_log_widgets_state()
                    # Log error to console only
                    self.output_text.config(state=tk.NORMAL)
                    self.output_text.insert(tk.END,
                                            f"\n!!! LOG FILE ERROR: Disabled "
                                            f"logging due to: {e} !!!\n",
                                            "stderr")
                    self.output_text.see(tk.END)
                    self.output_text.config(state=tk.DISABLED)

    def create_output_panel(self):
        out_frame = ttk.Frame(self, padding=0)
        out_frame.grid(row=5, column=0, sticky="nsew", padx=5, pady=5)
        out_frame.grid_columnconfigure(1, weight=1)
        out_frame.grid_rowconfigure(1, weight=1)

        log_options_frame = ttk.Frame(out_frame, padding=(5, 5, 0, 2))
        log_options_frame.grid(row=0, column=0, columnspan=3, sticky="ew")
        log_options_frame.grid_columnconfigure(1, weight=1)

        self.log_checkbox = ttk.Checkbutton(log_options_frame,
                                            text="Console output |"
                                                 " Save to log file: ",
                                            variable=self.log_to_file_var,
                                            command=self.toggle_log_path_prompt)
        self.log_checkbox.grid(row=0, column=0, sticky="w", padx=0, pady=2)
        self.lbl_log_path = ttk.Label(log_options_frame,
                                      textvariable=self.log_file_path_var,
                                      style="Path.TLabel", anchor="w",
                                      text="No log file selected")
        self.lbl_log_path.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.btn_browse_log = ttk.Button(log_options_frame, text="Select File",
                                         command=self.browse_log_file,
                                         style="Small.TButton")
        self.btn_browse_log.grid(row=0, column=2, padx=0, pady=2)
        self.update_log_widgets_state()
        text_container = ttk.Frame(out_frame)
        text_container.grid(row=1, column=0, columnspan=3, sticky="nsew",
                            padx=5, pady=(2, 5))
        text_container.grid_columnconfigure(0, weight=1)
        text_container.grid_rowconfigure(0, weight=1)

        self.output_text = tk.Text(text_container, height=12, state=tk.DISABLED,
                                   bg=util.BG_COLOR_OUTPUT,
                                   fg=util.FG_COLOR_OUTPUT,
                                   font=("Courier New", util.CONSOLE_FONT),
                                   bd=0, highlightthickness=0)
        self.output_text.grid(row=0, column=0, sticky="nsew")

        scrollbar_out = ttk.Scrollbar(text_container, orient="vertical",
                                      command=self.output_text.yview)
        scrollbar_out.grid(row=0, column=1, sticky="ns")
        self.output_text.config(yscrollcommand=scrollbar_out.set)

        self.output_text.tag_config("stdout", foreground="black")
        self.output_text.tag_config("stderr", foreground="red")
        self.output_text.tag_config("info", foreground="blue")

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self, textvariable=self.status_var,
                                    relief=tk.SUNKEN, anchor="w",
                                    padding=(5, 2))
        self.status_bar.grid(row=6, column=0, sticky="ew", padx=5, pady=(0, 5))

    def set_browse_folder_callback(self, callback):
        self.btn_select_base.config(command=callback)

    def set_refresh_scripts_callback(self, callback):
        self.btn_refresh_scripts.config(command=callback)

    def set_browse_interpreter_callback(self, callback):
        self.btn_browse_interpreter.config(command=callback)

    def set_check_interpreter_callback(self, callback):
        self.btn_check_interpreter.config(command=callback)

    def bind_script_select(self, callback):
        self.script_list.bind("<<ListboxSelect>>", callback)

    def bind_script_double_click(self, callback):
        self.script_list.bind("<Double-Button-1>", callback)

    def set_run_scheduler_callback(self, callback):
        self.btn_sched_run.config(command=callback)

    def set_pause_scheduler_callback(self, callback):
        self.btn_sched_pause.config(command=callback)

    def set_resume_scheduler_callback(self, callback):
        self.btn_sched_resume.config(command=callback)

    def set_stop_scheduler_callback(self, callback):
        self.btn_sched_stop.config(command=callback)

    def set_clear_schedule_callback(self, callback):
        self.btn_sched_clear.config(command=callback)

    def set_add_sleep_callback(self, callback):
        self.btn_add_sleep.config(command=callback)

    def bind_sched_item_select(self, callback):
        self.sched_tree.bind("<<TreeviewSelect>>", callback)

    def set_enable_sched_edit_callback(self, callback):
        self.btn_sched_edit.config(command=callback)

    def set_save_sched_edit_callback(self, callback):
        self.btn_sched_save.config(command=callback)

    def set_delete_sched_task_callback(self, callback):
        self.btn_sched_del.config(command=callback)
