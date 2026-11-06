import os
import shutil
import json
import pathlib
import threading
import requests
import time
import subprocess
import re
import ctypes  # Used to force minimize/hide external window handles on Windows
import customtkinter as ctk
from tkinter import filedialog, messagebox
from openai import OpenAI

# Minimalist Dark Mode Theme Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class AIFileAgentApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI File Agent")
        self.geometry("1050x720")
        self.minsize(900, 600)
        
        # Pure black background for minimalist design
        self.configure(fg_color="#000000")

        # OpenAI Client configured for local LM Studio instance
        self.client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
        self.models_url = "http://localhost:1234/v1/models"

        self.selected_directory = ""
        self.messages = []
        self.last_run_actions = []
        self.current_mode = "Level-by-Level"  # Default mode

        self.create_widgets()

        # Preload LM Studio and model in background thread on startup
        threading.Thread(target=self.ensure_lm_studio_running, daemon=True).start()

    def create_widgets(self):
        # --- 1. TOP BAR (Folder Selection, Mode Switch & Step Limit) ---
        top_frame = ctk.CTkFrame(self, fg_color="#111111", corner_radius=6, border_width=1, border_color="#333333")
        top_frame.pack(fill="x", padx=20, pady=(20, 10))

        self.dir_btn = ctk.CTkButton(
            top_frame, text="Select Folder", 
            fg_color="#ffffff", text_color="#000000", hover_color="#dddddd", 
            font=("Arial", 12, "bold"), corner_radius=4, command=self.browse_folder
        )
        self.dir_btn.pack(side="left", padx=15, pady=12)

        self.dir_label = ctk.CTkLabel(top_frame, text="No folder selected", text_color="#ffffff", anchor="w", font=("Arial", 11, "bold"))
        self.dir_label.pack(side="left", padx=5, fill="x", expand=True)

        # High-contrast Mode Switch
        lbl_mode = ctk.CTkLabel(top_frame, text="Mode:", text_color="#cccccc", font=("Arial", 11, "bold"))
        lbl_mode.pack(side="left", padx=(10, 5))

        mode_btn_frame = ctk.CTkFrame(top_frame, fg_color="#1a1a1a", corner_radius=4, border_width=1, border_color="#444444")
        mode_btn_frame.pack(side="left", padx=5, pady=10)

        self.btn_mode_lvl = ctk.CTkButton(
            mode_btn_frame, text="Level-by-Level", width=110, height=26,
            fg_color="#ffffff", text_color="#000000", hover_color="#dddddd",
            font=("Arial", 11, "bold"), command=lambda: self.set_mode("Level-by-Level")
        )
        self.btn_mode_lvl.pack(side="left", padx=2, pady=2)

        self.btn_mode_full = ctk.CTkButton(
            mode_btn_frame, text="Full Scan", width=90, height=26,
            fg_color="#1a1a1a", text_color="#ffffff", hover_color="#333333",
            font=("Arial", 11), command=lambda: self.set_mode("Full Scan (All)")
        )
        self.btn_mode_full.pack(side="left", padx=2, pady=2)

        # Step Limit Configuration
        lbl_steps = ctk.CTkLabel(top_frame, text="Max Steps:", text_color="#cccccc", font=("Arial", 11, "bold"))
        lbl_steps.pack(side="left", padx=(15, 5))
        
        self.steps_entry = ctk.CTkEntry(top_frame, width=55, fg_color="#1a1a1a", text_color="#ffffff", border_color="#444444", justify="center", font=("Arial", 11, "bold"))
        self.steps_entry.insert(0, "100")  # Default max steps value
        self.steps_entry.pack(side="right", padx=15, pady=12)

        # --- 2. CHAT DISPLAY ---
        chat_frame = ctk.CTkFrame(self, fg_color="#111111", corner_radius=6, border_width=1, border_color="#333333")
        chat_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.chat_box = ctk.CTkTextbox(chat_frame, fg_color="#111111", text_color="#ffffff", font=("Consolas", 12), border_width=0)
        self.chat_box.pack(fill="both", expand=True, padx=15, pady=15)
        self.chat_box.configure(state="disabled")

        # --- 3. BOTTOM CONTROLS (Prompt Input & Action Buttons) ---
        bottom_frame = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        bottom_frame.pack(fill="x", padx=20, pady=(10, 20))

        self.prompt_text = ctk.CTkTextbox(
            bottom_frame, height=70, 
            fg_color="#111111", text_color="#ffffff", 
            border_color="#444444", border_width=1, corner_radius=6, font=("Arial", 12)
        )
        self.prompt_text.pack(fill="x", pady=(0, 10))

        btn_row = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_row.pack(fill="x")

        self.btn_send = ctk.CTkButton(
            btn_row, text="Send / Run", 
            fg_color="#ffffff", text_color="#000000", hover_color="#dddddd", 
            font=("Arial", 12, "bold"), corner_radius=6, command=self.send_prompt
        )
        self.btn_send.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.btn_undo = ctk.CTkButton(
            btn_row, text="Undo Last Run", 
            fg_color="#1a1a1a", text_color="#ffffff", hover_color="#333333", 
            border_color="#444444", border_width=1, corner_radius=6, font=("Arial", 12, "bold"), command=self.undo_last_actions
        )
        self.btn_undo.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def set_mode(self, mode):
        self.current_mode = mode
        if mode == "Level-by-Level":
            self.btn_mode_lvl.configure(fg_color="#ffffff", text_color="#000000", font=("Arial", 11, "bold"))
            self.btn_mode_full.configure(fg_color="#1a1a1a", text_color="#ffffff", font=("Arial", 11))
        else:
            self.btn_mode_full.configure(fg_color="#ffffff", text_color="#000000", font=("Arial", 11, "bold"))
            self.btn_mode_lvl.configure(fg_color="#1a1a1a", text_color="#ffffff", font=("Arial", 11))

    def log(self, sender, message):
        """Clean, modern logger without separator lines, featuring markdown support for AI outputs."""
        self.chat_box.configure(state="normal")
        txt_widget = self.chat_box._textbox

        # Define styles
        txt_widget.tag_config("sender_system", font=("Consolas", 10, "bold"), foreground="#666666")
        txt_widget.tag_config("sender_user", font=("Consolas", 10, "bold"), foreground="#aaaaaa")
        txt_widget.tag_config("sender_ai", font=("Consolas", 10, "bold"), foreground="#ffffff")
        txt_widget.tag_config("sender_tool", font=("Consolas", 10, "bold"), foreground="#00ffcc")
        
        txt_widget.tag_config("h3", font=("Arial", 13, "bold"), foreground="#ffffff", spacing1=10, spacing2=4)
        txt_widget.tag_config("bold", font=("Consolas", 12, "bold"), foreground="#ffffff")
        txt_widget.tag_config("code", font=("Consolas", 11), background="#1a1a1a", foreground="#00ffcc")
        txt_widget.tag_config("bullet", lmargin1=15, lmargin2=30)
        txt_widget.tag_config("body", font=("Consolas", 12), foreground="#dddddd")

        tag_map = {
            "SYSTEM": "sender_system",
            "USER": "sender_user",
            "AI": "sender_ai",
            "TOOL": "sender_tool",
            "ERROR": "sender_tool",
            "UNDO": "sender_tool"
        }
        sender_tag = tag_map.get(sender, "sender_system")

        # Print Sender Header
        self.chat_box.insert("end", f"[{sender}]\n", sender_tag)

        # Print Message Body (with Markdown parsing for AI)
        if sender == "AI":
            lines = message.split("\n")
            for line in lines:
                if line.startswith("### "):
                    self.chat_box.insert("end", f"\n{line[4:].strip()}\n", "h3")
                elif line.startswith("## "):
                    self.chat_box.insert("end", f"\n{line[3:].strip()}\n", "h3")
                elif line.strip().startswith("* ") or line.strip().startswith("- "):
                    self.chat_box.insert("end", "  • ", "bullet")
                    self.insert_inline_markdown(line.strip()[2:], "bullet")
                    self.chat_box.insert("end", "\n")
                else:
                    if line.strip():
                        self.insert_inline_markdown(line + "\n", "body")
                    else:
                        self.chat_box.insert("end", "\n")
        else:
            self.chat_box.insert("end", f"{message}\n", "body")

        self.chat_box.insert("end", "\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def insert_inline_markdown(self, text, base_tag="body"):
        """Helper to parse inline markdown like **bold** and `code`."""
        pattern = r"(\*\*.*?\*\*|`.*?`)"
        tokens = re.split(pattern, text)
        for token in tokens:
            if not token:
                continue
            if token.startswith("**") and token.endswith("**"):
                clean_text = token[2:-2]
                tags = (base_tag, "bold")
                self.chat_box.insert("end", clean_text, tags)
            elif token.startswith("`") and token.endswith("`"):
                clean_text = token[1:-1]
                tags = (base_tag, "code")
                self.chat_box.insert("end", clean_text, tags)
            else:
                self.chat_box.insert("end", token, (base_tag,))

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_directory = folder
            self.dir_label.configure(text=folder, text_color="#ffffff")
            self.log("SYSTEM", f"Working directory set to: {folder}")
            
            self.messages = [
                {
                    "role": "system", 
                    "content": (
                        "You are an autonomous, relentless desktop file manager agent. "
                        "Your absolute priority is to completely finish the user's file organization request from start to finish WITHOUT stopping early. "
                        "EXECUTE actions immediately using tool calls in a continuous loop until the entire directory is fully and perfectly organized. "
                        "When all tasks are fully completed, provide a clean, well-structured final summary using Markdown formatting (like headers ###, bold text **, and bulleted lists) to show the user exactly what was accomplished."
                    )
                }
            ]
            self.last_run_actions.clear()

    def force_minimize_lm_studio(self):
        """Polls for the LM Studio window handle and instantly minimizes it via Win32 API."""
        for _ in range(40):
            hwnd = ctypes.windll.user32.FindWindowW(None, "LM Studio")
            if hwnd:
                # 6 = SW_MINIMIZE (minimizes window). Change to 0 (SW_HIDE) if you want it completely invisible.
                ctypes.windll.user32.ShowWindow(hwnd, 6)
                break
            time.sleep(0.5)

    # ==================== ROBUST LM STUDIO AUTO-START & LOAD LOGIC ====================
    def ensure_lm_studio_running(self):
        server_is_running = False
        model_already_loaded = False

        try:
            res = requests.get(self.models_url, timeout=2)
            if res.status_code == 200:
                server_is_running = True
                data = res.json().get("data", [])
                if len(data) > 0:
                    model_already_loaded = True
        except requests.exceptions.RequestException:
            pass

        if server_is_running and model_already_loaded:
            self.log("SYSTEM", "LM Studio Server & Model are already online and ready!")
            return True

        # Launch LM Studio if server is offline
        if not server_is_running:
            self.log("SYSTEM", "Starting LM Studio in the background...")
            path_exe1 = os.path.expandvars(r"%LOCALAPPDATA%\LM Studio\LM Studio.exe")
            path_exe2 = os.path.expandvars(r"%LOCALAPPDATA%\Programs\lm-studio\LM Studio.exe")
            path_shortcut = r"C:\Users\Ilay\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\LM Studio.lnk"
            
            # Start background thread to catch and minimize the window immediately when it opens
            threading.Thread(target=self.force_minimize_lm_studio, daemon=True).start()

            lm_studio_launched = False
            for p in [path_exe1, path_exe2, path_shortcut]:
                if os.path.exists(p) or p == path_shortcut:
                    try:
                        if p.endswith(".lnk"):
                            os.startfile(p)
                        else:
                            subprocess.Popen([p])
                        
                        lm_studio_launched = True
                        break
                    except Exception:
                        pass
            
            if not lm_studio_launched:
                self.log("ERROR", "Error: Could not launch LM Studio automatically.")
                return False

            self.log("SYSTEM", "Waiting for LM Studio server...")
            for _ in range(30):
                time.sleep(2)
                try:
                    res = requests.get(self.models_url, timeout=2)
                    if res.status_code == 200:
                        server_is_running = True
                        break
                except requests.exceptions.RequestException:
                    pass

        if not server_is_running:
            self.log("SYSTEM", "Error: LM Studio server is unreachable.")
            return False

        # Load model into VRAM if not already loaded
        if not model_already_loaded:
            self.log("SYSTEM", "Loading model 'google/gemma-4-12b-qat' into VRAM...")
            try:
                lms_cli_path = r"C:\Users\Ilay\.lmstudio\bin\lms.exe"
                if not os.path.exists(lms_cli_path):
                    lms_cli_path = "lms"

                subprocess.run([lms_cli_path, "load", "google/gemma-4-12b-qat"], check=False)
                time.sleep(4)
                self.log("SYSTEM", "LM Studio Server & Model are online and ready!")
                return True
            except Exception as e:
                self.log("ERROR", f"Error loading model: {e}")
                return False

        return True

    # ==================== TOOL IMPLEMENTATIONS ====================
    
    def tool_list_directory(self, subpath=""):
        if not self.selected_directory:
            return "Error: No folder selected."

        if self.current_mode == "Full Scan (All)":
            files_list = []
            for root, dirs, files in os.walk(self.selected_directory):
                if ".agent_backup" in root:
                    continue
                rel_path = os.path.relpath(root, self.selected_directory)
                files_list.append(f"Folder: {rel_path if rel_path != '.' else 'ROOT'}")
                for d in dirs:
                    if d != ".agent_backup":
                        files_list.append(f"  [Folder] {d}")
                for f in files:
                    files_list.append(f"  [File] {f}")
            return "\n".join(files_list)
        else:
            target_dir = self.selected_directory
            if subpath:
                target_dir = os.path.join(self.selected_directory, subpath)
                
            if not self.is_safe_path(target_dir):
                return "Error: Access denied."
                
            if not os.path.exists(target_dir):
                return f"Error: Directory '{subpath}' does not exist."

            try:
                items = os.listdir(target_dir)
                files_list = [f"Contents of '{subpath if subpath else 'ROOT'}':"]
                for item in items:
                    if item == ".agent_backup":
                        continue
                    full_item_path = os.path.join(target_dir, item)
                    if os.path.isdir(full_item_path):
                        files_list.append(f"  [Folder] {item}")
                    else:
                        files_list.append(f"  [File] {item}")
                return "\n".join(files_list)
            except Exception as e:
                return f"Error reading directory: {e}"

    def tool_create_folder(self, path):
        full_path = os.path.join(self.selected_directory, path)
        if not self.is_safe_path(full_path):
            return "Error: Access denied."
        os.makedirs(full_path, exist_ok=True)
        self.current_batch_actions.append({"type": "rmdir", "path": full_path})
        self.log("TOOL", f"Created folder: {path}")
        return f"Folder '{path}' created successfully."

    def tool_delete_file(self, path):
        full_path = os.path.join(self.selected_directory, path)
        if not self.is_safe_path(full_path):
            return "Error: Access denied."
        if not os.path.exists(full_path):
            return f"Error: File '{path}' does not exist."

        backup_dir = os.path.join(self.selected_directory, ".agent_backup")
        os.makedirs(backup_dir, exist_ok=True)
        backup_filename = f"{os.path.basename(full_path)}_{os.urandom(4).hex()}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        shutil.copy2(full_path, backup_path)
        os.remove(full_path)

        self.current_batch_actions.append({"type": "restore", "backup": backup_path, "original": full_path})
        self.log("TOOL", f"Deleted file: {path}")
        return f"File '{path}' deleted successfully."

    def tool_delete_folder(self, path):
        """Deletes an entire folder including its contents (with backup for undo)."""
        full_path = os.path.join(self.selected_directory, path)
        if not self.is_safe_path(full_path):
            return "Error: Access denied."
        if not os.path.exists(full_path) or not os.path.isdir(full_path):
            return f"Error: Folder '{path}' does not exist or is not a directory."

        backup_dir = os.path.join(self.selected_directory, ".agent_backup")
        os.makedirs(backup_dir, exist_ok=True)
        backup_foldername = f"{os.path.basename(full_path)}_{os.urandom(4).hex()}"
        backup_path = os.path.join(backup_dir, backup_foldername)
        
        shutil.move(full_path, backup_path)

        self.current_batch_actions.append({"type": "restore_folder", "backup": backup_path, "original": full_path})
        self.log("TOOL", f"Deleted folder: {path}")
        return f"Folder '{path}' successfully deleted."

    def tool_move_file(self, src, dest):
        full_src = os.path.join(self.selected_directory, src)
        full_dest = os.path.join(self.selected_directory, dest)
        if not self.is_safe_path(full_src) or not self.is_safe_path(full_dest):
            return "Error: Access denied."
        
        os.makedirs(os.path.dirname(full_dest), exist_ok=True)
        shutil.move(full_src, full_dest)
        self.current_batch_actions.append({"type": "move", "src": full_dest, "dest": full_src})
        self.log("TOOL", f"Moved file: {src} -> {dest}")
        return f"File moved from {src} to {dest}."

    def tool_move_folder(self, src, dest):
        full_src = os.path.join(self.selected_directory, src)
        full_dest = os.path.join(self.selected_directory, dest)
        if not self.is_safe_path(full_src) or not self.is_safe_path(full_dest):
            return "Error: Access denied."
        if not os.path.exists(full_src) or not os.path.isdir(full_src):
            return f"Error: Folder '{src}' does not exist or is not a directory."
        
        os.makedirs(full_dest, exist_ok=True)
        target_path = os.path.join(full_dest, os.path.basename(full_src))
        
        shutil.move(full_src, target_path)
        self.current_batch_actions.append({"type": "move_folder", "src": target_path, "dest": full_src})
        self.log("TOOL", f"Moved entire folder: {src} -> {dest}")
        return f"Folder '{src}' successfully moved into '{dest}'."

    def tool_rename_file(self, old_path, new_path):
        full_old = os.path.join(self.selected_directory, old_path)
        full_new = os.path.join(self.selected_directory, new_path)
        if not self.is_safe_path(full_old) or not self.is_safe_path(full_new):
            return "Error: Access denied."
        
        os.rename(full_old, full_new)
        self.current_batch_actions.append({"type": "rename", "old_path": full_new, "new_path": full_old})
        self.log("TOOL", f"Renamed: {old_path} -> {new_path}")
        return f"Successfully renamed to {new_path}."

    def is_safe_path(self, target_path):
        if not self.selected_directory:
            return False
        base = pathlib.Path(self.selected_directory).resolve()
        target = pathlib.Path(target_path).resolve()
        return base in target.parents or base == target

    def undo_last_actions(self):
        if not self.last_run_actions:
            messagebox.showinfo("Undo", "No actions available to undo.")
            return

        answer = messagebox.askyesno("Undo", "Do you want to completely undo all actions from the last run?")
        if not answer:
            return

        self.log("SYSTEM", "--- Starting Undo Process ---")
        for action in reversed(self.last_run_actions):
            try:
                act_type = action["type"]
                if act_type == "rmdir":
                    if os.path.exists(action["path"]) and not os.listdir(action["path"]):
                        os.rmdir(action["path"])
                        self.log("UNDO", f"Removed empty folder: {action['path']}")
                elif act_type == "restore":
                    if os.path.exists(action["backup"]):
                        os.makedirs(os.path.dirname(action["original"]), exist_ok=True)
                        shutil.copy2(action["backup"], action["original"])
                        os.remove(action["backup"])
                        self.log("UNDO", f"Restored file: {action['original']}")
                elif act_type == "restore_folder":
                    if os.path.exists(action["backup"]):
                        os.makedirs(os.path.dirname(action["original"]), exist_ok=True)
                        shutil.move(action["backup"], action["original"])
                        self.log("UNDO", f"Restored folder: {action['original']}")
                elif act_type == "move":
                    if os.path.exists(action["src"]):
                        os.makedirs(os.path.dirname(action["dest"]), exist_ok=True)
                        shutil.move(action["src"], action["dest"])
                        self.log("UNDO", f"Reversed file move: {action['src']} -> {action['dest']}")
                elif act_type == "move_folder":
                    if os.path.exists(action["src"]):
                        os.makedirs(os.path.dirname(action["dest"]), exist_ok=True)
                        shutil.move(action["src"], action["dest"])
                        self.log("UNDO", f"Reversed folder move: {action['src']} -> {action['dest']}")
                elif act_type == "rename":
                    if os.path.exists(action["old_path"]):
                        os.rename(action["old_path"], action["new_path"])
                        self.log("UNDO", f"Reversed rename: {action['old_path']} -> {action['new_path']}")
            except Exception as e:
                self.log("ERROR", f"Error during undo of {action}: {e}")

        self.last_run_actions.clear()
        self.log("SYSTEM", "--- Undo Completed Successfully ---")

    def send_prompt(self):
        if not self.selected_directory:
            messagebox.showerror("Error", "Please select a folder or USB stick first!")
            return

        user_instruction = self.prompt_text.get("1.0", "end-1c").strip()
        if not user_instruction:
            messagebox.showwarning("Notice", "Please enter a command in the text field!")
            return

        self.prompt_text.delete("1.0", "end")

        try:
            max_steps = int(self.steps_entry.get().strip())
        except:
            max_steps = 30

        self.current_batch_actions = []
        self.log("USER", user_instruction)
        self.messages.append({"role": "user", "content": user_instruction})

        threading.Thread(target=self.run_agent_task, args=(max_steps,), daemon=True).start()

    def run_agent_task(self, max_steps):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool_list_directory",
                    "description": "Lists contents of the directory or subpath based on the selected mode.",
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "subpath": {"type": "string", "description": "Optional subfolder path to list contents of, leave empty for root."}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_create_folder",
                    "description": "Creates a new folder.",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Folder name/path"}}, "required": ["path"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_delete_file",
                    "description": "Deletes an individual file (backed up for undo).",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "File path"}}, "required": ["path"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_delete_folder",
                    "description": "Deletes an entire folder and its contents (backed up for undo). Use this to delete folders like 'Stream Fab' or 'Custom Music Recording'.",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Folder path to delete"}}, "required": ["path"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_move_file",
                    "description": "Moves an individual file to a subfolder.",
                    "parameters": {"type": "object", "properties": {"src": {"type": "string"}, "dest": {"type": "string"}}, "required": ["src", "dest"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_move_folder",
                    "description": "Moves an entire folder into another folder (useful to merge, combine or dissolve folders).",
                    "parameters": {"type": "object", "properties": {"src": {"type": "string", "description": "Source folder name/path"}, "dest": {"type": "string", "description": "Destination parent folder name/path"}}, "required": ["src", "dest"]}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tool_rename_file",
                    "description": "Renames a file.",
                    "parameters": {"type": "object", "properties": {"old_path": {"type": "string"}, "new_path": {"type": "string"}}, "required": ["old_path", "new_path"]}
                }
            }
        ]

        for step in range(max_steps):
            try:
                response = self.client.chat.completions.create(
                    model="google/gemma-4-12b-qat",
                    messages=self.messages,
                    tools=tools,
                    tool_choice="auto"
                )
            except Exception as e:
                self.log("ERROR", f"Failed to connect to LM Studio: {e}")
                break

            response_message = response.choices[0].message
            self.messages.append(response_message)

            if response_message.content:
                self.log("AI", response_message.content)

            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except:
                        function_args = {}

                    tool_result = ""
                    if function_name == "tool_list_directory":
                        tool_result = self.tool_list_directory(function_args.get("subpath", ""))
                    elif function_name == "tool_create_folder":
                        tool_result = self.tool_create_folder(function_args.get("path"))
                    elif function_name == "tool_delete_file":
                        tool_result = self.tool_delete_file(function_args.get("path"))
                    elif function_name == "tool_delete_folder":
                        tool_result = self.tool_delete_folder(function_args.get("path"))
                    elif function_name == "tool_move_file":
                        tool_result = self.tool_move_file(function_args.get("src"), function_args.get("dest"))
                    elif function_name == "tool_move_folder":
                        tool_result = self.tool_move_folder(function_args.get("src"), function_args.get("dest"))
                    elif function_name == "tool_rename_file":
                        tool_result = self.tool_rename_file(function_args.get("old_path"), function_args.get("new_path"))
                    else:
                        tool_result = f"Error: Unknown tool {function_name}"

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(tool_result)
                    })
            else:
                break

        if self.current_batch_actions:
            self.last_run_actions = list(self.current_batch_actions)

        self.log("SYSTEM", "--- Task Finished (Ready for next message) ---")

if __name__ == "__main__":
    app = AIFileAgentApp()
    app.mainloop()
