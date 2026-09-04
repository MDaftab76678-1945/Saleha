import { coreEngine } from '@saleha/core';

export async function runCoreHeartbeat() {
    console.log('[Heartbeat] Testing connection to Saleha Core...');
    try {
        await coreEngine.initialize();
        const result = await coreEngine.verifyAST('print("hello")', 'python');
        console.log('[Heartbeat] Core response received:', result.passed ? '? SUCCESS' : '? FAILED');
        return true;
    } catch (error) {
        console.error('[Heartbeat] Core connection failed:', error);
        return false;
    }
}
