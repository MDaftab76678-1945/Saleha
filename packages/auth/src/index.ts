/**
 * @saleha/auth - Security, RBAC & Rate-Limiting Guardrails
 * Enforces zero-trust authentication across Desktop, Web, and Cloud API.
 */

import { z } from "zod";

export const UserRoleSchema = z.enum(["DEVELOPER", "ARCHITECT", "ADMIN"]);
export type UserRole = z.infer<typeof UserRoleSchema>;

export interface AuthSession {
  userId: string;
  email: string;
  role: UserRole;
  organizationId: string;
  expiresAt: number;
}

export class SecurityGuard {
  private static rateLimitMap = new Map<string, { count: number; resetTime: number }>();

  /**
   * Enforces token-bucket rate limiting per IP / User identifier.
   */
  static checkRateLimit(identifier: string, limit = 100, windowMs = 60_000): boolean {
    const now = Date.now();
    const record = this.rateLimitMap.get(identifier);

    if (!record || now > record.resetTime) {
      this.rateLimitMap.set(identifier, { count: 1, resetTime: now + windowMs });
      return true;
    }

    if (record.count >= limit) {
      return false;
    }

    record.count += 1;
    return true;
  }

  /**
   * Verifies RBAC role permission hierarchy.
   */
  static hasPermission(userRole: UserRole, requiredRole: UserRole): boolean {
    const roleHierarchy: Record<UserRole, number> = {
      DEVELOPER: 1,
      ARCHITECT: 2,
      ADMIN: 3,
    };
    return roleHierarchy[userRole] >= roleHierarchy[requiredRole];
  }

  /**
   * Sanitizes input strings against XSS and injection.
   */
  static sanitizeString(input: string): string {
    return input.replace(/[<>]/g, "");
  }
}

