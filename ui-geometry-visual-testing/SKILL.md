---
name: ui-geometry-visual-testing
description: >-
  Validate and debug web UIs using deterministic DOM geometry, overlap and overflow
  detection, alignment and centering checks, responsive viewport analysis,
  animation and layout-shift sampling, transformed/3D geometry, stacking and
  hit-testing evidence, accessibility checks, screenshots, and optional AI vision
  review. Use this skill whenever an agent is building, reviewing, testing,
  debugging, or fixing a web UI, especially when screenshot-only inspection is
  missing layout, animation, responsive, or interaction defects.
---

# UI Geometry & Visual Testing Skill

## Purpose

Use this skill when building, reviewing, or fixing web UIs. The goal is to catch UI problems that screenshots alone often miss by combining:

1. deterministic browser/DOM geometry checks,
2. temporal checks across animation frames,
3. responsive viewport checks,
4. accessibility and interaction checks,
5. visual regression,
6. AI/vision review only where deterministic rules cannot decide.

The agent must treat the test harness as an additional source of truth. Do not rely on visual inspection alone.

---

## Core Principle

**Test the rendered UI as geometry + behavior + time, not just as an image.**

Whenever possible:

- Measure first.
- Report exact coordinates and deviations.
- Distinguish real violations from intentional parent/child containment.
- Use screenshots as evidence, not as the only oracle.
- Use AI judgment for subjective visual quality, not for problems that can be measured deterministically.

---

# Operating Workflow

When asked to test or fix a UI:

1. Start the application.
2. Use Playwright or an equivalent real browser.
3. Enumerate relevant interactive and visible elements.
4. Collect DOM, computed-style, accessibility, and geometry data.
5. Run deterministic geometry rules.
6. Run viewport/responsive tests.
7. If animations or transitions exist, sample multiple points in time.
8. Inspect CSS transforms and stacking contexts for 3D/transformed UIs.
9. Capture screenshots at important states.
10. Run visual comparison and AI visual review only after deterministic checks.
11. Produce a structured failure report.
12. Give the coding agent the smallest actionable failure set.
13. After a fix, rerun the affected tests and nearby regression tests.

Never declare a UI healthy solely because one screenshot looks correct.

---

# Recommended Tooling

Preferred browser automation:

- Playwright

Useful supporting checks:

- browser DOM APIs such as `getBoundingClientRect()`
- `getComputedStyle()`
- Playwright accessibility snapshots / accessibility assertions where available
- axe or equivalent accessibility tooling
- screenshot comparison / pixel diff for visual regression

The skill is tool-agnostic. Adapt commands to the repository's existing stack rather than forcing a new framework when one already exists.

---

# 1. Element Discovery

For visible elements that matter to layout or interaction, collect:

```ts
{
  selector,
  role,
  tagName,
  text,
  visible,
  enabled,
  rect: {
    x,
    y,
    width,
    height,
    top,
    right,
    bottom,
    left
  },
  computed: {
    display,
    position,
    overflow,
    overflowX,
    overflowY,
    zIndex,
    opacity,
    visibility,
    transform,
    transformOrigin,
    perspective,
    perspectiveOrigin,
    fontSize,
    lineHeight,
    textAlign,
    whiteSpace
  },
  parentSelector
}
```

Do not blindly inspect every DOM node. Ignore nodes that are not rendered or are irrelevant to layout unless they are involved in an observed problem.

---

# 2. 2D Bounding-Box Engine

Use `element.getBoundingClientRect()` as the first-level geometry source.

Represent each element as:

```text
x1 = left
x2 = right
y1 = top
y2 = bottom
```

Two rectangles intersect when their areas overlap with non-zero area.

## Exclusions

Do NOT report normal containment as an overlap bug when:

- one element is an ancestor of the other,
- the overlap is required by a known component pattern,
- the element is a background/decorative layer,
- the element is intentionally positioned over another element.

When possible, use DOM relationships and stacking information before reporting a collision.

## Collision Severity

Use approximately this classification:

- **Critical**: interaction blocked, important content inaccessible, modal/dialog broken, major viewport overflow.
- **High**: unrelated content overlaps, text/button collision, navigation collision, primary control partially hidden.
- **Medium**: spacing/alignment collision with visible degradation.
- **Low**: minor decorative or subpixel deviation.

Report the intersection size whenever possible.

Example:

```text
OVERLAP: HIGH
A: .card-title
B: .card-actions
Intersection: 18px × 7px
Viewport: 390×844
```

---

# 3. Containment and Overflow

Check whether important content escapes its intended container.

Examples:

- text extends outside card
- button extends outside panel
- child escapes a clipped container unexpectedly
- fixed/absolute content extends beyond viewport
- horizontal page scrolling appears on a viewport where it should not

Use tolerance for subpixel rendering, typically around 1–2 CSS pixels unless the project has a stricter requirement.

Report both the expected container and the offending element.

Example:

```text
OVERFLOW: HIGH
Element: .profile-card .title
Container: .profile-card
Right overflow: 23px
Bottom overflow: 0px
```

---

# 4. Alignment and Centering

Detect repeated alignment patterns among siblings and related elements.

Useful checks:

- left-edge alignment
- right-edge alignment
- top-edge alignment
- baseline/vertical alignment where measurable
- horizontal centering
- vertical centering
- equal-width or equal-height groups
- consistent gaps

Do not enforce centering on every element. Infer expected alignment from:

1. sibling patterns,
2. container CSS (`justify-content`, `align-items`, `place-items`, grid alignment),
3. repeated components,
4. explicit design/test metadata when available.

For vertical centering in a container:

```text
expectedCenter = container.top + (container.height - element.height) / 2
actualCenter   = element.top
```

Use center-coordinate comparison rather than raw top-coordinate comparison.

Example failure:

```text
ALIGNMENT: MEDIUM
Element: .hero-title
Expected vertical-center deviation: ≤ 4px
Observed deviation: 19px
```

---

# 5. Spacing and Consistency

Where repeated components exist, compare:

- gap between siblings
- padding within comparable components
- column spacing
- row spacing
- button spacing
- heading-to-content spacing

Do not flag a spacing inconsistency unless there is a meaningful repeated pattern or an explicit design rule.

Prefer relative consistency over hard-coded universal numbers.

---

# 6. Responsive Testing

Test multiple viewport sizes, at minimum when relevant:

```text
320×568
375×667
390×844
768×1024
1024×768
1280×800
1440×900
1920×1080
```

Adapt this set to the application's supported breakpoints and target devices.

At every viewport, check:

- page-level horizontal overflow
- clipped content
- overlap
- text wrapping into unusable regions
- buttons/inputs leaving the viewport
- navigation/sidebar collisions
- dialog/modal bounds
- sticky/fixed elements covering content unexpectedly
- unexpected disappearance of important content
- touch target dimensions for interactive controls

A page must not be considered responsive merely because it technically shrinks.

---

# 7. Interaction-State Geometry

Test layout after interactions, not only on initial load.

Examples:

- open dropdown
- open modal
- expand accordion
- open mobile navigation
- focus an input
- show validation error
- show loading state
- show toast/notification
- hover/focus/active state when applicable
- toggle dark/light theme when supported

After each important state change, rerun geometry checks for affected regions.

---

# 8. Animation and Transition Testing

A single screenshot is insufficient for animated UI.

## Sampling

For each significant animation, inspect multiple points in time, for example:

```text
0ms
50ms
100ms
200ms
300ms
500ms
800ms
1000ms
```

Use a smaller or adaptive sample set when animation duration is known.

Capture at least:

- bounding boxes
- visibility
- opacity
- transforms
- computed styles
- stacking state where relevant

## Animation Failures

Detect:

- element leaving the intended viewport/container
- temporary overlap during motion
- clipping during motion
- abrupt position jumps
- unexpected disappearance
- animation ending outside the target position
- layout shift caused by animation
- interactive element becoming inaccessible during transition

Example:

```text
ANIMATION FAILURE: HIGH
Element: .mobile-menu
Time: 240ms
Observed right edge: -31px
Expected: >= 0px
Issue: menu leaves viewport during transition
```

## Layout Shift Tracking

Compare geometry between samples.

For each important element calculate approximately:

```text
Δx
Δy
Δwidth
Δheight
```

Flag large unexpected shifts, especially when they occur without an interaction that should cause them.

Distinguish intentional animation from accidental layout shifts.

---

# 9. Animation Quality Heuristics

Deterministic tests can catch geometry bugs, but animation quality can also require subjective review.

Use AI/vision review for questions such as:

- Does the transition feel abrupt?
- Is the motion visually confusing?
- Is the focal element being obscured?
- Is motion hierarchy appropriate?

Do NOT ask the vision model to rediscover simple rectangle collisions if geometry data can answer them directly.

---

# 10. 3D and CSS Transform Testing

For transformed UIs inspect:

- `transform`
- `transform-origin`
- `perspective`
- `perspective-origin`
- transform-related computed styles
- stacking contexts

A normal 2D bounding rectangle is useful but can be insufficient for transformed geometry.

For 3D/transformed elements:

1. determine whether a transform is active,
2. inspect the transform matrix when available,
3. reason about transformed/projected bounds,
4. compare projected bounds to the viewport/container,
5. inspect clipping and stacking behavior.

Detect:

- transformed element clipped unexpectedly
- rotated card extending outside its viewport/container
- perspective effect causing content to disappear
- transformed controls moving outside the intended interaction region
- unexpected transformed overlap

If exact 3D geometry cannot be derived robustly from available browser information, report the limitation and fall back to screenshot/vision review rather than inventing certainty.

---

# 11. Stacking Context and Occlusion

For layered interfaces inspect:

- `position`
- `z-index`
- stacking-context boundaries
- transforms
- opacity
- filters
- positioned ancestors

Do not assume a larger numeric `z-index` always wins globally. Stacking contexts matter.

Useful checks:

- modal should visually cover underlying page
- dropdown should appear above its intended content
- tooltip should not be hidden behind a sibling layer
- sticky header should not unintentionally cover critical content
- full-screen overlays should actually intercept input when intended

When possible, validate by interaction as well as computed styles.

---

# 12. Text-Specific Checks

Check:

- text outside parent bounds
- clipped text
- unexpected ellipsis
- excessive wrapping
- single-word overflow
- heading/button collision
- text vertically misaligned with an icon/control
- line-height creating visible clipping

For centering, compare the rendered text box rather than assuming the font's visual glyphs occupy the entire box.

Text measurement should allow small rendering tolerances.

---

# 13. Interactive Control Checks

For buttons, links, inputs, and other controls verify:

- visible and reachable
- not obscured by unrelated elements
- not clipped
- adequate size for target platform
- focus state remains visible
- disabled/loading state does not create unusable geometry
- label or accessible name exists

If a control appears to work visually but cannot receive pointer/keyboard input, treat that as a functional/UI failure.

---

# 14. Accessibility

Run accessibility checks in addition to visual checks.

At minimum investigate:

- accessible name
- labels for inputs
- keyboard focus visibility
- keyboard reachability
- heading structure when relevant
- contrast where supported by the chosen tool
- touch target sizing where applicable

Accessibility failures should be reported separately from purely visual failures.

---

# 15. Screenshot / Vision Layer

Use screenshot comparison for:

- unexpected visual regressions
- color/theme changes
- visual hierarchy regressions
- icon/illustration changes
- typography appearance
- decorative spacing not captured by deterministic rules

Use a vision-capable model after deterministic checks.

Prompt the vision model with:

1. screenshot,
2. viewport dimensions,
3. known deterministic violations,
4. task/design intent if available,
5. instruction to identify only additional likely problems.

Do not let the vision model overwrite objective geometry findings.

---

# 16. Test Contract / Metadata

Support optional per-element metadata so teams can express intent without writing every possible rule.

Examples:

```html
<div data-ui-test="card" data-ui-align="center">
```

```html
<button data-ui-test="primary-action">
```

Possible metadata:

- `data-ui-test`
- `data-ui-align`
- `data-ui-contained`
- `data-ui-ignore-overlap`
- `data-ui-ignore-spacing`
- `data-ui-viewport`
- `data-ui-expected-state`

Metadata should refine the generic engine, not replace it.

---

# 17. Ignore Rules

The engine must avoid noisy false positives.

Common intentional overlap:

- parent and child
- icon layered inside button
- badge positioned over avatar/card
- decorative background layers
- absolute-positioned ornaments
- intentionally overlapping hero elements

Allow narrow, explicit ignore rules and require a reason where practical.

Never create a global "ignore all overlap" escape hatch.

---

# 18. Failure Report Format

Always produce a machine-readable and human-readable summary.

Preferred structure:

```text
UI TEST RESULT: FAILED

Page: /dashboard
Viewport: 390×844
State: Mobile navigation open

[GEOMETRY]
HIGH  .nav ↔ .main-content
Intersection: 42×96px

[OVERFLOW]
HIGH  .hero-title
Right overflow: 18px

[ALIGNMENT]
MEDIUM .profile-name
Vertical deviation: 14px

[ANIMATION]
HIGH .mobile-menu
At 240ms: leaves viewport by 31px

[3D]
MEDIUM .hero-card
Projected bounds exceed container by 22px

[ACCESSIBILITY]
HIGH button "Save"
No accessible name

[VISUAL]
MEDIUM vision review suggests inconsistent card spacing

Recommended next action:
Fix mobile navigation collision and hero-title overflow first.
```

When possible include:

- selector
- URL
- viewport
- UI state
- exact coordinates
- expected vs observed values
- screenshot path
- severity
- confidence

---

# 19. Agent Fix Loop

When failures are found, the coding agent should:

1. Fix the highest-severity deterministic failures first.
2. Avoid changing unrelated components.
3. Rerun the failing test.
4. Rerun adjacent regression tests.
5. Compare before/after screenshots when useful.
6. Stop when the failure is resolved or when the remaining issue is genuinely subjective/ambiguous.

Do not hide a test failure by weakening the test unless the original assertion was demonstrably incorrect.

If an ignore rule is necessary, add a narrow rule and explain why.

---

# 20. Suggested Repository Layout

```text
ui-tests/
├── specs/
│   ├── login.spec.ts
│   ├── dashboard.spec.ts
│   └── settings.spec.ts
├── geometry/
│   ├── boxes.ts
│   ├── collisions.ts
│   ├── alignment.ts
│   ├── overflow.ts
│   ├── transforms.ts
│   ├── animation.ts
│   └── stacking.ts
├── visual/
│   ├── snapshots/
│   └── diffs/
├── reports/
└── config.ts
```

Suggested commands:

```bash
npm run ui:test
npm run ui:test -- --project=chromium
npm run ui:test -- dashboard.spec.ts
```

Adapt commands to the project.

---

# 21. Example Geometry Pseudocode

```ts
function intersects(a, b, tolerance = 0) {
  return (
    a.left < b.right - tolerance &&
    a.right > b.left + tolerance &&
    a.top < b.bottom - tolerance &&
    a.bottom > b.top + tolerance
  );
}
```

Then filter out intentional ancestor/descendant relationships before reporting a collision.

For containment:

```ts
function overflow(child, parent, tolerance = 1) {
  return {
    left: parent.left - child.left > tolerance,
    right: child.right - parent.right > tolerance,
    top: parent.top - child.top > tolerance,
    bottom: child.bottom - parent.bottom > tolerance,
  };
}
```

Use these as conceptual examples, not universal production implementations.

---

# 22. Critical Design Rule

**Never make the coding agent infer from pixels what the browser can tell you directly.**

Bad:

```text
"Look at the screenshot and determine whether anything overlaps."
```

Better:

```text
"Here are the rendered element rectangles and DOM relationships. Find
unintentional intersections, then use the screenshot only to validate
visual context."
```

Likewise:

Bad:

```text
"Does the animation look broken?"
```

Better:

```text
"At 0, 100, 200, 300, and 500ms, compare position, bounds, visibility,
transform, and collisions. Report violations. Then optionally judge visual quality."
```

---

# 23. Definition of Done

A UI task is complete only when:

- functional interaction tests pass,
- geometry checks pass,
- responsive viewport checks pass,
- important animation states pass,
- transformed/3D regions have been checked where relevant,
- accessibility checks pass or known exceptions are documented,
- visual regression is acceptable,
- remaining AI/vision findings have been reviewed,
- no test was weakened merely to make the suite green.

The objective is not perfect pixel identity. The objective is **stable, usable, correctly laid-out, accessible UI across space, time, and interaction state**.

---

# 24. Browser Adapter Architecture

Keep browser collection separate from the pure analysis engine.

Preferred architecture:

```text
Browser adapter
   ↓
Raw UI snapshot(s)
   ↓
Pure analysis engine
   ↓
Findings
   ↓
Reporter / agent feedback
```

The analysis engine must not depend on Playwright, Selenium, WebDriver, or any browser runtime. This makes it unit-testable and portable.

Support adapters in this order:

1. Playwright Chromium/Firefox/WebKit when already available.
2. An equivalent WebDriver-compatible browser when available.
3. Synthetic fixture input for deterministic engine tests when a real browser is unavailable.

Never pretend a synthetic test is equivalent to real-browser end-to-end validation. Report the execution mode explicitly:

```text
Execution mode: REAL_BROWSER
```

or

```text
Execution mode: SYNTHETIC_ENGINE
Browser E2E: NOT AVAILABLE
```

A missing browser must not prevent the geometry engine from being validated, but it must not be hidden either.

---

# 25. Deterministic Animation Capture Protocol

Do not rely on arbitrary sleeps such as `sleep(500)` when a deterministic clock is possible.

Preferred approaches:

1. Disable motion when testing static layout if the test is specifically about static layout.
2. For animation testing, explicitly sample the animation timeline.
3. Prefer controlling animation duration, delay, or a test clock when the application permits it.
4. Otherwise sample with `requestAnimationFrame` and record the actual timestamp.

Capture a frame record like:

```ts
{
  time: 203,
  elements: [
    {
      id: "mobile-menu",
      rect: { ... },
      transform: "...",
      opacity: 0.72,
      visible: true
    }
  ]
}
```

For each frame:

- run normal collision checks,
- run viewport/container overflow checks,
- record transformed geometry,
- record visibility and opacity,
- optionally record hit-testing results for important controls.

An animation fails when a forbidden state occurs at any sampled time, even if the final frame is correct.

---

# 26. Animation-Specific Test Categories

Treat these as separate checks:

### A. Motion bounds

The animated element must remain within its permitted viewport/container during the animation unless the design explicitly allows it to leave.

### B. Collision during motion

Check intersections at every sampled frame, not only the first and last frame.

### C. Final-state correctness

At the end of the animation the element must reach its intended final geometry.

### D. Layout stability

A transform animation should not unexpectedly change document flow. Flag large geometry changes in unrelated siblings unless explicitly expected.

### E. Interaction safety

A control must not become unreachable or permanently covered during an interaction-critical transition.

### F. Reduced-motion behavior

When the application supports reduced motion, verify that the UI still reaches the same meaningful end state without depending on animation completion.

---

# 27. Transform and 3D Geometry Protocol

When a browser exposes transformed quadrilateral geometry, prefer it over approximating a rotated element with its untransformed DOM rectangle.

Use, when available:

- `Element.getBoxQuads()`
- `DOMQuad`
- `DOMMatrix` / `DOMMatrixReadOnly`
- `getBoundingClientRect()` as the final projected axis-aligned fallback

For an element with a transform:

1. obtain its actual rendered quad when available,
2. otherwise derive a transformed quad from its local rectangle and transform matrix,
3. project to viewport coordinates,
4. calculate the enclosing projected rectangle,
5. test viewport/container boundaries,
6. perform separate occlusion/hit-testing checks.

Do not describe an AABB collision as a definitive 3D collision. A rotated/3D element can have overlapping axis-aligned bounds without its visible polygons actually colliding.

When exact polygon intersection is required, use convex-quad intersection or separating-axis testing on the projected quads.

---

# 28. 3D Occlusion and Hit-Testing

`z-index` alone is not a proof of visual ordering.

For important interactive layers, supplement CSS inspection with hit-testing.

For a representative point inside an interactive element, use browser hit testing such as:

```js
const top = document.elementFromPoint(x, y);
```

For larger elements sample multiple points, for example:

- center,
- four inset corners,
- edge midpoints for irregular/high-risk overlays.

Report when an intended interactive element is covered by an unrelated element.

Example:

```text
OCCLUSION: HIGH
Target: #checkout-button
Hit-test at center returns: .promo-overlay
Expected topmost interactive element: #checkout-button
```

This is stronger than guessing from `z-index` values.

---

# 29. Test Fixture Strategy

A validation suite for this skill must contain both known failures and known legitimate UI patterns.

Minimum fixture categories:

```text
collision
false-positive-containment
overflow
alignment
centering
spacing
responsive
small-touch-target
animation-shift
animation-collision
transform-2d
transform-3d-or-projected
stacking/occlusion
accessibility
combined-regression
```

Each fixture should contain several intentional cases and several traps that must NOT be reported.

Examples of legitimate traps:

- icon inside button,
- badge over avatar,
- decorative overlay,
- parent containing child,
- intentionally overlapping hero decoration,
- modal backdrop covering the page by design.

The validator should verify both detection and non-detection.

---

# 30. Ground-Truth Validation and Metrics

A skill validation test must not simply assert that a command exits successfully.

Keep explicit ground truth for each fixture:

```json
{
  "expected": [
    {"type": "collision", "a": "title", "b": "actions"},
    {"type": "overflow", "element": "hero-title"}
  ],
  "forbidden": [
    {"type": "collision", "a": "button", "b": "icon"}
  ]
}
```

Measure at least:

- true positives,
- false positives,
- false negatives,
- total cases passed.

For larger suites calculate precision and recall.

Do not allow a regression in false-positive rate to be hidden by improving only true-positive count.

---

# 31. Minimal Validation Command

The skill package should provide a dependency-light validation command that validates the analysis core without a browser.

Example:

```bash
node validation/test/run-validation.js
```

The command must:

1. load deliberately broken fixtures,
2. run the pure analysis engine,
3. verify required findings exist,
4. verify forbidden false positives do not exist,
5. print a readable report,
6. exit non-zero on failure.

A separate optional browser smoke test should validate real DOM collection whenever a browser runtime is already installed.

---

# 32. Browser E2E Validation Command

When Playwright or another supported browser runtime is available, run a real-browser fixture.

Example:

```bash
npx playwright test
```

The browser fixture should intentionally contain at least:

- one real overlap,
- one legitimate parent/child intersection,
- one overflow case,
- one alignment error,
- one interactive target,
- one transformed element.

Collect the real browser rectangles and compare the analyzer's findings to ground truth.

If browser startup fails because of environment restrictions, preserve the deterministic validation result and clearly report the unavailable E2E layer.

---

# 33. Regression Rules for the Agent

After modifying the geometry engine:

1. run all pure-engine validation cases,
2. run the affected fixture categories,
3. run browser smoke tests when available,
4. inspect false-positive traps,
5. only then modify the skill instructions if the old rule was wrong.

Do not "fix" a failing validation by weakening an assertion without identifying why the original expected result was incorrect.

If a new legitimate UI pattern creates a false positive, prefer:

1. improve relationship/semantics inference,
2. add a narrow metadata rule,
3. add a fixture proving the exception,
4. document why the exception exists.

Never add a blanket ignore rule to make the suite green.

---

# 34. Completion Criteria for This Skill

A complete implementation of this skill should be able to demonstrate all of the following:

```text
[PASS] 2D collision detection
[PASS] ancestor/descendant false-positive suppression
[PASS] viewport overflow detection
[PASS] container overflow detection
[PASS] sibling alignment detection
[PASS] centering detection
[PASS] touch-target sizing
[PASS] temporal/layout-shift detection
[PASS] collision during animation
[PASS] transformed/projected overflow
[PASS] interaction-state geometry checks
[PASS] stacking/occlusion strategy defined
[PASS] deterministic ground-truth validation
[PASS] browser adapter separation
[PASS] explicit browser-unavailable reporting
```

Animation quality and subjective visual quality may additionally require human/vision review; they should not be declared solved merely because deterministic geometry checks pass.

---

# 35. Final Agent Behavior

When this skill is invoked, the agent should think in this order:

```text
1. What state is the UI in?
2. What does the browser report about actual geometry?
3. Which relationships are intentional?
4. What deterministic rule can prove a violation?
5. Does the problem exist across viewports or time?
6. Is a transform/stacking context involved?
7. Can hit-testing prove occlusion?
8. What remains subjective?
9. Use screenshots/vision for the remainder.
10. Return exact, actionable failures.
```

The goal is not to make the agent "look harder at screenshots." The goal is to give the agent better evidence so it can reason and fix with confidence.
