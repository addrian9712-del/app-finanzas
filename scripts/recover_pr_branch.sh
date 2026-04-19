#!/usr/bin/env bash
set -euo pipefail

BASE_BRANCH=""
NEW_BRANCH=""
CHERRY_PICK_RANGE=""

usage() {
  cat <<EOF
Uso: $0 --new-branch <nombre> [--base-branch <rama_base>] [--cherry-pick-range <a..b>]

Opciones:
  --new-branch          Nombre de la nueva rama (obligatorio)
  --base-branch         Rama base para crear rama limpia (opcional)
  --cherry-pick-range   Rango de commits para cherry-pick (opcional, requiere --base-branch)

Ejemplos:
  $0 --new-branch fix/nueva-pr-fase1
  $0 --base-branch main --new-branch fix/nueva-pr-fase1 --cherry-pick-range abc123..def456
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-branch)
      BASE_BRANCH="$2"
      shift 2
      ;;
    --new-branch)
      NEW_BRANCH="$2"
      shift 2
      ;;
    --cherry-pick-range)
      CHERRY_PICK_RANGE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento no reconocido: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$NEW_BRANCH" ]]; then
  echo "ERROR: --new-branch es obligatorio." >&2
  usage
  exit 2
fi

if [[ -n "$CHERRY_PICK_RANGE" && -z "$BASE_BRANCH" ]]; then
  echo "ERROR: --cherry-pick-range requiere --base-branch." >&2
  exit 2
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: hay cambios sin commit. Haz commit/stash antes de continuar." >&2
  exit 1
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "Rama actual: $CURRENT_BRANCH"

if git show-ref --verify --quiet "refs/heads/$NEW_BRANCH"; then
  echo "ERROR: la rama '$NEW_BRANCH' ya existe localmente." >&2
  exit 1
fi

if [[ -n "$BASE_BRANCH" ]]; then
  echo "Creando rama limpia '$NEW_BRANCH' desde '$BASE_BRANCH'..."
  git checkout "$BASE_BRANCH"
  git checkout -b "$NEW_BRANCH"

  if [[ -n "$CHERRY_PICK_RANGE" ]]; then
    echo "Aplicando cherry-pick del rango: $CHERRY_PICK_RANGE"
    git cherry-pick "$CHERRY_PICK_RANGE"
  fi
else
  echo "Creando rama '$NEW_BRANCH' desde HEAD..."
  git checkout -b "$NEW_BRANCH"
fi

cat <<EOF

✅ Rama preparada: $NEW_BRANCH
Siguiente paso:
  git push -u origin $NEW_BRANCH
  # abre PR nueva desde $NEW_BRANCH

EOF
