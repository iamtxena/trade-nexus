'use client';

import {
  AlertTriangle,
  Clock3,
  Copy,
  Fingerprint,
  KeyRound,
  Loader2,
  RefreshCw,
  RotateCw,
  ShieldAlert,
} from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type {
  CreateValidationBotInviteCodeRegistrationPayload,
  CreateValidationBotPartnerBootstrapPayload,
  ValidationBotKeyMetadataResponse,
  ValidationBotKeyRotationResponse,
  ValidationBotRegistrationResponse,
  ValidationBotSummary,
  ValidationBotUsageMetadata,
} from '@/lib/validation/types';

interface InviteCodeFormState {
  botName: string;
  inviteCode: string;
}

interface PartnerBootstrapFormState {
  botName: string;
  ownerEmail: string;
  partnerKey: string;
  partnerSecret: string;
}

interface OneTimeIssuedKeyState {
  botName: string;
  keyPrefix: string;
  rawKey: string;
  issuedAt: string;
}

const DEFAULT_INVITE_FORM: InviteCodeFormState = {
  botName: '',
  inviteCode: '',
};

const DEFAULT_PARTNER_FORM: PartnerBootstrapFormState = {
  botName: '',
  ownerEmail: '',
  partnerKey: '',
  partnerSecret: '',
};

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }
  const responsePayload = payload as {
    error?: string | { message?: string };
  };
  const errorValue = responsePayload.error;
  if (typeof errorValue === 'string' && errorValue.trim()) {
    return errorValue;
  }
  if (errorValue && typeof errorValue === 'object' && typeof errorValue.message === 'string') {
    return errorValue.message;
  }
  return fallback;
}

function toUsageLabel(usage: ValidationBotUsageMetadata | undefined): string {
  if (!usage) {
    return 'No usage telemetry yet';
  }
  const requests =
    usage.totalRequests !== undefined
      ? `${usage.totalRequests.toLocaleString()} total requests`
      : '';
  const lastSeen = usage.lastSeenAt
    ? `last seen ${new Date(usage.lastSeenAt).toLocaleString()}`
    : 'never used';
  return requests ? `${requests}, ${lastSeen}` : lastSeen;
}

function resolveKeyStatusTone(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'active') {
    return 'default';
  }
  if (status === 'revoked') {
    return 'destructive';
  }
  return 'secondary';
}

function mergeBotSummary(
  current: ValidationBotSummary[],
  registration: ValidationBotRegistrationResponse,
): ValidationBotSummary[] {
  const incoming: ValidationBotSummary = {
    ...registration.bot,
    keys: [registration.issuedKey.key],
  };
  const filtered = current.filter((bot) => bot.id !== incoming.id);
  return [incoming, ...filtered];
}

function mapBotListResponse(payload: unknown): ValidationBotSummary[] {
  if (!payload || typeof payload !== 'object') {
    return [];
  }

  const value = payload as { bots?: ValidationBotSummary[]; items?: ValidationBotSummary[] };
  if (Array.isArray(value.bots)) {
    return value.bots.map((bot) => ({
      ...bot,
      keys: bot.keys ?? [],
    }));
  }
  if (Array.isArray(value.items)) {
    return value.items.map((bot) => ({
      ...bot,
      keys: bot.keys ?? [],
    }));
  }
  return [];
}

export default function BotsPage() {
  const [bots, setBots] = useState<ValidationBotSummary[]>([]);
  const [inviteForm, setInviteForm] = useState<InviteCodeFormState>(DEFAULT_INVITE_FORM);
  const [partnerForm, setPartnerForm] = useState<PartnerBootstrapFormState>(DEFAULT_PARTNER_FORM);
  const [latestIssuedKey, setLatestIssuedKey] = useState<OneTimeIssuedKeyState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);
  const [isLoadingBots, setIsLoadingBots] = useState(false);
  const [isSubmittingInvitePath, setIsSubmittingInvitePath] = useState(false);
  const [isSubmittingPartnerPath, setIsSubmittingPartnerPath] = useState(false);
  const [isCopyingKey, setIsCopyingKey] = useState(false);
  const [rotatingBotId, setRotatingBotId] = useState<string | null>(null);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);

  const activeBots = useMemo(() => bots.filter((bot) => bot.status === 'active'), [bots]);

  const loadBots = useCallback(async () => {
    setIsLoadingBots(true);
    setErrorMessage(null);
    try {
      const response = await fetch('/api/validation/bots');
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(extractErrorMessage(payload, `Failed to load bots (${response.status})`));
        return;
      }
      setBots(mapBotListResponse(payload));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load bots.');
    } finally {
      setIsLoadingBots(false);
    }
  }, []);

  useEffect(() => {
    void loadBots();
  }, [loadBots]);

  async function handleCreateViaInviteCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmittingInvitePath(true);
    setErrorMessage(null);
    setNoticeMessage(null);

    const payload: CreateValidationBotInviteCodeRegistrationPayload = {
      botName: inviteForm.botName.trim(),
      inviteCode: inviteForm.inviteCode.trim(),
      metadata: {
        source: 'frontend-runtime-ux',
      },
    };

    if (!payload.botName || !payload.inviteCode) {
      setErrorMessage('botName and inviteCode are required.');
      setIsSubmittingInvitePath(false);
      return;
    }

    try {
      const response = await fetch('/api/validation/bots/registrations/invite-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(
            responsePayload,
            `Invite-code registration failed (${response.status})`,
          ),
        );
        return;
      }

      const registration = responsePayload as ValidationBotRegistrationResponse;
      setLatestIssuedKey({
        botName: registration.bot.name,
        keyPrefix: registration.issuedKey.key.keyPrefix,
        rawKey: registration.issuedKey.rawKey,
        issuedAt: new Date().toISOString(),
      });
      setBots((previous) => mergeBotSummary(previous, registration));
      setInviteForm(DEFAULT_INVITE_FORM);
      setNoticeMessage(`Bot ${registration.bot.name} registered with invite-code path.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to register bot.');
    } finally {
      setIsSubmittingInvitePath(false);
    }
  }

  async function handleCreateViaPartnerBootstrap(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmittingPartnerPath(true);
    setErrorMessage(null);
    setNoticeMessage(null);

    const payload: CreateValidationBotPartnerBootstrapPayload = {
      botName: partnerForm.botName.trim(),
      ownerEmail: partnerForm.ownerEmail.trim(),
      partnerKey: partnerForm.partnerKey.trim(),
      partnerSecret: partnerForm.partnerSecret.trim(),
      metadata: {
        source: 'frontend-runtime-ux',
      },
    };

    if (!payload.botName || !payload.ownerEmail || !payload.partnerKey || !payload.partnerSecret) {
      setErrorMessage('botName, ownerEmail, partnerKey, and partnerSecret are required.');
      setIsSubmittingPartnerPath(false);
      return;
    }

    try {
      const response = await fetch('/api/validation/bots/registrations/partner-bootstrap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(
          extractErrorMessage(responsePayload, `Partner bootstrap failed (${response.status})`),
        );
        return;
      }

      const registration = responsePayload as ValidationBotRegistrationResponse;
      setLatestIssuedKey({
        botName: registration.bot.name,
        keyPrefix: registration.issuedKey.key.keyPrefix,
        rawKey: registration.issuedKey.rawKey,
        issuedAt: new Date().toISOString(),
      });
      setBots((previous) => mergeBotSummary(previous, registration));
      setPartnerForm(DEFAULT_PARTNER_FORM);
      setNoticeMessage(`Bot ${registration.bot.name} registered with partner bootstrap path.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to register bot.');
    } finally {
      setIsSubmittingPartnerPath(false);
    }
  }

  async function handleRotateKey(botId: string) {
    setRotatingBotId(botId);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch(`/api/validation/bots/${botId}/keys/rotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'rotation requested from dashboard' }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(extractErrorMessage(payload, `Key rotation failed (${response.status})`));
        return;
      }

      const rotation = payload as ValidationBotKeyRotationResponse;
      setLatestIssuedKey((current) => ({
        botName: bots.find((bot) => bot.id === botId)?.name ?? 'Runtime bot',
        keyPrefix: rotation.issuedKey.key.keyPrefix,
        rawKey: rotation.issuedKey.rawKey,
        issuedAt: new Date().toISOString(),
      }));
      setBots((previous) =>
        previous.map((bot) => {
          if (bot.id !== botId) {
            return bot;
          }
          const normalizedExisting = bot.keys.map((key) =>
            key.status === 'active' ? { ...key, status: 'rotated' as const } : key,
          );
          return {
            ...bot,
            keys: [rotation.issuedKey.key, ...normalizedExisting],
          };
        }),
      );
      setNoticeMessage('Key rotated. Copy the raw key now; it will not be shown again.');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to rotate key.');
    } finally {
      setRotatingBotId(null);
    }
  }

  async function handleRevokeKey(botId: string, keyId: string) {
    setRevokingKeyId(keyId);
    setErrorMessage(null);
    setNoticeMessage(null);
    try {
      const response = await fetch(`/api/validation/bots/${botId}/keys/${keyId}/revoke`, {
        method: 'POST',
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        setErrorMessage(extractErrorMessage(payload, `Key revoke failed (${response.status})`));
        return;
      }

      const revoked = payload as ValidationBotKeyMetadataResponse;
      setBots((previous) =>
        previous.map((bot) => {
          if (bot.id !== botId) {
            return bot;
          }
          return {
            ...bot,
            keys: bot.keys.map((key) => (key.id === keyId ? revoked.key : key)),
          };
        }),
      );
      setNoticeMessage(`Key ${revoked.key.keyPrefix} revoked.`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to revoke key.');
    } finally {
      setRevokingKeyId(null);
    }
  }

  async function handleCopyLatestKey() {
    if (!latestIssuedKey?.rawKey) {
      return;
    }
    setIsCopyingKey(true);
    try {
      await navigator.clipboard.writeText(latestIssuedKey.rawKey);
      setNoticeMessage('Raw key copied to clipboard.');
    } catch {
      setNoticeMessage('Clipboard copy failed. Please copy manually.');
    } finally {
      setIsCopyingKey(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/15">
            <Fingerprint className="size-5 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Bots</h1>
            <p className="text-sm text-muted-foreground">
              User-owned runtime identities with one-time key reveal and strict revocation controls.
            </p>
          </div>
        </div>
      </div>

      {errorMessage ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      ) : null}

      {noticeMessage ? (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
          {noticeMessage}
        </div>
      ) : null}

      {latestIssuedKey ? (
        <Card className="border-amber-500/40 bg-amber-500/5 py-4">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="size-4 text-amber-600" />
              One-Time Key Display
            </CardTitle>
            <CardDescription>
              Save this raw key now. It will never be retrievable again after this view.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded-md border border-amber-500/30 bg-background p-3">
              <p className="text-xs text-muted-foreground">Bot</p>
              <p className="text-sm font-medium">{latestIssuedKey.botName}</p>
              <p className="mt-2 font-mono text-xs break-all">{latestIssuedKey.rawKey}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleCopyLatestKey}
                disabled={isCopyingKey}
              >
                {isCopyingKey ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Copying…
                  </>
                ) : (
                  <>
                    <Copy className="size-4" />
                    Copy Raw Key
                  </>
                )}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setLatestIssuedKey(null)}>
                Clear From Screen
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="py-4">
          <CardHeader>
            <CardTitle>Create Bot Identity</CardTitle>
            <CardDescription>
              Register through invite-code trial or partner key/secret bootstrap path.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="invite-code">
              <TabsList variant="line">
                <TabsTrigger value="invite-code">Invite Code</TabsTrigger>
                <TabsTrigger value="partner-bootstrap">Partner Bootstrap</TabsTrigger>
              </TabsList>
              <TabsContent value="invite-code">
                <form className="space-y-3" onSubmit={handleCreateViaInviteCode}>
                  <div className="space-y-2">
                    <Label htmlFor="invite-bot-name">Bot Name</Label>
                    <Input
                      id="invite-bot-name"
                      value={inviteForm.botName}
                      onChange={(event) =>
                        setInviteForm((previous) => ({ ...previous, botName: event.target.value }))
                      }
                      placeholder="Momentum Guard Bot"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="invite-code">Invite Code</Label>
                    <Input
                      id="invite-code"
                      value={inviteForm.inviteCode}
                      onChange={(event) =>
                        setInviteForm((previous) => ({
                          ...previous,
                          inviteCode: event.target.value,
                        }))
                      }
                      placeholder="INV-TRIAL-XXXXXX"
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isSubmittingInvitePath}>
                    {isSubmittingInvitePath ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Registering…
                      </>
                    ) : (
                      'Register Bot (Invite Code)'
                    )}
                  </Button>
                </form>
              </TabsContent>
              <TabsContent value="partner-bootstrap">
                <form className="space-y-3" onSubmit={handleCreateViaPartnerBootstrap}>
                  <div className="space-y-2">
                    <Label htmlFor="partner-bot-name">Bot Name</Label>
                    <Input
                      id="partner-bot-name"
                      value={partnerForm.botName}
                      onChange={(event) =>
                        setPartnerForm((previous) => ({
                          ...previous,
                          botName: event.target.value,
                        }))
                      }
                      placeholder="Partner Relay Bot"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="partner-owner-email">Owner Email</Label>
                    <Input
                      id="partner-owner-email"
                      type="email"
                      value={partnerForm.ownerEmail}
                      onChange={(event) =>
                        setPartnerForm((previous) => ({
                          ...previous,
                          ownerEmail: event.target.value,
                        }))
                      }
                      placeholder="trader@example.com"
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="partner-key">Partner Key</Label>
                      <Input
                        id="partner-key"
                        value={partnerForm.partnerKey}
                        onChange={(event) =>
                          setPartnerForm((previous) => ({
                            ...previous,
                            partnerKey: event.target.value,
                          }))
                        }
                        placeholder="pk_live_partner_..."
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="partner-secret">Partner Secret</Label>
                      <Input
                        id="partner-secret"
                        type="password"
                        value={partnerForm.partnerSecret}
                        onChange={(event) =>
                          setPartnerForm((previous) => ({
                            ...previous,
                            partnerSecret: event.target.value,
                          }))
                        }
                        placeholder="ps_live_partner_..."
                      />
                    </div>
                  </div>
                  <Button type="submit" className="w-full" disabled={isSubmittingPartnerPath}>
                    {isSubmittingPartnerPath ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Registering…
                      </>
                    ) : (
                      'Register Bot (Partner Bootstrap)'
                    )}
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <Card className="py-4">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Registered Bots</CardTitle>
              <CardDescription>
                Active bots: {activeBots.length} / Total: {bots.length}
              </CardDescription>
            </div>
            <Button type="button" variant="outline" disabled={isLoadingBots} onClick={loadBots}>
              {isLoadingBots ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Refreshing…
                </>
              ) : (
                <>
                  <RefreshCw className="size-4" />
                  Refresh
                </>
              )}
            </Button>
          </CardHeader>
          <CardContent>
            {isLoadingBots && bots.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                Loading bot identities…
              </div>
            ) : bots.length === 0 ? (
              <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                No bots registered yet.
              </div>
            ) : (
              <div className="space-y-3">
                {bots.map((bot) => (
                  <div key={bot.id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="font-medium">{bot.name}</p>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <span className="font-mono">{bot.id}</span>
                          <Badge variant="outline">{bot.registrationPath}</Badge>
                          <Badge variant={resolveKeyStatusTone(bot.status)}>{bot.status}</Badge>
                        </div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={rotatingBotId === bot.id}
                        onClick={() => {
                          void handleRotateKey(bot.id);
                        }}
                      >
                        {rotatingBotId === bot.id ? (
                          <>
                            <Loader2 className="size-4 animate-spin" />
                            Rotating…
                          </>
                        ) : (
                          <>
                            <RotateCw className="size-4" />
                            Rotate Key
                          </>
                        )}
                      </Button>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <Clock3 className="size-3.5" />
                        {toUsageLabel(bot.usage)}
                      </span>
                    </div>

                    <div className="mt-3 space-y-2">
                      {bot.keys.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No key metadata available.</p>
                      ) : (
                        bot.keys.map((key) => (
                          <div
                            key={key.id}
                            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border/70 bg-muted/30 px-3 py-2"
                          >
                            <div className="space-y-1 text-xs">
                              <div className="flex items-center gap-2">
                                <KeyRound className="size-3.5 text-muted-foreground" />
                                <span className="font-mono">{key.keyPrefix}</span>
                                <Badge variant={resolveKeyStatusTone(key.status)}>
                                  {key.status}
                                </Badge>
                              </div>
                              <p className="text-muted-foreground">
                                Created {new Date(key.createdAt).toLocaleString()}
                                {key.lastUsedAt
                                  ? ` • Last used ${new Date(key.lastUsedAt).toLocaleString()}`
                                  : ''}
                              </p>
                            </div>

                            {key.status === 'active' ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                disabled={revokingKeyId === key.id}
                                onClick={() => {
                                  void handleRevokeKey(bot.id, key.id);
                                }}
                              >
                                {revokingKeyId === key.id ? (
                                  <>
                                    <Loader2 className="size-4 animate-spin" />
                                    Revoking…
                                  </>
                                ) : (
                                  <>
                                    <ShieldAlert className="size-4" />
                                    Revoke
                                  </>
                                )}
                              </Button>
                            ) : null}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
