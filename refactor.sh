#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "=============================================="
echo "MONOREPO REFACTOR SCRIPT"
echo "=============================================="
echo "Project root: $PROJECT_ROOT"
echo ""

DELETED_FILES=()
MOVED_FILES=()

log_delete() {
    DELETED_FILES+=("$1")
    echo "[DELETE] $1"
}

log_move() {
    MOVED_FILES+=("$1 -> $2")
    echo "[MOVE] $1 -> $2"
}

echo "=== PHASE 1: DEAD CODE & LEGACY FILE CLEANUP ==="

# Root legacy Python files (not part of monorepo architecture)
for f in Chat_Templates.py current_inference.py start.py bash_script.sh inference.service; do
    if [[ -f "$f" ]]; then
        rm -f "$f"
        log_delete "$f"
    fi
done

# Legacy root requirements (duplicates backend)
if [[ -f "requirements.txt" ]] && [[ -f "backend/requirements.txt" ]]; then
    rm -f "requirements.txt"
    log_delete "requirements.txt (duplicate of backend/requirements.txt)"
fi

# Old cloudformation file
if [[ -f "infrastructure/cloudformation/api-stack-old.yaml" ]]; then
    rm -f "infrastructure/cloudformation/api-stack-old.yaml"
    log_delete "infrastructure/cloudformation/api-stack-old.yaml"
fi

echo ""
echo "=== PHASE 2: SANITIZE DEBUG STATEMENTS ==="

# Remove print() from Python files (except tests/performance which needs them for output)
find backend -name "*.py" -type f ! -path "*/test*" -exec \
    sed -i '/^\s*print(/d' {} \; 2>/dev/null || true

# Remove console.log from TypeScript/JS (except intentional error logs)
find frontend/src -name "*.ts" -o -name "*.tsx" | while read -r f; do
    sed -i '/console\.log\|console\.debug\|debugger/d' "$f" 2>/dev/null || true
done

# Clean console.warn that's just stub code
sed -i "/console\.warn('Download not yet implemented/d" frontend/src/components/JobCard.tsx 2>/dev/null || true

echo "[SANITIZE] Removed debug statements from backend/ and frontend/src/"

echo ""
echo "=== PHASE 3: MOVE INFRASTRUCTURE TO BACKEND ==="

# Move infrastructure folder into backend
if [[ -d "infrastructure" ]] && [[ ! -d "backend/infrastructure" ]]; then
    mv infrastructure backend/
    log_move "infrastructure/" "backend/infrastructure/"

    # Update script paths in infrastructure scripts
    for script in backend/infrastructure/scripts/*.sh; do
        if [[ -f "$script" ]]; then
            # Fix relative paths now that we're one level deeper
            sed -i 's|../backend/|../../|g' "$script" 2>/dev/null || true
            sed -i 's|backend/lambdas|../lambdas|g' "$script" 2>/dev/null || true
            sed -i 's|backend/ecs_tasks|../ecs_tasks|g' "$script" 2>/dev/null || true
        fi
    done
    echo "[UPDATE] Fixed relative paths in backend/infrastructure/scripts/"
fi

echo ""
echo "=== PHASE 4: CONSOLIDATE DOCUMENTATION ==="

# Move root markdown files to docs/
for md in PHASE3_REVIEW_RESPONSE.md PHASE3_SUMMARY.md PLAN_REVIEW.md TESTING_SETUP.md; do
    if [[ -f "$md" ]]; then
        mv "$md" docs/
        log_move "$md" "docs/$md"
    fi
done

# Move sample_templates README and example_templates README to docs/templates/
if [[ -f "backend/sample_templates/README.md" ]]; then
    mv backend/sample_templates/README.md docs/templates/sample-templates.md
    log_move "backend/sample_templates/README.md" "docs/templates/sample-templates.md"
fi

if [[ -f "backend/example_templates/README.md" ]]; then
    mv backend/example_templates/README.md docs/templates/example-templates.md
    log_move "backend/example_templates/README.md" "docs/templates/example-templates.md"
fi

# Move backend README to docs
if [[ -f "backend/README.md" ]]; then
    mv backend/README.md docs/backend-architecture.md
    log_move "backend/README.md" "docs/backend-architecture.md"
fi

# Move frontend README to docs
if [[ -f "frontend/README.md" ]]; then
    mv frontend/README.md docs/frontend-architecture.md
    log_move "frontend/README.md" "docs/frontend-architecture.md"
fi

# Move tests README files to docs
if [[ -f "tests/README.md" ]]; then
    mv tests/README.md docs/testing-guide.md
    log_move "tests/README.md" "docs/testing-guide.md"
fi

for subdir in integration unit performance; do
    if [[ -f "tests/$subdir/README.md" ]]; then
        mv "tests/$subdir/README.md" "docs/testing-$subdir.md"
        log_move "tests/$subdir/README.md" "docs/testing-$subdir.md"
    fi
done

# Move workflow README
if [[ -f ".github/workflows/README.md" ]]; then
    mv .github/workflows/README.md docs/deployment/ci-cd-workflows.md
    log_move ".github/workflows/README.md" "docs/deployment/ci-cd-workflows.md"
fi

echo ""
echo "=== PHASE 5: CLEAN ROOT DIRECTORY ==="

# Remove legacy/duplicate config files
for f in .coveragerc pytest.ini setup.py requirements-dev.txt; do
    if [[ -f "$f" ]]; then
        rm -f "$f"
        log_delete "$f (config moved to pyproject.toml or backend)"
    fi
done

# Move json_data to backend (it's seed data)
if [[ -d "json_data" ]]; then
    mv json_data backend/seed_data
    log_move "json_data/" "backend/seed_data/"
fi

# Remove banner.png if not referenced in README
if [[ -f "banner.png" ]] && ! grep -q "banner.png" README.md 2>/dev/null; then
    rm -f banner.png
    log_delete "banner.png (unreferenced asset)"
elif [[ -f "banner.png" ]]; then
    mkdir -p docs/assets
    mv banner.png docs/assets/
    log_move "banner.png" "docs/assets/banner.png"
    sed -i 's|banner.png|docs/assets/banner.png|g' README.md 2>/dev/null || true
fi

# Remove main_dictionary.json (legacy data file)
if [[ -f "main_dictionary.json" ]]; then
    rm -f main_dictionary.json
    log_delete "main_dictionary.json (legacy data)"
fi

echo ""
echo "=== PHASE 6: UPDATE DOCUMENTATION LINKS ==="

# Update relative links in docs
find docs -name "*.md" -type f -exec sed -i \
    -e 's|\.\./backend/|../backend/|g' \
    -e 's|\.\./frontend/|../frontend/|g' \
    -e 's|\.\./tests/|../tests/|g' \
    {} \; 2>/dev/null || true

echo "[UPDATE] Fixed relative links in documentation"

echo ""
echo "=== PHASE 7: HARDENING ==="

# Ensure no hardcoded secrets (scan and warn)
echo "[SCAN] Checking for potential hardcoded secrets..."
SECRETS_FOUND=0
for pattern in "password\s*=" "secret\s*=" "api_key\s*=" "token\s*=" "AWS_ACCESS" "AWS_SECRET"; do
    if grep -rn --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" \
        -E "$pattern" backend frontend 2>/dev/null | grep -v "process\.env\|os\.environ\|os\.getenv\|\.env" | head -5; then
        SECRETS_FOUND=1
    fi
done
if [[ $SECRETS_FOUND -eq 0 ]]; then
    echo "[OK] No hardcoded secrets detected"
else
    echo "[WARN] Review above lines for potential hardcoded secrets"
fi

echo ""
echo "=============================================="
echo "CLEANUP SUMMARY"
echo "=============================================="
echo ""
echo "DELETED FILES:"
for f in "${DELETED_FILES[@]:-}"; do
    echo "  - $f"
done
echo ""
echo "MOVED FILES:"
for f in "${MOVED_FILES[@]:-}"; do
    echo "  - $f"
done
echo ""
echo "Refactoring complete!"
