import { WasmRuntimeInterface, WasmExecutionResult } from '@saleha/core';

export class MockWasmRuntime implements WasmRuntimeInterface {
  async installPackage(pkg: string, manager: 'npm' | 'pip'): Promise<boolean> {
    console.log(`[MockWasm] Installing ${pkg} via ${manager}...`);
    return true;
  }

  async execute(code: string, language: 'python' | 'javascript' | 'rust'): Promise<WasmExecutionResult> {
    console.log(`[MockWasm] Executing ${language} code...`);
    return {
      stdout: `Mock output for ${language} code:\n${code.slice(0, 50)}...`,
      stderr: '',
      exitCode: 0,
      executionTimeMs: 12.5,
    };
  }

  async getFileSystem(): Promise<string[]> {
    return ['/home/user/main.py', '/home/user/package.json'];
  }

  async reset(): Promise<void> {
    console.log('[MockWasm] Runtime reset.');
  }
}
