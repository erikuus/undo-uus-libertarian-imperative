# Design QA

final result: passed

## Reference and evidence

- Selected source: `/Users/erikuus/.codex/generated_images/01a08139-f87d-7023-9659-9067f002031e/exec-e589d416-969d-4e06-9376-c273616410a1.png` (1487 × 1058).
- Implementation: http://localhost:4321/.
- Desktop screenshot: `/tmp/imperative-qa/desktop.jpg`.
- Expanded desktop foldout: `/tmp/imperative-qa/foldout.jpg`.
- Mobile screenshots: `/tmp/imperative-qa/mobile.jpg` and `/tmp/imperative-qa/mobile-foldout.jpg`.
- Requested desktop CSS viewport: 1487 × 1058. Browser screenshot output: 1472 × 1047; the browser capture excludes its scrollbar and slightly scales the image. Comparison accounted for that small framing difference; no pixel-perfect claim is made.
- Requested mobile CSS viewport: 390 × 844. Browser screenshot output: 375 × 812. Also checked overflow at 320 CSS pixels. Temporary viewport overrides were reset.
- State: opening article, closed foldouts; additional expanded desktop and mobile states.
- Full-view evidence: source and updated desktop screenshot were emitted together in one comparison call. Text is readable at that scale, so separate headline crops were unnecessary. Expanded foldouts were inspected in their own screenshots.

## Findings and comparison history

- Initial implementation: [P2] body text was too small relative to the display heading, and the description's display serif was too heavy. Increased desktop body text from 18px to 22px and gave the description a lighter Georgia serif treatment. The subsequent combined comparison showed the corrected hierarchy and reading density.
- No remaining actionable P0/P1/P2 findings.
- Intentional adaptation: the retained desktop menu takes an understated right sidebar, so the article is narrower than the menu-free reference. At smaller widths the same menu labels wrap above the article. All article sections retain their original sequence.

## Required fidelity surfaces

- Typography: locally hosted DM Serif Display for large headings and quotations; DM Sans for body and controls; Georgia for the lighter description. Strong navy display hierarchy, natural wrapping, no clipping. The generated reference does not identify an exact font, so these are visual matches rather than a claim to the original typeface.
- Spacing and layout: open white page, broad margins, generous section spacing, thin rules instead of enclosing boxes. Foldouts retain their existing chevrons, with clear open, hover, and keyboard-focus states.
- Colors: navy `#09244d`, slate `#344661`, blue `#204fc0`, near-white `#fdfefe`. No gradients, shadows, or decorative imagery.
- Image quality: the selected design is typographic; no image assets are needed or substituted. Fonts are self-hosted with their OFL licenses.
- Copy: browser `main.textContent` matched the pre-edit snapshot exactly (16,702 characters), including hidden foldouts. All seven menu labels matched exactly. No content source files were edited.

## Verification

- All 11 foldouts opened by click and closed by Enter, with associated panel visibility verified.
- Desktop Substitutions and mobile Objections navigation tested; all seven menu anchors resolve to existing targets.
- Mobile expanded objection visually checked.
- No horizontal overflow at 390px or 320px.
- Browser console error check returned no errors; fonts reported loaded.
- `npm run check`: no errors, warnings, or hints.
- `npm run build`: passed.
- `git diff --check`: passed.

## Implementation checklist

- [x] Apply the selected visual direction.
- [x] Keep the menu simple and available across viewport sizes.
- [x] Preserve all text, sections, order, and foldout behavior.
- [x] Verify responsive rendering and interactions.
- [x] Leave local preview open.

## Follow-up polish

None required. QA screenshot files are temporary local session artifacts.
