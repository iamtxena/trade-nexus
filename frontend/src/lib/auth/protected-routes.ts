export const PROTECTED_ROUTE_PATTERNS = [
  '/dashboard(.*)',
  '/strategist(.*)',
  '/strategies(.*)',
  '/validation(.*)',
  '/shared-validation(.*)',
  '/bots(.*)',
  '/agents(.*)',
  '/portfolio(.*)',
  '/api/validation(.*)',
  '/api/shared-validation(.*)',
  '/api/strategies(.*)',
  '/api/agents(.*)',
  '/api/predictions(.*)',
  '/api/portfolio(.*)',
  '/api/strategist(.*)',
];

export function isPathProtected(pathname: string): boolean {
  return PROTECTED_ROUTE_PATTERNS.some((pattern) => new RegExp(`^${pattern}$`).test(pathname));
}
