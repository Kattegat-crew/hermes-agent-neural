---
name: nextjs-app-router-expert
description: >-
  Use when building Next.js App Router apps Routes, and caching strategies.'
tags: [nextjs, app-router, react, server-actions, streaming, caching, frontend]
license: MIT
compatibility: opencode---


# Next.js App Router Expert

Patterns and best practices for Next.js (14/15+) App Router applications.

## Key Concepts
1. **Data Fetching & Caching**: Understand `fetch` cache options (`force-cache`, `no-store`, `revalidateTag`, `revalidatePath`).
2. **Server Actions**: Secure form submissions and mutations directly from components. Always validate inputs with Zod and authorize before mutating.
3. **Route Handlers**: Use `route.ts` for public REST APIs or webhooks.
4. **Streaming & Suspense**: Use `loading.tsx` and `<Suspense>` to stream slow dynamic UI without blocking the initial page shell.
5. **Metadata & SEO**: Use `generateMetadata` for dynamic OpenGraph tags and structured data.
