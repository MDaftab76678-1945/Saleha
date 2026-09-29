import { HyperbolicVector, AgentProfile, GammaReport, WasmRuntimeInterface } from './types';
import { HYPERBOLIC_DIM } from './constants';

export class SalehaCoreEngine {
  private isInitialized: boolean = false;
  private wasmRuntime: WasmRuntimeInterface | null = null;

  async initialize(wasmRuntime?: WasmRuntimeInterface): Promise<void> {
    console.log('[SalehaCore] Initializing Polyglot Engine...');
    this.wasmRuntime = wasmRuntime || null;
    this.isInitialized = true;
    console.log('[SalehaCore] Core Engine Ready.');
  }

  async computeHyperbolicDistance(u: HyperbolicVector, v: HyperbolicVector): Promise<number> {
    const diffSq = u.coords.reduce((acc, val, i) => acc + Math.pow(val - v.coords[i], 2), 0);
    const uSq = u.coords.reduce((acc, val) => acc + val * val, 0);
    const vSq = v.coords.reduce((acc, val) => acc + val * val, 0);
    const denom = Math.max(1e-7, (1.0 - uSq) * (1.0 - vSq));
    const val = 1.0 + (2.0 * diffSq) / denom;
    return Math.log(val + Math.sqrt(Math.max(0, val * val - 1.0)));
  }

  async verifyAST(code: string, language: string): Promise<GammaReport> {
    // No verifier exists on this side: the previous version returned
    // passed:true with empty violations for any input. Fail loudly
    // instead -- like runInSandbox below -- so no caller can mistake
    // this for a clean bill of health. Real verification lives in the
    // Python backend (saleha/core/verification/).
    throw new Error(
      `AST verification is not implemented in the web client (asked for ${language}, ${code.length} chars).`
    );
  }

  async runInSandbox(code: string, language: 'python' | 'javascript' | 'rust'): Promise<any> {
    if (!this.wasmRuntime) {
      throw new Error('Wasm Runtime not initialized.');
    }
    return await this.wasmRuntime.execute(code, language);
  }
}

export const coreEngine = new SalehaCoreEngine();
