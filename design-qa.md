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
- Refinement evidence: the revised opening article and an expanded Substitutions foldout were captured and inspected in the in-app browser after the September 8 typography and surface update. The browser did not expose a new local screenshot path; the captures are present in the current task's visual evidence.

## Findings and comparison history

- Initial implementation: [P2] the description's display serif was too heavy. It received a lighter Georgia serif treatment.
- User refinement: the 22px body setting was visually too large for sustained reading. Reduced desktop body text to 18px, medium-width text to 17.2px, the display title to a 118px maximum, section headings to a 50.4px maximum, and prominent quotations to a 44px maximum. The revised browser capture shows more comfortable line length and density without losing the selected hierarchy.
- User refinement: internal rules produced too much visual noise. Removed quotation rules, lemma-row rules, and accordion rules. Major `h2` boundaries retain a thin rule; the compact menu and footer retain their boundary rules because they separate regions.
- User refinement: foldouts now use a light gray `#f2f4f7` surface, 6.4px corners, 10.4px gaps, and a slightly darker hover surface. Open and closed states remain visually distinct.
- Annotation refinement: removed the darker hover surface from foldout buttons. Hover now keeps the same `#f2f4f7` background and changes only the text color.
- Annotation refinement: restored the blue left rule on highlighted quotations and reduced their scale. General callouts now top out at 27.2px and the primary Imperative callout at 31.2px, keeping both clearly below nearby section-title sizes.
- No remaining actionable P0/P1/P2 findings.
- Intentional adaptation: the retained desktop menu takes an understated right sidebar, so the article is narrower than the menu-free reference. At smaller widths the same menu labels wrap above the article. All article sections retain their original sequence.

## Required fidelity surfaces

- Typography: locally hosted DM Serif Display for large headings and quotations; DM Sans for body and controls; Georgia for the lighter description. Strong navy display hierarchy, natural wrapping, no clipping. The generated reference does not identify an exact font, so these are visual matches rather than a claim to the original typeface.
- Spacing and layout: open white page, broad margins, generous section spacing, thin section rules, and a restrained blue rule marking quotations. Foldouts use separate light gray surfaces with small rounded corners and retain their chevrons, open state, text-only hover state, and keyboard focus.
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
- September 8 refinement: opening layout and expanded foldout visually inspected after hot reload; `npm run check` and `npm run build` passed again.

## Implementation checklist

- [x] Apply the selected visual direction.
- [x] Keep the menu simple and available across viewport sizes.
- [x] Preserve all text, sections, order, and foldout behavior.
- [x] Verify responsive rendering and interactions.
- [x] Leave local preview open.

## Follow-up polish

None required. QA screenshot files are temporary local session artifacts.
