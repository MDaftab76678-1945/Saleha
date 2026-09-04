import { AgentDepartment } from './constants';

export interface HyperbolicVector {
  coords: number[];
}

export interface AgentProfile {
  id: string;
  name: string;
  department: AgentDepartment;
  capabilities: string[];
  state: HyperbolicVector;
}

export interface SPSCMessage<T> {
  id: string;
  payload: T;
  timestamp: number;
  priority: number;
}

export interface ASTViolation {
  ruleId: string;
  severity: 'CRITICAL' | 'ERROR' | 'WARNING' | 'SECURITY';
  message: string;
  line: number;
  column: number;
  fixHint: string;
}

export interface GammaReport {
  passed: boolean;
  violations: ASTViolation[];
  executionTimeMs: number;
  sandboxOutput: string;
  sandboxExitCode: number;
}

export interface WasmExecutionResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  executionTimeMs: number;
}

export interface WasmRuntimeInterface {
  installPackage(pkg: string, manager: 'npm' | 'pip'): Promise<boolean>;
  execute(code: string, language: 'python' | 'javascript' | 'rust'): Promise<WasmExecutionResult>;
  getFileSystem(): Promise<string[]>;
  reset(): Promise<void>;
}
