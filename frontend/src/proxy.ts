import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { type NextRequest, NextResponse } from 'next/server';

import { PROTECTED_ROUTE_PATTERNS } from '@/lib/auth/protected-routes';

const isProtectedRoute = createRouteMatcher(PROTECTED_ROUTE_PATTERNS);

function isValidationProxySmokeRoute(pathname: string): boolean {
  if (pathname === '/api/validation/runs') {
    return true;
  }
  if (/^\/api\/validation\/runs\/[^/]+$/.test(pathname)) {
    return true;
  }
  return /^\/api\/validation\/runs\/[^/]+\/artifact$/.test(pathname);
}

const clerkProtectedMiddleware = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
    if (isValidationProxySmokeRoute(req.nextUrl.pathname)) {
      return;
    }
    await auth.protect();
  }
});

async function passthroughMiddleware(_request: NextRequest) {
  return NextResponse.next();
}

const clerkDisabled = process.env.DISABLE_CLERK_MIDDLEWARE === '1';

export default clerkDisabled ? passthroughMiddleware : clerkProtectedMiddleware;

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
};
