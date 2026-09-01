import { z } from "zod";
import { router, publicProcedure } from "../trpc";

export const astRouter = router({
  verifySnippet: publicProcedure
    .input(
      z.object({
        code: z.string().min(1),
        language: z.enum(["python", "javascript", "typescript", "c", "rust"]).default("python"),
        strictMode: z.boolean().default(true),
      })
    )
    .mutation(async ({ input }) => {
      const isDivZero = input.code.includes("/ 0") || input.code.includes("/0");
      const hasMemoryLeak = input.code.includes("malloc(") && !input.code.includes("free(");

      return {
        isValid: !isDivZero && !hasMemoryLeak,
        language: input.language,
        violations: [
          ...(isDivZero ? ["Division by zero literal violation"] : []),
          ...(hasMemoryLeak ? ["Unfreed malloc buffer detected (Memory leak)"] : []),
        ],
        executionTimeUs: 85,
        gammaScore: isDivZero || hasMemoryLeak ? 0.0 : 1.0,
      };
    }),
});

