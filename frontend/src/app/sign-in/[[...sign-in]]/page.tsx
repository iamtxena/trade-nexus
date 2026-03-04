'use client';

import { Suspense } from 'react';
import { resolveSignInForceRedirectUrl } from '@/lib/auth/sign-in-redirect';
import { SignIn } from '@clerk/nextjs';
import { useSearchParams } from 'next/navigation';

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center" />}>
      <SignInPageContent />
    </Suspense>
  );
}

function SignInPageContent() {
  const searchParams = useSearchParams();
  const forceRedirectUrl = resolveSignInForceRedirectUrl(searchParams.get('redirect_url'));

  return (
    <div className="flex min-h-screen items-center justify-center">
      <SignIn forceRedirectUrl={forceRedirectUrl} />
    </div>
  );
}
