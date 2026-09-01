import { initTRPC, TRPCError } from "@trpc/server";
import { ZodError } from "zod";

export interface Context {
  user?: {
    id: string;
    email: string;
    role: string;
  };
}

export const createTRPCContext = async (opts: { req?: Request }): Promise<Context> => {
  return {};
};

const t = initTRPC.context<Context>().create({
  errorFormatter({ shape, error }) {
    return {
      ...shape,
      data: {
        ...shape.data,
        zodError: error.cause instanceof ZodError ? error.cause.flatten() : null,
      },
    };
  },
});

export const router = t.router;
export const publicProcedure = t.procedure;
export const protectedProcedure = t.procedure.use(({ ctx, next }) => {
  if (!ctx.user) {
    throw new TRPCError({ code: "UNAUTHORIZED", message: "Valid auth session required" });
  }
  return next({ ctx: { ...ctx, user: ctx.user } });
});

