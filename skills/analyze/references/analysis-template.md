# ANALYSIS.md — {domain}

> Generated on {date} from static clone at `clones/{domain}/static-clone/`

---

## 1. Clone Inventory

| Metric | Count |
|--------|-------|
| HTML pages | {count} |
| CSS files | {count} |
| JavaScript files | {count} |
| Images | {count} |
| Fonts | {count} |
| SVGs | {count} |
| Other assets | {count} |

**Captured supplementary files:**
- `robots.txt`: {present/absent}
- `sitemap.xml`: {present/absent}
- `manifest.json`: {present/absent}
- API responses: {count} files

---

## 2. Tech Stack

### Frontend Framework

| Detection | Evidence |
|-----------|----------|
| Framework | {framework name or "Unknown"} |
| Marker | {specific attribute, script tag, or path pattern observed} |
| Confidence | {High/Medium/Low} |

### CSS Framework

| Detection | Evidence |
|-----------|----------|
| Framework | {Tailwind CSS / Bootstrap / Custom / etc.} |
| Marker | {class patterns or file references observed} |

### UI Component Libraries

| Library | Evidence |
|---------|----------|
| {library name} | {data attributes or class patterns} |

### Third-Party Services

| Service | Category | Evidence |
|---------|----------|----------|
| {service name} | {Analytics / Auth / Payments / Error Tracking / Chat} | {script source or global variable} |

---

## 3. Architecture

### Routing Pattern

| Aspect | Finding |
|--------|---------|
| Type | {SPA / SSR / SSG / Hybrid} |
| Evidence | {single HTML file with hash routes / multiple HTML files / hydration scripts} |
| URL structure | {pattern description, e.g., "/blog/[slug]", "/docs/[category]/[page]"} |

### Component Hierarchy

```
Layout
├── Navbar
│   ├── Logo
│   ├── NavLinks
│   └── MobileMenu
├── PageContent
│   ├── Hero
│   ├── FeatureGrid
│   │   └── FeatureCard (repeated)
│   ├── Testimonials
│   │   └── TestimonialCard (repeated)
│   └── CTASection
└── Footer
    ├── FooterColumns
    └── Copyright
```

### Code Splitting

| Aspect | Finding |
|--------|---------|
| Bundle count | {number of JS files} |
| Splitting strategy | {route-based / component-based / none observed} |
| Lazy loading | {yes/no, with evidence} |

### API Patterns

| Endpoint Pattern | Method | Purpose |
|------------------|--------|---------|
| {/api/v1/resource} | {GET/POST} | {description} |

---

## 4. Inferred Database Schema

| Entity | Fields (inferred) | Source |
|--------|--------------------|--------|
| {entity name} | {field1: type, field2: type, ...} | {API endpoint or JSON file} |

### Relationships

| Relationship | Evidence |
|-------------|----------|
| {entity1} has many {entity2} | {foreign key field or nested array in response} |

---

## 5. SEO Strategy

### Meta Tags by Page Type

| Page Type | Title Pattern | Description Length | Canonical |
|-----------|--------------|-------------------|-----------|
| Home | {pattern} | {char count} | {yes/no} |
| Blog post | {pattern} | {char count} | {yes/no} |
| Product | {pattern} | {char count} | {yes/no} |

### Open Graph Implementation

| Property | Coverage | Example Value |
|----------|----------|---------------|
| og:title | {X of Y pages} | {example} |
| og:description | {X of Y pages} | {example} |
| og:image | {X of Y pages} | {example URL} |
| og:type | {X of Y pages} | {website/article/product} |

### Twitter Cards

| Property | Coverage | Value |
|----------|----------|-------|
| twitter:card | {X of Y pages} | {summary/summary_large_image} |
| twitter:title | {X of Y pages} | {example} |
| twitter:image | {X of Y pages} | {example URL} |

### Technical SEO

| Factor | Status | Details |
|--------|--------|---------|
| robots.txt | {present/absent} | {key rules} |
| sitemap.xml | {present/absent} | {page count, last modified} |
| Structured data | {present/absent} | {schema types: Organization, Article, Product, etc.} |
| Heading hierarchy | {correct/issues} | {H1 count per page, nesting issues} |
| Image alt text | {X% coverage} | {total images, images with alt, images without} |
| Canonical URLs | {X% coverage} | {self-referencing, cross-domain, missing} |

### Internal Linking

| Pattern | Details |
|---------|---------|
| Main navigation | {link count, structure} |
| Footer navigation | {link count, columns} |
| Breadcrumbs | {present/absent, depth} |
| In-content links | {average per page} |

---

## 6. Design System

### CSS Custom Properties

#### Colors
```css
--primary: {value};
--primary-foreground: {value};
--secondary: {value};
--accent: {value};
--background: {value};
--foreground: {value};
--muted: {value};
--border: {value};
--destructive: {value};
--success: {value};
```

#### Typography
```css
--font-sans: {value};
--font-serif: {value};
--font-mono: {value};
--font-size-xs: {value};
--font-size-sm: {value};
--font-size-base: {value};
--font-size-lg: {value};
--font-size-xl: {value};
--font-size-2xl: {value};
--font-size-3xl: {value};
```

#### Spacing
```css
--spacing-1: {value};
--spacing-2: {value};
--spacing-4: {value};
--spacing-6: {value};
--spacing-8: {value};
--spacing-12: {value};
--spacing-16: {value};
```

#### Shadows
```css
--shadow-sm: {value};
--shadow-md: {value};
--shadow-lg: {value};
```

#### Border Radius
```css
--radius-sm: {value};
--radius-md: {value};
--radius-lg: {value};
--radius-full: {value};
```

#### Animations
```css
--transition-fast: {value};
--transition-base: {value};
--transition-slow: {value};
```

### Typography System

| Property | Values Used |
|----------|-------------|
| Font families | {list of font families loaded} |
| Font sizes | {min}px to {max}px in {count} steps |
| Font weights | {list: 400, 500, 600, 700, etc.} |
| Line heights | {values used} |

### Color Palette

| Category | Color | Hex/HSL | Usage |
|----------|-------|---------|-------|
| Brand primary | {name} | {value} | {CTA buttons, links, accents} |
| Brand secondary | {name} | {value} | {secondary buttons, hover states} |
| Text primary | {name} | {value} | {headings, body text} |
| Text muted | {name} | {value} | {captions, placeholders} |
| Background | {name} | {value} | {page background} |
| Card background | {name} | {value} | {card surfaces} |
| Border | {name} | {value} | {dividers, input borders} |
| Success | {name} | {value} | {success states} |
| Warning | {name} | {value} | {warning states} |
| Error | {name} | {value} | {error states} |

### Breakpoints

| Name | Width | Usage |
|------|-------|-------|
| Mobile | {value}px | {description} |
| Tablet | {value}px | {description} |
| Desktop | {value}px | {description} |
| Wide | {value}px | {description} |

---

## 7. Content Strategy

### Page Types

| Page Type | Count | Purpose | Key Elements |
|-----------|-------|---------|--------------|
| Home | 1 | {primary conversion} | {hero, features, testimonials, CTA} |
| Product/Feature | {count} | {feature showcase} | {feature detail, screenshots, CTA} |
| Blog | {count} | {content marketing} | {article, author, date, categories} |
| Documentation | {count} | {user education} | {sidebar nav, code blocks, search} |
| Legal | {count} | {compliance} | {privacy, terms, cookie policy} |
| Auth | {count} | {user access} | {login, signup, password reset} |

### Conversion Flows

| Flow | Entry Point | Steps | CTA Text |
|------|-------------|-------|----------|
| {primary signup} | {location} | {step count} | {button text} |
| {secondary conversion} | {location} | {step count} | {button text} |

### Social Proof Elements

| Type | Count | Location |
|------|-------|----------|
| Customer logos | {count} | {page/section} |
| Testimonials | {count} | {page/section} |
| Stats/metrics | {count} | {page/section} |
| Case studies | {count} | {page/section} |
| Trust badges | {count} | {page/section} |

---

## 8. Cloning Notes

### Fidelity Considerations
- {Note any elements that may be difficult to clone with high fidelity}
- {Note dynamic content that will appear static in the clone}
- {Note any anti-bot or rate limiting observed}

### Conversion Recommendations
- {Recommended framework for conversion and why}
- {Components that should be prioritized for extraction}
- {Data that should be made dynamic vs kept static}
