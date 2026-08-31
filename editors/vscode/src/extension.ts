import * as vscode from 'vscode';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient;

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

    vscode.commands.registerCommand('saleha.hud', () => {
      const term = vscode.window.createTerminal('Saleha HUD');
      term.show();
      term.sendText('saleha hud');
    })
  );
}

export function deactivate(): Thenable<void> | undefined {
  if (!client) {
    return undefined;
  }
  return client.stop();
}
