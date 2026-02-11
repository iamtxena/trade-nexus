import { Redis } from '@upstash/redis';

export const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

export async function cacheGet<T>(key: string): Promise<T | null> {
  return redis.get<T>(key);
}

export async function cacheSet<T>(key: string, value: T, ttlSeconds = 300): Promise<void> {
  await redis.set(key, value, { ex: ttlSeconds });
}

export async function cacheDelete(key: string): Promise<void> {
  await redis.del(key);
}
