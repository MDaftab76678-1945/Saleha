/**
 * Product facts, stated once.
 *
 * The landing page said "19-Agent Swarm", the Web Studio header said
 * "25-Agent Swarm", its sidebar said "19-Agent Swarm", and its own node
 * list held 27 entries -- four numbers for one product, none of them
 * checked against the code. The footer's "850 Tests Passed" was stale by
 * roughly 1,500 tests. Every surface now reads these instead of
 * hardcoding its own, so a single wrong number is a one-line fix rather
 * than a hunt across three apps.
 *
 * Each value below is measured, and the command that measures it is
 * named next to it. Re-run that command before changing the number.
 */

/** BaseAgent subclasses in saleha/agents/. Measured: grep -l "class.*BaseAgent" saleha/agents/*.py | wc -l */
export const AGENT_COUNT = 27;

/** Persona specs in saleha/skills/agent_*.md. Measured: ls saleha/skills/agent_*.md | wc -l */
export const PERSONA_COUNT = 30;

/** Registered CLI subcommands. Measured: python -c "from saleha.cli.commands import cli; print(len(cli.commands))" */
export const CLI_COMMAND_COUNT = 166;

export const HYPERBOLIC_DIM = 16;
export const CURVATURE_C = 1.0;
export const EPSILON_BOUNDARY = 0.9999;

export enum AgentDepartment {
  FOUNDATION_REASONING = 'FOUNDATION_REASONING',
  GENAI_MULTIMODAL = 'GENAI_MULTIMODAL',
  AGENTIC_SWARMS = 'AGENTIC_SWARMS',
  ADVANCED_RAG = 'ADVANCED_RAG',
  SYSTEMS_KERNEL = 'SYSTEMS_KERNEL',
  AIOPS_INFRA = 'AIOPS_INFRA',
  SECURITY_GOVERNANCE = 'SECURITY_GOVERNANCE',
  PHYSICAL_ROBOTICS = 'PHYSICAL_ROBOTICS',
  QUANTUM_PHYSICS = 'QUANTUM_PHYSICS',
  ENTERPRISE_AI = 'ENTERPRISE_AI',
}
