# Design Tokens

Drop these into `tailwind.config.ts` (extending `theme`). All colors are in OKLCH for perceptual consistency.

## Color palette

```ts
// tailwind.config.ts (extend.colors)
colors: {
  bg: {
    DEFAULT: 'oklch(0.992 0.002 250)',  // page background
    elev:    'oklch(0.975 0.004 250)',  // raised surfaces (cards, inputs)
  },
  fg: {
    DEFAULT: 'oklch(0.18 0.01 250)',    // primary text
    muted:   'oklch(0.55 0.012 250)',   // secondary text, labels
  },
  border: {
    DEFAULT: 'oklch(0.92 0.005 250)',
  },
  accent: {
    DEFAULT: 'oklch(0.55 0.18 285)',    // violet — primary accent (suburb A)
    soft:    'oklch(0.95 0.04 285)',
  },
  // Suburb B (comparator) — amber
  accentB: {
    DEFAULT: 'oklch(0.62 0.16 75)',
  },
  // Router category colors (chips, etc.) — share chroma & lightness, vary hue
  cat: {
    crime:      'oklch(0.55 0.18 25)',   // red-orange
    gis:        'oklch(0.55 0.16 235)',  // blue
    sentiment:  'oklch(0.55 0.16 75)',   // amber (note: hue 75)
    comparator: 'oklch(0.55 0.18 285)',  // violet
  },
  // Sentiment readouts
  sent: {
    pos: 'oklch(0.55 0.16 145)',
    neu: 'oklch(0.65 0.02 250)',
    neg: 'oklch(0.55 0.18 25)',
  },
}
```

For each `cat.*` color, you also want softened backgrounds for chips:
- bg: `oklch(0.96 0.04 <hue>)`
- border: `oklch(0.85 0.05 <hue>)`
- text: `oklch(0.40 0.14 <hue>)`

You can express these as Tailwind plugin utilities (`bg-cat-crime/soft`) or as direct utility classes when needed.

## Typography

```ts
// tailwind.config.ts (extend.fontFamily)
fontFamily: {
  sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
  mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
}
```

Add to `app/layout.tsx`:
```tsx
import { Inter, JetBrains_Mono } from 'next/font/google';
const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const jetbrains = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });
```

### Typography scale (where to use what)

| Use | Tailwind class | Notes |
|---|---|---|
| Page title | `text-[17px] font-semibold tracking-[-0.015em]` | Header bars |
| Suburb name (hero) | `text-2xl font-semibold tracking-[-0.02em]` | In Direction B/C heroes |
| Body / chat text | `text-[13.5px] leading-[1.65] tracking-[-0.005em]` | All conversational copy |
| Labels (uppercase) | `font-mono text-[10px] uppercase tracking-[0.08em] text-fg-muted` | Section titles like "PIPELINE", "ROUTE" |
| Numbers / scores | `font-mono` always | Use `font-mono` for ALL numbers, IDs, latency, etc. |
| Footnotes [n] | `font-mono text-[10px]` | The `<sup>` superscript style |

## Spacing & radius

- **Card radius**: `rounded-[10px]` for panels, `rounded-lg` (8px) for inner blocks, `rounded-md` (6px) for buttons/chips, `rounded-full` for pill chips
- **Section padding**: `p-[18px]` for `SectionCard`, `p-6` (24px) for hero-level cards
- **Standard gap**: `gap-3` between primitives, `gap-4` to `gap-5` between sections, `gap-2` inside chip rows

## Shadows

Keep them very subtle. Two recipes:
- Cards: none, just `border border-border`
- Floating UI (map controls, pill rail): `shadow-[0_1px_2px_rgba(0,0,0,0.04)]` or `shadow-[0_2px_8px_rgba(0,0,0,0.05)]`

## Iconography

The reference uses inline SVG paths defined in `direction-a.jsx`'s `Icon` component. For your codebase, **lucide-react** is a good drop-in: `Clock`, `Plus`, `ArrowRight`, `ChevronRight`, `X`, `BookOpen`, `Layers`. Set `strokeWidth={1.4}` for a slightly lighter feel that matches the design.

## Dark mode

Not designed yet. If you ship dark mode, invert by:
- `bg.DEFAULT` → `oklch(0.16 0.008 250)`
- `bg.elev` → `oklch(0.21 0.01 250)`
- `fg.DEFAULT` → `oklch(0.95 0.005 250)`
- `border` → `oklch(0.28 0.01 250)`
- Keep `accent` and `cat.*` the same — they have enough chroma for both modes.
