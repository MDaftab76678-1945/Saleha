import { router } from "./trpc";
import { astRouter } from "./routers/ast";
import { swarmRouter } from "./routers/swarm";

export const appRouter = router({
  ast: astRouter,
  swarm: swarmRouter,
});

export type AppRouter = typeof appRouter;

