import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';
import { type NextRequest, NextResponse } from 'next/server';

const isProtectedRoute = createRouteMatcher([
  '/dashboard(.*)',
  '/strategist(.*)',
  '/strategies(.*)',
  '/validation(.*)',
  '/agents(.*)',
  '/portfolio(.*)',
  '/api/validation(.*)',
  '/api/strategies(.*)',
  '/api/agents(.*)',
  '/api/predictions(.*)',
  '/api/portfolio(.*)',
  '/api/strategist(.*)',
]);

const clerkProtectedMiddleware = clerkMiddleware(async (auth, req) => {
  if (isProtectedRoute(req)) {
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
