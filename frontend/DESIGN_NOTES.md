## 1. Reference Site Breakdown

### A. Landing Page (`/`)
- **Section Order**:
  1. Sticky Navigation Bar (Brand Wordmark, Anchor Nav links, Primary & Outline CTAs, Mobile Hamburger).
  2. Hero Section: Eyebrow pill tag with status dot, multi-line high-impact headline, sub-headline, dual CTAs (Primary solid + Secondary ghost/outline).
  3. Interactive/Visual Mock Showcase: High-fidelity stylised application interface card showing real scheduling and matrix flows.
  4. Pain Points / Contrast Matrix ("Nightmares Erased"): Multi-card grid highlighting existing workflow friction vs automated solutions.
  5. Core Capabilities / Features: 2x2 and 3-column feature cards with distinct icon badges and structured descriptions.
  6. Process Workflow ("How It Works in 4 Steps"): Numbered cards (`01`–`04`) connected with visual progression indicators and micro-descriptions.
  7. Mobile & Accessibility Feature Spotlight: Split layout (feature list on left, responsive device preview on right).
  8. Value Proposition / Metrics: Compact data counters emphasizing speed, error reduction, and operational efficiency.
  9. FAQ Accordion: Clean bordered accordion cards with subtle hover expansion.
  10. Final Call-to-Action (CTA) Band: High-contrast banner with primary action and auxiliary inquiry link.
  11. Multi-column Footer: Institutional branding, structured link groups, and copyright/legal notices.
- **Layout Patterns**:
  - Max container width constrained to `1280px` (`max-w-7xl`) with generous horizontal padding (`px-4 sm:px-6 lg:px-8`).
  - Strict vertical rhythm: `py-20` to `py-24` on desktop; `py-12` to `py-14` on mobile.
  - Multi-column grids: 4-column cards on desktop (`grid-cols-1 md:grid-cols-2 lg:grid-cols-4`), collapsing gracefully to 1 column on mobile.
- **Type Scale & Hierarchy**:
  - Display Headline: ~`48px`–`64px` (`text-4xl md:text-6xl`), tight leading (`leading-[1.1]`), bold weight (`font-extrabold`).
  - Section Headings: `30px`–`36px` (`text-2xl md:text-4xl`), tracking tight (`tracking-tight`).
  - Card Titles: `16px`–`18px` (`text-base md:text-lg`), font-semibold.
  - Body Text: `14px`–`16px` (`text-sm md:text-base`), relaxed line height (`leading-relaxed`), muted foreground.
  - Eyebrows & Badges: `11px`–`12px` (`text-xs`), uppercase tracking wide (`tracking-wider`).
- **Colour Usage & Contrast**:
  - Dominant surfaces: Pure white (`#ffffff`) and light zinc/neutral (`#f8fafc` / `#f4f4f5`) background alternating between sections.
  - High-contrast text: `#09090b` for primary headlines, `#71717a` for secondary text.
  - Restrained Accent: Deep vibrant blue/indigo (`#2563eb`) used selectively on primary buttons, badge highlights, and interactive states.
  - Semantic Status: Minimalist amber for warnings, emerald for positive confirmation, rose for rejection.
- **Component Styling**:
  - **Cards**: Subtle `1px` border (`#e2e8f0`), rounded corners (`rounded-xl` / `12px`), minimal elevation (`shadow-xs` / `shadow-sm`) transitioning on hover (`hover:shadow-md hover:-translate-y-0.5`).
  - **Buttons**: Rounded-lg or pill, `h-10` to `h-11` on desktop, crisp typography, distinct focus rings (`focus-visible:ring-2 focus-visible:ring-offset-2`).
  - **Navigation**: Frosted glass / backdrop blur (`backdrop-blur-md bg-white/80`) sticky header with subtle bottom border.

---

### B. Authentication Page (`/auth/login`)
- **Layout Patterns**:
  - Centered card container or balanced two-column presentation:
    - Side A: Brand identity panel highlighting institutional context, reassurance points, and system purpose.
    - Side B: Clean, high-focus authentication card with field labels, icon-adorned inputs, password toggles, and primary submission action.
- **Mobile Adaptability (390px)**:
  - Form card takes full width (`w-full`), side brand panel stacks or reduces to a concise banner.
  - Touch targets maintain minimum `44px` height (`h-10`–`h-11`) for finger usability.
- **Form Elements**:
  - Input fields: `h-10`, rounded-lg borders (`#e5e7eb`), clear placeholder text, focus rings matching primary brand token.
  - Clear distinction between primary credentials and secondary development/demo helpers.

---

## 2. 8–10 High-Value Patterns Worth Adapting for SVSU No-Dues

1. **High-Fidelity In-Code Dashboard Visual**:
   Instead of abstract illustrations or stock imagery, showcase a stylized, interactive mock of the actual student clearance dossier right in the landing page hero (showing the 10 parallel departments, status badges, and progress bar).
2. **Two-Column Auth Screen Layout**:
   Provide a split layout on desktop: the left side presents a polished institutional briefing panel with key workflow highlights, while the right side houses the streamlined login form.
3. **Structured 4-Step Process Timeline**:
   Connect the clearance steps (`01 Bank Details` → `02 Parallel Reviews` → `03 HoD Approval` → `04 Refund Disbursement`) with visual connector lines, step numbers, and hover lift cards.
4. **Restrained Brand Accent**:
   Introduce a single, crisp brand accent color (deep cobalt/indigo `hsl(221 83% 53%)`) used strictly for active states, key CTAs, and focus rings, leaving cards and backgrounds pure black and white.
5. **Interactive Sample Badge & Mock Notice**:
   Clearly tag mock UI previews with a "Sample Preview" badge to distinguish them from live personal data.
6. **Card Elevation Rhythm**:
   Use two distinct shadow tiers: `shadow-xs` (`0 1px 2px rgba(0,0,0,0.04)`) for resting cards and `shadow-card` (`0 4px 12px rgba(0,0,0,0.06)`) on hover or active cards, maintaining architectural minimalism.
7. **Collapsible Developer / Demo Account Section**:
   Tuck development demo email chips into a cleanly styled collapsible accordion or disclosure card so regular users experience a production-grade form while testers retain one-click convenience.
8. **Consistent Section Vertical Rhythm**:
   Standardize section spacing to `py-20 md:py-24` on desktop and `py-12 md:py-14` on mobile, eliminating awkward whitespace jumps.
9. **Accessible Focus-Visible Rings**:
   Ensure all interactive elements (buttons, inputs, links, tabs) feature explicit `:focus-visible` rings with offset, utilizing the brand accent token rather than the browser's default cyan/blue.
10. **Clean Institutional Wordmark & Sticky Blur Header**:
    Maintain a text-only, bold Syne wordmark (`SVSU NO-DUES`) inside a frosted navigation header (`backdrop-blur-md bg-white/90`) that remains pinned and readable during scroll.
