/**
 * Saleha AI VS Code Extension Bridge
 * Connects the VS Code IDE to the local Saleha REST/SSE, Ollama, and MCP Server.
 * 
 * Features:
 * 1. Ghost-Text Inline Code Autocomplete (Ollama Powered)
 * 2. AST Security SAST Scanner & Inline Quick-Fix Actions
 * 3. Interactive Webview Studio Sidebar with 20 Agent Personas
 * 4. 5-Stage Autonomous Multi-Agent Swarm Integration
 * 5. Git-Native Autonomous PR & Commit Bridge
 */

const vscode = require('vscode');
const http = require('http');

let lastCompletionTime = 0;
const COMPLETION_DEBOUNCE_MS = 250;

/**
 * Calls local Ollama or Saleha Gateway for inline code completion.
 */
async function fetchInlineCompletion(prefix, suffix, model, endpoint) {
    return new Promise((resolve) => {
        try {
            const url = new URL(endpoint || 'http://127.0.0.1:11434/api/generate');
            const postData = JSON.stringify({
                model: model || 'qwen2.5-coder:1.5b',
                prompt: prefix,
                suffix: suffix,
                stream: false,
                options: {
                    temperature: 0.2,
                    num_predict: 64,
                    stop: ['\n\n', '```']
                }
            });

            const req = http.request({
                hostname: url.hostname,
                port: url.port || 11434,
                path: url.pathname,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData)
                },
                timeout: 3000
            }, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end', () => {
                    try {
                        const parsed = JSON.parse(data);
                        resolve(parsed.response || '');
                    } catch (e) {
                        resolve('');
                    }
                });
            });

            req.on('error', () => { resolve(''); });
            req.on('timeout', () => { req.destroy(); resolve(''); });
            req.write(postData);
            req.end();
        } catch (e) {
            resolve('');
        }
    });
}

/**
 * Sidebar Webview View Provider for Interactive AI Studio
 */
class SalehaSidebarProvider {
    constructor(extensionUri) {
        this._extensionUri = extensionUri;
    }

    resolveWebviewView(webviewView, context, token) {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri]
        };

        // Settings ko honor karo -- pehle webview JS mein endpoint HARDCODED tha
        // (saleha.ollamaEndpoint setting ignore hoti thi).
        const cfg = vscode.workspace.getConfiguration('saleha');
        this._ollamaEndpoint = cfg.get('ollamaEndpoint', 'http://127.0.0.1:11434/api/generate');
        this._chatModel = cfg.get('autocompleteModel', 'qwen2.5-coder:1.5b');

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview, this._ollamaEndpoint, this._chatModel);

        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'insertCode': {
                    const editor = vscode.window.activeTextEditor;
                    if (editor) {
                        editor.edit(editBuilder => {
                            editBuilder.insert(editor.selection.active, data.code);
                        });
                        vscode.window.showInformationMessage('✅ Code inserted into active editor.');
                    } else {
                        vscode.window.showWarningMessage('No active editor open to insert code.');
                    }
                    break;
                }
                case 'runSast': {
                    vscode.commands.executeCommand('saleha.auditSecurity');
                    break;
                }
                case 'runSwarm': {
                    vscode.commands.executeCommand('saleha.runSwarm');
                    break;
                }
            }
        });
    }

    _getHtmlForWebview(webview, ollamaEndpoint, chatModel) {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Saleha Studio</title>
    <style>
        body {
            font-family: var(--vscode-font-family, sans-serif);
            padding: 10px;
            color: var(--vscode-foreground);
            background-color: var(--vscode-sideBar-background);
            margin: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
            box-sizing: border-box;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--vscode-panel-border);
        }
        .header h3 {
            margin: 0;
            font-size: 13px;
            color: var(--vscode-textLink-activeForeground, #58a6ff);
        }
        .badge {
            background: #238636;
            color: #ffffff;
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 10px;
        }
        select, textarea, button {
            width: 100%;
            box-sizing: border-box;
            margin-bottom: 8px;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--vscode-input-border, #30363d);
            border-radius: 4px;
            padding: 6px 8px;
            font-size: 12px;
        }
        button.primary {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            font-weight: 600;
            cursor: pointer;
        }
        button.primary:hover {
            background: var(--vscode-button-hoverBackground);
        }
        button.secondary {
            background: var(--vscode-button-secondaryBackground, #21262d);
            color: var(--vscode-button-secondaryForeground, #c9d1d9);
            cursor: pointer;
        }
        .chat-history {
            flex: 1;
            overflow-y: auto;
            border: 1px solid var(--vscode-panel-border, #30363d);
            border-radius: 4px;
            padding: 8px;
            margin-bottom: 8px;
            background: var(--vscode-editor-background);
            font-size: 12px;
        }
        .msg {
            margin-bottom: 10px;
            padding: 6px 8px;
            border-radius: 4px;
        }
        .msg.user {
            background: var(--vscode-editor-selectionBackground);
        }
        .msg.agent {
            background: var(--vscode-editor-inactiveSelectionBackground);
            border-left: 3px solid #58a6ff;
        }
        pre {
            background: #0d1117;
            padding: 6px;
            border-radius: 4px;
            overflow-x: auto;
            color: #58a6ff;
        }
    </style>
</head>
<body>
    <div class="header">
        <h3>🧠 Saleha AI Studio</h3>
        <span class="badge">Local Ollama</span>
    </div>

    <label style="font-size: 11px; margin-bottom: 4px; display: block;">Select Domain Agent Persona:</label>
    <select id="agent-select">
        <option value="agent_sde">💻 SDE (Distributed Systems & Algorithms)</option>
        <option value="agent_software_designer">📐 Software Designer (LLD & Architecture)</option>
        <option value="agent_security_engineer">🛡️ Security Engineer (SAST & Vulnerabilities)</option>
        <option value="agent_product_manager">📋 Product Manager (PRD & Stories)</option>
        <option value="agent_test_automation_engineer">🧪 QA Architect (Unittest & E2E)</option>
    </select>

    <div class="chat-history" id="chat-box">
        <div class="msg agent">
            <strong>Saleha:</strong> Hello! Ask me to generate code, refactor active editor file, or run AST SAST scans.
        </div>
    </div>

    <textarea id="prompt-input" rows="3" placeholder="Type prompt (e.g. Build thread-safe rate limiter)..."></textarea>
    <button class="primary" id="send-btn">🚀 Send to Agent</button>

    <div style="display: flex; gap: 4px;">
        <button class="secondary" id="sast-btn">🛡️ Scan File</button>
        <button class="secondary" id="swarm-btn">👥 5-Agent Swarm</button>
    </div>

    <script>
        const vscode = acquireVsCodeApi();
        // Settings se inject hua endpoint/model (hardcoded nahi)
        const OLLAMA_ENDPOINT = "${ollamaEndpoint}";
        const CHAT_MODEL = "${chatModel}";
        const chatBox = document.getElementById('chat-box');
        const promptInput = document.getElementById('prompt-input');
        const sendBtn = document.getElementById('send-btn');
        const sastBtn = document.getElementById('sast-btn');
        const swarmBtn = document.getElementById('swarm-btn');
        const agentSelect = document.getElementById('agent-select');

        sastBtn.addEventListener('click', () => {
            vscode.postMessage({ type: 'runSast' });
        });

        swarmBtn.addEventListener('click', () => {
            vscode.postMessage({ type: 'runSwarm' });
        });

        function appendMessage(className, labelText, bodyText) {
            // SECURITY: innerHTML nahi -- model output ya user prompt ko
            // textContent ke through insert karte hain (webview XSS fix).
            const div = document.createElement('div');
            div.className = 'msg ' + className;
            const strong = document.createElement('strong');
            strong.textContent = labelText;
            div.appendChild(strong);
            if (bodyText !== undefined && bodyText !== null) {
                div.appendChild(document.createElement('br'));
                const pre = document.createElement('pre');
                const code = document.createElement('code');
                code.textContent = bodyText;
                pre.appendChild(code);
                div.appendChild(pre);
                const btn = document.createElement('button');
                btn.textContent = '📝 Insert Code';
                btn.style.cssText = 'margin-top: 4px; font-size: 10px; padding: 2px 4px;';
                btn.addEventListener('click', insertLatestCode);
                div.appendChild(btn);
            }
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
            return div;
        }

        sendBtn.addEventListener('click', async () => {
            const prompt = promptInput.value.trim();
            if (!prompt) return;

            const agent = agentSelect.options[agentSelect.selectedIndex].text;

            appendMessage('user', 'You:', prompt);
            promptInput.value = '';

            const agentDiv = appendMessage('agent', agent.split(' ')[1] + ':', 'Thinking via local Ollama...');

            try {
                const res = await fetch(OLLAMA_ENDPOINT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: CHAT_MODEL,
                        prompt: 'Role: ' + agent + '\\nTask: ' + prompt + '\\nReturn concise code or guidance.',
                        stream: false
                    })
                });
                const data = await res.json();
                window.latestCode = data.response;
                agentDiv.remove();
                appendMessage('agent', agent.split(' ')[1] + ':', data.response);
            } catch (err) {
                agentDiv.remove();
                appendMessage('agent', 'Saleha:', '⚠️ Error connecting to local Ollama at ' + OLLAMA_ENDPOINT + ' (is it running?)');
            }
        });

        function insertLatestCode() {
            if (window.latestCode) {
                vscode.postMessage({ type: 'insertCode', code: window.latestCode });
            }
        }
    </script>
</body>
</html>`;
    }
}

function activate(context) {
    const config = vscode.workspace.getConfiguration('saleha');
    const endpoint = config.get('ollamaEndpoint', 'http://127.0.0.1:11434/api/generate');
    const model = config.get('autocompleteModel', 'qwen2.5-coder:1.5b');

    // 1. Status Bar Item (Live Status & Latency)
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.text = `$(hubot) Saleha: ${model.split(':')[0]}`;
    statusBarItem.tooltip = 'Saleha AI Engine Active (Click to open Web Studio)';
    statusBarItem.command = 'saleha.openStudio';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // 2. Ghost-Text Inline Completion Provider
    const inlineProvider = {
        async provideInlineCompletionItems(document, position, completionContext, token) {
            const now = Date.now();
            if (now - lastCompletionTime < COMPLETION_DEBOUNCE_MS) {
                return [];
            }
            lastCompletionTime = now;

            const textBefore = document.getText(new vscode.Range(
                new vscode.Position(Math.max(0, position.line - 20), 0),
                position
            ));
            const textAfter = document.getText(new vscode.Range(
                position,
                new vscode.Position(Math.min(document.lineCount, position.line + 10), 0)
            ));

            if (!textBefore.trim()) return [];

            const startPing = Date.now();
            const suggestion = await fetchInlineCompletion(textBefore, textAfter, model, endpoint);
            const latency = Date.now() - startPing;

            if (suggestion && suggestion.trim()) {
                statusBarItem.text = `$(hubot) Saleha: ${latency}ms`;
                setTimeout(() => {
                    statusBarItem.text = `$(hubot) Saleha: ${model.split(':')[0]}`;
                }, 2000);
                return [new vscode.InlineCompletionItem(suggestion, new vscode.Range(position, position))];
            }
            return [];
        }
    };

    const inlineDisposable = vscode.languages.registerInlineCompletionItemProvider(
        { pattern: '**' },
        inlineProvider
    );
    context.subscriptions.push(inlineDisposable);

    // 3. AST Security Quick Fix Provider (CodeActionProvider)
    const codeActionProvider = {
        provideCodeActions(document, range, contextAction, token) {
            const actions = [];
            const lineText = document.lineAt(range.start.line).text;

            // Pattern: shell=True fix
            if (lineText.includes('shell=True')) {
                const fix = new vscode.CodeAction('🛡️ Saleha: Remove dangerous shell=True', vscode.CodeActionKind.QuickFix);
                fix.edit = new vscode.WorkspaceEdit();
                const newLine = lineText.replace(/,\s*shell\s*=\s*True/g, '').replace(/shell\s*=\s*True\s*,?/g, '');
                fix.edit.replace(document.uri, document.lineAt(range.start.line).range, newLine);
                actions.push(fix);
            }

            // Pattern: raw eval() fix
            if (lineText.includes('eval(')) {
                const fix = new vscode.CodeAction('🛡️ Saleha: Replace unsafe eval() with ast.literal_eval()', vscode.CodeActionKind.QuickFix);
                fix.edit = new vscode.WorkspaceEdit();
                const newLine = lineText.replace(/eval\(/g, 'ast.literal_eval(');
                fix.edit.replace(document.uri, document.lineAt(range.start.line).range, newLine);
                actions.push(fix);
            }

            return actions;
        }
    };

    const codeActionDisposable = vscode.languages.registerCodeActionsProvider(
        { pattern: '**/*.{py,js,ts}' },
        codeActionProvider,
        { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
    );
    context.subscriptions.push(codeActionDisposable);

    // 4. Sidebar Webview Provider
    const sidebarProvider = new SalehaSidebarProvider(context.extensionUri);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('saleha.webview', sidebarProvider)
    );

    // 5. Open Web Studio Command
    let openStudioCmd = vscode.commands.registerCommand('saleha.openStudio', () => {
        vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:8000'));
    });
    context.subscriptions.push(openStudioCmd);

    // 6. Audit Security Command
    let auditCmd = vscode.commands.registerCommand('saleha.auditSecurity', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showInformationMessage('Open a file to run Saleha Security Audit.');
            return;
        }
        const filePath = editor.document.uri.fsPath;
        vscode.window.showInformationMessage(`🛡️ Running Saleha AST SAST Scan on ${filePath}...`);
        
        const terminal = vscode.window.createTerminal('Saleha SAST');
        terminal.show();
        terminal.sendText(`saleha sast "${filePath}"`);
    });
    context.subscriptions.push(auditCmd);

    // 7. Run Swarm Command
    let swarmCmd = vscode.commands.registerCommand('saleha.runSwarm', async () => {
        const goal = await vscode.window.showInputBox({
            prompt: 'Enter software goal for 5-Agent Swarm (PM -> Architect -> SDE -> Security -> QA):',
            placeHolder: 'e.g. Build in-memory cache with TTL expiration'
        });
        if (!goal) return;

        const terminal = vscode.window.createTerminal('Saleha Swarm');
        terminal.show();
        terminal.sendText(`saleha team "${goal}" --debate`);
    });
    context.subscriptions.push(swarmCmd);

    // 8. Generate PR Command
    let prCmd = vscode.commands.registerCommand('saleha.generatePR', async () => {
        const goal = await vscode.window.showInputBox({
            prompt: 'Enter goal for autonomous PR generation:',
            placeHolder: 'e.g. Implement user authentication with JWT'
        });
        if (!goal) return;

        const terminal = vscode.window.createTerminal('Saleha PR');
        terminal.show();
        terminal.sendText(`saleha pr "${goal}" --debate --push`);
    });
    context.subscriptions.push(prCmd);
}

function deactivate() {}

module.exports = {
    activate,
    deactivate,
    SalehaSidebarProvider
};
