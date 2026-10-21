---
name: premium-app-ux
description: Audit and improve the complete user experience of an existing app when asked to make it feel premium, fix overlooked interaction states, unify multi-screen flows, or improve error recovery. Focus on feedback, continuity, and dependable task completion; use a visual design workflow for purely cosmetic requests.
---

# Premium App UX

Make the app feel considered throughout a real task: users understand what happened, what is happening, and what they can do next. Visual polish supports that trust. Evaluate the transitions and failure states with the same care as the main screens.

## Establish the assignment

- Follow the user's scope. For an audit, deliver evidence and recommendations without editing. For an improvement or implementation request, inspect, fix, and verify the relevant experience rather than stopping at a proposal. If invoked without a scope, start with a read-only audit of the main journey.
- Read the project's instructions and identify the current build, platform, existing components, and verification workflow before implementation. Use current versioned documentation when required by the project or by the API being changed.
- Preserve the product's identity and business rules. A request for premium UX does not imply a new visual identity, subscription system, onboarding funnel, or feature set.
- Choose the journey that matters most to the request. Trace it from entry through completion and later return. Inspect adjacent screens only where they affect that journey.

## Observe a complete journey

Use the running app when available and inspect the relevant implementation. A screenshot can establish visual observations, but cannot prove saving, recovery, accessibility, or navigation behavior. Keep observed behavior separate from code-based inference and untested hypotheses.

Identify what the person is trying to accomplish, what they have already entered or created, and where they could lose progress or confidence. For each meaningful action, record:

`Trigger -> immediate feedback -> work in progress -> result -> next action -> recovery/back/undo`

Include only applicable states: first use or empty content, loading, partial success, completion, invalid input, cancellation, denied permissions, unavailable capability, interruption, and reopening. Do not invent network errors for an entirely local action or add a loading animation to instantaneous work.

Ask at each step:

- Can the user tell whether the action started and whether it finished?
- Is the result meaningful, and is its location clear?
- Can they go back or correct a mistake without redoing unrelated work?
- Does the next screen retain their context and use familiar controls?
- If something fails, do they know what was preserved and how to proceed?

## Apply three lenses

### 1. Complete the overlooked interaction states

Replace silent or ambiguous actions with proportionate feedback. Show progress or a pending state when work takes perceptible time. Announce meaningful completion through the existing interface and accessible status mechanisms; avoid a toast for every tap.

Empty states should explain the situation and offer the relevant first action. Validation should identify the actual problem near its source and preserve valid input. Back, cancel, reset, delete, and undo should have distinct, predictable meanings. Protect work already created or entered, especially when navigating away, retrying, or replacing content.

Success must reflect the real operation. Distinguish saving locally, syncing, exporting a file, and handing a file to another app. Do not claim a file was saved or a share completed merely because a dialog opened.

### 2. Preserve continuity across screens

Walk through the screens in sequence, then revisit the task. Check that repeated actions retain the same labels, icon meanings, positions, interaction patterns, and state conventions. Prefer existing shared components and tokens when fixing an inconsistency.

Retain the selected project, input, relevant scroll position, and task progress where users reasonably expect continuity. Make the current mode and selection visible. Describe usage limits or availability accurately if they already exist; use actual counts and reset dates rather than inventing quotas or adding a paywall.

Judge consistency by meaning and behavior. Different tasks can require different layouts; do not force all screens into an identical structure.

### 3. Design useful recovery

Exercise plausible interruptions in a development or test environment. Examples include denied permissions, unavailable sensors, canceled file pickers, malformed imports, failed writes, background/resume, or a dropped connection during a network operation. Choose the cases relevant to the journey.

A recovery state should communicate the problem in plain language, say what happened to the user's work, and provide an actionable route forward. Prefer a specific correction, safe retry, alternate input method, or return to preserved work over a generic error with an OK button.

Before offering retry, account for operations that may already have succeeded. Avoid duplicate saves, submissions, charges, or exports. Keep intentional user cancellation distinct from failure. Never manufacture failures or add entertainment that delays recovery. The service-recovery idea motivates careful handling of real problems; it is not a promise that failures improve satisfaction.

## Choose and implement improvements

Keep a compact findings list with the trigger, observed behavior, user consequence, proposed correction, and evidence location. Prioritize lost work, blocked completion, misleading success, and irreversible mistakes before consistency issues and decorative details. Use qualitative severity tied to consequences; do not invent numerical quality scores.

For implementation requests, finish the changes necessary to complete the requested journey. Use the app's existing design language, components, motion, and feedback mechanisms. Add a new mechanism only when the current ones cannot express the needed state. Avoid unrelated cleanup and broad redesigns.

Preserve accessibility throughout the change: understandable labels and errors, a usable focus path, screen-reader status where needed, sufficiently large controls, legible contrast, and motion that respects platform settings. Do not convey an important state through color or haptics alone.

Do not show fabricated confidence or certainty. A sensor-based app should report only what its platform measurements justify. Calibration guidance cannot substantiate an unsupported claim of one-degree accuracy.

## Verify the changed experience

Run the current source using the repository's required workflow. Exercise the changed happy path and the relevant interruption or recovery path in the actual target interface. Check returning to the task where persistence or navigation changed. Compilation alone is not evidence of correct interaction.

Use focused automated tests when they protect consequential behavior such as preserved input, truthful completion, or preventing duplicate operations. Do not add tests merely to mirror styling or wording. Capture screenshots when useful for changed visual states; record the actual steps and outcome for behavior that screenshots cannot prove.

If runtime verification is unavailable, continue with meaningful static checks and clearly identify what remains unverified. Do not invent observations, report old builds as current evidence, or call a flow verified based only on source inspection.

## Adapt to the product

Examples to consider when relevant, not features to add automatically:

- **Compass or sensor tool:** explain unavailable readings or detected interference; preserve the project while offering recalibration or an existing manual mode. Distinguish live readings from a locked orientation.
- **Floor-plan editor:** retain the original image and edits when import or export fails; preserve completed alignment steps after a recoverable error; make reset or replacement consequences clear.
- **Form or checkout:** retain valid entries, identify the field needing correction, and check an uncertain submission before retrying.
- **Local document app:** distinguish a successful local save from a failed external export or sync, so recovery does not discard work that is already safe.

## Deliver the result

For an audit, lead with the highest-impact observed gaps, concrete corrections, and evidence limits. For implementation, state what changed, why it helps task completion, what was exercised, and any material remaining issue. Match the detail to the work; avoid ritual checklists and unsupported claims that the app is now premium.

## Origin

Inspired by Tim Gabe's [The Psychology of Premium Apps](https://www.youtube.com/watch?v=8EAYZe6y3I8), as summarized through Gemini in the originating conversation. These instructions operationalize the themes of complete interaction states, cohesive journeys, and useful recovery. They do not independently verify the video's research citations, statistics, or business results. Using the skill does not require reopening the video or Gemini.
