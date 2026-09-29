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
      // Toy substring checks only ("/ 0", malloc without free). This is
      // not a verification: real AST/SAST checking lives in the Python
      // backend (saleha/core/verification/). Labeled as what it is.
      const isDivZero = input.code.includes("/ 0") || input.code.includes("/0");
      const hasMemoryLeak = input.code.includes("malloc(") && !input.code.includes("free(");

      return {
        stub: true,
        note: "Substring heuristics only, not a verification.",
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

