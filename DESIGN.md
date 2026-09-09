# DESIGN.md

> Project-wide UI/UX Design System and implementation rules.
>
> This document defines the visual language, information hierarchy, component behavior, and UI quality standards for the entire application.
> It is binding for new UI work, UI refactors, and new modules.

---

## 1. Design Goal

The application should feel like a **professional creative production tool**, not a generic AI SaaS dashboard.

Core qualities:

- Minimal
- Restrained
- Professional
- Modern
- Functional
- Content-first
- Consistent
- Calm
- Production-oriented

The visual language should be closer to a mature editor / creative workstation / productivity application than to an "AI-generated dashboard".

### Core principle

> **Remove before adding.**

If a visual element is not necessary, remove it.

If an area does not need a border, do not add one.

If an area does not need a card, do not turn it into a card.

If a color has no semantic purpose, do not use it.

If an animation does not improve interaction, do not add it.

Minimalism is not about making the interface empty. It is about keeping only what has a clear purpose.

---

## 2. Anti-AI-Slop Rules

The application must avoid the common visual patterns associated with generic AI-generated interfaces.

### Avoid

- Large purple / blue gradients
- Gradient backgrounds
- Excessive glassmorphism
- Excessive blur
- Glow effects
- Neon accents
- Heavy shadows
- Excessive rounded cards
- Every section wrapped in a card
- Every module assigned a different accent color
- Oversized decorative icons
- Decorative "AI" labels
- Excessive "Magic / AI / Intelligence" visual badges
- Marketing-style hero sections inside the application
- Excessive pill-shaped controls
- Decorative illustrations without functional purpose
- Excessive animation
- Excessive border usage
- Dense card grids

### AI Slop Review

Every UI change must pass the following review:

1. Is there an unnecessary card?
2. Is there an unnecessary border?
3. Is there an unnecessary background color?
4. Is there an unnecessary shadow?
5. Is there an unnecessary gradient?
6. Is there excessive rounding?
7. Are there too many accent colors?
8. Does every section look like an isolated component?
9. Does the interface look more like a SaaS landing page than a production tool?
10. Could the UI become cleaner by removing something?

When the answer is yes, prefer **removal and simplification** over adding another visual treatment.

---

## 3. Visual Hierarchy

Use hierarchy before decoration.

Preferred hierarchy tools:

1. Layout
2. Spacing
3. Typography
4. Alignment
5. Background contrast
6. Subtle borders where necessary
7. Color
8. Shadow

Do not reverse this order by using color blocks, borders, and shadows to compensate for poor layout.

---

## 4. Surface System

The application should use a small number of surface levels.

Recommended conceptual layers:

- `background` — application background
- `surface` — normal working surface
- `surface-elevated` — dialogs, popovers, temporary elevated elements

Do not create a unique surface color for every module.

Surfaces should be visually close to each other.

Large areas should generally remain visually quiet.

---

## 5. Border Rules

Borders are structural tools, not decoration.

### Do not automatically add a border to:

- The top navigation
- The whole page
- Every panel
- Every section
- Every list item
- Every card
- Simple text/content areas

### Use borders when they have a functional purpose:

- Separating controls with ambiguous boundaries
- Input fields
- Tables
- Complex inspectors
- Resizable regions
- Dialog boundaries
- Timeline boundaries
- Explicit structural separators
- Focus / accessibility states when necessary

Default border treatment should be subtle.

---

## 6. Navigation

The top navigation is part of the application shell.

It should feel **integrated**, not like a separate rectangular container.

### Default behavior

- No obvious border
- No heavy shadow
- No gradient
- No thick background block
- Compact height
- Clear active state
- Strong alignment
- Stable spacing

Navigation items should use:

- Typography
- Spacing
- Subtle background on active/hover states
- Minimal indicators

Avoid turning every navigation item into a rounded colored pill.

---

## 7. Application Shell

The application should follow a production-tool structure:

```text
Application Shell
├── Navigation
├── Main Workspace
│   ├── Optional Project Sidebar
│   ├── Main Content
│   └── Optional Inspector / Context Panel
└── Bottom Status / Generation Area
```

The shell should be visually quiet.

Avoid:

```text
Header
↓
Card
↓
Card
↓
Card
↓
Card
↓
AI Card
↓
AI Card
```

---

## 8. Project Center

Project Center is the application's main dashboard / production cockpit.

It should communicate:

- Current project
- Overall progress
- Current stage
- Current task
- Next recommended action
- Needs Attention
- Recent generation jobs
- Phase completion

### Do not make every item a colored card.

Use:

- Typography
- Status indicators
- Progress
- Spacing
- Alignment
- Subtle surface contrast

Project phase status should use a consistent system:

- `Completed`
- `In Progress`
- `Not Started`
- `Needs Review`
- `Outdated`
- `Failed`
- `Cancelled`

### Outdated state

Dependency changes should create an explicit `Outdated` state rather than silently regenerating downstream content.

Example:

```text
Script v3 changed
    ↓
Character Assets → Outdated
Scene Assets     → Outdated
Storyboard       → Outdated
Dubbing          → Outdated
Video            → Outdated
```

The UI should show what is affected and allow selective regeneration.

---

## 9. Information Architecture

The application is a creative production workflow.

Major stages should be understandable as a continuous pipeline:

```text
Novel
  ↓
Script
  ↓
Story Bible / Assets
  ↓
Storyboard
  ↓
Dubbing
  ↓
Video
  ↓
Final Output
```

The UI should expose this workflow without making every stage visually heavy.

The user should always be able to answer:

- Where am I?
- What is complete?
- What is currently running?
- What needs review?
- What became outdated?
- What should I do next?

---

## 10. Design Tokens

All pages and components should use centralized design tokens.

Do not create one-off values unless there is a strong reason.

Conceptual tokens:

```css
--background
--surface
--surface-elevated

--foreground
--foreground-muted
--foreground-subtle

--border
--border-subtle

--accent
--accent-muted

--success
--warning
--error
--info

--radius-sm
--radius-md
--radius-lg

--space-1
--space-2
--space-3
--space-4
--space-5
--space-6
--space-8
--space-10
--space-12
```

Use the project's existing token mechanism when one already exists.

Do not introduce a second competing token system.

---

## 11. Color System

Keep the palette restrained.

### Base colors

Most of the UI should use:

- Background
- Surface
- Foreground
- Muted foreground
- Subtle border

### Accent

A single primary accent should dominate.

Accent should be used for:

- Primary actions
- Active navigation
- Focus
- Important selection
- Key progress states

Do not use accent colors as large decorative blocks.

### Semantic colors

Use semantic colors consistently:

- Success → completed / healthy
- Warning → attention / needs review
- Error → failed
- Info → neutral system information

Do not reinterpret these colors differently across pages.

---

## 12. Typography

Create one global typography hierarchy.

Recommended levels:

- Page Title
- Section Title
- Subsection Title
- Body
- Secondary
- Caption
- Label
- Metadata

Hierarchy should primarily come from:

- Font size
- Font weight
- Line height
- Spacing

Do not rely only on color differences.

Avoid oversized typography inside normal application workspaces.

---

## 13. Spacing

Use a consistent spacing scale.

Do not introduce arbitrary spacing such as:

```text
13px
17px
23px
27px
31px
```

unless it is required by an existing component system.

Prefer a tokenized spacing scale.

Spacing should be generous enough to create hierarchy but compact enough for a professional production application.

This is an application, not a marketing website.

---

## 14. Radius

Use one coherent radius system.

Default direction:

- Small to medium radius
- Consistent across components
- Functional rather than decorative

Avoid excessive large-radius cards.

Avoid making every control a pill.

Pills should be reserved for cases where the shape communicates a specific semantic concept.

---

## 15. Shadows and Elevation

Default to no shadow.

Use elevation only when an object genuinely sits above the working surface:

- Dropdown
- Popover
- Dialog
- Floating toolbar
- Context menu

Avoid shadows on ordinary panels.

Avoid layered shadows.

---

## 16. Component System

The following components must share one visual language:

- Button
- Input
- Select
- Dropdown
- Tabs
- Dialog
- Tooltip
- Toast
- Card
- Panel
- List
- Table
- Status
- Progress
- Timeline
- Empty State
- Loading State
- Error State

Do not implement page-specific versions of these components unless the behavior is genuinely different.

Prefer existing shared primitives.

---

## 17. Buttons

Buttons should communicate priority clearly.

Suggested hierarchy:

- Primary
- Secondary
- Tertiary / Ghost
- Destructive

Avoid:

- Gradient buttons
- Excessively rounded buttons
- Multiple competing primary buttons
- Large decorative CTA buttons inside normal workspaces

Use the smallest visual treatment that makes the action obvious.

---

## 18. Panels

Panels should be used when they improve workspace organization.

A panel does not automatically need:

- Border
- Shadow
- Rounded container
- Colored background

A panel can simply be defined through:

- Width
- Spacing
- Alignment
- Background level

Use structural separators only where necessary.

---

## 19. Lists and Tables

Lists should prioritize scanning efficiency.

Prefer:

```text
Title
metadata
status
action
```

over:

```text
[large colored card]
[large icon]
[large label]
[large description]
[large button]
```

For dense production data, use tables or compact lists rather than card grids.

---

## 20. Status System

All modules should use the same status vocabulary and visual treatment.

```text
Completed
In Progress
Not Started
Needs Review
Outdated
Failed
Cancelled
```

Status must be understandable without color alone.

Use:

- Icon
- Label
- Position
- Optional color

Do not rely exclusively on red / green / yellow.

---

## 21. Empty States

Empty states should explain what to do next.

Good:

```text
No characters yet

Create characters from the current script
[Create Characters]
```

Bad:

```text
Nothing here
```

Do not use large decorative illustrations unless they serve a clear product purpose.

---

## 22. Loading States

Loading should communicate actual system state.

Prefer:

- Skeletons for content loading
- Progress for known progress
- Spinner for short indeterminate operations
- Job status for long-running generation

Never fabricate progress.

For AI/media generation, use explicit states:

```text
Queued
Running
Completed
Failed
Cancelled
```

---

## 23. Error States

Errors should be actionable.

Show:

- What failed
- Why it failed when known
- Whether retry is possible
- What the user can do next

Avoid vague:

```text
Something went wrong
```

when the application actually knows the reason.

---

## 24. Generation Center

Generation is a core application workflow.

It should not be visually scattered across many unrelated AI buttons.

Central concepts:

```text
Generation Job
├── Provider
├── Model
├── Input
├── Parameters
├── Status
├── Progress
├── Result
├── Retry
├── Cancel
└── Version
```

The UI must support:

- Queue
- Running
- Completed
- Failed
- Cancelled
- Retry
- Cancel
- Preview
- Regenerate
- Version history

Do not use fake progress.

---

## 25. AI Interaction

AI should be context-aware.

Avoid a generic giant chat box taking visual priority over the actual production workspace.

AI actions should appear where they are useful:

- Script → rewrite / expand / analyze
- Character → generate variations
- Scene → generate description / assets
- Storyboard → regenerate shot
- Dubbing → regenerate dialogue
- Video → regenerate clip

AI is a tool inside the production workflow, not the entire visual identity of the application.

---

## 26. Asset Browser

Assets should be treated as production resources.

Potential categories:

- Characters
- Scenes
- Props
- Images
- Video
- Audio
- Voice
- Prompt
- Versions

The asset browser should favor:

- Search
- Filtering
- Metadata
- Status
- Version
- Preview

Avoid making every asset a large decorative card.

Use compact grids where visual preview is important and compact lists/tables where metadata is more important.

---

## 27. Dubbing / Voice Studio

Dubbing should behave like a media-production workspace.

Conceptual structure:

```text
Character
    ↓
Voice Profile
    ↓
TTS Model
    ↓
Dialogue Clip
    ↓
Audio Asset
    ↓
Timeline
```

A character, voice profile, provider, and TTS model are separate concepts.

The UI should not collapse these concepts into one generic "AI Voice" control.

Each dialogue clip should support:

- Speaker
- Voice
- Text
- Emotion / parameters
- Timeline position
- Audio asset
- Generation status
- Version
- Regenerate
- Preview

The timeline should be treated as a workspace, not as a decorative component.

---

## 28. Timeline and Media Workspace

Timeline UIs should prioritize:

- Accurate time
- Clear tracks
- Selection
- Playback
- Duration
- Clip boundaries
- Alignment
- Status

Avoid unnecessary decorative backgrounds and colored blocks.

Color should communicate meaning, not merely separate every item.

---

## 29. Animation

Animation should be subtle and functional.

Use animation for:

- State transitions
- Expanding / collapsing
- Feedback
- Dragging
- Selection
- Loading

Avoid:

- Constant floating motion
- Large entrance animations
- Excessive spring effects
- Decorative particle effects
- Animations that slow down production workflows

The interface should feel fast.

---

## 30. Accessibility

Do not sacrifice usability for minimalism.

Maintain:

- Readable contrast
- Visible focus state
- Keyboard navigation
- Clear labels
- Non-color status indicators
- Adequate hit areas

Minimal UI should still be obvious and accessible.

---

## 31. Responsive / Window Behavior

The application should remain coherent at different desktop window sizes.

Important regions should have intentional behavior:

- Navigation can compress
- Sidebars can collapse
- Inspector can collapse
- Main workspace retains priority
- Timeline can resize
- Dense controls can regroup rather than overflow

Avoid uncontrolled horizontal overflow and nested scrollbar explosions.

---

## 32. UI Review Process

Before implementing a major UI change:

### Step 1 — Audit

Inspect:

- Existing components
- Existing design tokens
- Existing layout system
- Existing CSS conventions
- Existing component library
- Existing pages

Do not assume the project is empty.

### Step 2 — Define

Before coding, define:

- Layout
- Hierarchy
- Component reuse
- Token usage
- State behavior
- Responsive behavior

### Step 3 — Implement

Modify the smallest necessary scope.

Do not rewrite the entire frontend merely to change appearance.

### Step 4 — Review

Check:

- Visual consistency
- Spacing
- Typography
- Border usage
- Radius
- Color
- Shadow
- State handling
- Accessibility
- Existing functionality

### Step 5 — AI Slop Review

Apply the anti-AI-slop checklist from Section 2.

### Step 6 — Validate

Run the project's existing:

- Type checks
- Lint
- Tests
- Build

Fix regressions before finishing.

---

## 33. Skill Usage — Mandatory for UI Work

The project has two installed skills:

- `frontend-design`
- `ui-ux`

Both should be treated as reusable expert workflows.

OpenAI's current Skills system supports reusable `SKILL.md` workflows, and Codex can discover configured skills and their usage instructions. Skills can be used automatically when relevant; explicitly invoking a skill is also supported by the skill environment. citehttps://openai.com/academy/skills/

### Which skill does what

#### `frontend-design`

Use this skill for:

- Visual design
- Layout
- Typography
- Color
- Spacing
- Component styling
- Frontend implementation
- Visual refinement
- Avoiding generic AI aesthetics

Think:

> "How should this UI look and feel?"

#### `ui-ux`

Use this skill for:

- Information architecture
- User flow
- Interaction design
- Usability
- Consistency
- UI/UX review
- Accessibility
- Empty/loading/error states
- Design quality checks

Think:

> "Is this UI structured and usable correctly?"

### When to use both

For any significant UI redesign, use both:

```text
ui-ux
    ↓
Define user flow / information architecture / interaction
    ↓
frontend-design
    ↓
Implement visual system / layout / components
    ↓
ui-ux
    ↓
Review usability / consistency / accessibility
```

For a small purely visual change, `frontend-design` may be sufficient.

For a UX or information architecture change, `ui-ux` should be involved.

For a new major page or module, use both.

### Explicit skill instructions

When starting a significant UI task, explicitly tell Codex:

```text
Use the installed `ui-ux` skill and `frontend-design` skill for this task.

First load and follow both skills' SKILL.md instructions.

Use `ui-ux` primarily for information architecture, interaction design,
usability, accessibility, and UX review.

Use `frontend-design` primarily for visual design, layout, typography,
spacing, color, component styling, and implementation.

Do not skip the skills because the task appears visually simple.
```

If the project's Codex environment exposes skills through explicit skill selection / invocation, select the corresponding skill by its exact installed name.

Do not invent or assume a skill API. Follow the invocation mechanism exposed by the current Codex environment.

---

## 34. Skill Priority

When instructions conflict:

```text
Project-specific DESIGN.md
        ↓
Project-specific AGENTS.md / DEVELOPMENT_RULES.md
        ↓
Installed UI/UX skills
        ↓
Framework / component conventions
        ↓
Individual task prompt
```

Project-specific design decisions should remain authoritative for this application.

The skills provide methodology and implementation guidance; they must not override the application's explicit design language unless the project documentation is intentionally updated.

---

## 35. Do Not Modify Business Logic

UI work should not casually modify:

- Data models
- API contracts
- AI provider logic
- Generation job logic
- Persistence
- Authentication
- Project state logic
- Generation semantics

Only make the smallest required integration changes.

If a UI requirement genuinely requires a business-logic change, identify it before implementing it.

---

## 36. No Visual Fragmentation

Every new page must look like it belongs to the same application.

Before adding a new component, ask:

- Does an existing component already solve this?
- Can an existing token express this?
- Can an existing layout pattern express this?
- Does this introduce a new color?
- Does this introduce a new radius?
- Does this introduce a new border style?
- Does this introduce a new interaction pattern?

Prefer reuse over invention.

---

## 37. Definition of Done for UI

A UI task is complete only when:

- The page follows the design system
- Existing functionality still works
- The visual language matches adjacent modules
- No unnecessary borders were introduced
- No unnecessary cards were introduced
- No unnecessary color blocks were introduced
- Typography follows the shared hierarchy
- Spacing follows the shared system
- States are handled
- Empty/loading/error states are usable
- Keyboard/focus behavior is acceptable
- The result passes the AI Slop Review
- Typecheck/lint/tests/build pass where available

---

## 38. Final Rule

> **The interface should disappear into the workflow.**

Users should notice their project, script, characters, scenes, storyboard, audio, and video—not the UI decorations around them.

Use hierarchy, spacing, typography, and interaction quality to make the product feel premium.

Do not use visual noise to make it feel premium.
