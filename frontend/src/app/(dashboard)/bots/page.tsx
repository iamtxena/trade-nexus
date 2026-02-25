'use client';

import {
  AlertTriangle,
  Clock3,
  Copy,
  Filter,
  Fingerprint,
  KeyRound,
  Loader2,
  RefreshCw,
  RotateCw,
  ShieldAlert,
  UserRound,
} from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  type ValidationBotListFilter,
  applyValidationBotKeyRevocation,
  applyValidationBotKeyRotation,
  filterValidationBots,
  formatValidationBotTimestamp,
  mapValidationBotListResponse,
  mergeValidationBotSummary,
  resolveValidationBotKeyStateCounts,
  resolveValidationBotOwnershipLabel,
  resolveValidationBotRegistrationPathLabel,
  toValidationBotUsageLabel,
} from '@/lib/validation/bot-ux-state';
import type {
  CreateValidationBotInviteCodeRegistrationPayload,
  CreateValidationBotPartnerBootstrapPayload,
  ValidationBotKeyMetadataResponse,
  ValidationBotKeyRotationResponse,
  ValidationBotRegistrationResponse,
  ValidationBotSummary,
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

const BOT_FILTER_OPTIONS: Array<{ value: ValidationBotListFilter; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'revoked', label: 'Revoked' },
];

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

function resolveKeyStatusTone(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'active') {
    return 'default';
  }
  if (status === 'revoked') {
    return 'destructive';
  }
  return 'secondary';
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
  const [botFilter, setBotFilter] = useState<ValidationBotListFilter>('all');
  const [botSearchQuery, setBotSearchQuery] = useState('');

  const activeBots = useMemo(() => bots.filter((bot) => bot.status === 'active'), [bots]);
  const visibleBots = useMemo(
    () => filterValidationBots(bots, botFilter, botSearchQuery),
    [bots, botFilter, botSearchQuery],
  );

  const visibleBotKeyTotals = useMemo(
    () =>
      visibleBots.reduce(
        (totals, bot) => {
          const counts = resolveValidationBotKeyStateCounts(bot);
          return {
            active: totals.active + counts.active,
            rotated: totals.rotated + counts.rotated,
            revoked: totals.revoked + counts.revoked,
          };
        },
        { active: 0, rotated: 0, revoked: 0 },
      ),
    [visibleBots],
  );

  const applyFailClosedOnAccessError = useCallback((status: number) => {
    if (status === 401 || status === 403) {
      setBots([]);
      setLatestIssuedKey(null);
    }
  }, []);

  const loadBots = useCallback(async () => {
    setIsLoadingBots(true);
    setErrorMessage(null);
    try {
      const response = await fetch('/api/validation/bots');
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        applyFailClosedOnAccessError(response.status);
        setErrorMessage(extractErrorMessage(payload, `Failed to load bots (${response.status})`));
        return;
      }
      setBots(mapValidationBotListResponse(payload));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Failed to load bots.');
    } finally {
      setIsLoadingBots(false);
    }
  }, [applyFailClosedOnAccessError]);

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
        applyFailClosedOnAccessError(response.status);
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
      setBots((previous) => mergeValidationBotSummary(previous, registration));
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
        applyFailClosedOnAccessError(response.status);
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
      setBots((previous) => mergeValidationBotSummary(previous, registration));
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
        applyFailClosedOnAccessError(response.status);
        setErrorMessage(extractErrorMessage(payload, `Key rotation failed (${response.status})`));
        return;
      }

      const rotation = payload as ValidationBotKeyRotationResponse;
      setLatestIssuedKey({
        botName: bots.find((bot) => bot.id === botId)?.name ?? 'Runtime bot',
        keyPrefix: rotation.issuedKey.key.keyPrefix,
        rawKey: rotation.issuedKey.rawKey,
        issuedAt: new Date().toISOString(),
      });
      setBots((previous) => applyValidationBotKeyRotation(previous, botId, rotation.issuedKey.key));
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
        applyFailClosedOnAccessError(response.status);
        setErrorMessage(extractErrorMessage(payload, `Key revoke failed (${response.status})`));
        return;
      }

      const revoked = payload as ValidationBotKeyMetadataResponse;
      setBots((previous) => applyValidationBotKeyRevocation(previous, botId, revoked.key));
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
              User-owned runtime identities with deterministic key lifecycle controls and explicit
              ownership visibility.
            </p>
          </div>
        </div>
      </div>

      <Card className="py-4">
        <CardHeader>
          <CardTitle className="text-base">Ownership Scope</CardTitle>
          <CardDescription>
            Current contract uses a single owner per bot (`ownerUserId`). This view keeps owner and
            lifecycle state explicit so future multi-user delegation can layer without ambiguity.
          </CardDescription>
        </CardHeader>
      </Card>

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
              <p className="mt-1 text-xs text-muted-foreground">
                Prefix {latestIssuedKey.keyPrefix} • Issued{' '}
                {formatValidationBotTimestamp(latestIssuedKey.issuedAt)}
              </p>
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
                Active bots: {activeBots.length} / Total: {bots.length} • Showing{' '}
                {visibleBots.length}
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
              <div className="space-y-4">
                <div className="rounded-md border border-border/70 bg-muted/20 p-3">
                  <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                    <div className="relative">
                      <Input
                        value={botSearchQuery}
                        onChange={(event) => {
                          setBotSearchQuery(event.target.value);
                        }}
                        placeholder="Search by bot name, id, owner, or key prefix"
                      />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Filter className="size-4 text-muted-foreground" />
                      {BOT_FILTER_OPTIONS.map((option) => (
                        <Button
                          key={option.value}
                          type="button"
                          size="sm"
                          variant={botFilter === option.value ? 'secondary' : 'outline'}
                          onClick={() => {
                            setBotFilter(option.value);
                          }}
                        >
                          {option.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Badge variant="outline">Active keys: {visibleBotKeyTotals.active}</Badge>
                    <Badge variant="outline">Rotated keys: {visibleBotKeyTotals.rotated}</Badge>
                    <Badge variant="outline">Revoked keys: {visibleBotKeyTotals.revoked}</Badge>
                  </div>
                </div>

                {visibleBots.length === 0 ? (
                  <div className="rounded-md border border-dashed border-border px-4 py-6 text-sm text-muted-foreground">
                    No bots match the current filters.
                  </div>
                ) : (
                  visibleBots.map((bot) => {
                    const keyCounts = resolveValidationBotKeyStateCounts(bot);
                    const canRotateKey = bot.status === 'active';

                    return (
                      <div key={bot.id} className="rounded-md border border-border p-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="space-y-1">
                            <p className="font-medium">{bot.name}</p>
                            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                              <span className="font-mono">{bot.id}</span>
                              <Badge variant="outline">
                                {resolveValidationBotRegistrationPathLabel(bot.registrationPath)}
                              </Badge>
                              <Badge variant={resolveKeyStatusTone(bot.status)}>{bot.status}</Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              <span className="inline-flex items-center gap-1">
                                <UserRound className="size-3.5" />
                                Owner:{' '}
                                <span className="font-mono">
                                  {resolveValidationBotOwnershipLabel(bot)}
                                </span>
                              </span>
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={!canRotateKey || rotatingBotId === bot.id}
                            onClick={() => {
                              void handleRotateKey(bot.id);
                            }}
                          >
                            {rotatingBotId === bot.id ? (
                              <>
                                <Loader2 className="size-4 animate-spin" />
                                Rotating…
                              </>
                            ) : canRotateKey ? (
                              <>
                                <RotateCw className="size-4" />
                                Rotate Key
                              </>
                            ) : (
                              <>
                                <ShieldAlert className="size-4" />
                                Bot Inactive
                              </>
                            )}
                          </Button>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <Clock3 className="size-3.5" />
                            {toValidationBotUsageLabel(bot.usage)}
                          </span>
                          <Badge variant="outline">Active: {keyCounts.active}</Badge>
                          <Badge variant="outline">Rotated: {keyCounts.rotated}</Badge>
                          <Badge variant="outline">Revoked: {keyCounts.revoked}</Badge>
                        </div>

                        <div className="mt-3 space-y-2">
                          {bot.keys.length === 0 ? (
                            <p className="text-xs text-muted-foreground">
                              No key metadata available.
                            </p>
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
                                    Created {formatValidationBotTimestamp(key.createdAt)}
                                    {key.lastUsedAt
                                      ? ` • Last used ${formatValidationBotTimestamp(key.lastUsedAt)}`
                                      : ''}
                                    {key.revokedAt
                                      ? ` • Revoked ${formatValidationBotTimestamp(key.revokedAt)}`
                                      : ''}
                                  </p>
                                </div>

                                {key.status === 'active' ? (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    disabled={revokingKeyId === key.id || !canRotateKey}
                                    onClick={() => {
                                      void handleRevokeKey(bot.id, key.id);
                                    }}
                                  >
                                    {revokingKeyId === key.id ? (
                                      <>
                                        <Loader2 className="size-4 animate-spin" />
                                        Revoking…
                                      </>
                                    ) : canRotateKey ? (
                                      <>
                                        <ShieldAlert className="size-4" />
                                        Revoke
                                      </>
                                    ) : (
                                      <>
                                        <ShieldAlert className="size-4" />
                                        Bot Inactive
                                      </>
                                    )}
                                  </Button>
                                ) : null}
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
