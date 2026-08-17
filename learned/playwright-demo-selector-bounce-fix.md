# Playwright Demo Recording — Selector Bounce & Below-the-Fold Output

**Extracted:** 2026-06-18
**Context:** Recording Playwright demo videos (e.g. via the `ui-demo` skill) of SPAs where a primary action button shares its visible text with a navigation item, and where the action's output renders below the fold.

## Problem
Two silent failures break demo recordings of single-page apps:

1. **Selector bounce.** A loose text selector like `button:has-text("Plan My Journey")` matches the *first* element containing that substring. If a bottom-nav / sidebar button shares similar text (e.g. a "Journey" nav tab), Playwright clicks the wrong one and the app navigates to the wrong screen (Profile, a nav route, etc.) instead of submitting. The recording completes with no error — it just shows the wrong thing.

2. **Output below the fold.** After a successful submit, the result often renders *below* the current scroll position. The video ends on an unchanged-looking viewport, so the feature appears not to work even though it did.

## Solution
1. **Anchor the selector to text unique to the real action.** Prefer the exact label including any decorative glyph the button actually renders (`✦`, icons-as-text, etc.), or scope to a container, or use `getByRole('button', { name: 'Exact Label', exact: true })`. The decorative symbol is often the cheapest disambiguator because nav items rarely repeat it.
2. **Scroll down after submit** with a smooth scroll so the cursor "moves down" and the freshly-rendered output enters the viewport.
3. **Rehearse first** (`--rehearse`): assert every selector resolves to exactly one visible element *and* that it's the intended one before recording. A passing rehearsal with the exact-text selector is the proof the bounce is gone.

## Example
```javascript
// ❌ Bounces to the "Journey" nav tab — both contain "Journey"
await moveAndClick(page, 'button:has-text("Plan My Journey")', 'Submit journey');

// ✅ Exact label with the decorative glyph the submit button actually renders
await moveAndClick(
  page,
  'button:has-text("✦ Plan My Journey")',
  'Submit journey',
  { postClickDelay: 2000 },
);

// ✅ Reveal output that renders below the fold
async function smoothScroll(page, top, ms) {
  await page.evaluate((t) => window.scrollTo({ top: t, behavior: 'smooth' }), top);
  await page.waitForTimeout(ms);
}
await smoothScroll(page, 380, 1600);
await smoothScroll(page, 820, 1600);
```

## When to Use
- Writing or fixing a Playwright demo/walkthrough script where a click "goes to the wrong page" or the recording ends on a screen that looks like nothing happened.
- Any SPA where action buttons and nav items can share visible text.
- During the **Rehearse** phase of the `ui-demo` skill — verify selectors resolve to the *intended* element, not just *an* element.
