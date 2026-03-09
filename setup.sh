#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# DOLL (Docker OCI Local Liaison) - System Setup & Validation
# ──────────────────────────────────────────────────────────────────────────────
# Checks that the host system meets the requirements to run DOLL:
#   1. dockerd and containerd are installed and running
#   2. Socket files exist at expected paths
#   3. Docker is configured to use the containerd image store
# ──────────────────────────────────────────────────────────────────────────────

DOCKER_SOCKET="/var/run/docker.sock"
CONTAINERD_SOCKET="/run/containerd/containerd.sock"
DAEMON_JSON="/etc/docker/daemon.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

pass()  { echo -e "  ${GREEN}✓${NC} $1"; }
fail()  { echo -e "  ${RED}✗${NC} $1"; }
warn()  { echo -e "  ${YELLOW}!${NC} $1"; }
info()  { echo -e "  ${CYAN}→${NC} $1"; }
header() { echo -e "\n${BOLD}$1${NC}"; }

# Track overall status
ERRORS=0

# ──────────────────────────────────────────────────────────────────────────────
# 1. Check that docker and containerd are installed
# ──────────────────────────────────────────────────────────────────────────────
header "Checking installed services and tools..."

DOCKER_INSTALLED=false
CONTAINERD_INSTALLED=false
CTR_INSTALLED=false
JQ_INSTALLED=false

if command -v docker &>/dev/null; then
    docker_version=$(docker --version 2>/dev/null || echo "unknown")
    pass "docker is installed ($docker_version)"
    DOCKER_INSTALLED=true
else
    fail "docker is not installed"
    ERRORS=$((ERRORS + 1))
fi

if command -v containerd &>/dev/null; then
    containerd_version=$(containerd --version 2>/dev/null || echo "unknown")
    pass "containerd is installed ($containerd_version)"
    CONTAINERD_INSTALLED=true
else
    fail "containerd is not installed"
    ERRORS=$((ERRORS + 1))
fi

if command -v ctr &>/dev/null; then
    pass "ctr is installed"
    CTR_INSTALLED=true
else
    fail "ctr is not installed"
    ERRORS=$((ERRORS + 1))
fi

if command -v jq &>/dev/null; then
    jq_version=$(jq --version 2>/dev/null || echo "unknown")
    pass "jq is installed ($jq_version)"
    JQ_INSTALLED=true
else
    fail "jq is not installed"
    ERRORS=$((ERRORS + 1))
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    fail "Required services/tools are missing. Please install them and run this script again."
    if [ "$DOCKER_INSTALLED" = false ]; then
        info "Install Docker Engine: https://docs.docker.com/engine/install/"
    fi
    if [ "$CONTAINERD_INSTALLED" = false ]; then
        info "containerd is typically bundled with Docker Engine."
        info "If installing Docker via the official packages, containerd should be included."
        info "Standalone install: https://github.com/containerd/containerd/blob/main/docs/getting-started.md"
    fi
    if [ "$CTR_INSTALLED" = false ]; then
        info "ctr is the containerd CLI and is typically installed alongside containerd."
        info "If containerd is installed but ctr is missing, check that the containerd"
        info "bin directory is on your PATH, or install the containerd package for your distro."
    fi
    if [ "$JQ_INSTALLED" = false ]; then
        info "Install jq: https://jqlang.github.io/jq/download/"
        info "  Debian/Ubuntu: sudo apt install jq"
        info "  Fedora/RHEL:   sudo dnf install jq"
        info "  macOS:         brew install jq"
    fi
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# 2. Check that services are running
# ──────────────────────────────────────────────────────────────────────────────
header "Checking service status..."

DOCKER_RUNNING=false
CONTAINERD_RUNNING=false

if systemctl is-active --quiet docker 2>/dev/null; then
    pass "dockerd is running"
    DOCKER_RUNNING=true
elif pgrep -x dockerd &>/dev/null; then
    pass "dockerd is running (not managed by systemd)"
    DOCKER_RUNNING=true
else
    fail "dockerd is not running"
    info "Start it with: sudo systemctl start docker"
    ERRORS=$((ERRORS + 1))
fi

if systemctl is-active --quiet containerd 2>/dev/null; then
    pass "containerd is running"
    CONTAINERD_RUNNING=true
elif pgrep -x containerd &>/dev/null; then
    pass "containerd is running (not managed by systemd)"
    CONTAINERD_RUNNING=true
else
    fail "containerd is not running"
    info "Start it with: sudo systemctl start containerd"
    ERRORS=$((ERRORS + 1))
fi

if [ "$DOCKER_RUNNING" = false ] || [ "$CONTAINERD_RUNNING" = false ]; then
    echo ""
    fail "Required services are not running. Please start them and run this script again."
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# 3. Check socket files
# ──────────────────────────────────────────────────────────────────────────────
header "Checking socket files..."

if [ -S "$DOCKER_SOCKET" ]; then
    pass "Docker socket found at $DOCKER_SOCKET"
else
    fail "Docker socket not found at $DOCKER_SOCKET"
    # Try to find it elsewhere
    alt_socket=$(find /var/run /run -name "docker.sock" -type s 2>/dev/null | head -1 || true)
    if [ -n "$alt_socket" ]; then
        warn "Found Docker socket at: $alt_socket"
        info "DOLL expects it at $DOCKER_SOCKET"
        info "You can symlink it: sudo ln -s $alt_socket $DOCKER_SOCKET"
        info "Or set DOCKER_HOST=unix://$alt_socket in your environment"
    else
        info "Could not locate a Docker socket file."
        info "Ensure dockerd is configured to listen on a unix socket."
    fi
    ERRORS=$((ERRORS + 1))
fi

if [ -S "$CONTAINERD_SOCKET" ]; then
    pass "containerd socket found at $CONTAINERD_SOCKET"
else
    fail "containerd socket not found at $CONTAINERD_SOCKET"
    alt_socket=$(find /var/run /run -name "containerd.sock" -type s 2>/dev/null | head -1 || true)
    if [ -n "$alt_socket" ]; then
        warn "Found containerd socket at: $alt_socket"
        info "DOLL expects it at $CONTAINERD_SOCKET"
        info "You can symlink it: sudo ln -s $alt_socket $CONTAINERD_SOCKET"
        info "Or set CONTAINERD_SOCKET=unix://$alt_socket in your environment"
    else
        info "Could not locate a containerd socket file."
        info "Ensure containerd is configured with a unix socket listener."
    fi
    ERRORS=$((ERRORS + 1))
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    fail "Socket issues detected. Please resolve and run this script again."
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────────
# 4. Check Docker storage driver / containerd image store
# ──────────────────────────────────────────────────────────────────────────────
header "Checking Docker storage configuration..."

# Get storage driver info from docker info
STORAGE_DRIVER=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "")
DRIVER_STATUS=$(docker info --format '{{json .DriverStatus}}' 2>/dev/null || echo "")

USING_CONTAINERD_STORE=false

# Check if the driver status indicates a containerd snapshotter
if echo "$DRIVER_STATUS" | grep -qi "io.containerd.snapshotter"; then
    USING_CONTAINERD_STORE=true
fi

# Also check daemon.json for the feature flag as a secondary signal
if [ -f "$DAEMON_JSON" ]; then
    if grep -q '"containerd-snapshotter"' "$DAEMON_JSON" 2>/dev/null; then
        # Check if it's set to true (crude but effective for most formatting)
        if grep -A1 '"containerd-snapshotter"' "$DAEMON_JSON" | grep -qi "true"; then
            USING_CONTAINERD_STORE=true
        fi
    fi
fi

if [ "$USING_CONTAINERD_STORE" = true ]; then
    pass "Docker is using the containerd image store (driver: $STORAGE_DRIVER)"
else
    fail "Docker is NOT using the containerd image store (current driver: $STORAGE_DRIVER)"
    echo ""
    info "DOLL requires the containerd image store to access image content"
    info "via containerd's gRPC API."
    echo ""
    echo -e "${BOLD}Would you like to enable the containerd image store now?${NC}"
    echo ""
    warn "This will restart the Docker daemon."
    warn "Existing images will be migrated into the containerd image store"
    warn "via docker save/ctr import (no re-download required)."
    echo ""
    read -rp "  Proceed? [y/N] " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo ""
        info "No changes made. To enable manually, see:"
        info "https://docs.docker.com/storage/containerd/"
        exit 1
    fi

    # ── Step 1: Export current images to a temp archive ───────────────────
    header "Step 1: Capturing current images..."
    IMAGE_LIST=$(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -v '<none>' || true)
    IMAGE_COUNT=$(echo "$IMAGE_LIST" | grep -c . || echo "0")

    EXPORT_DIR=""
    if [ "$IMAGE_COUNT" -gt 0 ]; then
        info "Found $IMAGE_COUNT image(s) to migrate:"
        echo "$IMAGE_LIST" | while read -r img; do
            echo -e "      $img"
        done
        echo ""

        EXPORT_DIR=$(mktemp -d -t doll-migration-XXXXXX)
        info "Exporting images to $EXPORT_DIR ..."
        echo ""

        EXPORT_ERRORS=0
        while IFS= read -r img; do
            # Sanitize image name for filename (replace / and : with _)
            safe_name=$(echo "$img" | tr '/:' '__')
            echo -ne "  Saving ${BOLD}$img${NC}..."
            if docker image save "$img" -o "${EXPORT_DIR}/${safe_name}.tar" 2>/dev/null; then
                size=$(du -h "${EXPORT_DIR}/${safe_name}.tar" | cut -f1)
                echo -e "\r  $(pass "$img ($size)")"
            else
                echo -e "\r  $(fail "$img — export failed, will need manual re-pull")"
                EXPORT_ERRORS=$((EXPORT_ERRORS + 1))
            fi
        done <<< "$IMAGE_LIST"

        echo ""
        EXPORTED_COUNT=$(find "$EXPORT_DIR" -name "*.tar" 2>/dev/null | wc -l)
        if [ "$EXPORTED_COUNT" -gt 0 ]; then
            total_size=$(du -sh "$EXPORT_DIR" | cut -f1)
            pass "Exported $EXPORTED_COUNT image(s) ($total_size total)"
        fi
        if [ "$EXPORT_ERRORS" -gt 0 ]; then
            warn "$EXPORT_ERRORS image(s) failed to export"
        fi
    else
        info "No tagged images found — nothing to migrate."
    fi

    # ── Step 2: Update daemon.json ────────────────────────────────────────
    header "Step 2: Updating $DAEMON_JSON..."

    if [ ! -f "$DAEMON_JSON" ]; then
        info "Creating $DAEMON_JSON..."
        sudo tee "$DAEMON_JSON" > /dev/null <<'EOF'
{
  "features": {
    "containerd-snapshotter": true
  }
}
EOF
        pass "Created $DAEMON_JSON with containerd-snapshotter enabled"
    else
        info "Existing $DAEMON_JSON found:"
        echo ""
        cat "$DAEMON_JSON"
        echo ""

        # Use jq to merge the feature flag into the existing config
        info "Merging containerd-snapshotter feature into existing config..."
        TMPFILE=$(mktemp)
        if sudo jq '.features = ((.features // {}) + {"containerd-snapshotter": true})' "$DAEMON_JSON" > "$TMPFILE"; then
            sudo mv "$TMPFILE" "$DAEMON_JSON"
            pass "Updated $DAEMON_JSON with containerd-snapshotter enabled"
        else
            rm -f "$TMPFILE"
            fail "Failed to update $DAEMON_JSON with jq"
            exit 1
        fi
    fi

    echo ""
    info "Current $DAEMON_JSON:"
    cat "$DAEMON_JSON"
    echo ""

    # ── Step 3: Restart Docker ────────────────────────────────────────────
    header "Step 3: Restarting Docker daemon..."
    read -rp "  Ready to restart Docker? [Y/n] " restart_confirm
    if [[ "$restart_confirm" =~ ^[Nn]$ ]]; then
        info "Skipping restart. You will need to restart Docker manually:"
        info "  sudo systemctl restart docker"
        if [ -n "$EXPORT_DIR" ]; then
            info "Exported images are saved at: $EXPORT_DIR"
            info "Import them after restart with:"
            info "  for f in ${EXPORT_DIR}/*.tar; do sudo ctr -n moby image import \"\$f\"; done"
        fi
        info "Then re-run this script to verify."
        exit 0
    fi

    sudo systemctl restart docker
    pass "Docker daemon restarted"

    # Verify the switch worked
    sleep 2
    NEW_DRIVER_STATUS=$(docker info --format '{{json .DriverStatus}}' 2>/dev/null || echo "")
    NEW_STORAGE_DRIVER=$(docker info --format '{{.Driver}}' 2>/dev/null || echo "")

    if echo "$NEW_DRIVER_STATUS" | grep -qi "io.containerd.snapshotter"; then
        pass "Confirmed: Docker is now using the containerd image store (driver: $NEW_STORAGE_DRIVER)"
    else
        fail "Docker does not appear to be using the containerd image store after restart."
        info "Current driver: $NEW_STORAGE_DRIVER"
        info "Please check $DAEMON_JSON and Docker logs: journalctl -u docker"
        if [ -n "$EXPORT_DIR" ]; then
            info "Your exported images are preserved at: $EXPORT_DIR"
        fi
        exit 1
    fi

    # ── Step 4: Import images into containerd ─────────────────────────────
    if [ -n "$EXPORT_DIR" ] && [ "$EXPORTED_COUNT" -gt 0 ]; then
        header "Step 4: Importing images into containerd image store..."
        echo ""

        IMPORT_ERRORS=0
        while IFS= read -r img; do
            safe_name=$(echo "$img" | tr '/:' '__')
            tar_path="${EXPORT_DIR}/${safe_name}.tar"
            [ -f "$tar_path" ] || continue

            repo="${img%%:*}"
            tag="${img##*:}"

            # Qualify the image name for containerd:
            #   nginx         -> docker.io/library/nginx
            #   user/repo     -> docker.io/user/repo
            #   ghcr.io/x/y   -> ghcr.io/x/y (already has registry)
            qualified_repo="$repo"
            if [[ "$repo" != *.* ]]; then
                # No dots in the name — it's a Docker Hub reference
                if [[ "$repo" != */* ]]; then
                    # Official image (no slash) — e.g. nginx -> docker.io/library/nginx
                    qualified_repo="docker.io/library/${repo}"
                else
                    # User image — e.g. jataware/doll -> docker.io/jataware/doll
                    qualified_repo="docker.io/${repo}"
                fi
            fi

            echo -ne "  Importing ${BOLD}$img${NC}..."
            if sudo ctr -n moby image import --base-name "${qualified_repo}" "$tar_path" 2>/dev/null; then
                echo -e "\r  $(pass "$img -> ${qualified_repo}:${tag}")"
            else
                echo -e "\r  $(fail "$img — import failed")"
                IMPORT_ERRORS=$((IMPORT_ERRORS + 1))
            fi
        done <<< "$IMAGE_LIST"

        echo ""
        if [ "$IMPORT_ERRORS" -gt 0 ]; then
            warn "$IMPORT_ERRORS image(s) failed to import. You may need to re-pull these manually."
        else
            pass "All images imported successfully"
        fi

        # Clean up export temp dir
        rm -rf "$EXPORT_DIR"
        info "Cleaned up temporary export directory"
    fi

    # ── Step 5: Clean up old storage driver data ──────────────────────────
    OLD_OVERLAY2="/var/lib/docker/overlay2"
    OLD_IMAGE_DB="/var/lib/docker/image/overlay2"

    old_data_exists=false
    old_data_size="0"
    if [ -d "$OLD_OVERLAY2" ] || [ -d "$OLD_IMAGE_DB" ]; then
        old_data_exists=true
        old_data_size=$(sudo du -sh "$OLD_OVERLAY2" 2>/dev/null | cut -f1 || echo "unknown")
    fi

    if [ "$old_data_exists" = true ]; then
        echo ""
        header "Step 5: Clean up old storage driver data"
        warn "The old $STORAGE_DRIVER data is still on disk at:"
        [ -d "$OLD_OVERLAY2" ] && info "$OLD_OVERLAY2 ($old_data_size)"
        [ -d "$OLD_IMAGE_DB" ] && info "$OLD_IMAGE_DB"
        echo ""
        warn "This data is orphaned — Docker will no longer use it with the"
        warn "containerd image store enabled. Removing it will free disk space."
        echo ""
        warn "If you remove this data, you will NOT be able to revert to the"
        warn "old storage driver and recover these images."
        echo ""
        read -rp "  Remove old $STORAGE_DRIVER data? [y/N] " cleanup_confirm
        if [[ "$cleanup_confirm" =~ ^[Yy]$ ]]; then
            info "Stopping Docker before cleanup..."
            sudo systemctl stop docker
            [ -d "$OLD_OVERLAY2" ] && sudo rm -rf "$OLD_OVERLAY2" && pass "Removed $OLD_OVERLAY2"
            [ -d "$OLD_IMAGE_DB" ] && sudo rm -rf "$OLD_IMAGE_DB" && pass "Removed $OLD_IMAGE_DB"
            info "Restarting Docker..."
            sudo systemctl start docker
            sleep 2
            pass "Old storage driver data removed"
        else
            info "Keeping old data. You can remove it later with:"
            info "  sudo rm -rf $OLD_OVERLAY2 $OLD_IMAGE_DB"
        fi
    fi
fi

# ──────────────────────────────────────────────────────────────────────────────
# 5. Check that the moby namespace exists in containerd
# ──────────────────────────────────────────────────────────────────────────────
header "Checking containerd namespace..."

if sudo ctr namespaces list 2>/dev/null | grep -q "moby"; then
    pass "containerd 'moby' namespace exists"
else
    warn "containerd 'moby' namespace not found"
    info "This namespace is created by Docker when using the containerd image store."
    info "It should appear after pulling at least one image with Docker."
fi

# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────
header "Setup complete!"
echo ""
pass "System is ready to run DOLL"
info "Start with: docker compose up"
info "Or run directly: python -m doll"
echo ""
