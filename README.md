# ScriptRunner
![ScriptRunner_Logo](https://github.com/algotom/scriptrunner/raw/main/ScriptRunner_icon.png)

---

*GUI software for rendering arguments of CLI Python scripts and scheduling runs*

---

Motivation
==========

In synchrotron facilities where Linux OS is the main platform, running data acquisition, 
data processing, or beamline operation is often done through Python command-line interfaces. 
This can be a hassle for users who are not familiar with Linux or command-line interfaces.

The idea of this GUI is to render the arguments of CLI scripts, making it easier for users 
to run Python scripts through a graphical user interface. Beyond that, ScriptRunner allows 
scheduling script runs in a flexible way, enabling users to run a group of scripts with ease. 
For example, a list of data acquisition or data processing scripts can be scheduled to run 
different acquisition modes or different data-processing pipelines in order.

To make it even more convenient for users, ScriptRunner allows modifying and changing Python 
scripts without the need for another script editor like VS Code, Gedit, or Vim.


Features
========

- _**Automatic GUI generation for CLI Python scripts**_:

    ScriptRunner parses arguments from ArgParse-based CLI scripts and automatically renders them as user-friendly GUI input fields.

    ![Fig1](https://github.com/algotom/scriptrunner/raw/main/figs/fig1.png)

- **_Run individual scripts or schedule multi-script workflows_**:

    Execute a single script on demand, or create a scheduled sequence of multiple scripts. This enables automated data acquisition, processing pipelines, or batch operations without manual intervention.
    
    ![Fig2](https://github.com/algotom/scriptrunner/raw/main/figs/fig2.png)

- _**Built-in script editor with side-by-side comparison**_:

    Edit Python scripts directly inside the application, no need for external editors like VS Code or Vim. Compare two scripts side-by-side to track modifications or validate parameter changes.

    ![Fig3](https://github.com/algotom/scriptrunner/raw/main/figs/fig3.png)

- **_Console logging and export_**:

    View real-time console output for each script and save logs to a file for debugging, documentation, or reproducibility.

    ![Fig3](https://github.com/algotom/scriptrunner/raw/main/figs/fig4.png)

- **_Pick a Bluesky run from a Tiled catalog (optional)_**:

    An argument that names a run (`--uid`, `--run_uid`, `--scan_uid`, `--run` or `--scan_id`) gets a "Pick run..." button.
    It opens a run browser that searches a [Tiled](https://blueskyproject.io/tiled/) catalog by date, plan name and proposal
    (`data_session`). Choosing a run fills in its uid or scan id. The search runs with the script's own interpreter, so
    `tiled` only needs to be installed in the environment the script uses, not in ScriptRunner's. The script then reads
    the run from Tiled itself.


Installation
============

Install [Miniconda, Anaconda or Miniforge](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html), then 
open a Linux terminal or the Miniconda/Anaconda PowerShell prompt and use the following commands
for installation.

Using pip:
```commandline
pip install scriptrunner-gui
```
Using conda:
```commandline
conda install -c conda-forge scriptrunner-gui
```
Once installed, launching ScriptRunner with
```commandline
scriptrunner
```
Using -h for option usage
```commandline
scriptrunner -h
```
---
Installing from source:
- If using a single file:
    + Copy the file *scriptrunner.py*. Install python.
    + Run:
        ```commandline
        python scriptrunner.py
        ```
- If using setup.py
    + Create conda environment
      ```commandline
      conda create -n scriptrunner python=3.11
      conda activate scriptrunner
      ``` 
    + Clone the source (git needs to be installed)
      ```commandline
      git clone https://github.com/algotom/scriptrunner.git
      ```
    + Navigate to the cloned directory (having setup.py file)
      ```commandline
      pip install .
      ```
Usage
=====

- Select a base folder containing Python scripts.

- Clicking a script will show the arguments of that script in the right panel.

- Double-clicking a script will open the Editor panel window.

- Clicking "Run Now" will run the current script.

- Select a script and use "Add to schedule" to schedule multiple scripts. There is an option to add sleep time between scripts.

- Enable/disable saving console output to a file using the checkbox.

- For a run argument (e.g. `--uid`), click "Pick run...", set the Tiled URI and catalog path (e.g. `hex/raw`), then
  search and double-click a run. The URI, catalog, plan name and proposal are remembered for next time. If the server
  needs a login, log in once from a terminal with the script's interpreter, so a token is cached.

- By default, ScriptRunner picks and displays ArgParse-based scripts. However, users can choose to display all Python scripts by running:
  ```commandline
  scriptrunner -t "all"
  ```
  or tick the box "Show all .py"