import os
import sys
import time
import subprocess
import signal
import queue
from threading import Thread
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import scriptrunner.lib.utilities as util
from scriptrunner.lib.rendering import ScriptRunnerRendering, CodeEditorWindow
from scriptrunner.lib.run_picker import RunPickerWindow


# ==============================================================================
#                          GUI Interactions
# ==============================================================================


class ScriptRunnerInteractions(ScriptRunnerRendering):

    def __init__(self, initial_folder, script_type="cli"):
        super().__init__(initial_folder)

        self.script_type = script_type
        self.show_all_var.set(script_type == "all")

        # Connect view events to controller logic
        self.chk_show_all.config(command=self.populate_script_list)
        self.set_browse_folder_callback(self.browse_folder)
        self.set_refresh_scripts_callback(self.populate_script_list)

        self.set_browse_interpreter_callback(self.browse_interpreter)
        self.set_check_interpreter_callback(self.check_interpreter)

        self.bind_script_select(self.on_script_select)
        self.bind_script_double_click(self.on_script_double_click)

        self.set_run_scheduler_callback(self.run_scheduler)
        self.set_pause_scheduler_callback(self.pause_scheduler)
        self.set_resume_scheduler_callback(self.resume_scheduler)
        self.set_stop_scheduler_callback(self.stop_scheduler)
        self.set_clear_schedule_callback(self.clear_schedule)
        self.set_add_sleep_callback(self.add_sleep_to_scheduler)

        self.bind_sched_item_select(self.on_sched_item_select)
        self.set_enable_sched_edit_callback(self.enable_sched_edit)
        self.set_save_sched_edit_callback(self.save_sched_edit)
        self.set_delete_sched_task_callback(self.delete_sched_task)

        # Initial population
        self.populate_script_list()
        # Window + signal handling
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        signal.signal(signal.SIGINT, self.on_exit_signal)
        self.check_for_exit_signal()
        self.after(100, self.process_queue)

    def resolve_interpreter(self, script_full_path):
        manual_path = self.interpreter_path.get().strip()
        if manual_path:
            if os.path.exists(manual_path) and os.path.isfile(manual_path):
                return manual_path, "Manual Entry"
        try:
            with open(script_full_path, 'r') as f:
                first_line = f.readline().strip()
                if first_line.startswith("#!"):
                    potential_path = first_line[2:].strip()
                    if os.path.exists(potential_path) and os.path.isfile(
                            potential_path):
                        return potential_path, "Script Shebang (#!)"
        except Exception:
            pass
        return sys.executable, "System Default"

    def check_interpreter(self):
        if not self.current_script:
            messagebox.showwarning("Warning", "Please select a script "
                                              "from the list to check.")
            return
        script_full_path = os.path.join(self.current_folder.get(),
                                        self.current_script)
        interp_path, source = self.resolve_interpreter(script_full_path)
        msg = f"Interpreter Source: {source}\n\nPath used:\n{interp_path}"
        messagebox.showinfo("Interpreter Check", msg)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.current_folder.get())
        if folder:
            self.current_folder.set(folder)
            self.current_script = None
            self.entries = {}
            self.script_inputs = {}
            self.scheduled_tasks = []
            self.refresh_sched_tree()
            for widget in self.sched_scroll_frame.winfo_children():
                widget.destroy()
            self.btn_sched_edit.config(state=tk.DISABLED)
            self.btn_sched_del.config(state=tk.DISABLED)
            self.btn_sched_save.config(state=tk.DISABLED)
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.populate_script_list()
            util.update_config(last_folder=folder)

    def browse_interpreter(self):
        filename = filedialog.askopenfilename(title="Select Python Interpreter",
                                              initialdir="/")
        if filename:
            self.interpreter_path.set(filename)

    def populate_script_list(self):
        self.script_list.delete(0, tk.END)
        folder = self.current_folder.get()
        files = util.find_possible_scripts(folder)
        show_all = self.show_all_var.get()
        for script in files:
            if self.script_type != "cli" or show_all:
                self.script_list.insert(tk.END, script)
            else:
                if util.get_script_arguments(os.path.join(folder, script))[0]:
                    self.script_list.insert(tk.END, script)

    def on_script_select(self, event):
        selection = self.script_list.curselection()
        if not selection:
            return
        script_name = self.script_list.get(selection[0])
        if self.current_script:
            self.save_current_inputs()
        self.current_script = script_name
        self.display_arguments(script_name)

    def on_script_double_click(self, event):
        selection = self.script_list.curselection()
        if not selection:
            return
        script_name = self.script_list.get(selection[0])
        full_path = os.path.join(self.current_folder.get(), script_name)

        if self.editor_window and self.editor_window.winfo_exists():
            self.editor_window.add_file(full_path)
        else:
            self.editor_window = CodeEditorWindow(self,
                                                  self.populate_script_list)
            self.editor_window.add_file(full_path)

    def display_arguments(self, script_name):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        full_path = os.path.join(self.current_folder.get(), script_name)
        arguments, has_argparse = util.get_script_arguments(full_path)
        self.entries = {}

        self.scrollable_frame.grid_columnconfigure(0, weight=0)
        self.scrollable_frame.grid_columnconfigure(1, weight=0)
        self.scrollable_frame.grid_columnconfigure(2, weight=0)
        self.scrollable_frame.grid_columnconfigure(3, weight=1)

        ttk.Label(self.scrollable_frame, text=f"{script_name}",
                  font=(util.FONT_FAMILY, util.FONT_SIZE + 1),
                  foreground="#0055aa").grid(row=0, column=0, columnspan=4,
                                             pady=0, sticky="nw", padx=5)
        row = 1
        if has_argparse:
            for (raw_flag, clean_name, help_text, arg_type, required,
                 default_value) in arguments:

                ttk.Label(self.scrollable_frame, text=raw_flag,
                          width=15, anchor="w",
                          font=(util.FONT_FAMILY,
                                util.PARA_FONT_SIZE)).grid(row=row, column=0,
                                                           sticky="w", padx=2,
                                                           pady=2)

                ttk.Label(self.scrollable_frame, text=f"[{arg_type.__name__}]",
                          width=6, anchor="w", foreground="#0055aa",
                          font=(util.FONT_FAMILY,
                                util.PARA_FONT_SIZE)).grid(row=row, column=1,
                                                           sticky="w", padx=2,
                                                           pady=2)
                entry = ttk.Entry(self.scrollable_frame, width=15)
                entry.grid(row=row, column=2, sticky="w", padx=2, pady=2)

                if script_name in self.script_inputs and clean_name in \
                        self.script_inputs[script_name]:
                    entry.insert(0, self.script_inputs[script_name][clean_name])
                elif default_value is not None:
                    entry.insert(0, str(default_value))

                help_parent = self.scrollable_frame
                run_field = util.run_argument_field(clean_name)
                if run_field:
                    help_parent = ttk.Frame(self.scrollable_frame)
                    help_parent.grid(row=row, column=3, sticky="w")
                    ttk.Button(help_parent, text="Pick run...",
                               style="Small.TButton",
                               command=lambda e=entry, f=run_field,
                               s=script_name: self.pick_run(s, e, f)).pack(
                        side=tk.LEFT, padx=(5, 0))
                help_label = ttk.Label(help_parent, text=help_text,
                                       justify="left", foreground="#555",
                                       font=(util.FONT_FAMILY,
                                             util.PARA_FONT_SIZE))
                if run_field:
                    help_label.pack(side=tk.LEFT, padx=5)
                else:
                    help_label.grid(row=row, column=3, sticky="w", padx=5,
                                    pady=2)
                # Use clean_name as the key in dictionaries
                self.entries[clean_name] = (entry, arg_type)
                row += 1
        else:
            msg = "This script has no declared argparse arguments"
            ttk.Label(self.scrollable_frame, text=msg,
                      width=50, anchor="w",
                      font=(util.FONT_FAMILY,
                            util.PARA_FONT_SIZE + 1)).grid(row=1, column=0,
                                                           sticky="w",
                                                           padx=2, pady=2)

        btn_frame = ttk.Frame(self.scrollable_frame)
        btn_frame.grid(row=row + 1, column=0, columnspan=4, pady=10,
                       sticky="ew")
        ttk.Button(btn_frame, text="Run now", width=10,
                   command=lambda: self.run_script_direct(script_name)).pack(
            side=tk.LEFT, padx=(5, 0))
        ttk.Button(btn_frame, text="Stop run", width=10,
                   command=self.stop_script).pack(side=tk.LEFT, padx=5)

        frame_add = ttk.Frame(btn_frame)
        frame_add.pack(side=tk.RIGHT, padx=5)
        ttk.Label(frame_add, text="Iteration:").pack(side=tk.LEFT)
        self.entry_sched_iter = ttk.Entry(frame_add, width=3)
        self.entry_sched_iter.insert(0, "1")
        self.entry_sched_iter.pack(side=tk.LEFT, padx=5)
        ttk.Label(frame_add, text="Position:").pack(side=tk.LEFT)
        self.entry_sched_index = ttk.Entry(frame_add, width=3)
        self.entry_sched_index.insert(0, "-1")
        self.entry_sched_index.pack(side=tk.LEFT, padx=0)
        ttk.Button(frame_add, text="Add to schedule", width=15,
                   command=self.schedule_script).pack(side=tk.LEFT, padx=(5, 0))

    def pick_run(self, script_name, entry, run_field):
        script_full_path = os.path.join(self.current_folder.get(), script_name)
        interpreter, _ = self.resolve_interpreter(script_full_path)

        def fill(run):
            value = run.get(run_field)
            if value is None:
                messagebox.showwarning(
                    "Run has no value",
                    f"The selected run has no {run_field}.", parent=self)
                return
            entry.delete(0, tk.END)
            entry.insert(0, str(value))

        RunPickerWindow(self, interpreter, fill,
                        title=f"Pick a run for {script_name}")

    def save_current_inputs(self):
        if not self.current_script:
            return
        if self.current_script not in self.script_inputs:
            self.script_inputs[self.current_script] = {}
        for clean_name, (entry, _) in self.entries.items():
            self.script_inputs[self.current_script][clean_name] = entry.get()

    def refresh_sched_tree(self):
        self.sched_tree.delete(*self.sched_tree.get_children())
        for i, task in enumerate(self.scheduled_tasks):
            name_display = task['name'] if task['type'] == 'script'\
                else f"Sleep: {task['params']['duration']} sec"
            iter_val = task.get('iterations', 1)
            self.sched_tree.insert("", "end", iid=i, values=(
                i + 1, iter_val, name_display, task['status']))

    def _insert_task_at_position(self, task, position_text):
        """
        Insert a task into the internal scheduled_tasks
        """
        try:
            user_input = int(position_text)
        except Exception:
            user_input = -1

        if user_input == -1:
            # Append to the end
            self.scheduled_tasks.append(task)
        else:
            internal_idx = user_input - 1
            if internal_idx < 0:
                internal_idx = 0
            if internal_idx >= len(self.scheduled_tasks):
                self.scheduled_tasks.append(task)
            else:
                self.scheduled_tasks.insert(internal_idx, task)

    def schedule_script(self):
        if not self.current_script:
            return
        current_params = {}
        for flag, (entry, _) in self.entries.items():
            current_params[flag] = entry.get()
        try:
            iterations = int(self.entry_sched_iter.get())
            if iterations < 1:
                iterations = 1
        except:
            iterations = 1

        task = {'type': 'script', 'name': self.current_script,
                'params': current_params, 'status': util.STATUS_PENDING,
                'iterations': iterations}
        self._insert_task_at_position(task, self.entry_sched_index.get())
        self.refresh_sched_tree()
        # If scheduler is hidden, expand it
        if not self.scheduler_visible:
            self.toggle_scheduler()

    def add_sleep_to_scheduler(self):
        try:
            dur = float(self.sleep_duration_var.get())
            task = {'type': 'sleep', 'name': 'Sleep',
                    'params': {'duration': dur}, 'status': util.STATUS_PENDING,
                    'iterations': 1}
            self._insert_task_at_position(task, self.sleep_position_var.get())
            self.refresh_sched_tree()
            # If scheduler is hidden, expand it
            if not self.scheduler_visible:
                self.toggle_scheduler()
        except ValueError:
            messagebox.showerror("Error", "Invalid input")

    def clear_schedule(self):
        if self.scheduler_running:
            messagebox.showwarning("Warning",
                                   "Cannot clear queue while running.")
            return
        self.scheduled_tasks = []
        self.refresh_sched_tree()

        for widget in self.sched_scroll_frame.winfo_children():
            widget.destroy()
        self.btn_sched_edit.config(state=tk.DISABLED)
        self.btn_sched_del.config(state=tk.DISABLED)
        self.btn_sched_save.config(state=tk.DISABLED)

    def on_sched_item_select(self, event):
        selected_item = self.sched_tree.selection()
        if not selected_item:
            self.btn_sched_edit.config(state=tk.DISABLED)
            self.btn_sched_del.config(state=tk.DISABLED)
            return

        idx = int(selected_item[0])
        task = self.scheduled_tasks[idx]
        self.display_sched_details(task)

        self.btn_sched_edit.config(state=tk.NORMAL)
        self.btn_sched_del.config(state=tk.NORMAL)
        self.btn_sched_save.config(state=tk.DISABLED)

    def display_sched_details(self, task):
        for widget in self.sched_scroll_frame.winfo_children():
            widget.destroy()
        self.scheduler_entries = {}

        self.sched_scroll_frame.grid_columnconfigure(1, weight=1)

        if task['type'] == 'script':
            ttk.Label(self.sched_scroll_frame, text=f"{task['name']}",
                      font=(util.FONT_FAMILY, util.FONT_SIZE),
                      foreground="#0055aa").grid(row=0, column=0, columnspan=2,
                                                 sticky="w", pady=0, padx=5)
            full_path = os.path.join(self.current_folder.get(), task['name'])
            arguments, has_args = util.get_script_arguments(full_path)
            if has_args:
                row = 1
                for raw_flag, clean_name, help_text, arg_type, required, \
                        default_val in arguments:
                    ttk.Label(self.sched_scroll_frame, text=raw_flag,
                              font=(util.FONT_FAMILY,
                                    util.FONT_SIZE - 2)).grid(row=row, column=0,
                                                              sticky="w",
                                                              padx=5, pady=2)
                    entry = ttk.Entry(self.sched_scroll_frame, width=20)
                    entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
                    val = task['params'].get(clean_name, "")
                    entry.insert(0, val)
                    entry.config(state='readonly')
                    self.scheduler_entries[clean_name] = entry
                    row += 1

        elif task['type'] == 'sleep':
            ttk.Label(self.sched_scroll_frame, text="Sleep",
                      font=(util.FONT_FAMILY, util.FONT_SIZE),
                      foreground="#0055aa").grid(row=0, column=0, columnspan=2,
                                                 sticky="w", pady=0, padx=5)
            ttk.Label(self.sched_scroll_frame, text="Duration (seconds):").grid(
                row=1, column=0, sticky="w", padx=5, pady=5)
            entry = ttk.Entry(self.sched_scroll_frame, width=20)
            entry.insert(0, str(task['params']['duration']))
            entry.config(state='readonly')
            entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
            self.scheduler_entries['duration'] = entry

    def enable_sched_edit(self):
        for entry in self.scheduler_entries.values():
            entry.config(state='normal')
        self.btn_sched_save.config(state=tk.NORMAL)
        self.btn_sched_edit.config(state=tk.DISABLED)

    def save_sched_edit(self):
        selected = self.sched_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        for key, entry in self.scheduler_entries.items():
            self.scheduled_tasks[idx]['params'][key] = entry.get()
            entry.config(state='readonly')
        task = self.scheduled_tasks[idx]
        name_display = task['name'] if task['type'] == 'script'\
            else f"Sleep: {task['params']['duration']} sec"
        iter_val = task.get('iterations', 1)
        self.sched_tree.item(selected, values=(
            idx + 1, iter_val, name_display, task['status']))

        self.btn_sched_save.config(state=tk.DISABLED)
        self.btn_sched_edit.config(state=tk.NORMAL)

    def delete_sched_task(self):
        selected = self.sched_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        del self.scheduled_tasks[idx]
        self.refresh_sched_tree()
        for widget in self.sched_scroll_frame.winfo_children():
            widget.destroy()
        self.btn_sched_edit.config(state=tk.DISABLED)
        self.btn_sched_del.config(state=tk.DISABLED)

    # ---------------------------------------------------------
    # Logic: Execution Engine
    # ---------------------------------------------------------

    def run_scheduler(self):
        if self.scheduler_running:
            return
        if not self.scheduled_tasks:
            messagebox.showinfo("Info", "Queue is empty")
            return

        self.scheduler_running = True
        self.scheduler_paused = False
        self.shutdown_flag = False
        self.btn_sched_run.config(state=tk.DISABLED)
        self.btn_sched_pause.config(state=tk.NORMAL)
        self.btn_sched_stop.config(state=tk.NORMAL)
        Thread(target=self.scheduler_loop, daemon=True).start()

    def pause_scheduler(self):
        self.scheduler_paused = True
        self.btn_sched_pause.config(state=tk.DISABLED)
        self.btn_sched_resume.config(state=tk.NORMAL)
        self.log_to_console(">>> Scheduler Paused...", "info")

    def resume_scheduler(self):
        self.scheduler_paused = False
        self.btn_sched_pause.config(state=tk.NORMAL)
        self.btn_sched_resume.config(state=tk.DISABLED)
        self.log_to_console(">>> Scheduler Resumed...", "info")

    def stop_scheduler(self):
        self.shutdown_flag = True
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.scheduler_running = False
        self.btn_sched_run.config(state=tk.NORMAL)
        self.btn_sched_pause.config(state=tk.DISABLED)
        self.btn_sched_resume.config(state=tk.DISABLED)
        self.btn_sched_stop.config(state=tk.DISABLED)
        self.log_to_console(">>> Scheduler Stopped by User.", "stderr")

    def scheduler_loop(self):
        # 1. Get global iterations
        try:
            queue_iters = int(self.entry_queue_iter.get())
            if queue_iters < 1:
                queue_iters = 1
        except ValueError:
            queue_iters = 1
        # 2. Auto-reset check
        if self.scheduled_tasks:
            all_completed = all(
                t['status'] in [util.STATUS_DONE, util.STATUS_FAILED] for t in
                self.scheduled_tasks)
            if all_completed:
                self.log_to_console(
                    ">>> Queue is finished. Resetting for new run...", "info")
                for i, task in enumerate(self.scheduled_tasks):
                    task['status'] = util.STATUS_PENDING
                    self.update_tree_status(i, util.STATUS_PENDING)
        # 3. Outer Loop: cycle the entire queue
        for q_run in range(queue_iters):
            if self.shutdown_flag:
                break
            if q_run > 0:
                self.log_to_console(f"--- Restarting Queue (Iteration "
                                    f"{q_run + 1}/{queue_iters}) ---", "info")
                for i, task in enumerate(self.scheduled_tasks):
                    task['status'] = util.STATUS_PENDING
                    self.update_tree_status(i, util.STATUS_PENDING)
            elif queue_iters > 1:
                self.log_to_console(f"--- Starting Queue (Iteration "
                                    f"1/{queue_iters}) ---", "info")
            # 4. Inner Loop: Execute tasks
            for i, task in enumerate(self.scheduled_tasks):
                if self.shutdown_flag:
                    break
                while self.scheduler_paused:
                    if self.shutdown_flag:
                        break
                    time.sleep(0.2)
                # Skip tasks that are already done
                if task['status'] == util.STATUS_DONE:
                    continue
                total_runs = task.get('iterations', 1)
                for run_idx in range(total_runs):
                    if self.shutdown_flag:
                        break
                    while self.scheduler_paused:
                        if self.shutdown_flag:
                            break
                        time.sleep(0.2)
                    status_txt = util.STATUS_RUNNING if total_runs == 1\
                        else f"Run {run_idx + 1}/{total_runs}"
                    task['status'] = status_txt
                    self.update_tree_status(i, status_txt)
                    if task['type'] == 'sleep':
                        try:
                            dur = float(task['params']['duration'])
                            self.log_to_console(
                                f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
                                f"\n Sleeping for {dur} seconds...\n"
                                f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n",
                                "info")
                            elapsed = 0
                            while elapsed < dur:
                                if self.shutdown_flag:
                                    break
                                while self.scheduler_paused:
                                    if self.shutdown_flag:
                                        break
                                    time.sleep(0.2)
                                time.sleep(0.1)
                                elapsed += 0.1
                        except:
                            task['status'] = util.STATUS_FAILED
                            self.update_tree_status(i, util.STATUS_FAILED)
                            break

                    elif task['type'] == 'script':
                        self.task_output_complete.clear()
                        success = self.execute_queue_script(task)
                        if not self.shutdown_flag:
                            self.task_output_complete.wait()
                        if not success:
                            task['status'] = util.STATUS_FAILED
                            self.update_tree_status(i, util.STATUS_FAILED)
                            break
                # After inner task completion
                if (not self.shutdown_flag
                        and task['status'] != util.STATUS_FAILED):
                    task['status'] = util.STATUS_DONE
                    self.update_tree_status(i, util.STATUS_DONE)
            # If any task failed in the inner loop, break the outer loop
            any_failed = any(
                t['status'] == util.STATUS_FAILED for t in self.scheduled_tasks)
            if any_failed:
                break

        self.scheduler_running = False
        self.msg_queue.put(("UI_RESET", None))

    def update_tree_status(self, index, status):
        self.msg_queue.put(("TREE_UPDATE", (index, status)))

    def execute_queue_script(self, task):
        script_path = os.path.join(self.current_folder.get(), task['name'])
        interpreter, _ = self.resolve_interpreter(script_path)
        command = [interpreter, script_path]
        command.insert(1, "-u")
        script_args_def, has_args = util.get_script_arguments(script_path)
        if has_args:
            arg_map = {clean_name: arg_type for
                       (_, clean_name, _, arg_type, _, _) in script_args_def}
            self.msg_queue.put(("STATUS_BAR", f"Running: {task['name']}..."))

            for clean_name, val in task['params'].items():
                if not val:
                    continue
                try:
                    if clean_name in arg_map:
                        _ = arg_map[clean_name](val)
                except Exception:
                    self.log_to_console(f"Error: Invalid param "
                                        f"{clean_name}={val}", "stderr")
                    self.msg_queue.put(("STATUS_BAR", ""))
                    return False
                raw_flag = None
                for rf, cn, _, _, _, _ in script_args_def:
                    if cn == clean_name:
                        raw_flag = rf
                        break
                if raw_flag is None:
                    raw_flag = f"--{clean_name}"
                command.append(raw_flag)
                command.append(val)

        full_cmd_str = " ".join(command)
        start_time = time.ctime()

        self.msg_queue.put(("info", f"\n{'=' * 60}"))
        self.msg_queue.put(("info", f"STARTED AT: {start_time}"))
        self.msg_queue.put(("info", f"COMMAND:\n{full_cmd_str}"))
        self.msg_queue.put(("info", f"{'=' * 60}\n"))

        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True,
                                            bufsize=1)
            for line in iter(self.process.stdout.readline, ''):
                self.msg_queue.put(("stdout", line))

            self.process.stdout.close()
            self.process.wait()

            end_time = time.ctime()
            self.msg_queue.put(("info", f"\n{'=' * 60}"))
            self.msg_queue.put(("info", f"COMMAND:\n{full_cmd_str}"))
            self.msg_queue.put(("info", f"FINISHED AT: {end_time}"))
            self.msg_queue.put(("info", f"{'=' * 60}\n"))
            self.msg_queue.put(("TASK_DONE_SIGNAL", None))
            if self.shutdown_flag:
                return False
            return (self.process.returncode == 0)
        except Exception as e:
            self.msg_queue.put(("stderr", f"Scheduler Error: {e}"))
            self.msg_queue.put(("STATUS_BAR", ""))
            return False

    def run_script_direct(self, script_name):
        if self.process and self.process.poll() is None:
            messagebox.showerror("Error", "Process running")
            return
        current_params = {}
        for flag, (entry, _) in self.entries.items():
            current_params[flag] = entry.get()
        task = {'type': 'script', 'name': script_name, 'params': current_params}
        Thread(target=self.execute_queue_script, args=(task,),
               daemon=True).start()

    def stop_script(self):
        if self.process:
            self.process.terminate()
            self.log_to_console("\n!!! Stopped by User !!!\n", "stderr")

    def process_queue(self):
        try:
            while True:
                msg_type, msg = self.msg_queue.get_nowait()
                if msg_type in ["stdout", "stderr", "info"]:
                    self.log_to_console(msg, msg_type)
                elif msg_type == "TREE_UPDATE":
                    idx, status = msg
                    if self.sched_tree.exists(idx):
                        self.sched_tree.set(idx, "Status", status)
                elif msg_type == "UI_RESET":
                    self.btn_sched_run.config(state=tk.NORMAL)
                    self.btn_sched_pause.config(state=tk.DISABLED)
                    self.btn_sched_resume.config(state=tk.DISABLED)
                    self.btn_sched_stop.config(state=tk.DISABLED)
                    self.log_to_console("\n=== Scheduler Queue Finished ===\n",
                                        "info")
                elif msg_type == "TASK_DONE_SIGNAL":
                    self.task_output_complete.set()
                elif msg_type == "STATUS_BAR":
                    if hasattr(self, 'status_bar'):
                        self.status_bar.config(text=str(msg))
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

    def on_exit_signal(self, signum, frame):
        self.stop_script()
        self.on_exit()

    def check_for_exit_signal(self):
        self.after(200, self.check_for_exit_signal)

    def on_exit(self):
        self.shutdown_flag = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        print("\n************")
        print("Exit the app")
        print("************\n")
        try:
            self.destroy()
        except Exception:
            pass
