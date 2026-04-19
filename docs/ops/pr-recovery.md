# Recuperación de PR bloqueada en Codex

Cuando Codex muestra:

> "Actualmente, Codex no permite actualizar las PR que se hayan modificado fuera de la plataforma. Por ahora, crea una nueva PR."

usa este procedimiento para continuar sin perder cambios.

## Flujo recomendado

1. Verificar que no hay cambios sin commit.
2. Crear una rama nueva desde la rama de trabajo actual.
3. (Opcional) aplicar solo un rango de commits a una rama limpia desde la base.
4. Publicar la nueva rama y abrir PR nueva.

## Comandos manuales

```bash
git status --short
git checkout -b fix/nueva-pr-fase1
git push -u origin fix/nueva-pr-fase1
```

## Script automatizado

Este repo incluye `scripts/recover_pr_branch.sh` para automatizar los pasos.

Ejemplos:

```bash
# Caso simple: nueva rama desde HEAD
./scripts/recover_pr_branch.sh --new-branch fix/nueva-pr-fase1

# Caso avanzado: rama limpia desde base + cherry-pick de rango
./scripts/recover_pr_branch.sh \
  --base-branch main \
  --new-branch fix/nueva-pr-fase1 \
  --cherry-pick-range abc123..def456
```

## Verificación final

- Ejecutar tests y validaciones.
- Abrir PR nueva.
- Cerrar la PR bloqueada anterior para evitar confusión.
