import * as vscode from 'vscode';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient;
let watcherTerminal: vscode.Terminal | undefined;

export function activate(context: vscode.ExtensionContext) {
  // 1. Configure Language Server executable launching 'saleha lsp --stdio'
  const serverOptions: ServerOptions = {
    command: 'saleha',
    args: ['lsp', '--stdio'],
    transport: TransportKind.stdio
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { scheme: 'file', language: 'python' },
      { scheme: 'file', language: 'javascript' },
      { scheme: 'file', language: 'typescript' },
      { scheme: 'file', language: 'go' },
      { scheme: 'file', language: 'rust' }
    ],
    synchronize: {
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.*')
    }
  };

  client = new LanguageClient(
    'salehaLSP',
    'Saleha AI Language Server',
    serverOptions,
    clientOptions
  );

  client.start();

  // 2. Register Interactive Editor Commands
  context.subscriptions.push(
    // Auto-Heal Active Test / Build Errors
    vscode.commands.registerCommand('saleha.fix', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No active file open for Saleha Auto-Heal.');
        return;
      }
      const term = vscode.window.createTerminal('Saleha Fix');
      term.show();
      term.sendText(`saleha fix "pytest ${editor.document.fileName}"`);
    }),

    // Deep OWASP AI Code Review
    vscode.commands.registerCommand('saleha.reviewAI', async () => {
      const editor = vscode.window.activeTextEditor;
      const target = editor ? `"${editor.document.fileName}"` : '.';
      const term = vscode.window.createTerminal('Saleha AI Review');
      term.show();
      term.sendText(`saleha review-ai ${target} --html`);
    }),

    // Surgical Diff & Blast Radius Preview
    vscode.commands.registerCommand('saleha.diffPreview', async () => {
      const term = vscode.window.createTerminal('Saleha Diff Preview');
      term.show();
      term.sendText(`saleha diff-preview`);
    }),

    // Episodic Project Memory
    vscode.commands.registerCommand('saleha.memoryProject', async () => {
      const action = await vscode.window.showQuickPick(
        ['Recall Decisions', 'Show Journal History', 'Remember Custom Rule'],
        { placeHolder: 'Select Project Memory Action' }
      );
      if (!action) return;

      const term = vscode.window.createTerminal('Saleha Memory');
      term.show();
      if (action.startsWith('Recall')) {
        const query = await vscode.window.showInputBox({ prompt: 'Search memory for:' });
        if (query) term.sendText(`saleha memory-project --recall "${query}"`);
      } else if (action.startsWith('Show')) {
        term.sendText(`saleha memory-project --journal`);
      } else {
        const entry = await vscode.window.showInputBox({ prompt: 'Rule/Decision to remember:' });
        if (entry) term.sendText(`saleha memory-project --remember "${entry}"`);
      }
    }),

    // Real-Time Watcher Toggle
    vscode.commands.registerCommand('saleha.watchAI', () => {
      if (watcherTerminal) {
        watcherTerminal.dispose();
        watcherTerminal = undefined;
        vscode.window.showInformationMessage('Saleha Real-Time Watcher stopped.');
      } else {
        watcherTerminal = vscode.window.createTerminal('Saleha Watcher');
        watcherTerminal.show();
        watcherTerminal.sendText('saleha watch-ai .');
        vscode.window.showInformationMessage('Saleha Real-Time Watcher started on current workspace.');
      }
    }),

    // Hybrid Semantic Search
    vscode.commands.registerCommand('saleha.search', async () => {
      const query = await vscode.window.showInputBox({
        prompt: 'Enter natural language semantic code search query',
        placeHolder: 'e.g. compact conversation history'
      });
      if (query) {
        const term = vscode.window.createTerminal('Saleha Search');
        term.show();
        term.sendText(`saleha search "${query}" --semantic`);
      }
    }),

    // Open Real-Time Terminal HUD
    vscode.commands.registerCommand('saleha.hud', () => {
      const term = vscode.window.createTerminal('Saleha HUD');
      term.show();
      term.sendText('saleha hud');
    }),

    // Local LoRA Fine-Tuning
    vscode.commands.registerCommand('saleha.tune', () => {
      const term = vscode.window.createTerminal('Saleha LoRA Tuner');
      term.show();
      term.sendText('saleha tune --export');
    })
  );
}

export function deactivate(): Thenable<void> | undefined {
  if (watcherTerminal) {
    watcherTerminal.dispose();
  }
  if (!client) {
    return undefined;
  }
  return client.stop();
}
