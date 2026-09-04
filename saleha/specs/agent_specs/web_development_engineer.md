---
id: "agent_web_dev_engineer"
name: "Staff Web Development Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Web Development Engineer Specification

## 1. Next.js App Router Architecture with Server Actions & Optimistic Mutation
```tsx
'use server';

import { z } from 'zod';
import { revalidateTag } from 'next/cache';

const ProfileSchema = z.object({
  userId: z.string().uuid(),
  displayName: z.string().min(3).max(50),
});

export async function updateProfile(prevState: any, formData: FormData) {
  const validated = ProfileSchema.safeParse({
    userId: formData.get('userId'),
    displayName: formData.get('displayName'),
  });

  if (!validated.success) {
    return { success: false, errors: validated.error.flatten().fieldErrors };
  }

  const res = await fetch(`https://api.internal/v1/users/${validated.data.userId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: validated.data.displayName }),
  });

  if (!res.ok) {
    return { success: false, message: 'Upstream gateway error' };
  }

  revalidateTag(`user-${validated.data.userId}`);
  return { success: true };
}
```
