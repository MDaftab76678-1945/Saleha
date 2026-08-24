---
id: "agent_test_automation_engineer"
name: "Senior Test Automation Architect"
type: "agent_profile"
version: "2.0.0"
---

# Senior Test Automation Architect Specification

## 1. Playwright E2E Test Suite with Idempotency Validation
```typescript
import { test, expect } from '@playwright/test';

test.describe('Payment Checkout Flow Test Suite', () => {
  test('should complete checkout and verify idempotency', async ({ page }) => {
    await page.goto('/checkout?item=sku_9921');
    const orderBtn = page.locator('button#submit-order');
    await expect(orderBtn).toBeVisible();

    await orderBtn.click();
    await expect(orderBtn).toBeDisabled();

    const successToast = page.locator('[data-testid="order-success-toast"]');
    await expect(successToast).toContainText('Order Confirmed');
  });
});
```

