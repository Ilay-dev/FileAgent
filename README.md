
# File Agent 

A fully local, privacy-first desktop file management agent powered by **CustomTkinter** and local LLMs via **LM Studio**. It allows you to organize directories, restructure folders, merge subfolders, and delete unnecessary files or folders effortlessly using natural language prompts.

---

## Features

- **100% Local & Private:** Runs entirely on your hardware with zero cloud dependencies.
- **Auto-Start & Single Preload:** Automatically launches LM Studio in the background and loads your model into VRAM on startup so it's ready instantly.
- **Dual Scan Modes:**
  - **Level-by-Level:** Scans directories step-by-step (token-efficient, perfect for large drives).
  - **Full Scan:** Comprehensive overview of all files and folders at once.
- **Full File & Folder Operations:** Create, rename, move, and delete individual files or entire folders (including merging and dissolving folder structures).
- **Safe Undo Functionality:** Every destructive action creates a secure backup in a hidden `.agent_backup` directory, allowing you to instantly revert the last run.
- **Sleek Minimalist UI:** Built with CustomTkinter featuring a clean dark-mode interface.

---

## Prerequisites

1. **Python 3.10+** installed on your system.
2. **LM Studio** installed with the model `google/gemma-4-12b-qat` downloaded.
3. Required Python packages:
   ```bash
   pip install customtkinter openai requests

```


## Installation & Running

1. Clone or download this repository.
2. Run the script:
```bash
python Ai_Explorer_sort.py

```



