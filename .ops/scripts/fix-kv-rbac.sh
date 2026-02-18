#!/usr/bin/env bash
# fix-kv-rbac.sh — Assign Key Vault Secrets User role to CLI user
# VOps remediation for trade-nexus-kv RBAC gap
# Run: .ops/scripts/fix-kv-rbac.sh [--yes]

set -euo pipefail

SUBSCRIPTION="42bd545b-deb0-4381-80b1-6186dfb9f3b8"
RESOURCE_GROUP="trade-nexus"
VAULT_NAME="trade-nexus-kv"
ROLE="Key Vault Secrets User"

# Get current user OID
USER_OID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")
if [[ -z "$USER_OID" ]]; then
  echo "ERROR: Cannot determine signed-in user. Run 'az login' first."
  exit 1
fi

SCOPE="/subscriptions/$SUBSCRIPTION/resourcegroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$VAULT_NAME"

echo "=== Key Vault RBAC Remediation ==="
echo "Vault:        $VAULT_NAME"
echo "Role:         $ROLE"
echo "User OID:     $USER_OID"
echo "Scope:        $SCOPE"
echo ""

# Check existing assignment
EXISTING=$(az role assignment list --assignee "$USER_OID" --scope "$SCOPE" --role "$ROLE" --query "length(@)" -o tsv 2>/dev/null || echo "0")
if [[ "$EXISTING" -gt 0 ]]; then
  echo "Role '$ROLE' is already assigned. No action needed."
  exit 0
fi

# Confirmation
if [[ "${1:-}" != "--yes" ]]; then
  echo "This will assign '$ROLE' to user $USER_OID on $VAULT_NAME."
  read -rp "Proceed? [y/N] " confirm
  if [[ "$confirm" != [yY] ]]; then
    echo "Aborted."
    exit 0
  fi
fi

echo "Assigning role..."
az role assignment create \
  --role "$ROLE" \
  --assignee "$USER_OID" \
  --scope "$SCOPE" \
  -o table

echo ""
echo "Verifying..."
sleep 5
az keyvault secret list --vault-name "$VAULT_NAME" --query "[].name" -o tsv 2>/dev/null && echo "SUCCESS: Can now list Key Vault secrets." || echo "WARN: Propagation may take a few minutes. Retry shortly."
