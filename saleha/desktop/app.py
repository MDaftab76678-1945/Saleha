"""
Saleha Desktop: Native Desktop GUI Application Controller

Manages local HTTP backend, browser-app window launcher (Chrome/Edge App Mode),
and Local LLM (Ollama) Health/Model manager for the desktop environment.
"""

from __future__ import annotations

import os
import sys
import time
import json
import socket
import threading
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from http.server import HTTPServer

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler, get_auth_token, set_auth_token


@dataclass
class LocalModelInfo:
    name: str
    size_bytes: int = 0
    modified_at: str = ""
    family: str = "code"


@dataclass
class LocalLLMStatus:
    is_running: bool
    server_url: str = "http://localhost:11434"
    models: List[LocalModelInfo] = field(default_factory=list)
    active_model: str = "qwen2.5-coder"
    gpu_available: bool = False
    message: str = ""


class LocalLLMManager:
    """Detects and manages local Ollama and llama.cpp model runtimes."""

    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip("/")

    def check_status(self) -> LocalLLMStatus:
        """Pings local Ollama server and lists installed models."""
        url = f"{self.host}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SalehaDesktop/2.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_models = data.get("models", [])
                models = [
                    LocalModelInfo(
                        name=m.get("name", "unknown"),
                        size_bytes=m.get("size", 0),
                        modified_at=m.get("modified_at", ""),
                        family=m.get("details", {}).get("family", "code"),
                    )
                    for m in raw_models
                ]
                return LocalLLMStatus(
                    is_running=True,
                    server_url=self.host,
                    models=models,
                    active_model=models[0].name if models else "auto",
                    gpu_available=True,
                    message=f"Connected to Ollama. {len(models)} local models installed.",
                )
        except Exception:
            return LocalLLMStatus(
                is_running=False,
                server_url=self.host,
                models=[],
                active_model="qwen2.5-coder",
                gpu_available=False,
                message="Ollama not detected on localhost:11434. Running in cloud/simulation mode.",
            )

    def pull_model(self, model_name: str) -> bool:
        """Triggers model pull via Ollama REST API."""
        url = f"{self.host}/api/pull"
        payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SalehaDesktop/2.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False


class SalehaDesktopApp:
    """Controls the native desktop GUI window and embedded server lifecycle."""

    def __init__(self, port: int = 0, host: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.llm_manager = LocalLLMManager()
        self.token = get_auth_token()
        self.is_running = False

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, 0))
            return s.getsockname()[1]

    def start_server(self) -> int:
        """Starts background web server on an available port."""
        if self.port == 0:
            self.port = self._find_free_port()

        self.server = HTTPServer((self.host, self.port), SalehaAPIHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.is_running = True
        return self.port

    def get_app_url(self) -> str:
        """Returns authenticated browser URL."""
        return f"http://{self.host}:{self.port}/?token={self.token}"

    def launch_window(self, app_url: Optional[str] = None) -> bool:
        """Launches native app window using Chrome/Edge App Mode or default browser."""
        url = app_url or self.get_app_url()

        # Potential app launchers for Windows / macOS / Linux
        launchers = []
        if sys.platform == "win32":
            edge_path = os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")
            chrome_path = os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe")
            if os.path.isfile(edge_path):
                launchers.append([edge_path, f"--app={url}", "--window-size=1280,820"])
            if os.path.isfile(chrome_path):
                launchers.append([chrome_path, f"--app={url}", "--window-size=1280,820"])

        for cmd in launchers:
            try:
                subprocess.Popen(cmd)
                return True
            except Exception:
                continue

        # Fallback to system default browser
        import webbrowser
        webbrowser.open(url)
        return True

    def stop(self):
        """Stops the embedded server gracefully."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        self.is_running = False


# Global instance
desktop_app = SalehaDesktopApp()
